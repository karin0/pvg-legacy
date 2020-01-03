import os, shutil
from functools import partial

from error import MaxTryLimitExceedError

uopen = partial(open, encoding='utf-8')

def fixed_path(path):
    return path[:-1] if path.endswith('/') else path

def to_filename(url):
    return url[url.rfind('/') + 1:]

def to_ext(fn):
    return fn[fn.rfind('.') + 1:]

def ckall(func, lst):
    return all((func(x) for x in lst))

def ckany(func, lst):
    return any((func(x) for x in lst))

def force_move(src, dest):
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(src, dest)

def remove_noexcept(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

def retry(max_depth=5, catchee=(BaseException, )):
    def decorater(func):
        def wrapper(args, kwargs, depth):
            if depth >= max_depth:
                raise MaxTryLimitExceedError
            try:
                if 'depth' in kwargs:
                    kwargs['depth'] = depth
                return func(*args, **kwargs)
            except catchee as e:
                print(f'In depth {depth}: {type(e).__name__}: {e}')
                return wrapper(args, kwargs, depth + 1)
        def handler(*args, **kwargs):
            return wrapper(args, kwargs, 0)
        return handler
    return decorater

retry_def = retry()
