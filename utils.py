import random
from xkcdpass import xkcd_password as xp

def generate_topic_name():
    words = xp.locate_wordfile()
    mywords = xp.generate_wordlist(wordfile=words, min_length=4, max_length=8)
    random_name = xp.generate_xkcdpassword(mywords, numwords=3, delimiter="-")
    return random_name + "-" + str(random.randint(0, 100))