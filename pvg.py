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


# no / at the end; make sure they exist
PIX_PATH = './pixs'
REMOVED_PATH = './pixs/removed'
REQ_PATH = './req'
CONF_PATH = 'conf.json'
image_sufs = {'bmp', 'jpg', 'png', 'tiff', 'tif', 'gif', 'pcx', 'tga', 'exif', 'fpx', 'svg', 'psd', 'cdr', 'pcd', 'dxf', 'ufo', 'eps', 'ai', 'raw', 'wmf', 'webp'}

api = AppPixivAPI()
fav = []
uid = 0
conf = None

def to_filename(url):
    return url[url.rfind('/') + 1:]

def ckall(func, lst):
    return all((func(x) for x in lst))

def ckany(func, lst):
    return any((func(x) for x in lst))

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
    if os.system('curl google.com -m 5 >/dev/null 2>/dev/null'):
        raise RuntimeError('Bad network connection, exiting..')

def login():
    check_google()
    global uid
    if not uid:
        ret = api.login(conf['username'], conf['passwd'])
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
    os.system('mv %s/* %s/' % (REQ_PATH, PIX_PATH))
    print("Unselected.")

def select(filt):
    pixs = find(filt)
    unselect()
    for pix in pixs:
        # assert(pix.is_downloaded())
        for name in pix.filenames:
            shutil.move('%s/%s' % (PIX_PATH, name), REQ_PATH)
    print("Selected %d pixs." % len(pixs))
    return pixs

def download_all():
    check_google()
    unselect()
    print('Counting undownloaded files..')
    ls = set(os.listdir(PIX_PATH))
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
    os.system('wget -nv --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36" --header="Referer: http://www.pixiv.net" -i todo.txt -P %s/' % PIX_PATH)
    clean()
    print('Done.')

def clean():
    print('Cleaning removed pixs..')
    unselect()
    ids = {x.id for x in fav}
    cnt = 0
    for x in os.listdir(PIX_PATH):
        name = x.lower()
        if name[name.rfind('.') + 1:] in image_sufs and int(name[:name.find('_')]) not in ids:
            os.system(f'mv "{PIX_PATH}/{x}" {REMOVED_PATH}/')
            cnt += 1
    print('Cleaned %d files.' % cnt)

def update():
    os.system('mv fav.json fav_bak.json')
    fetch_fav()
    with open('fav.json', 'w', encoding='utf-8') as f:
        json.dump([pix.original_data for pix in fav], f)
    download_all()

# interface

def wf_halt(*tgs):
    return WorkFilter(lambda pix: ckall(lambda x: x in pix.spec, tgs))
def wf_hayt(*tgs):
    return WorkFilter(lambda pix: ckany(lambda x: x in pix.spec, tgs))
def wf_hat(tag):
    return WorkFilter(lambda pix: tag in pix.spec)

wf_true = WorkFilter(lambda pix: True)
wf_w = WorkFilter(lambda pix: pix.width >= pix.height)
wf_h = wf_hayt('R-18', 'R-17', 'R-16', 'R-15')

def shell_check():
    print(f"{conf['username']} UID: {uid}, {len(fav)} likes, {sum((len(pix.urls) for pix in fav))} files")

def shell_system_nohup(cmd):
    os.system(f'nohup {cmd} &')

def shell_system(cmd):
    os.system(cmd)

def shell():
    subs = {
        'fetch': download_all, 
        'update': update,
        'clean': clean,
        'check': shell_check,
        'exit': lambda: sys.exit(0),
        'unselect': unselect,
        'count': count,
        'open': lambda: shell_system_nohup('xdg-open .'),
        'gopen': lambda: shell_system_nohup(f'gthumb {REQ_PATH}')
        }
    wfs = {
        '$h': wf_h,
        '$$h': ~wf_h,
        '$w': wf_w,
        '$$w' : ~wf_w
    }
    history = InMemoryHistory()
    completer = WordCompleter(list(subs.keys()) + list(wfs.keys()) + ['select', 'select_any'], ignore_case=True)

    shell_check()
    while True:
        try:
            line = prompt('> ', history=history, completer=completer, auto_suggest=AutoSuggestFromHistory())
            args = line.split()
            if not args: continue
            cmd = args[0]
            if cmd in subs: subs[cmd]()
            elif cmd.startswith('select') or cmd[0] == '?':
                if len(args) == 1: raise ValueError('Too few arguments.')
                opt = (lambda x, y: x | y) if cmd.endswith('any') else (lambda x, y: x & y)
                filt = wf_true
                for cond in args[1:]:
                    if cond.startswith('$'):
                        if cond in wfs: filt = opt(filt, wfs[cond])
                        elif cond[1] == '$': filt = opt(filt, ~wf_hat(cond[2:]))
                        else: raise ValueError(f'Invalid tag syntax: {cond}')
                    else: filt = opt(filt, wf_hat(cond))
                select(filt)
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
def foo(*tgs):
    return select(wf_halt(*tgs))
def foow(*tgs):
    return select(wf_halt(*tgs) & wf_w)
def fooh(*tgs):
    return select(wf_halt(*tgs) & wf_h)
def foon(*tgs):
    return select(wf_halt(*tgs) & ~wf_h)

if __name__ == '__main__':
    assert(all((os.path.exists(x) for x in [PIX_PATH, REMOVED_PATH, REQ_PATH, CONF_PATH])))
    with open(CONF_PATH, encoding='utf-8') as fp:
        conf = json.load(fp, encoding='utf-8')
    with open('fav.json', 'r', encoding='utf-8') as f:
        _fav = json.load(f, encoding='utf-8')
    fav = [Work(data) for data in _fav]

    shell()
