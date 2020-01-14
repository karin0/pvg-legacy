import os

from .env import conf_tmp_path
from .util import uopen, remove_noexcept
from functools import wraps

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
    
    def locked(self):
        return os.path.exists(self.path)

    def unlock(self):
        remove_noexcept(self.path)

memlocks = set()

class MemLock(object):
    def __init__(self, name):
        self.name = name

    def lock(self):
        if self.name in memlocks:
            print('memlocked', self.name)
            return False
        memlocks.add(self.name)
        return True
    
    def locked(self):
        return self.name in memlocks

    def unlock(self):
        memlocks.remove(self.name)

class _Locked(object):
    pass

locked = _Locked()

def use_lock_with(LockType, name1=None):
    def use(f, name=None):
        if name1:
            name = name1
        elif not name:
            name = f.__module__ + '-' + f.__name__
        lock = LockType(name)
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not lock.lock():
                return locked
            try:
                return f(*args, **kwargs)
            finally:
                lock.unlock()
        return wrapper
    return use

use_lock = use_lock_with(Lock)
use_mem_lock = use_lock_with(MemLock)
