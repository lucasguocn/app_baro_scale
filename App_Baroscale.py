import asyncio
import json
from datetime import datetime
from bleak import BleakClient
from BSTBLESensorClient import *

class App_BaroScale:
    def __init__(self, clientBoard:str, dbg = False):
        self.dbg = dbg
        self.clientBoard = clientBoard
        self.config = self.__load_config(clientBoard)
        self.__setup_ble_client()

    def __load_config(self, clientBoard:str):
        """Load configuration from a JSON file."""
        # Map board type to config file
        config_files = {
            "app3.x": "app_baro_scale_app3.x.json",
            "nicla": "app_baro_scale_nicla.json"
        }
        config_file_name = config_files[clientBoard]
        with open(config_file_name, "r") as file:
            return json.load(file)

    def __setup_ble_client(self):
        if self.clientBoard == "app3.x":
            self.ble_client = App3X_BLEClient(config=self.config, dbg=self.dbg)
        elif self.clientBoard == "nicla":
            self.ble_client = NiclaSenseME_BLEClient(config=self.config, dbg=self.dbg)
        else:
            return
        self.ble_client.configSensors()
        self.ble_client.startListeningLoop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect to a BST Sensor Board via BLE")
    parser.add_argument("-b", "--board", choices=["nicla", "app3.x"], required=True, help="Specify the BLE board: 'nicla' or 'app3.x'")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    app_baro_scale = App_BaroScale(clientBoard = args.board, dbg = args.verbose)

