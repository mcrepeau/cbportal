import base64
import hashlib
import io
import os
import platform
import tempfile
import time
import threading
from getpass import getpass

from PIL import Image
from PIL import ImageGrab
from PIL.PngImagePlugin import PngImageFile
import paho.mqtt.client as mqtt
import pyperclip
from cryptography.fernet import Fernet, InvalidToken

from config_loader import load_config
from clipboard_payload import ClipboardPayload
from utils import create_key_from_password


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
            decrypted_clipboard_content = self.cipher.decrypt(encrypted_clipboard_content).decode()
        except InvalidToken:
            print("Could not decrypt clipboard. The content may have been tampered with or the wrong key was used.")
            return None

        if clipboard_hash != self.last_content_hash:
            if clipboard_payload.type == 'image':
                print("Clipboard content (image) received from portal!")
                image = Image.open(io.BytesIO(decrypted_clipboard_content))
                # Save the image to a temporary file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
                    image.save(temp.name)
                # Put the image in the clipboard using the appropriate command
                if platform.system() == "Darwin":  # macOS
                    os.system(f'osascript -e \'set the clipboard to (read (POSIX file "{temp.name}") as JPEG picture)\'')
                elif platform.system() == "Linux":
                    os.system(f'xclip -selection clipboard -t image/png -i {temp.name}')
                # Delete the temporary file
                os.unlink(temp.name)
            else:
                print("Clipboard content (text) received from portal!")
                pyperclip.copy(decrypted_clipboard_content)
            self.last_content_hash = clipboard_hash


class ClipboardMonitor(threading.Thread):
    def __init__(self, mqttc, mqttc_wrapper, cipher, topic):
        super().__init__()
        self.mqttc = mqttc
        self.mqttc_wrapper = mqttc_wrapper
        self.cipher = cipher
        self.topic = topic
        self.interval = 2
        self.running = True

    def run(self):
        while self.running:
            # Get clipboard contents
            clipboard_content = pyperclip.paste()
            im = ImageGrab.grabclipboard()
            if im is not None:
                if isinstance(im, PngImageFile):
                    #print("Image detected in clipboard, size: ", im.size, ",format: ", im.format)
                    with io.BytesIO() as output:
                        im.save(output, format="PNG")
                        image_data = output.getvalue()
                        clipboard_content = base64.b64encode(image_data).decode()
            
            clipboard_data = clipboard_content.encode()
            clipboard_hash = hashlib.sha256(clipboard_data).hexdigest()
            if clipboard_hash != self.mqttc_wrapper.last_content_hash:
                # Publish clipboard contents to MQTT broker
                encrypted_content_str = self.cipher.encrypt(clipboard_content.encode()).decode()
                clipboard_payload = ClipboardPayload(clipboard_hash, 'image' if im is not None else 'text', encrypted_content_str)
                self.mqttc.publish(self.topic, clipboard_payload.to_json())
                print("Clipboard content sent to portal!")
                self.mqttc_wrapper.last_content_hash = clipboard_hash

            time.sleep(self.interval)  # Local clipboard monitoring interval


    def stop(self):
        self.running = False


def main():
    config = load_config('config.json')
    mqtt_config = config['mqtt']

    broker_address = mqtt_config['broker_address']
    broker_port = mqtt_config['broker_port']
    topic = mqtt_config['topic']

    # Prompt the user for a password
    password = getpass("Enter a password to encrypt & decrypt the clipboard content: ")

    # Create a cipher object
    cipher = Fernet(create_key_from_password(password, topic))

    try:
        # Initialize MQTT client
        mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc_wrapper = MQTTClientWithClipboard(mqttc, topic, cipher)
        mqttc_wrapper.client.connect(broker_address, broker_port, 60)

        # Start the MQTT loop
        mqttc_wrapper.client.loop_start()

        # Start the clipboard monitor
        clipboard_monitor = ClipboardMonitor(mqttc, mqttc_wrapper, cipher, topic)
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
