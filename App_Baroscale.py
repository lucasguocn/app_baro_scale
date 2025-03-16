import asyncio
import json
from datetime import datetime
from bleak import BleakClient
from BSTBLESensorClient import *

class App_BaroScale:
    def __init__(self, clientBoard:str, dbg = False):
        self.dbg = dbg
        self.__setup_ble(clientBoard)

    def __setup_ble(self, clientBoard):
        # Map board type to config file
        config_files = {
            "app3.x": "app_baro_scale_app3.x.json",
            "nicla": "app_baro_scale_nicla.json"
        }

        config_file = config_files[clientBoard]
        if clientBoard == "app3.x":
            self.ble_client = App3X_BLEClient(config_file_name=config_file, dbg=self.dbg)
        elif args.board == "nicla":
            self.ble_client = NiclaSenseME_BLEClient(config_file_name=config_file, dbg=self.dbg)
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



