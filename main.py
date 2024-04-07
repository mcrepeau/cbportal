import paho.mqtt.client as mqtt
import pyperclip
import base64
import time
from PIL import ImageGrab
import json
import io

from PIL.Image import Image
from PIL.PngImagePlugin import PngImageFile


def load_config(file_path):
    try:
        with open(file_path, 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        print("Config file not found.")
        return None
    except json.JSONDecodeError:
        print("Invalid JSON format in config file.")
        return None


last_content = ""

config = load_config('config.json')
mqtt_config = config['mqtt']

broker_address = mqtt_config['broker_address']
broker_port = mqtt_config['broker_port']
username = mqtt_config['username']
password = mqtt_config['password']
topic = mqtt_config['topic']
client_id = mqtt_config['client_id']

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(topic)


# Callback function when a message is received from the MQTT broker
def on_message(client, userdata, message):
    clipboard_data = message.payload
    if clipboard_data.startswith(b'image'):
        print("Received: image")
    else:
        clipboard_text = clipboard_data.decode()
        if clipboard_text != pyperclip.paste():
            pyperclip.copy(clipboard_text)
            print("Received:", clipboard_text)


# Initialize MQTT client
mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.connect("mqtt.eclipseprojects.io", 1883, 60)

# Start the MQTT loop
mqttc.loop_start()

try:
    while True:
        # Get clipboard contents
        clipboard_content = pyperclip.paste()
        im = ImageGrab.grabclipboard()

        if im is not None:
            if isinstance(im, PngImageFile):
                print("This is an image")
                with io.BytesIO() as output:
                    im.save(output, format="PNG")
                    image_data = output.getvalue()
                    clipboard_content = "image," + base64.b64encode(image_data).decode()

        # Publish clipboard contents to MQTT broker
        if clipboard_content != last_content:
            mqttc.publish(topic, clipboard_content.encode())
            last_content = clipboard_content
            print("Sent:", clipboard_content)

        time.sleep(5)  # Adjust this value as needed
except KeyboardInterrupt:
    pass

# Stop the MQTT loop and disconnect from the broker
mqttc.loop_stop()
mqttc.disconnect()
