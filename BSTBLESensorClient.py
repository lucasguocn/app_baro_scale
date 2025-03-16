from abc import ABC, abstractmethod
import json
from datetime import datetime
import struct
import asyncio
from bleak import BleakClient
import argparse


class BSTBLESensorClient(ABC):
    """Base class for BLE sensor clients."""

    def __init__(self, config:dict, dbg=False):
        self.config = config
        self.dbg = dbg
        self.log_file = None  # Initialize log file attribute

    @abstractmethod
    def configSensors(self):
        """Configure the sensor."""
        pass

    @abstractmethod
    def handle_data(self, sender, data, timestamp):
        """Handle the received data."""
        pass

    def __notification_handler(self, sender, data):
        """Handle notifications from the BLE device."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.handle_data(sender, data, timestamp)
        except UnicodeDecodeError:
            print(f"Decoding error for data: {data}")

    async def __run(self):
        async with BleakClient(self.config["mac_address"]) as client:
            is_connected = await client.is_connected()
            if self.dbg:
                print(f"Connected: {is_connected}")

            # Only create log file if logging is enabled
            if self.config.get("log_data", False):
                timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]
                log_file_name = f"{timestamp}-{self.config['board_name']}.csv"
                self.log_file = open(log_file_name, "w")

            await client.start_notify(self.config["rx_uuid"], lambda sender, data: self.__notification_handler(sender, data))
            print("Notifications started. Press Ctrl+C to stop.")

            try:
                while True:
                    await asyncio.sleep(self.config["sleep_time"])
            except KeyboardInterrupt:
                print("Exiting program.")
            finally:
                await client.stop_notify(self.config["rx_uuid"])
                print("Notifications stopped.")
                
                if self.log_file:
                    self.log_file.close()

    def startListeningLoop(self):
        asyncio.run(self.__run())


class App3X_BLEClient(BSTBLESensorClient):
    """Implementation for App3X BLE Sensor Client."""

    def __init__(self, config: dict, dbg=False):
        super().__init__(config, dbg)

    def configSensors(self):
        if self.dbg:
            print(f"[App3X_BLEClient] Configuring sensor...")

    def handle_data(self, sender, data, timestamp):
        readstr = data.decode('utf-8')
        sensor_name = self.config["sensor_name"]
        formatted_data = f"{sensor_name}, {timestamp}, {readstr}"

        if self.config["print_raw_data"]:
            print(formatted_data)

        if self.log_file:
            self.log_file.write(formatted_data + "\n")
            self.log_file.flush()


class NiclaSenseME_BLEClient(BSTBLESensorClient):
    """Implementation for Nicla Sense ME BLE Sensor Client."""

    def __init__(self, config: dict, dbg=False):
        super().__init__(config, dbg)

    def configSensors(self):
        if self.dbg:
            print(f"[NiclaSenseME_BLEClient] Configuring sensor...")

    def handle_data(self, sender, data, timestamp):
        if self.dbg:
            print(f"data size: {len(data)}")

        data = bytearray(data)
        data[5] = 0  # Modify the byte array
        
        (sid, sz, value) = struct.unpack("<BBI", data[0:6])
        value = value * 0.078125
        sensor_name = self.config["sensor_name"]
        formatted_data = f"{sensor_name}, {timestamp}, {value:.2f}"

        if self.config["print_raw_data"]:
            print(formatted_data)

        if self.log_file:
            self.log_file.write(formatted_data + "\n")
            self.log_file.flush()

# Example Usage:
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect to a BST Sensor Board via BLE")
    parser.add_argument("-b", "--board", choices=["nicla", "app3.x"], required=True, help="Specify the BLE board: 'nicla' or 'app3.x'")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Map board type to config file
    config_files = {
        "app3.x": "app_baro_scale_app3.x.json",
        "nicla": "app_baro_scale_nicla.json"
    }

    config_file = config_files[args.board]
    
    with open(config_file, "r") as file:
        config = json.load(file)

    if args.board == "app3.x":
        client = App3X_BLEClient(config=config, dbg=args.verbose)
    elif args.board == "nicla":
        client = NiclaSenseME_BLEClient(config=config, dbg=args.verbose)

    client.configSensors()
    client.startListeningLoop()
