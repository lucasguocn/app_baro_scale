from abc import ABC, abstractmethod
import json
from datetime import datetime
import struct
import asyncio
from bleak import BleakClient

class BSTBLESensorClient(ABC):
    """Base class for BLE sensor clients."""

    def __init__(self, config_file_name: str, dbg=False):
        self.config = self.__load_config(config_file_name)
        self.config_file_name = config_file_name
        self.dbg = dbg

    def __load_config(self, config_file_name):
        """Load configuration from a JSON file."""
        with open(config_file_name, "r") as file:
            return json.load(file)

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
            # Get the current timestamp in the required format
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.handle_data(sender, data, timestamp)  # Call the overridden method
        except UnicodeDecodeError:
            print(f"Decoding error for data: {data}")

    async def __run(self):
        async with BleakClient(self.config["mac_address"]) as client:
            is_connected = await client.is_connected()
            if self.dbg:
                print(f"Connected: {is_connected}")

            timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f")[:-3]
            log_file_name = timestamp + '-' + self.config["board_name"] + ".csv"
            self.log_file_name = log_file_name
            with open(log_file_name, "w") as log_file:
                self.log_file = log_file
                # Start listening for notifications
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
        # Run the async BLE client
        asyncio.run(self.__run())


class App3X_BLEClient(BSTBLESensorClient):
    """Implementation for App3X BLE Sensor Client."""

    def __init__(self, config_file_name: str, dbg=False):
        super().__init__(config_file_name, dbg)

    def configSensors(self):
        print(f"[App3X_BLEClient] Configuring sensor using {self.config_file_name}...")

    def handle_data(self, sender, data, timestamp):
            # Decode the received data
            readstr = data.decode('utf-8')
            sensor_name = self.config["sensor_name"]
            # Format the data with the timestamp
            formatted_data = f"{sensor_name}, {timestamp}, {readstr}"

            # Print and write the formatted data
            if self.config["print_raw_data"]:
                print(f"{formatted_data}")

            if self.config["log_data"]:
                self.log_file.write(formatted_data + "\n")
                self.log_file.flush()


class NiclaSenseME_BLEClient(BSTBLESensorClient):
    """Implementation for Nicla Sense ME BLE Sensor Client."""

    def __init__(self, config_file_name: str, dbg=False):
        super().__init__(config_file_name, dbg)

    def configSensors(self):
        print(f"[NiclaSenseME_BLEClient] Configuring sensor using {self.config_file_name}...")

    def handle_data(self, sender, data, timestamp):
        if self.dbg:
            print(f"data size: {len(data)}")
        data[5] = 0
        (sid, sz, value) = struct.unpack("<BBI", data[0:6])
        value = value * 0.078125
        readstr = value
        sensor_name = self.config["sensor_name"]
        formatted_data = f"{sensor_name}, {timestamp}, {readstr:.2f}"
        if self.config["print_raw_data"]:
            print(formatted_data)
        if self.config["log_data"]:
            self.log_file.write(formatted_data + "\n")
            self.log_file.flush()

# Example Usage:
if __name__ == "__main__":
    # Uncomment to use App3X client
     app3x_client = App3X_BLEClient(config_file_name="app_baro_scale_app3.x.json", dbg=True)
     app3x_client.configSensors()
     app3x_client.startListeningLoop()

    # nicla_client = NiclaSenseME_BLEClient(config_file_name="app_baro_scale_nicla.json", dbg=True)
    # nicla_client.configSensors()  # Correct method name
    #nicla_client.startListeningLoop()

