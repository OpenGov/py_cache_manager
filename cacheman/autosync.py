from collections import namedtuple, deque
from datetime import datetime
from operator import attrgetter
from builtins import range

from .cachewrap import PersistentCache

TimeCount = namedtuple('TimeCount', ['time_length', 'count'])
MANY_WRITE_TIME_COUNTS = [TimeCount(60, 1000000), TimeCount(300, 10000), TimeCount(900, 1)]

class AutoSyncCacheBase(object):
    def __init__(self, base_class, cache_name, time_checks=None, time_bucket_size=None, **kwargs):
        # These are sorted from shortest time frame to longest
        self.time_checks = sorted(time_checks or [TimeCount(60, 10000), TimeCount(300, 10), TimeCount(900, 1)],
            key=attrgetter('time_length'))
        self.time_bucket_size = time_bucket_size or 15 # Seconds
        self.time_counts = deque(0 for _ in range(self.bucket_count()))
        self.last_shift_time = datetime.now()
        self.base_class = base_class

        self.base_class.__init__(self, cache_name, **kwargs)

    def bucket_count(self):
        return self.time_checks[-1].time_length // self.time_bucket_size

    def _delta_bucket_match(self, delta_shift_time):
        return max(min(self.bucket_count(),
               int(delta_shift_time.total_seconds() // self.time_bucket_size)), 0)

    def find_bucket(self, edit_time):
        '''
        Raises IndexError on times outside bucket range.
        '''
        delta_shift_time = self.last_shift_time - edit_time
        bucket = self.bucket_count() - 1 - int(delta_shift_time.total_seconds() // self.time_bucket_size)
        if bucket < 0 or bucket >= self.bucket_count():
            raise IndexError('Time of edit since last shift outside bucket bounds')
        return bucket

    def time_shift_buckets(self):
        shift_time = datetime.now()
        snapped_seconds = self.time_bucket_size * (shift_time.second // self.time_bucket_size)
        shift_time = shift_time.replace(second=snapped_seconds)
        delta_buckets = self._delta_bucket_match(shift_time - self.last_shift_time)

        if delta_buckets:
            self.time_counts.rotate(-delta_buckets)
            for i in range(1, delta_buckets + 1):
                self.time_counts[-i] = 0

        self.last_shift_time = shift_time
        return shift_time

    def bucket_within_time(self, bucket, time_check):
        return len(self.time_counts) - 1 - bucket < time_check.time_length // self.time_bucket_size

    def clear_bucket_counts(self):
        for i in range(self.bucket_count()):
            self.time_counts[i] = 0

    def check_save_conditions(self):
        bucket = len(self.time_counts) - 1
        for check in self.time_checks:
            time_count = 0
            while bucket >= 0 and self.bucket_within_time(bucket, check):
                time_count += self.time_counts[bucket]
                if time_count >= check.count:
                    self.save()
                    return True
                bucket -= 1
        return False

    def track_edit(self, count=1, edit_time=None):
        self.time_shift_buckets()
        if edit_time is None:
            edit_time = self.last_shift_time

        try:
            self.time_counts[self.find_bucket(edit_time)] += count
            self.check_save_conditions()
        except IndexError:
            pass # Edit is too far back or in the future, skip it

    def __setitem__(self, *args, **kwargs):
        self._check_contents_present()
        ret_val = self.contents.__setitem__(*args, **kwargs)
        self.track_edit()
        return ret_val

    def __delitem__(self, *args, **kwargs):
        self._check_contents_present()
        ret_val = self.contents.__delitem__(*args, **kwargs)
        self.track_edit()
        return ret_val

    def _build(self, *args, **kwargs):
        self.clear_bucket_counts()
        return self.base_class._build(self, *args, **kwargs)

    def load(self, *args, **kwargs):
        self.clear_bucket_counts()
        return self.base_class.load(self, *args, **kwargs)

    def save(self, *args, **kwargs):
        self.clear_bucket_counts()
        return self.base_class.save(self, *args, **kwargs)

    def delete_saved_content(self, *args, **kwargs):
        self.clear_bucket_counts()
        return self.base_class.delete_saved_content(self, *args, **kwargs)

class AutoSyncCache(AutoSyncCacheBase, PersistentCache):
    '''
    AutoSyncCache defaults to a pickle basis over PersistentCache.
    '''
    def __init__(self, cache_name, **kwargs):
        AutoSyncCacheBase.__init__(self, PersistentCache, cache_name, **kwargs)
