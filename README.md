# Clipboard Portal

Clipboard Portal is a Python application that synchronizes clipboard content across multiple devices using MQTT protocol. It supports both text and image content.

## Use cases

- When using a VM with no clipboard sharing capabilities with the host machine
- When wanting to copy-paste data between 2 (or more!) computers

## Features

- Synchronizes clipboard content in real-time.
- Supports both text and image content.
- Encrypts clipboard content for secure transmission.

## Requirements

- Python 3.6 or higher
- Python packages: paho-mqtt, cryptography, pyperclip, pillow, pywin32 (on Windows)

## Installation

1. Clone this repository:

2. Navigate to the project directory:

3. Install the required Python packages:
`pip3 install .`

## Usage

1. Run the application:
`python main.py`

2. Enter your MQTT broker details and password when prompted.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)