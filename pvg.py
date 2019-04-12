import os, json, shutil, sys, subprocess #, zipfile
from functools import reduce
from pixivpy3 import AppPixivAPI
from pyaria2 import Aria2RPC
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

def to_filename(url):
    return url[url.rfind('/') + 1:]
def to_noext(fn):
    return fn[:fn.rfind('.') + 1]
def to_ext(fn):
    return fn[fn.rfind('.') + 1:]
def re_ext(fn, new_ext):
    return to_noext(fn) + new_ext
def ckall(func, lst):
    return all((func(x) for x in lst))
def ckany(func, lst):
    return any((func(x) for x in lst))
def force_move(src, dest):
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(src, dest)
def check_cmd(cmd): # assuming no spaces in args
    subprocess.check_call(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        dbg = data
        self.author = data['user']['name']
        self.tags = [x['name'] for x in data['tags']]
        self.spec = '$!$'.join(self.tags + [self.title])
        if self.type == 'ugoira':
            self.srcs = []
            '''
            url = self.ugoira_metadata['zip_urls']['medium']
            self.srcs = [(re_ext(to_filename(url), 'gif'), url)]
            '''
        else:
            if self.page_count == 1:
                urls = [data['meta_single_page']['original_image_url']]
            else:
                urls = [x['image_urls']['original'] for x in data['meta_pages']]
            self.srcs = [(to_filename(url), url) for url in urls]
        self.intro = {
            'id': self.id,
            'title': self.title,
            'author': self.author,
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
    que = list(reversed([x for x in fav if 'R-18' in x.tags and x.bookmark_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    add_handler = retry_def(api.illust_bookmark_add)
    # delete_handler = retry_def(api.illust_bookmark_delete)
    tot = len(que)
    for i, pix in enumerate(que, 1):
        print(f'{i}/{tot}: {pix.title} ({pix.id})')
        # delete_handler(pix.id)
        add_handler(pix.id, restrict='private')
    update()

# local db operation

def fetch_fav(quick):
    global fav
    if quick:
        ids = {pix.id for pix in fav}
    else:
        fav = []

    def fetch_by_restrict(restrict):
        @retry_def
        def bookmarks_handler(**kwargs):
            res = api.user_bookmarks_illust(**kwargs)
            if 'illusts' not in res:
                raise BadRequestError
            return res
        cnt = icnt = rcnt = 0
        nqs = dict()
        res = []
        r = bookmarks_handler(user_id=api.user_id, restrict=restrict)
        while True:
            cnt += 1
            print(f'{len(r.illusts)} on {restrict} page #{cnt}')

            for data in r.illusts:
                if data['user']['id']:
                    '''
                    if data['type'] == 'ugoira':
                        ucnt += 1
                        continue
                    '''
                        # data['ugoira_metadata'] = api.ugoira_metadata(data['id'])['ugoira_metadata'] # disable it
                    if quick and data['id'] in ids:
                        print(f'{rcnt} {restrict} new in total, {icnt} invalid')
                        return
                    data = dict(data)
                    data['bookmark_restrict'] = restrict
                    fav.append(Work(data)) # no need to add the id to ids
                    rcnt += 1
                else:
                    icnt += 1

            if r.next_url is None:
                break
            r = bookmarks_handler(**api.parse_qs(r.next_url))
        print(f'{rcnt} {restrict} in total, {icnt} invalid')
    
    login()
    fetch_by_restrict('public')
    fetch_by_restrict('private')

def update(quick = False):
    fetch_fav(quick)
    if os.path.exists('fav.json'):
        force_move('fav.json', 'fav_bak.json')
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
        for img in pix.srcs:
            url = f'{conf_pix_path}/{img[0]}'
            if os.path.exists(url):
                shutil.move(url, conf_req_path)
    print(f'Selected {len(pixs)} pixs.')
    return pixs

def gen_pix_files():
    pix_files.clear()
    for pix in fav:
        if conf_max_page_count <= 0 or pix.page_count <= conf_max_page_count:
            for img in pix.srcs:
                pix_files.add(img[0].lower())
                
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
    recover()
    print('Counting undownloaded files..')
    ls_pix = set(os.listdir(conf_pix_path))
    ls_unused = set(os.listdir(conf_unused_path))
    que = []
    cnt = 0
    for pix in fav:
        if conf_max_page_count <= 0 or pix.page_count <= conf_max_page_count:
            for img in pix.srcs:
                fn = img[0]
                if fn not in ls_pix and fn.lower() in pix_files: # to leave out works with too many pages
                    if fn in ls_unused:
                        shutil.move(f'{conf_unused_path}/{fn}', conf_pix_path)
                        cnt += 1
                    else:
                        que.append((img[1], fn, pix))
    if cnt:
        print(f'Recovered {cnt} files from unused dir.')
    if not que:
        print('All files are downloaded.')
        return
    # (done) generate aria2.conf first
    with open('aria2-tmpl.conf') as ft, open('aria2.conf', 'w') as fc:
        fc.write(ft.read().format(dir=os.path.abspath(conf_pix_path)))
    try:
        env = os.environ.copy()
        env['LANG']='en_US.utf-8' # ! linux only now
        proc = subprocess.Popen(
            (['proxychains'] if conf_proxychains_for_aria2 else []) +
            ['aria2c', '--conf', 'aria2.conf'],
            stdout=subprocess.PIPE, 
            stderr=subprocess.DEVNULL,
            env=env) # (done) force proxychains now

        s = proc.stdout.readline().decode()
        while 'listening on' not in s:
            s = proc.stdout.readline().decode()

        aria2 = Aria2RPC() # ! bug if pvg has proxychains
        tot = len(que)
        for i, tup in enumerate(que, 1):
            print(f'{i}/{tot}: {tup[1]} from {tup[2].title}')
            aria2.addUri([tup[0]], {})
        cnt = 0
        for s in proc.stdout:
            s = s.decode().strip()
            if 'Download complete' in s:
                cnt += 1
                print(f'{cnt}/{tot}', s)
            if cnt >= tot:
                break
        print('Downloaded all.')
    finally:
        proc.terminate()

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
    print(f"{conf_username} uid: {api.user_id}, {len(fav)} likes, {sum((len(pix.srcs) for pix in fav))} files, {len(pix_files)} local files")

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
        'qupdate': lambda: update(True),
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
conf_tmp_path = conf['tmp_path']
conf_max_page_count = conf['max_page_count'] # do fetch after modifying this
conf_proxychains_for_aria2 = conf['proxychains_for_aria2']
# conf_ignore_ugoira = conf['ignore_ugoira']
try:
    _conf_nonh_id_except = set(conf['_nonh_id_except'])
except KeyError:
    _conf_nonh_id_except = set()
assert(all((os.path.exists(x) for x in [conf_pix_path, conf_unused_path, conf_req_path])))
if not os.path.exists(conf_tmp_path):
    os.makedirs(conf_tmp_path)

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
