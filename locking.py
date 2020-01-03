import os

from env import conf_tmp_path
from util import uopen

class Lock(object):
    def __init__(self, name):
        self.path = conf_tmp_path + '/' + name + '.lck'

    def lock(self):
        if os.path.exists(self.path):
            print('locked', self.path)
            return False
        with uopen(self.path, 'w') as fp:
            fp.write('\n')
        return True

    def unlock(self):
        os.remove(self.path)

class _Locked(object):
    pass

locked = _Locked()

def use_lock(f):
    lock = Lock(f.__module__ + '-' + f.__name__)
    def wrapper(*args, **kwargs):
        if not lock.lock():
            return locked
        try:
            return f(*args, **kwargs)
        finally:
            lock.unlock()
    return wrapper
