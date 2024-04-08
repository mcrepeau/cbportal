from setuptools import setup, find_packages

setup(
    name='cbportal',
    version='1.0.0',
    url='https://github.com/mcrepeau/cbportal.git',
    author='Matthieu Crépeau'
    author_email='creposukre@gmail.com',
    description='This is a basic Python app that uses MQTT to share clipboard content between devices.',
    packages=find_packages(),    
    install_requires=[
        'paho-mqtt',
        'pyperclip',
        'Pillow',
        'xkcdpass',
    ],
    entry_points={
        'console_scripts': [
            'cbportal=main:main',
        ],
    },
)