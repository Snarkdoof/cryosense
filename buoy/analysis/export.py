# Export data
import CryoCore
from CryoCore.Core.Status.StatusDbReader import StatusDbReader
db = StatusDbReader()


def get_timestamps(column):
    c = db._execute("SELECT timestamp, value FROM kraknes WHERE paramid=%s", [column])
    print("Clock column", column)

    # t = list(c.fetchall())
    t = [(t, float(v)) for t, v in c.fetchall()]
    # We now calculate the drift
    offset = t[0][0] - t[0][1]
    print("Timestamp offset", offset)

    offsets = {}
    for ts, val in t:
        if val < t[0][1]:
            val += t[0][1]

        offsets[ts] = ts - val

    print(offsets.values())


def get_data(device, columns, timestamp):

    r = db.get_channels_and_parameters()
    # Get the timestamps
    ts_col = r[device][timestamp]
    data_cols = [r[device][c] for c in columns]

    SQL = "SELECT timestamp, paramid, value FROM kraknes WHERE paramid=%s OR "
    args = [ts_col]
    args.extend(data_cols)
    for c in columns:
        SQL += "PARAMID=%s OR "
    SQL = SQL[:-3] + " ORDER BY id"
    c = db._execute(SQL, args)

    print(SQL % tuple(args))
    res = [(t,p,v) for t, p, v in c.fetchall()]
    return res


def process_data(data):
    # Initialize variables to hold connection status, timestamp, and block of entries between 'Connected' and 'Disconnected'
    connected = False
    block_offset = 0
    connected_time = None

    # Iterate through the data
    for i in range(len(data)):
        timestamp, paramid, value = data[i]
        if value == 'Connected':
            block_offset = i + 1
            connected = True
            connected_time = timestamp
        elif value == 'Disconnected':
            if not connected: 
                continue
            last_sensor_ts = data[i - 1][0]

            offset = last_sensor_ts - connected_time
            for j in range(block_offset, i):
                timestamp, paramid, value = data[j]
                if value in ["Connected", "Disconnected"]:
                    raise SystemExit("F==") 
                data[j] = (timestamp - offset, paramid, value)
    return data


def to_csv(data, filename):
    res = {}
    for ts, paramid, value in data:
        if value in ["Connected", "Disconnected"]:
            continue
        if ts not in res:
            res[ts] = []
        res[ts].append((paramid, value))

    # We must now ensure that they are in order
    import operator
    for ts in res:
        d = sorted(res[ts], key=operator.itemgetter(0))
        res[ts] = (di[1] for di in d)

    with open(filename, "w") as f:
        f.write("timestamp,x,y,z\n")
        for ts in res:
            f.write("{},{}\n".format(ts, ",".join(res[ts])))


def oldtocsv(device, columns, timestamp, filename):
    """
    Timestamp tries to adjust for local clock drift on the cryosense
    """

    r = db.get_channels_and_parameters()
    # Get the timestamps
    ts_col = r[device][timestamp]
    timestamps = get_timestamps(ts_col)


    cols = [r[device][c] for c in columns]

    print(cols)

    # Get all the data
    data = {}
    for col in cols:
        c = db._execute("SELECT timestamp, value FROM kraknes WHERE paramid=%s", [col])
        for ts, value in c.fetchall():
            if ts not in data:
                data[ts] = []
            data[ts].append(value)

    with open(filename, "w") as f:
        f.write("timestamp,x,y,z\n")
        for ts in data:
            f.write("{},{}\n".format(ts, ",".join(data[ts])))

green = "CryoSense.30aea42d5fa8"
red = "CryoSense.807d3ac2dde4"
cols = ["sensor.LIS2HH12.AcX", "sensor.LIS2HH12.AcY", "sensor.LIS2HH12.AcZ"]
cols = ["sensor.LIS2HH12.MotA", "sensor.LIS2HH12.MotY", "sensor.LIS2HH12.MotZ"]



timestamp = "state"
try:
    green_data = get_data(green, cols, timestamp)
    green_data = process_data(green_data)
    # for i, g in enumerate(green_data):
    #    print(i, g)
    to_csv(green_data, "/tmp/green.csv")

    red_data = get_data(red, cols, timestamp)
    red_data = process_data(red_data)
    # for i, g in enumerate(red_data):
    #    print(i, g)
    to_csv(red_data, "/tmp/red.csv")

    raise SystemExit()


    tocsv(green, cols, timestamp, "/tmp/green.csv")
    tocsv(red, cols, timestamp, "/tmp/red.csv")
finally:
    CryoCore.API.shutdown()