import asyncio
import json
from datetime import datetime
from bleak import BleakClient
from BSTBLESensorClient import *
from SensorMQTTClient import *
from enum import Enum

class BSTSensorBoardType(Enum):
    APP3_X = "app3.x"
    NICLA = "nicla"

class App_BaroScale:
    accepted_config_files = {
        "app3.x": "app_baro_scale_app3.x.json",
        "nicla": "app_baro_scale_nicla.json"
    }

    def __init__(self, clientBoard:str, dbg = False):
        self.dbg = dbg

        if clientBoard == "app3.x":
            self.clientBoardType = BSTSensorBoardType.APP3_X
        elif clientBoard == "nicla":
            self.clientBoardType = BSTSensorBoardType.NICLA
        else:
            print(f"invalid board type: {clientBoard}")
            return

        self.config = self.__load_config()
        self.__setup_msgn_client()
        self.__setup_ble_client()

    def __load_config(self):
        """Load configuration from a JSON file."""
        # Map board type to config file
        config_files = self.__class__.accepted_config_files
        config_file_name = config_files[self.clientBoardType.value]
        with open(config_file_name, "r") as file:
            return json.load(file)


    def __handler_calib_start(self, args:list = None)->int:
        return 0

    def __handler_calib_stop(self, args:list = None)->int:
        return 0

    def __handler_tare(self, args:list = None)->int:
        return 0

    def __handle_data(self, sender, data, timestamp):
        if (self.clientBoardType == BSTSensorBoardType.APP3_X):
            line = data.decode('utf-8')
            value_baro = float(line.split(",")[-2].strip())
            pressure_data = {
                "value":value_baro,
                "timestamp": str(datetime.now())
            }
            topic_data = "bstsn/" + self.config["mac_address"] + "/data/pressure"
            self.mqtt_client.publish(topic_data, pressure_data)

        elif (self.clientBoardType == BSTSensorBoardType.NICLA):
            pass

    def __setup_ble_client(self):
        if self.clientBoardType == BSTSensorBoardType.APP3_X:
            self.ble_client = App3X_BLEClient(config=self.config, dbg=self.dbg)
        elif self.clientBoardType == BSTSensorBoardType.NICLA:
            self.ble_client = NiclaSenseME_BLEClient(config=self.config, dbg=self.dbg)
        self.ble_client.configSensors()
        self.ble_client.subscribe(self.__handle_data)
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

