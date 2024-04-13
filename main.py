import base64
import hashlib
import io
import os
import platform
import tempfile
import time
import threading
import paho.mqtt.client as mqtt
import pyperclip
import argparse
if platform.system() == "Windows":
    import win32clipboard

from getpass import getpass
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image
from PIL import ImageGrab
from PIL.PngImagePlugin import PngImageFile

from config_loader import load_config
from clipboard_payload import ClipboardPayload
from utils import create_key_from_password
from version import __version__


class MQTTClientWithClipboard:
    def __init__(self, client, topic, cipher):
        self.client = client
        self.topic = topic
        self.cipher = cipher
        self.last_content_hash = None
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect

    # The callback for when the client receives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected with {reason_code}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(self.topic)

    def on_message(self, client, userdata, message):
        clipboard_payload = ClipboardPayload.from_json(message.payload.decode())
        clipboard_hash = clipboard_payload.hash
        encrypted_clipboard_content = clipboard_payload.content.encode()
        try:
            decrypted_clipboard_content = self.cipher.decrypt(encrypted_clipboard_content)
        except InvalidToken:
            print("Could not decrypt clipboard. The content may have been tampered with or the wrong key was used.")
            return None

        if clipboard_hash != self.last_content_hash:
            if clipboard_payload.type == 'image':
                print("Clipboard content (image) received from portal!")
                image_data = base64.b64decode(decrypted_clipboard_content)
                image = Image.open(io.BytesIO(image_data))
                # Save the image to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
                    image.save(temp.name)
                # Put the image in the clipboard using the appropriate command
                if platform.system() == "Darwin":  # macOS
                    os.system(f'osascript -e \'set the clipboard to (read (POSIX file "{temp.name}") as JPEG picture)\'')
                elif platform.system() == "Linux":
                    os.system(f'xclip -selection clipboard -t image/png -i {temp.name}')
                elif platform.system() == "Windows":
                    # Open the image file
                    output = io.BytesIO()
                    image.save(output, "BMP")
                    data = output.getvalue()[14:]
                    output.close()

                    # Open the clipboard
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    # Set the data to clipboard
                    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                    # Close the clipboard
                    win32clipboard.CloseClipboard()
                # Delete the temporary file
                os.unlink(temp.name)
            else:
                print("Clipboard content (text) received from portal!")
                pyperclip.copy(decrypted_clipboard_content.decode())
            self.last_content_hash = clipboard_hash


def process_clipboard_content(cipher):
    # Get clipboard contents
    clipboard_content = pyperclip.paste()
    im = ImageGrab.grabclipboard()
    content_type = 'text'
    if im is not None:
        if isinstance(im, PngImageFile):
            with io.BytesIO() as output:
                im.save(output, format="PNG")
                image_data = output.getvalue()
                clipboard_content = base64.b64encode(image_data).decode()
            content_type = 'image'
    
    # Skip if clipboard_content is blank
    if content_type == 'text' and not clipboard_content.strip():
        return None

    clipboard_data = clipboard_content.encode()
    clipboard_hash = hashlib.sha256(clipboard_data).hexdigest()
    encrypted_content_str = cipher.encrypt(clipboard_data).decode()
    clipboard_payload = ClipboardPayload(clipboard_hash, content_type, encrypted_content_str)

    return clipboard_payload


class ClipboardMonitor(threading.Thread):
    def __init__(self, mqttc_wrapper, topic, cipher):
        super().__init__()
        self.mqttc_wrapper = mqttc_wrapper
        self.topic = topic
        self.cipher = cipher
        self.interval = 2
        self.running = True

    def run(self):
        while self.running:
            clipboard_payload = process_clipboard_content(self.cipher)
            if clipboard_payload and clipboard_payload.hash != self.mqttc_wrapper.last_content_hash:
                # Publish clipboard contents to MQTT broker
                self.mqttc_wrapper.client.publish(self.topic, clipboard_payload.to_json())
                print(f"Clipboard content ({clipboard_payload.type}) sent to portal!")
                self.mqttc_wrapper.last_content_hash = clipboard_payload.hash

            time.sleep(self.interval)  # Local clipboard monitoring interval


    def stop(self):
        self.running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('---mode', choices=['send', 'receive', 'sync'], help='Mode of operation', default='sync')

    args = parser.parse_args()

    config = load_config('config.json')
    mqtt_config = config['mqtt']

    broker_address = mqtt_config['broker_address']
    broker_port = mqtt_config['broker_port']
    topic = mqtt_config['topic']

    # Prompt the user for a password
    password = getpass("Enter a password to encrypt & decrypt the clipboard content: ")

    # Create a cipher object
    cipher = Fernet(create_key_from_password(password, topic))

    # Initialize MQTT client
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc_wrapper = MQTTClientWithClipboard(mqttc, topic, cipher)

    if args.mode == 'send':
        clipboard_payload = process_clipboard_content(cipher)
        mqttc.connect(broker_address, broker_port, 60)
        mqttc.publish(topic, clipboard_payload.to_json(), retain=True)
        mqttc.disconnect()
    elif args.mode == 'receive':
        mqttc.on_message = mqttc_wrapper.on_message
        mqttc.connect(broker_address, broker_port, 60)
        mqttc.subscribe(topic)
        mqttc.loop_start()
        time.sleep(2)  # wait for a short while to receive messages
        mqttc.loop_stop()
        mqttc.disconnect()
    else:  # args.mode == 'sync'
        try:
            mqttc_wrapper.client.connect(broker_address, broker_port, 60)

            # Start the MQTT loop
            mqttc_wrapper.client.loop_start()

            # Start the clipboard monitor
            clipboard_monitor = ClipboardMonitor(mqttc_wrapper, topic, cipher)
            clipboard_monitor.start()

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            # Stop the clipboard monitor
            clipboard_monitor.stop()
            clipboard_monitor.join()

            # Stop the MQTT loop and disconnect from the broker
            mqttc.loop_stop()
            mqttc.disconnect()

if __name__ == "__main__":
    main()
