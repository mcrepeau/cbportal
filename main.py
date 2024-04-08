import base64
import hashlib
import io
import json
import os
import platform
import tempfile
import time
import uuid
import random

import paho.mqtt.client as mqtt
import pyperclip
from PIL import Image
from PIL import ImageGrab
from PIL.PngImagePlugin import PngImageFile
from getpass import getpass
from os import urandom
from xkcdpass import xkcd_password as xp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend


def generate_topic_name():
    words = xp.locate_wordfile()
    mywords = xp.generate_wordlist(wordfile=words, min_length=4, max_length=8)
    random_name = xp.generate_xkcdpassword(mywords, numwords=3, delimiter="-")
    return random_name + "-" + str(random.randint(0, 100))


def load_config(file_path):
    try:
        with open(file_path, 'r') as file:
            config = json.load(file)

        if not config['mqtt'].get('topic'):
            print("No MQTT topic found in the config.")
            while True:
                action = input("Do you want to (j)oin a topic or (c)reate a new one? ")
                if action.lower() == 'j':
                    topic = input("Enter the topic you want to join: ")
                    break
                elif action.lower() == 'c':
                    topic = generate_topic_name()
                    print(f"Created new topic: {topic}")
                    break
                elif action.lower() == 'a':
                    return None
                else:
                    print("Invalid option. Please enter 'j' to join a topic, 'c' to create a new one or 'a' to abort.")

            config['mqtt']['topic'] = topic

            # Write the updated config back to the file
            with open(file_path, 'w') as file:
                json.dump(config, file)
        return config
    except FileNotFoundError:
        print("Config file not found.")
        return None
    except json.JSONDecodeError:
        print("Invalid JSON format in config file.")
        return None

class ClipboardPayload:
    def __init__(self, content_hash, content_type, content):
        self.hash = content_hash
        self.type = content_type
        self.content = content

    def to_json(self):
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        return cls(data['hash'], data['type'], data['content'])


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
        if clipboard_hash != self.last_content_hash:
            if clipboard_payload.type == 'image':
                print("Image received from portal!")
                # Remove the 'image,' prefix and decode the base64 image
                base64_image = self.cipher.decrypt(encrypted_clipboard_content).decode()
                image_data = base64.b64decode(base64_image)
                image = Image.open(io.BytesIO(image_data))
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
                print("Text received from portal!")
                clipboard_text = self.cipher.decrypt(encrypted_clipboard_content).decode()
                pyperclip.copy(clipboard_text)
            self.last_content_hash = clipboard_hash


def main():
    config = load_config('config.json')
    mqtt_config = config['mqtt']

    broker_address = mqtt_config['broker_address']
    broker_port = mqtt_config['broker_port']
    topic = mqtt_config['topic']

    # Prompt the user for a password
    password = getpass("Enter a password to encrypt & decrypt the clipboard content: ")

    # Derive a key from the password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=urandom(16),
        iterations=100000,
        backend=default_backend()
    )

    key = base64.b64encode(kdf.derive(password.encode()))  # Key for Fernet must be 32 base64-encoded bytes
    # Create a cipher object
    cipher = Fernet(key)

    # Initialize MQTT client
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqttc_wrapper = MQTTClientWithClipboard(mqttc, topic, cipher)
    mqttc_wrapper.client.connect(broker_address, broker_port, 60)

    # Start the MQTT loop
    mqttc_wrapper.client.loop_start()

    try:
        while True:
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
            if clipboard_hash != mqttc_wrapper.last_content_hash:
                # Publish clipboard contents to MQTT broker
                encrypted_content_str = cipher.encrypt(clipboard_content.encode()).decode()
                clipboard_payload = ClipboardPayload(clipboard_hash, 'image' if im is not None else 'text', encrypted_content_str)
                mqttc.publish(topic, clipboard_payload.to_json())
                print("Clipboard content sent to portal!")
                mqttc_wrapper.last_content_hash = clipboard_hash

            time.sleep(5)  # Adjust this value as needed
    except KeyboardInterrupt:
        pass

    # Stop the MQTT loop and disconnect from the broker
    mqttc.loop_stop()
    mqttc.disconnect()

if __name__ == "__main__":
    main()
