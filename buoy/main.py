# MICRO - this is a tiny, tiny main that ONLY FUCKING DOES AS LITTLE AS POSSIBLE!


"""

Run every SLEEP_TIME ms
Run LIS on every wake
Run GPS only if current time modulo 900000 is less than SLEEP_TIME (Run once every 15 minutes)
Post if current time modulo 300000 is less than SLEEP_TIME (Once every 5 minutes)
"""
import machine
import network
import time
import json
import pycom
import os

SLEEP_TIME = 30000

class Stats:

    def __init__(self, max_measurements=10):
        self.x = []
        self.y = []
        self.z = []
        self.max_measurements = max_measurements

    def clear(self):
        self.x = []
        self.y = []
        self.z = []

    def update(self, measurement):
        self.x.append(measurement[0])
        self.y.append(measurement[1])
        self.z.append(measurement[2])

        if len(self.x) > self.max_measurements:
            self.x.pop(0)
            self.y.pop(0)
            self.z.pop(0)

    def get_diff(self, lst):
        """
        Return the maximum distance between all values in the list
        """
        lmin = 100000
        lmax = -100000
        for x in lst:
            lmin = min(x, lmin)
            lmax = max(x, lmax)

        return lmax - lmin

    def get_motion(self):
        x = self.get_diff(self.x)
        y = self.get_diff(self.y)
        z = self.get_diff(self.z)

        a = x + y + z

        return (x, y, z, a)



def connect(timeout=30000):
    set_led(0x000013)
    try:
        lte = network.LTE()
    except:
        print("LTE Failed, try to reset")
        try:
            lte.reset()
        except:
            pass
        time.sleep(2)
    try:
        lte = network.LTE()
    except:
        print("LTE Failed")
        return None

    timeout = time.ticks_ms() + timeout

    if not lte.isattached():
        print("Attaching to LTE")
        lte.attach()
    while not lte.isattached() and time.ticks_ms() < timeout:
        time.sleep_ms(250)

    if not lte.isattached():
        print("LTE Not attached, resetting")
        lte.reset()
        return None

    # Attached
    if not lte.isconnected():
        print("Connecting to LTE")
        lte.connect()
    while not lte.isconnected() and time.ticks_ms() < timeout:
        time.sleep_ms(250)
    if not lte.isconnected():
        print("LTE Not connected")
        lte.reset()
        return None

    print("LTE OK")
    return lte

def check_clock():
    # If not RTC is synched, do that now
    if rtc.now()[0] == 1970:  # and not rtc.synced(): synced() is not persisted over deepsleep
        print("Clock not synchronized", rtc.now())
        if connect():
            rtc.ntp_sync("pool.ntp.org")
            time.sleep_ms(5000)

    return True


def sleep(ms):
    print("Sleeping", ms)
    # pytrack.sensor_power(False)
    machine.deepsleep(max(100, int(ms)))
    return

    try:
        # pytrack.sensor_power(False)
        pytrack.setup_sleep(min(1, int(ms/1000)))
        pytrack.go_to_sleep()
    except Exception as e:
        print("Failed, using normal deepsleep:", e)
        machine.deepsleep(max(100, int(ms)))

def measure_lis():
    print("MEASURE ACCELEROMETER")
    import LIS2HH12
    acc = LIS2HH12.LIS2HH12()

    s = Stats()
    # Measure 10 times
    for i in range(10):
        a = acc.acceleration()
        s.update(a)

    motion = s.get_motion()
    return json.dumps({"m": {"1": [{
        "ts_ms": time.ticks_ms(),
        "AcX": a[0],
        "AcY": a[1],
        "AcZ": a[2],
        "MotX": motion[0],
        "MotY": motion[1],
        "MotZ": motion[2],
        "MotA": motion[3]
    }]}})


def measure_gps():
    GPS_I2CADDR = const(0x10)
    i2c = machine.I2C(0, mode=machine.I2C.MASTER, pins=("P22", "P21"))
    reg = bytearray(1)
    i2c.writeto(GPS_I2CADDR, reg)

    measurements = []
    measurement = {}
    stop_time = time.ticks_ms() + 10000  # 10 seconds
    buf = b""
    while time.ticks_ms() < stop_time and "pos" not in measurement:
        reg = i2c.readfrom(GPS_I2CADDR, 128)
        if reg.strip():
            buf += reg

            if buf[0] != b"$":
                p = buf.find(b"$")
                if p > -1:
                    buf = buf[p:]

            # If we don't stop on a line, we will save that for later
            if buf[-1] != "\n":
                tmp = buf[:buf.rfind(b"\n")]
            else:
                tmp = b""
            for line in buf.split(b"\n"):
                try:
                    if not line.strip():
                        continue
                    m = _parse_line(line.strip())
                    if m:
                        measurement.update(m)
                        # measurement["ts_ms"] = time.ticks_ms()
                        measurement["ts_ms"] = get_time()

                    if measurement and "lat" in measurement:
                        measurement["pos"] = (measurement["lat"], measurement["lon"])
                        measurements.append(measurement)
                        break
                except:
                    pass  # Bad line
            buf = tmp
    print("GPS", measurements)

    return json.dumps({"m": {"0": measurements}})

def communicate(posts):
    # We read from posts file
    if posts.tell() == 0:
        print("No data")
        return

    print("Communicating", posts.tell(), "bytes")
    lte = connect()
    if not lte:
        print("Not connected")
        return

    import socket
    import ubinascii
    addr = socket.getaddrinfo("193.156.106.218", 9999)[0][-1][0:2]
    try:
        sock = socket.socket()
        sock.connect(addr)
        sock.settimeout(3.0)

        sensors = [{"class": "gps", "name": "L76GNSS", "driver": "NMEA"}, {"class": "acc", "name": "LIS2HH12", "driver": "LIS2HH12"}, {"class": "fipy", "name": "FiPy", "driver": "PyTrack20"}]
        ts_ms = get_time()
        timeoffset = (get_time() - time.ticks_ms()) / 1000.
        info = {
            "info": "v1", "devid": ubinascii.hexlify(machine.unique_id()), "sensors": sensors,
            "ts_ms": ts_ms, "timeoffset": timeoffset
        }
        print("Sending information")
        sock.send(json.dumps(info) + "\n")

        print("Sending data")
        posts.seek(0)
        while True:
            read = posts.read(100000)
            if not read:
                break
            sock.send(read)

        posts.close()
        posts = open("posts.tmp", "wb")
    except Exception as e:
        print("Exception communicating:", e)
    finally:
        try:
            sock.close()
        except:
            pass

        # Power off the modem
        lte.deinit()

def get_time():
    now = rtc.now()
    ts = (time.mktime(now) * 1000) + (now[6] / 1000.)
    return ts


def _parse_line(data, ts=0):
    """
    Parse a line of data and update status parameters.

    Supports messages:

    $GPRMC,UTC,POS_STAT,LAT,LAT_REF,LON,LON_REF,SPD,HDG,DATE,MAG_VAR,MAG_REF*CS<cr><lf>
    $GPGLL,LAT,LAT_REF,LONG,LONG_REF,UTC,POS_STAT*CS<cr><lf>
    $GPGGA,UTC,LAT,LAT_REF,LONG,LONG_REF,FIX_MODE,SAT_USED,HDOP,ALT,ALT_UNIT,GEO,G_UNIT,D_AGE,D_REF*CS<cr><lf>
    $GPZDA,UTC,DD,MM,YYYY,TH,TM,*CS<cr><lf>
    $GPZDG,GPSTIME,DD,MM,YYYY,AA.BB,V*CS<cr><lf>
    """

    value = data.decode("ascii").strip().split(",")
    value[0] = value[0].replace("$GN", "$GP")
    if value[0] in "$GPRMC":
        elems = ['UTC', 'POS_STAT', 'LAT', 'LAT_REF', 'LON', 'LON_REF', 'SPD', 'HDG', 'DATE', 'MAG_VAR', 'MAG_REF*CS']
    elif value[0] == "$GPGLL":
        elems = ['LAT', 'LAT_REF', 'LONG', 'LONG_REF', 'UTC', 'POS_STAT*CS']
    elif value[0] == "$GPGGA":
        elems = ['UTC', 'LAT', 'LAT_REF', 'LONG', 'LONG_REF', 'FIX_MODE', 'SAT_USED', 'HDOP', 'ALT', 'ALT_UNIT', 'GEO', 'G_UNIT', 'D_AGE', 'D_REF*CS']
    elif value[0] == "$GPZDA":
        elems = ['UTC', 'DD', 'MM', 'YYYY', 'TH', 'TM', '*CS']
    elif value[0] == "$GPZDG":
        elems = ['GPSTIME', 'DD', 'MM', 'YYYY', 'AA.BB', 'V*C']
    elif value[0] == "$GPGSV":
        # Don't care - Satellites in view
        return
    elif value[0] == "$GPVTG":
        # Don't care - Track Made Good and Ground Speed
        return
    elif value[0] == "$GPGSA":
        # Don't care - GPS DOP and active satellites
        return
    elif value[0] == "$GLGSV":
        return  # Let's ignore, these are broken
        elems = ['MSGS', 'MSGNR', 'NUM_SAT', 'AZIMUTH', 'SIG_STREN', 'SIG_ID', '*CS']
    else:
        # print("Unknown string: '%s'" % value)
        return

    if len(value) < len(elems) + 1:
        # Likely out of sync due to buffering issues
        raise Exception("Missing items for %s, expected %d, got %d" % (value[0], len(elems), len(value) - 1))

    _date = None
    _utc = None

    values = {}
    for i in range(0, len(elems)):
        key = elems[i].lower()

        # lat and lon are at least in decimal minutes, so fix that
        if key in ["lat", "lon"]:
            _val = value[i+1].strip()
            if len(_val) < 4:
                continue
            if elems[i].lower() == "lat":
                print("LAT", _val, value, i)
                limiter = _val.find(".")
                degrees = float(_val[:limiter - 2])
                mins = float(_val[limiter - 2:])
            else:
                limiter = _val.find(".")
                degrees = float(_val[:limiter - 2])
                mins = float(_val[limiter - 2:])
            val = degrees + (mins/60)
            print("  ->", val)
            values[elems[i].lower()] = val
        else:
            val = value[i + 1]

        if isinstance(val, str) and val.replace(".", "").isdigit():
            try:
                values[key] = float(val)
            except Exception:
                pass
        elif key == "utc":
            _utc = val
        elif key == "date":
            _date = val
        elif key == "fix_mode":
            values[key] = int(val)
        elif key in values:
            values[key] = val

    return values


def set_led(value=0x0):
    try:
        pycom.rgbled(value)
    except:
        pass

def clear_sd():
    """
    Only run manually on terminal - this will erase everything on the SD
    """
    sd = machine.SD()
    try:
        os.mount(sd, "/sd")
    except:
        # W assume already mounted
        pass

    erased = kept = 0
    for fn in os.listdir("/sd"):
        try:
            os.remove("/sd/" + fn)
            erased += 1
        except Exception:
            kept += 1
            pass
    print("Erased %d, kept %d files" % (erased, kept))

############# MAIN ##############
try:
    pycom.heartbeat(False)
    pycom.lte_modem_en_on_boot(False)
    pycom.pybytes_on_boot(False)

    set_led(0x0)
    network.WLAN().deinit()
    rtc = machine.RTC()
    instruments = []
    import pycoproc_2
    pytrack = pycoproc_2.Pycoproc()

    if check_clock():
        set_led(0x130000)
        print("Running")
        wakeup = time.ticks_ms()

        # Fire up all sensors
        
        pytrack.sensor_power(True)

        posts = open("posts.tmp", "a+")

        # Clock OK
        # Measure LIS
        data = ""

        now = time.ticks_ms()
        print("Now", now, now % 900000, now % 300000)
        set_led(0x0)
        data += measure_lis() + "\n"

        if now % 900000 < SLEEP_TIME:
            set_led(0x001300)

            pytrack.gps_standby(False)
            set_led(0x0)
            for i in range(2):
                try:
                    data += measure_gps() + "\n"
                    break
                except:
                    # Failed to read GPS
                    time.sleep_ms(500)

            pytrack.gps_standby(True)

        if now % 300000 < SLEEP_TIME:
            # We also send the voltage when sending
            voltage = pytrack.read_battery_voltage()
            print("Current voltage", voltage)
            data += json.dumps({"m": {"2": [{"voltage": voltage, "ts_ms": time.ticks_ms()}]}}) + "\n"

        if data.strip():
            import json
            posts.write(data)
            posts.flush()

            # Also write to SD
            try:
                print("Saving to SD")
                sd = machine.SD()
                os.mount(sd, "/sd")
                f = open("/sd/data.log", "a+")
                f.write(data)
                f.close()
                os.sync()
                print("Saved to SD")
            except:
                print("Failed to write to SD")
                pass

        if now % 300000 < SLEEP_TIME:
            set_led(0x121212)
            communicate(posts)

        # Sleep until next time
        print("Powering down", time.ticks_ms() - wakeup)
        set_led(0x0)
        os.sync()
        sleep(SLEEP_TIME - (time.ticks_ms() - wakeup))
    else:
        print("Missing clock")
        # Sleep 10 seconds
        sleep(10000)
except Exception as e:
    print("Exception in main!")
    import sys
    sys.print_exception(e)

    try:
        f = open("error.log", "a+")
        f.write("{}: {}".format(get_time(), e))
        f.close()
        f.flush()
        os.sync()
    except:
        pass

    finally:
        # Deepsleep to reset
        print("Deepsleep 10s to reset things?")
        machine.deepsleep(10000)
