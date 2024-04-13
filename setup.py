from setuptools import setup, find_packages
from cbportal.version import __version__

setup(
    name='cbportal',
    version=__version__,
    url='https://github.com/mcrepeau/cbportal.git',
    author='Matthieu Crépeau',
    author_email='creposukre@gmail.com',
    description='This is a basic Python app that uses MQTT to share clipboard content between devices.',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.6',    
    install_requires=[
        'paho-mqtt',
        'pyperclip',
        'Pillow',
        'xkcdpass',
        'cryptography',
        'argparse'
    ],
    extras_require={
        ':sys_platform == "win32"': [
            'pywin32',
        ],
    },
    entry_points={
        'console_scripts': [
            'cbportal=cbportal.main:main',
        ],
    },
)
