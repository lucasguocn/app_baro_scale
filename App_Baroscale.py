import asyncio
import json
from datetime import datetime
from bleak import BleakClient
from BSTBLESensorClient import *
from SensorMQTTClient import *
from enum import Enum

class App_BaroScale:
    accepted_config_files = {
        "app3.x": "app_baro_scale_app3.x.json",
        "nicla": "app_baro_scale_nicla.json"
    }

    def __init__(self, clientBoard:str, dbg = False):
        self.dbg = dbg
        self.clientBoard = clientBoard
        if clientBoard not in self.__class__.accepted_config_files:
            print(f"invalid board type: {clientBoard}")
            return
        self.config = self.__load_config(clientBoard)
        self.__setup_msgn_client()
        self.__setup_ble_client()

    def __load_config(self, clientBoard:str):
        """Load configuration from a JSON file."""
        # Map board type to config file
        config_files = self.__class__.accepted_config_files
        config_file_name = config_files[clientBoard]
        with open(config_file_name, "r") as file:
            return json.load(file)


    def __handler_calib_start(self, args:list = None)->int:
        return 0

    def __handler_calib_stop(self, args:list = None)->int:
        return 0

    def __handler_tare(self, args:list = None)->int:
        return 0

    def __setup_ble_client(self):
        if self.clientBoard == "app3.x":
            self.ble_client = App3X_BLEClient(config=self.config, dbg=self.dbg)
        elif self.clientBoard == "nicla":
            self.ble_client = NiclaSenseME_BLEClient(config=self.config, dbg=self.dbg)
        self.ble_client.configSensors()
        self.ble_client.startListeningLoop()

    def __cb_mqtt_app_baro_scale(self, topic, payload):
        print(f"App received message on [{topic}]: [{payload}]")
        #example valid message:
        #topic:[nicla/44:4D/cmd]: 
        #payload:[{"_payload":{"payload":{"command":"calibrate_start","arg1":503},,"socketid":"IEI2qi-67j9Ex3-dAAAD"}}]

        cmd_handlers = {
                "calibrate_start"   :{'cb':__handler_calib_start,   'num_args' : 1},
                "calibrate_stop"    :{'cb':__handler_calib_stop,    'num_args' : 0},
                "tare"              :{'cb':__handler_tare,          'num_args' : 0},
                }
        try:
            # Attempt to parse the JSON message
            data = json.loads(payload)

            # Safely extract the values
            command = data["_payload"]["payload"].get("command", None)
            arg1 = data["_payload"]["payload"].get("arg1", None)

            if self.dbg:
                print("command:", command)
                print("arg1:", arg1)

            if command in cmd_handlers:
                num_args = cmd_handlers[command].get('num_args', 0)

        except json.JSONDecodeError:
            print("Error: Received an invalid JSON message")
        except KeyError as e:
            print(f"Error: Missing key in JSON message - {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def __setup_msgn_client(self):
        hostname = self.config.get("mqtt_hostname", "localhost")
        port = self.config.get("mqtt_port", 1883)
        user = self.config.get("mqtt_user", None)
        password = self.config.get("mqtt_password", None)
        clientid = self.config.get("mqtt_client_id", None)
        self.mqtt_client = SensorMQTTClient(
            hostname=hostname,
            port=port,
            user=user,
            password=password,
            clientid=clientid)

        if self.mqtt_client is not None:
            self.mqtt_client.start()
            pressure_data = {
                    "value":0,
                    "timestamp": str(datetime.now())
            }
            topic_data = "bstsn/" + self.config["mac_address"] + "/data/pressure"
            self.mqtt_client.publish(topic_data, pressure_data)
            #msg_pres_data = '{"value":' + str(baro) + ',' + '"timestamp":' + str(timestamp) + '}'

            #cmd = self.clientBoard + "/" + self.config["mac_address"] + "/cmd"
            topic_cmd = "bstsn/" + self.config["mac_address"] + "/cmd"
            self.mqtt_client.subscribe(topic_cmd, self.__cb_mqtt_app_baro_scale)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect to a BST Sensor Board via BLE")
    parser.add_argument("-b", "--board", choices=["nicla", "app3.x"], required=True, help="Specify the BLE board: 'nicla' or 'app3.x'")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    app_baro_scale = App_BaroScale(clientBoard = args.board, dbg = args.verbose)

