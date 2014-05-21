from cacheman import autosync
from datetime import datetime

class FakeTime(object):
    def __init__(self):
        self.stored_time = datetime.now()

    def now(self):
        return self.stored_time;

    def incr_time(self, delta_time):
        self.stored_time += delta_time
autosync.datetime = FakeTime()
