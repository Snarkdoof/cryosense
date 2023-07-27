import json
import requests
from CryoCore import API
import sys

# SERVER_ENDPOINT = 'https://api-dev.biolanglobal.com/biolan/data/api'
SERVER_ENDPOINT = 'https://api.biolanglobal.com/biolan/data/api'



class BioLan:

    def __init__(self, username=None, password=None):
        self._username = username
        self._password = password
        self._token = None
        self._refresh_token = None


        self.cfg = API.get_config("CryoSense.BioLan")
        self.status = API.get_status("CryoSense.BioLan")
        self.log = API.get_log("CryoSense.BioLan")

        self.cfg.set_default("username", self._username)
        self.cfg.set_default("password", self._password)
        self.cfg.set_default("refresh_time_s", 600)  # Every 10 minutes

        if not self._username:
            self._username = self.cfg["username"]
        if not self._password:
            self._password = self.cfg["password"]

        self.status["state"] = "Initializing"

    def refresh_authentiation(self):
        if not self._refresh_token:
            raise Exception("Can't refresh without authentication")

        self.status["state"] = "Refreshing token"

        data = {
            "refresh": self._refresh_token
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.get(SERVER_ENDPOINT + '/refresh/', json=data, headers=headers)

        if response.status_code == 200:
            self._token = response.json().get('access_token')
            self._refresh_token = response.json().get('refresh')
        else:
            self._token = self._refresh_token = None
            raise Exception("Refresh failed. Error:", response.text)


    def authenticate(self):

        self.status["state"] = "Authenticating"

        data = {
            "email": self._username,
            "password": self._password
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(SERVER_ENDPOINT + '/api-token/', json=data, headers=headers)

        if response.status_code == 200:
            self._token = response.json().get('access')
            self._refresh_token = response.json().get('refresh')
        else:
            self._token = self._refresh_token = None
            raise Exception("Authentication failed. Error:", response.text)

    def list_analysis(self):

        self.status["state"] = "Getting list"

        data = {
            "ordering": "local_timestamp",
            "page": 1
        }

        headers = {
            "Authorization": "Bearer %s" % self._token,
            "accept": "application/json"
        }
        response = requests.get(SERVER_ENDPOINT + '/7000-analysis', json=data, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data
        else:
            raise Exception("List failed. Error:", response.text)


    def cc_report_measurement(self, measurement):
        """
        Add a measurement to CryoCore if it hasn't been added already
        """

        snr = "Sensors.{}".format(measurement["biosensorSerial"])
        if self.cfg[snr] and self.cfg[snr] <= measurement["localTimestamp"]:
            return

        # Store it
        for key in measurement:
            self.status[key] = measurement[key]
            self.cfg[snr] = measurement["localTimestamp"]

if __name__ == "__main__":

    from argparse import ArgumentParser

    parser = ArgumentParser(description="Integration with BioLAN 7000 API")
    parser.add_argument("-u", "--user", dest="user",
                        default=None,
                        help="Username (if not in config)")

    parser.add_argument("-p", "--password", dest="password",
                        default=None,
                        help="Password (if not in config)")


    parser.add_argument("--debug", dest="debug",
                        default=None,
                        help="File with response dump for debugging")


    if "argcomplete" in sys.modules:
        argcomplete.autocomplete(parser)

    options = parser.parse_args()

    try:
        if not options.debug:
            biolan = BioLan(options.user, options.password)
            biolan.authenticate()
            measurements = biolan.list_analysis()
        else:
            with open(options.debug, "r") as f:
                measurements = json.load(f)

        for measurement in measurements:
            biolan.cc_report_measurement(measurement)
    finally:
        API.shutdown()
