import os, shutil
from functools import partial, wraps
from typing import Dict

from .error import MaxTryLimitExceedError

uopen = partial(open, encoding='utf-8')


def fixed_path(path):
    return path[:-1] if path.endswith('/') else path


def to_filename(path):
    return path[path.rfind('/') + 1:]


def to_ext(fn):
    return os.path.splitext(fn)[1][1:]


def find_suffix(s, t):
    p = s.find(t)
    if p >= 0:
        return s[p + len(t):]


def force_move(src, dest):
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(src, dest)


def remove_noexcept(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def get_size(path):
    try:
        return os.stat(path).st_size
    except FileNotFoundError:
        return 0


def list_copy(dest, src):
    dest.clear()
    for x in src:
        dest.append(x)


def dict_copy(dest, src):
    dest.clear()
    for k, v in src.items():
        dest[k] = v


def retry_factory(max_depth=3, catchee=(BaseException, )):
    def decorater(func):
        def wrapper(args, kwargs, depth):
            if depth >= max_depth:
                raise MaxTryLimitExceedError
            if 'depth' in kwargs:
                kwargs['depth'] = depth
            try:
                return func(*args, **kwargs)
            except catchee as e:
                print(f'In depth {depth}: {type(e).__name__}: {e}')
                return wrapper(args, kwargs, depth + 1)

        @wraps(func)
        def handler(*args, **kwargs):
            return wrapper(args, kwargs, 0)

        return handler

    return decorater


retry = retry_factory()

mimes: Dict[str, str] = {
    'bmp': 'image/bmp',
    'jpg': 'image/jpeg',
    'png': 'image/png',
    'tiff': 'image/tiff',
    'tif': 'image/tiff',
    'gif': 'image/gif',
    'svg': 'image/svg+xml',
    'webp': 'image/webp',
    'ico': 'image/vnd.microsoft.icon'
}

pixiv_headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36',
    'referer': 'https://www.pixiv.net/'
}
# todo: headers should be case insensitive
