from functools import wraps

locked = object()


def use_lock(func):
    lock = False

    @wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal lock
        if lock:
            return locked
        lock = True
        try:
            return func(*args, **kwargs)
        finally:
            lock = False

    return wrapper
