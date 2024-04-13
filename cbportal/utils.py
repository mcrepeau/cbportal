import random
import base64
from xkcdpass import xkcd_password as xp
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

def generate_topic_name():
    words = xp.locate_wordfile()
    mywords = xp.generate_wordlist(wordfile=words, min_length=4, max_length=8)
    random_name = xp.generate_xkcdpassword(mywords, numwords=3, delimiter="-")
    return random_name + "-" + str(random.randint(0, 100))


def create_key_from_password(password, topic):
    # Derive a key from the password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=topic.encode(),
        iterations=100000,
        backend=default_backend()
    )

    return base64.b64encode(kdf.derive(password.encode()))  # Key for Fernet must be 32 base64-encoded bytes