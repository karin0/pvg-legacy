import os
import json
import shutil
import sys
import subprocess
from functools import reduce
from pixivpy3 import AppPixivAPI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

def to_filename(url):
    # TODO: ugoira -> webp
    return url[url.rfind('/') + 1:]
def to_ext(fn):
    return fn[fn.rfind('.') + 1:]
def ckall(func, lst):
    return all((func(x) for x in lst))
def ckany(func, lst):
    return any((func(x) for x in lst))
def retry(max_depth=5, catchee=(BaseException, )):
    def decorater(func):
        def wrapper(args, kwargs, depth):
            if depth >= max_depth: raise MaxTryLimitExceedError
            try:
                return func(*args, **kwargs)
            except catchee as e:
                print(f'In depth {depth}: {type(e).__name__}: {e}')
                return wrapper(args, kwargs, depth + 1)
        def handler(*args, **kwargs):
            return wrapper(args, kwargs, 0)
        return handler
    return decorater

retry_def = retry()

class Work(object):
    def __init__(self, data):
        self.data = data
        self.user_name = data['user']['name']
        self.tags = [x['name'] for x in data['tags']]
        self.spec = '$!$'.join(self.tags + [self.title])
        if self.page_count == 1:
            self.urls = [data['meta_single_page']['original_image_url']]
        else:
            self.urls = [x['image_urls']['original'] for x in data['meta_pages']]
        self.filenames = [to_filename(url) for url in self.urls]
        self.intro = {
            'id': self.id,
            'title': self.title,
            'author': self.user_name,
            'pages': self.page_count,
            'likes': self.total_bookmarks,
            'tags': self.tags
        }
    def __repr__(self):
        return repr(self.intro)
    def __str__(self):
        return str(self.intro)
    def __getattr__(self, item):
        return self.data[item]
        
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

class PvgError(Exception):
    pass
class MaxTryLimitExceedError(PvgError):
    pass
class OperationFailedError(PvgError):
    pass
class BadRequestError(PvgError):
    pass

# remote handler

def login():
    if not api.user_id:
        retry_def(api.login)(conf_username, conf_passwd)
        print("Logined, uid =", api.user_id)

def _hnanowaikenaito_omoimasu():
    update()
    que = list(reversed([x for x in fav if 'R-18' in x.tags and x.pvg_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    tot = len(que)
    cnt = 0
    add_handler = retry_def(api.illust_bookmark_add)
    delete_handler = retry_def(api.illust_bookmark_delete)
    for pix in que:
        cnt += 1
        print(f'{cnt}/{tot}: {pix.title} ({pix.id})')
        delete_handler(pix.id)
        add_handler(pix.id, restrict='private')
    update()

# local db operation
def fetch_fav():
    global fav
    def foo(restrict):
        @retry_def
        def bookmarks_handler(**kwargs):
            res = api.user_bookmarks_illust(**kwargs)
            if 'illusts' not in res:
                raise BadRequestError
            return res
        def pix_formatter(data):
            data = dict(data)
            data['pvg_restrict'] = restrict
            return data

        cnt = 0
        nqs = dict()
        res = []
        while True:
            if cnt: r = bookmarks_handler(**nqs)
            else: r = bookmarks_handler(user_id=api.user_id, restrict=restrict)
            cnt += 1
            print(f'{len(r.illusts)} on {restrict} page #{cnt}')
            res += list(map(pix_formatter, r.illusts))
            if r.next_url is None:
                break
            nqs = api.parse_qs(r.next_url)
        vres = [Work(data) for data in res if data['user']['id'] > 0]
        print(f'{len(vres)} {restrict} in total, {len(res) - len(vres)} invalid')
        return vres
    login()
    fav = foo('public') + foo('private')

def update():
    fetch_fav()
    if os.path.exists('fav.json'):
        shutil.move('fav.json', 'fav_bak.json')
    with open('fav.json', 'w', encoding='utf-8') as f:
        json.dump([pix.data for pix in fav], f)
    # gen_pix_files() // do it in fetch -> recover
    fetch()

def find(filt):
    return [pix for pix in fav if filt(pix)]

def count(filt):
    return len(find(filt))

# file operation

def select(filt):
    pixs = find(filt)
    recover()
    for pix in pixs:
        for fn in pix.filenames:
            url = f'{conf_pix_path}/{fn}'
            if os.path.exists(url):
                shutil.move(url, conf_req_path)
    print(f'Selected {len(pixs)} pixs.')
    return pixs

def gen_pix_files():
    pix_files.clear()
    for pix in fav:
        if conf_max_page_count <= 0 or pix.page_count <= conf_max_page_count:
            for x in pix.filenames:
                pix_files.add(x.lower())
                
def get_pix_urls():
    pix_files.clear()

def recover():
    gen_pix_files()
    print('Moving requested files..')
    cnt = 0
    for fn in os.listdir(conf_req_path):
        if to_ext(fn.lower()) in sufs:
            cnt += 1
            shutil.move(f'{conf_req_path}/{fn}', conf_pix_path)
    print(f'Unselected {cnt} files.')
    print('Cleaning unavailable files..')
    cnt = 0
    for path in (conf_pix_path, conf_req_path):
        for fn in os.listdir(path):
            fnl = fn.lower()
            if fnl not in pix_files and to_ext(fnl) in sufs:
                shutil.move(f'{path}/{fn}', conf_unused_path)
                cnt += 1
    print('Cleaned %d files.' % cnt)

def fetch():
    '''
    wget_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36'
    wget_header = 'Referer: https://www.pixiv.net'
    @retry_def
    def run_wget():
        subprocess.run('wget -nv -nc --timeout=20'
        + f' --user-agent="{wget_ua}"'
        + f' --header="{wget_header}" -P {conf_pix_path} -i down.txt',
        check=True, shell=True)
    '''
    recover()
    print('Counting undownloaded files..')
    ls_pix = set(os.listdir(conf_pix_path))
    ls_unused = set(os.listdir(conf_unused_path))
    que = []
    cnt = 0
    for pix in fav:
        if conf_max_page_count <= 0 or pix.page_count <= conf_max_page_count:
            for url in pix.urls:
                fn = to_filename(url)
                if fn not in ls_pix and fn in pix_files: # to leave out works with too many pages
                    if fn in ls_unused:
                        shutil.move(f'{conf_unused_path}/{fn}', conf_pix_path)
                        cnt += 1
                    else: que.append((url, fn, pix.title))
    if cnt:
        print(f'Recovered {cnt} files from unused dir.')
    if not que:
        print('All files are downloaded.')
        return

    tot = len(que)
    cnt = 0
    download_handler = retry_def(api.download)
    for tup in que:
        cnt += 1
        print(f'{cnt}/{tot}: {tup[1]} from {tup[2]}')
        download_handler(tup[0], path=conf_pix_path, replace=True)
    ''' # Wget way
    que.sort(key=lambda x: x[1]) # by id of pix
    with open('down.txt', 'w', encoding='utf-8') as fp:
        for x in que:
            fp.write(x[0] + '\n')
    run_wget()
    '''
    print('Downloaded all.')

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
    print(f"{conf_username} uid: {api.user_id}, {len(fav)} likes, {sum((len(pix.urls) for pix in fav))} files, {len(pix_files)} local files")

def shell_system_nohup(cmd):
    subprocess.run(f'nohup {cmd} &', shell=True)

def shell_system(cmd):
    subprocess.run(cmd, shell=True)

def parse_filter(seq, any_mode=False):
    if not seq: raise OperationFailedError('No arguments.')
    opt = (lambda x, y: x | y) if any_mode else (lambda x, y: x & y)
    def conv(s):
        if s.startswith('$'):
            if s in wfs: return wfs[s]
            if s[1] == '$': return ~wf_hat(s[2:])
            else: raise OperationFailedError(f'Invalid syntax: {s}')
        else: return wf_hat(s)
    return reduce(opt, map(conv, seq))

def shell():
    subs = {
        'fetch': fetch, 
        'update': update,
        'recover': recover,
        'check': shell_check,
        'exit': lambda: sys.exit(),
        'open': lambda: shell_system_nohup('xdg-open .'),
        'gopen': lambda: shell_system_nohup(f'gthumb {conf_req_path}'),
        # '_hnano': _hnanowaikenaito_omoimasu
    }
    comp_list = list(subs.keys()) + ['select', 'select_any'] + list(wfs.keys()) + list(get_all_tags().keys()) 
    completer = WordCompleter(comp_list, ignore_case=True)
    suggester = AutoSuggestFromHistory()
    session = PromptSession(completer=completer)
    shell_check()
    while True:
        try:
            line = session.prompt('> ', auto_suggest=suggester, complete_while_typing=True)
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
            else: raise OperationFailedError('Unknown command.')
        except EOFError:
            sys.exit()
        except PvgError as e:
            print(f'{type(e).__name__}: {e}')

def get_all_tags():
    tags = dict()
    for pix in fav:
        for tag in pix.tags:
            if tag in tags: tags[tag] += 1
            else: tags[tag] = 1
    return tags

# init

CONF_PATH = 'conf.json'
sufs = {'bmp', 'jpg', 'png', 'tiff', 'tif', 'gif', 'pcx', 'tga', 'exif', 'fpx', 'svg', 'psd', 'cdr', 'pcd', 'dxf', 'ufo', 'eps', 'ai', 'raw', 'wmf', 'webp'}

pix_files = set()
api = AppPixivAPI()

with open(CONF_PATH, encoding='utf-8') as fp:
    conf = json.load(fp, encoding='utf-8')

conf_username = conf['username']
conf_passwd = conf['passwd']
conf_pix_path = conf['pix_path']
conf_unused_path = conf['unused_path']
conf_req_path = conf['req_path']
conf_max_page_count = conf['max_page_count'] # do fetch after modifying this
try:
    _conf_nonh_id_except = set(conf['_nonh_id_except'])
except KeyError:
    pass
assert(all((os.path.exists(x) for x in [conf_pix_path, conf_unused_path, conf_req_path])))

try:
    with open('fav.json', 'r', encoding='utf-8') as fp:
        fav = [Work(data) for data in json.load(fp, encoding='utf-8')]
except Exception as e:
    fav = []
    print('Cannot load from local fav:', e)
else:
    fetch()

if __name__ == '__main__':
    shell()