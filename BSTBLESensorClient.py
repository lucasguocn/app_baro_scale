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
        self.subscribers = []

    @abstractmethod
    def configSensors(self):
        """Configure the sensor."""
        pass

    def __handle_data(self, sender, data, timestamp):
        """Handle the received data."""
        if len(self.subscribers) > 0:
            for ss in self.subscribers:
                ss(sender, data, timestamp)
        else:
            self._handle_data_dft(sender, data, timestamp)
            
    
    @abstractmethod
    def _handle_data_dft(self, sender, data, timestamp):
        pass

    def __notification_handler(self, sender, data):
        """Handle notifications from the BLE device."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.__handle_data(sender, data, timestamp)
        except UnicodeDecodeError:
            print(f"Decoding error for data: {data}")

    async def __run(self):
        async with BleakClient(self.config["mac_address"]) as client:
            is_connected = await client.is_connected()
            if self.dbg:
                print(f"Connected: {is_connected}")

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
                

    def startListeningLoop(self):
        asyncio.run(self.__run())
        
    def subscribe(self, cb):
        self.subscribers.append(cb)


class App3X_BLEClient(BSTBLESensorClient):
    """Implementation for App3X BLE Sensor Client."""

    def __init__(self, config: dict, dbg=False):
        super().__init__(config, dbg)

    def configSensors(self):
        if self.dbg:
            print(f"[App3X_BLEClient] Configuring sensor...")

    def _handle_data_dft(self, sender, data, timestamp):
        readstr = data.decode('utf-8')
        sensor_name = self.config["sensor_name"]
        formatted_data = f"{sensor_name}, {timestamp}, {readstr}"

        if self.config["print_raw_data"]:
            print(formatted_data)


class NiclaSenseME_BLEClient(BSTBLESensorClient):
    """Implementation for Nicla Sense ME BLE Sensor Client."""

    def __init__(self, config: dict, dbg=False):
        super().__init__(config, dbg)

    def configSensors(self):
        if self.dbg:
            print(f"[NiclaSenseME_BLEClient] Configuring sensor...")

    def _handle_data_dft(self, sender, data, timestamp):
        if self.dbg:
            print(f"data size: {len(data)}")

        if 129 == data[0]:
            data = bytearray(data)
            data[5] = 0  # Modify the byte array
            
            (sid, sz, value) = struct.unpack("<BBI", data[0:6])
            value = value * 0.078125
            sensor_name = self.config["sensor_name"]
            formatted_data = f"{sensor_name}, {timestamp}, {value:.2f}"
        else:
            return

        if self.config["print_raw_data"]:
            print(formatted_data)

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
