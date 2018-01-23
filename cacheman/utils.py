import string
import random

def random_name(length = 18):
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(length))
