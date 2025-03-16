import asyncio
import json
from datetime import datetime
from bleak import BleakClient

def load_config(file_name):
    """Load configuration from a JSON file."""
    with open(file_name, "r") as file:
        return json.load(file)

def notification_handler(sender, data, config, file):
    """Handle notifications from the BLE device."""
    try:
        # Decode the received data
        readstr = data.decode('utf-8')

        # Get the current timestamp in the required format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        sensor_name = config["sensor_name"]
        # Format the data with the timestamp
        formatted_data = f"{sensor_name}, {timestamp}, {readstr}"

        # Print and write the formatted data
        if config["print_raw_data"]:
            print(f"{formatted_data}")
        file.write(formatted_data + "\n")
        file.flush()
    except UnicodeDecodeError:
        print(f"Decoding error for data: {data}")

async def run(config, dbg = False):
    async with BleakClient(config["mac_address"]) as client:
        is_connected = await client.is_connected()
        if dbg:
            print(f"Connected: {is_connected}")

        # Start listening for notifications
        with open(config["log_file"], "w") as file:
            await client.start_notify(config["rx_uuid"], lambda sender, data: notification_handler(sender, data, config, file))
            print("Notifications started. Press Ctrl+C to stop.")

            try:
                while True:
                    await asyncio.sleep(config["sleep_time"])
            except KeyboardInterrupt:
                print("Exiting program.")
            finally:
                await client.stop_notify(config["rx_uuid"])
                print("Notifications stopped.")

if __name__ == "__main__":
    # Load configuration from JSON file
    config_file = "app_baro_scale_app3.x.json"
    config = load_config(config_file)

    # Run the async BLE client
    asyncio.run(run(config))

