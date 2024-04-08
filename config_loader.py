import json
from utils import generate_topic_name

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