import asyncio
import json
from datetime import datetime
from bleak import BleakClient
from BSTBLESensorClient import *
from SensorMQTTClient import *
from enum import Enum
from AlgoPressureToWeight import *

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

        self.inCalibration = False
        self.calib_target = 0
        self.algoPTW = AlgoPressureToWeight(dbg = dbg)
        self.__setup_misc()
        self.__setup_msgn_client()
        self.__setup_ble_client()
        #end of function


    def __load_config(self):
        """Load configuration from a JSON file."""
        # Map board type to config file
        config_files = self.__class__.accepted_config_files
        config_file_name = config_files[self.clientBoardType.value]
        with open(config_file_name, "r") as file:
            return json.load(file)

    def __setup_misc(self):
        # Only create log file if logging is enabled
        if self.config.get("log_data", False):
            timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]
            log_file_name = f"{timestamp}-{self.config['board_name']}.csv"
            self.log_file = open(log_file_name, "w")
    def __tear_down(self):
        if self.log_file:
            self.log_file.close()

    def __handler_calib_start(self, args:list = None)->int:
        self.inCalibration = True
        self.calib_target = args[0]
        self.algoPTW.updateCalibStatus(self.inCalibration, self.calib_target)
        return 0

    def __handler_calib_stop(self, args:list = None)->int:
        self.inCalibration = False
        self.algoPTW.updateCalibStatus(self.inCalibration, self.calib_target)
        return 0

    def __handler_tare(self, args:list = None)->int:
        self.inCalibration = True
        self.calib_target = 0
        self.algoPTW.updateCalibStatus(self.inCalibration, self.calib_target)
        return 0

    def __handle_data(self, sender, data, timestamp):
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        timestamp_ms = int(timestamp.timestamp() * 1000)
        if (self.clientBoardType == BSTSensorBoardType.APP3_X):
            line = data.decode('utf-8')
            line_s = line.split(",")
            value_baro = float(line_s[-2].strip())
            value_temp = float(line_s[-1].strip())
            sensor_name = self.config["sensor_name"]
            formatted_data = f"{sensor_name}, {timestamp_str}, {self.inCalibration}, {self.calib_target}, {line}"

            if self.config["print_raw_data"]:
                print(formatted_data)

            if self.log_file:
                self.log_file.write(formatted_data + "\n")
                self.log_file.flush()

            pressure_data = {
                "value":value_baro,
                "timestamp": timestamp_ms
            }

            topic_data = "bstsn/" + self.config["mac_address"] + "/data/pressure"
            self.mqtt_client.publish(topic_data, pressure_data)
            self.algoPTW.updateData('p', value_baro, timestamp_ms)
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
                "calibrate_start"   :{'cb':self.__handler_calib_start,   'num_args' : 1},
                "calibrate_stop"    :{'cb':self.__handler_calib_stop,    'num_args' : 0},
                "tare"              :{'cb':self.__handler_tare,          'num_args' : 0},
                }
        try:
            # Attempt to parse the JSON message
            data = json.loads(payload)

            # Safely extract the values
            command = data["_payload"]["payload"].get("command", None)
            arg1 = data["_payload"]["payload"].get("arg1", None)
            args = [arg1]

            if self.dbg:
                print("command:", command)
                print("arg1:", arg1)

            if command in cmd_handlers:
                num_args = cmd_handlers[command].get('num_args', 0)

                cb = cmd_handlers[command]['cb']
                cb(args)

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

