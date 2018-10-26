import json
import os
import requests
import time
import shutil
import sys
from pixivpy3 import *
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

CONF_PATH = 'conf.json'

conf_pix_path = None
conf_unused_path = None
conf_req_path = None
conf_username = None
conf_passwd = None
conf = None
fav = []
pix_files = set()
api = AppPixivAPI()
uid = 0

def to_filename(url):
    return url[url.rfind('/') + 1:]

def to_ext(fn):
    return fn[fn.rfind('.') + 1:]

def ckall(func, lst):
    return all((func(x) for x in lst))

def ckany(func, lst):
    return any((func(x) for x in lst))

def try_move(src, dest):
    try:
        shutil.move(src, dest)
    except FileNotFoundError:
        pass

class Work(object):
    def __init__(self, data):
        self.original_data = data
        self.id = data['id']
        self.title = data['title']
        self.caption = data['caption']
        self.width = data['width']
        self.height = data['height']
        self.page_count = data['page_count']
        self.type = data['type']
        self.user_name = data['user']['name']
        self.total_view = data['total_view']
        self.total_bookmarks = data['total_bookmarks']
        self.tags = [x['name'] for x in data['tags']]
        self.spec = '$!$'.join(self.tags + [self.title])
        self.urls = [data['meta_single_page']['original_image_url']] if data['meta_single_page'] \
               else [x['image_urls']['original'] for x in data['meta_pages']]
        self.filenames = [to_filename(url) for url in self.urls]
        self.intro = {'id': self.id, 'title': self.title, 'author': self.user_name, 'pages': self.page_count, 'likes': self.total_bookmarks, 'tags': self.tags}
    def __repr__(self):
        return repr(self.intro)
    def __str__(self):
        return str(self.intro)
        
class WorkFilter(object):
    def __init__(self, func):
        self.func = func
    def __call__(self, pix):
        return self.func(pix)
    def __and__(self, rhs):
        return WorkFilter(lambda pix: self.func(pix) and rhs.func(pix))
    def __or__(self, rhs):
        return WorkFilter(lambda pix: self.func(pix) or rhs.func(pix))
    def __invert__(self):
        return WorkFilter(lambda pix: not self.func(pix))

def check_google():
    if os.system('curl google.com -m 5'):
        raise RuntimeError('Bad network connection, exiting..')

def login():
    check_google()
    global uid
    if not uid:
        ret = api.login(conf_username, conf_passwd)
        uid = int(ret['response']['user']['id'])
        print("Logined, uid =", uid)

def api_handler(**args):
    try:
        return api.user_bookmarks_illust(**args)
    except BaseException:
        return api_handler(**args)

# database operation

def fetch_fav():
    global fav
    def foo(rest):
        cnt = 0
        nqs = dict()
        res = []
        while True:
            r =      api_handler(**nqs)              if cnt  \
                else api_handler(user_id=uid, restrict=rest)
            cnt += 1
            print('Page #%d: %d found (%s)' % (cnt, len(r.illusts), rest))
            res += list(map(dict, r.illusts))
            if r.next_url is None:
                break
            nqs = api.parse_qs(r.next_url)
        vres = [Work(data) for data in res if data['user']['id'] > 0]
        print('Total %d; Invalid %d; Over (%s)' % (len(vres), len(res) - len(vres), rest))
        return vres
    login()
    fav = foo('public') + foo('private')

def find(filt):
    return [pix for pix in fav if filt(pix)]

def count(filt):
    return len(find(filt))

# file operation

def unselect():
    cnt = 0
    for fn in os.listdir(conf_req_path):
        if fn.lower() in pix_files:
            cnt += 1
            shutil.move(f'{conf_req_path}/{fn}', conf_pix_path)
    print(f'Unselected {cnt} files.')

def select(filt):
    pixs = find(filt)
    unselect()
    for pix in pixs:
        # assert(pix.is_downloaded())
        for fn in pix.filenames:
            shutil.move(f'{conf_pix_path}/{fn}', conf_req_path)
    print(f'Selected {len(pixs)} pixs.')
    return pixs

def download_all():
    check_google()
    unselect()
    print('Counting undownloaded files..')
    ls = set(os.listdir(conf_pix_path))
    nfav = [x for pix in fav for x in pix.urls if to_filename(x) not in ls]
    if not nfav:
        print('All pixs are downloaded.')
        return
    siz = len(nfav)
    print('%d new files' % siz)
    lst = []
    for x in nfav:
        print(x)
        lst.append(x)
    lst.sort(key=lambda x: to_filename(x))
    with open('todo.txt', 'w', encoding='utf-8') as fp:
        for x in lst:
            fp.write(x + '\n')
    os.system('wget -nv --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36" --header="Referer: http://www.pixiv.net" -i todo.txt -P %s/' % conf_pix_path)
    clean()
    print('Done.')

def gen_pix_files():
    pix_files.clear()
    for pix in fav:
        for x in pix.filenames:
            pix_files.add(x.lower())

def clean():
    sufs = {'bmp', 'jpg', 'png', 'tiff', 'tif', 'gif', 'pcx', 'tga', 'exif', 'fpx', 'svg', 'psd', 'cdr', 'pcd', 'dxf', 'ufo', 'eps', 'ai', 'raw', 'wmf', 'webp'}
    print('Cleaning unavailable files..')
    unselect()
    cnt = 0
    for fn in os.listdir(conf_pix_path):
        fnl = fn.lower()
        if fnl not in pix_files and to_ext(fnl) in sufs:
            shutil.move(f'{conf_pix_path}/{fn}', conf_unused_path)
            cnt += 1
    print('Cleaned %d files.' % cnt)

def update():
    fetch_fav()
    try_move('fav.json', 'fav_bak.json')
    with open('fav.json', 'w', encoding='utf-8') as f:
        json.dump([pix.original_data for pix in fav], f)
    gen_pix_files()
    download_all()

# interface

def wf_halt(*tgs):
    return WorkFilter(lambda pix: ckall(lambda x: x in pix.spec, tgs))

def wf_hayt(*tgs):
    return WorkFilter(lambda pix: ckany(lambda x: x in pix.spec, tgs))

def wf_hat(tag):
    return WorkFilter(lambda pix: tag in pix.spec)

wf_true = WorkFilter(lambda pix: True)
wf_false = WorkFilter(lambda pix: False)
wf_w = WorkFilter(lambda pix: pix.width >= pix.height)
wf_h = wf_hayt('R-18', 'R-17', 'R-16', 'R-15')
wfs = {
    '$h': wf_h,
    '$$h': ~wf_h,
    '$w': wf_w,
    '$$w' : ~wf_w
}

def shell_check():
    print(f"{conf_username} UID: {uid}, {len(fav)} likes, {sum((len(pix.urls) for pix in fav))} files")

def shell_system_nohup(cmd):
    os.system(f'nohup {cmd} &')

def shell_system(cmd):
    os.system(cmd)

def parse_filter(seq, any_mode=False):
    if not seq: raise ValueError('No arguments.')
    opt = (lambda x, y: x | y) if any_mode else (lambda x, y: x & y)
    filt = wf_false if any_mode else wf_true
    for cond in seq:
        if cond.startswith('$'):
            if cond in wfs: filt = opt(filt, wfs[cond])
            elif cond[1] == '$': filt = opt(filt, ~wf_hat(cond[2:]))
            else: raise ValueError(f'Invalid syntax: {cond}')
        else: filt = opt(filt, wf_hat(cond))
    return filt

def shell():
    subs = {
        'fetch': download_all, 
        'update': update,
        'clean': clean,
        'check': shell_check,
        'exit': lambda: sys.exit(0),
        'unselect': unselect,
        'open': lambda: shell_system_nohup('xdg-open .'),
        'gopen': lambda: shell_system_nohup(f'gthumb {conf_req_path}')
        }
    history = InMemoryHistory()
    comp_list = list(subs.keys()) + list(wfs.keys()) + list(get_all_tags().keys()) + ['select', 'select_any']
    completer = WordCompleter(comp_list, ignore_case=True)

    shell_check()
    while True:
        try:
            line = prompt('> ', history=history, completer=completer, auto_suggest=AutoSuggestFromHistory())
            args = line.split()
            if not args: continue
            cmd = args[0]
            if cmd in subs: subs[cmd]()
            elif cmd.startswith('select') or cmd[0] == '?':
                select(parse_filter(args[1:]))
            elif cmd == 'count':
                count(parse_filter(args[1:]))
            elif line[0] == '!':
                if line[1] == '!': shell_system_nohup(line[2:])
                else: shell_system(line[1:])
            elif line[0] == '$': exec(line[1:])
            else: raise ValueError('Unknown command.')
        except EOFError:
            sys.exit(0)
        except ValueError as e:
            print(e)

def get_all_tags():
    tags = dict()
    for pix in fav:
        for tag in pix.tags:
            if tag in tags: tags[tag] += 1
            else: tags[tag] = 1
    return tags

# init

with open(CONF_PATH, encoding='utf-8') as fp:
    conf = json.load(fp, encoding='utf-8')

conf_username = conf['username']
conf_passwd = conf['passwd']
conf_pix_path = conf['pix_path']
conf_unused_path = conf['unused_path']
conf_req_path = conf['req_path']
assert(all((os.path.exists(x) for x in [conf_pix_path, conf_unused_path, conf_req_path, CONF_PATH])))

try:
    with open('fav.json', 'r', encoding='utf-8') as fp:
        fav = [Work(data) for data in json.load(fp, encoding='utf-8')]
    gen_pix_files()
except Exception as e:
    print('Failed to load from local fav:', e)

if __name__ == '__main__':
    shell()
