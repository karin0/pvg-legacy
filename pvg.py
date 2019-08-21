import os, json, shutil, sys, subprocess, webbrowser
from functools import reduce, partial
from collections import Counter
from pixivpy3 import AppPixivAPI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

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
        self.author = data['user']['name']
        self.tags = [x['name'] for x in data['tags']]
        self.spec = '$!$'.join(self.tags + [self.title])
        self.likes = data['total_bookmarks']
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
            'likes': self.likes,
            'tags': self.tags
        }
    def __repr__(self):
        return repr(self.intro)
    def __str__(self):
        return str(self.intro)
    def __getattr__(self, item):
        return self.data[item]
    def _open(self):
        return webbrowser.open(f'https://www.pixiv.net/member_illust.php?mode=medium&illust_id={self.id}')
        
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
class DownloadUncompletedError(PvgError):
    pass
class ConfMissing(PvgError):
    pass

# remote db

def login():
    if not api.user_id:
        retry_def(api.login)(conf_username, conf_passwd)
        print("Logined, uid =", api.user_id)


def greendam(quick = False):
    login()
    update(quick)
    # que = list(reversed([x for x in fav if 'R-18' in x.tags and x.bookmark_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    add_handler = retry_def(api.illust_bookmark_add)
    que = list(reversed([pix for pix in fav if 'R-18' in pix.tags and pix.bookmark_restrict == 'public']))
    tot = len(que)
    for i, pix in enumerate(que, 1):
        print(f'{i}/{tot}: {pix.title} ({pix.id})')
        add_handler(pix.id, restrict='private')
        pix.data['bookmark_restrict'] = 'private' # Be careful when assigning to "attributes" of Works.. maybe we can remove the "data" field
    fav_save()
    # update()

# local db

def fav_save(): # call after local db is modified
    if os.path.exists('fav.json'):
        force_move('fav.json', f'{conf_tmp_path}/fav-old.json')
    with uopen('fav.json', 'w') as f:
        json.dump([pix.data for pix in fav], f)

def fav_load():
    global fav
    with uopen('fav.json', 'r') as fp:
        fav = list(map(Work, json.load(fp, encoding='utf-8')))
    # fav.sort(key=lambda pix: -pix.likes)

def update(quick = False):
    global fav
    if quick:
        ids = {pix.id for pix in fav}
    else:
        fav = []

    def fetch(restrict):
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
    fetch('public')
    fetch('private')

    fav_save()
    # gen_pix_files() // do it in download -> restore
    download()

def find(filt):
    return [pix for pix in fav if filt(pix)]

def count(filt):
    return len(find(filt))

# file operation

def select(filt):
    pixs = find(filt)
    restore()
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
                pix_files[img[0].lower()] = img[1]
                
def restore():
    clean_aria2()
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
    print(f'Cleaned {cnt} files.')

def gen_aria2_conf(**kwargs):
    return '''\
user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36
referer=https://www.pixiv.net
allow-overwrite=true
lowest-speed-limit=10K
continue=false
max-concurrent-downloads=10
timeout=8
split=5
min-split-size=5M
max-connection-per-server=16
disable-ipv6=true
max-tries=5
dir={dir}
enable-mmap=true
file-allocation={file_allocation}
disk-cache=64M
check-certificate=false
input-file={input_file}
all-proxy={all_proxy}
enable-rpc=true
rpc-allow-origin-all=true
rpc-listen-all=true
'''.format(**kwargs)

def clean_aria2():
    for fn in os.listdir(conf_pix_path):
        if fn.endswith('.aria2'):
            print('Found', fn)
            os.remove(f'{conf_pix_path}/{fn}')
            try:
                os.remove(f'{conf_pix_path}/{fn[:-6]}')
            except FileNotFoundError:
                pass

def download():
    restore()
    print('Counting undownloaded files..')
    ls_pix = set(os.listdir(conf_pix_path))
    ls_unused = set(os.listdir(conf_unused_path))
    ls_extra = dict()
    if conf_local_source and os.path.exists(conf_local_source):
        print('Local source is avaliable.')
        for x in ('pix', 'req', 'unused'):
            try:
                print('Listing ', x)
                path = f'{conf_local_source}/{x}/'
                ls = os.listdir(path)
                for fn in ls:
                    ls_extra[fn] = path + fn
                print(f'Found {len(ls)} files from {x} dir.')
            except FileNotFoundError:
                print(f'Warn: {path} from local source does not exist!')
                pass


    que = []
    cnt = 0
    extcnt = 0
    # for pix in fav:
    #     if conf_max_page_count <= 0 or pix.page_count <= conf_max_page_count:
    #         for img in pix.srcs:
    #             fn = img[0]
    #             if fn not in ls_pix and fn.lower() in pix_files:
    for fn, url in pix_files.items():
        if fn not in ls_pix:
            if fn in ls_unused:
                shutil.move(f'{conf_unused_path}/{fn}', conf_pix_path)
                cnt += 1
            elif fn in ls_extra:
                print(f'Found {fn} from local source!')
                shutil.copy(ls_extra[fn], conf_pix_path)
                extcnt += 1
            else:
                que.append((url, fn, pix))
    if cnt:
        print(f'Restored {cnt} files from unused path.')
    if extcnt:
        print(f'Copied {extcnt} files from local source.')
    if not que:
        print('All files are downloaded.')
        return

    urls_path = f'{conf_tmp_path}/urls'
    aria2_conf_path = f'{conf_tmp_path}/aria2.conf'
    tot = len(que)
    print(f'{tot} files to download.')
    with uopen(urls_path, 'w') as fp:
        for i, tup in enumerate(que, 1):
            print(f'{i}/{tot}: {tup[1]} from {tup[2].title}')
            fp.write(tup[0] + '\n')

    with uopen(aria2_conf_path, 'w') as fp:
        fp.write(gen_aria2_conf(
            dir=os.path.abspath(conf_pix_path),
            input_file=os.path.abspath(urls_path),
            file_allocation='falloc' if os.name == 'nt' else 'prealloc', # ! not for ext
            all_proxy=conf_aria2_proxy
        ))
    try:
        env = os.environ.copy()
        env['LANG']='en_US.utf-8' # ! linux only now
        proc = subprocess.Popen(
            # (['proxychains'] if conf_proxychains_for_aria2 else []) +
            ['aria2c', '--conf', aria2_conf_path],
            stdout=subprocess.PIPE, 
            stderr=subprocess.DEVNULL,
            env=env
        ) # (done) force proxychains now
        print('Aria2c started.')
        cnt = 0
        for s in proc.stdout:
            s = s.decode().strip()
            # print(s)
            if 'Download complete' in s or '下载已完成' in s:
                cnt += 1
                print(f'{cnt}/{tot}', s)
            if cnt >= tot:
                break
        else:
            raise DownloadUncompletedError
        # proc.wait()\
        print('All done!')
    except DownloadUncompletedError:
        print('Download not completed.')
        clean_aria2()
        raise DownloadUncompletedError
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
wf_h = wf_hayt('R-18')
wfs = {
    '$h': wf_h,
    '$$h': ~wf_h,
    '$w': wf_w,
    '$$w' : ~wf_w
}

def shell_check():
    print(f'{conf_username} uid: {api.user_id}, {len(fav)} likes, {sum((len(pix.srcs) for pix in fav))} files, {len(pix_files)} local files')

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
        'download': download, 
        'update': update,
        'qupd': lambda: update(True),
        'greendam': greendam, 
        'qgreen': lambda: greendam(True),
        'restore': restore,
        'check': shell_check,
        'exit': sys.exit,
        'open': lambda: subprocess.run(
            args=['xdg-open', '.'], 
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        'gthumb': lambda: subprocess.Popen(
            args=['gthumb', conf_req_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # '_hnano': _hnanowaikenaito_omoimasu
    }
    comp_list = list(subs.keys()) + ['select', 'select_any'] + list(wfs.keys()) + list(get_all_tags()) 
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
            if cmd in subs:
                subs[cmd]()
            elif cmd == 'select' or cmd[0] == '?':
                select(parse_filter(args[1:]))
            elif cmd == 'select_any':
                select(parse_filter(args[1:], True))
            elif cmd == 'count':
                count(parse_filter(args[1:]))
            elif line[0] == '!':
                if line[1] == '!': shell_system_nohup(line[2:])
                else: shell_system(line[1:])
            elif line[0] == '$':
                exec(line[1:])
            else:
                raise OperationFailedError('Unknown command.')
        except EOFError:
            sys.exit()
        except PvgError as e:
            print(f'{type(e).__name__}: {e}')

def get_all_tags(struct=set):
    tags = struct()
    for pix in fav:
        tags.update(pix.tags)
    return tags

_count_all_tags = partial(get_all_tags, struct=Counter)

# init

def load_conf():
    l = (f'conf-{os.name}.json', 'conf.json')
    for fn in l:
        if os.path.exists(fn):
            with uopen(fn) as fp:
                return json.load(fp, encoding='utf-8')
    raise ConfMissing(f'Cannot load configuration from {l}')

CONF_PATH = 'conf.json'
sufs = {'bmp', 'jpg', 'png', 'tiff', 'tif', 'gif', 'pcx', 'tga', 'exif', 'fpx', 'svg', 'psd', 'cdr', 'pcd', 'dxf', 'ufo', 'eps', 'ai', 'raw', 'wmf', 'webp'}

pix_files = dict()
api = AppPixivAPI()

conf = load_conf()
conf_username = conf['username']
conf_passwd = conf['passwd']
conf_pix_path = fixed_path(conf['pix_path'])
conf_unused_path = fixed_path(conf['unused_path'])
conf_req_path = fixed_path(conf['req_path'])
conf_tmp_path = fixed_path(conf['tmp_path'])
conf_max_page_count = conf.get('max_page_count', -1) # do download after modifying this
conf_aria2_proxy = conf.get('aria2_proxy', '') # do download after modifying this
conf_local_source = fixed_path(conf['local_source']) if 'local_source' in conf else None
# conf_proxychains_for_aria2 = conf['proxychains_for_aria2']
# conf_ignore_ugoira = conf['ignore_ugoira'] # it is true
# _conf_nonh_id_except = set(conf.get('_nonh_id_except', ()))
for s in [conf_pix_path, conf_unused_path, conf_req_path, conf_tmp_path]:
    if not os.path.isdir(s):
        os.makedirs(s)

try:
    fav_load()
except Exception as e:
    fav = []
    print('Cannot load from local fav:', e)
else:
    download()

if __name__ == '__main__':
    shell()
