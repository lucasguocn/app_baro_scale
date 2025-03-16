import asyncio
import json
from datetime import datetime
from bleak import BleakClient

class App_BaroScale:
    def __init__(self, config_file_name:str, dbg = False):
        self.dbg = dbg
        self.config = self.__load_config(config_file_name)

    def __load_config(self, config_file_name):
        """Load configuration from a JSON file."""
        with open(config_file_name, "r") as file:
            return json.load(file)

    def __notification_handler(self, sender, data):
        """Handle notifications from the BLE device."""
        try:
            # Decode the received data
            readstr = data.decode('utf-8')

            # Get the current timestamp in the required format
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            sensor_name = self.config["sensor_name"]
            # Format the data with the timestamp
            formatted_data = f"{sensor_name}, {timestamp}, {readstr}"

            # Print and write the formatted data
            if self.config["print_raw_data"]:
                print(f"{formatted_data}")
            self.log_file.write(formatted_data + "\n")
            self.log_file.flush()
        except UnicodeDecodeError:
            print(f"Decoding error for data: {data}")

    async def __run(self):
        async with BleakClient(self.config["mac_address"]) as client:
            is_connected = await client.is_connected()
            if self.dbg:
                print(f"Connected: {is_connected}")

            with open(self.config["log_file"], "w") as log_file:
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

if __name__ == "__main__":
    # Load configuration from JSON file
    config_file = "app_baro_scale_app3.x.json"
    app = App_BaroScale(config_file, dbg = True)
    app.startListeningLoop()


