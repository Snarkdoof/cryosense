#!/usr/bin/env python3
import argparse
from urllib.parse import urlparse, parse_qs
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from CryoCore import API
from CryoCore.Core.Status.StatusDbReader import StatusDbReader
db = StatusDbReader()


class RequestHandler(BaseHTTPRequestHandler):
    """
    Format for POST:

    {
        "sensor": "<sensorname>",
        "timestamp": "<epoc of when status was representative>",
        "status": {
            "<parameter name>": "<value>",
            "<parameter2 name>": "<value2>"
        }
    }

    """
    def _send_response(self, message, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(message), "utf8"))

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            params = parse_qs(parsed_path.query)
            
            if 'sensor' not in params:
                API.get_log("CryoSense.DTU").exception("Missing sensor parameter")
                return self._send_response({"error": "Missing 'sensor' parameter"}, status=400)

            sensor = params['sensor'][0]
            channel = "CryoSense.DTU.{}".format(sensor.replace(" ", "_"))

            # Get the last values from the given sensor (if any)
            r = db.get_channels_and_parameters()
            if channel not in r:
                API.get_log("CryoSense.DTU").exception("Unknown sensor")
                return self._send_response({"error": "Unknown sensor '{}'".format(sensor)}) 

            res = {"sensor": sensor, "state": {}}
            for name in r[channel]:
                ts, val = db.get_last_status_value_by_id(r[channel][name])
                res["state"][name] = {"timestamp": ts, "value": val}
            self._send_response(res)
        except Exception as e:
            API.get_log("CryoSense.DTU").exception("Unknown error on GET")
            self._send_response({"error": str(e)}, status=500)


    def do_POST(self):
        try:
            content_length = self.headers.get('Content-Length')
            if content_length:
                post_data = self.rfile.read(int(content_length))
                data_str = post_data.decode()
            else:
                data_str = ''
                while True:
                    chunk = self.rfile.read(64).decode()
                    if not chunk:
                        break
                    data_str += chunk

            # parse JSON from received data
            data = json.loads(data_str)

            sensor = data['sensor']
            timestamp = data['timestamp']
            statusreport = data['status']

            try:
                status = API.get_status("CryoSense.DTU.{}".format(sensor.replace(" ", "_")))

                for param in statusreport:
                    status[param].set_value(statusreport[param], timestamp=float(timestamp))

                self._send_response({"message": "Success!"})
            except Exception as e2:
                API.get_log("CryoSense.DTU").exception("Sensor format error")
                self._send_response({"error: Bad status format: {}".format(e2)}, status=500)
        except Exception as e:
            API.get_log("CryoSense.DTU").exception("Got in trouble")
            self._send_response({"error": str(e)}, status=400)

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd on port {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start a simple http server')
    parser.add_argument('-p', '--port', type=int, default=8000, help='Port to listen on')
    args = parser.parse_args()
    run(port=args.port)
