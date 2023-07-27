import argparse
import requests
import json
import time

def post_data(url, sensor, params):
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
    data = {
        "sensor": sensor,
        "timestamp": int(time.time()),
        "status": params
    }

    try:
        print("Posting", data)
        response = requests.post(url, json=data)
        response.raise_for_status()

        if response.headers['content-type'] == 'application/json':
            return response.json()
        else:
            return response.text

    except requests.exceptions.HTTPError as errh:
        print ("HTTP Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Error:", err)


def read_data(url, sensor):
    try:
        print(url + "?sensor={}".format(sensor))

        response = requests.get(url + "?sensor={}".format(sensor))
        response.raise_for_status()

        if response.headers['content-type'] == 'application/json':
            return response.json()
        else:
            return response.text

    except requests.exceptions.HTTPError as errh:
        print ("HTTP Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Error:", err)


def parse_params(params_list):
    params = {}
    for param in params_list:
        key, value = param.split('=')
        params[key] = value
    return params

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send a POST request')
    parser.add_argument('-u', '--url', required=True, help='Server URL')
    parser.add_argument('-s', '--sensor', required=True, help='Sensor name')
    parser.add_argument('-r', '--read', required=False, help='Read last posted values',
                        action="store_true", default=False)
    parser.add_argument('-p', '--params', nargs='+', required=False, help='List of parameter=value entries')
    args = parser.parse_args()


    if args.read:
        print(read_data(args.url, args.sensor))
    else:
        params = parse_params(args.params)
        post_data(args.url, args.sensor, params)
