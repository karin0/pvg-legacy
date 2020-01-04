import os, json, shutil, sys, subprocess, webbrowser
from time import sleep
from collections import Counter

from pixivpy3 import AppPixivAPI
from PIL import Image

from util import *
from error import *
from env import *
from locking import use_lock

def load_size(f):
    local_url = conf_pix_path + '/' + f['fn']
    try:
        im = Image.open(local_url)
        f['w'], f['h'] = im.size
        return True
    except:
        f['w'] = f['h'] = -1
        return False

# CLEAR_FILES_META = False

class Work(object):
    def __init__(self, data):
        # if CLEAR_FILES_META:
        #     data.pop('files')
        self.data = data
        self.author = data['user']['name']
        self.author_id = data['user']['id']
        self.tags = [x['name'] for x in data['tags']]
        self.spec = '$$'.join(self.tags + [self.title, self.author])
        self.likes = data['total_bookmarks']
        self.width = data['width']
        self.height = data['height']
        self.page_count = data['page_count']
        self.intro = {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'pages': self.page_count,
            'likes': self.likes,
            'tags': self.tags
        }

    def gen_files(self):
        if self.type == 'ugoira':
            self.files = self.data['files'] = []
            return False

        self.files = self.data.get('files')
        if self.page_count == 1:
            if self.files and len(self.files) == 1:
                return False # No action

            url = self.data['meta_single_page']['original_image_url']
            self.files = self.data['files'] = [{
                'fn': to_filename(url),
                'url': url,
                'w': self.width,
                'h': self.height
            }]
        else:
            if self.files and len(self.files) == self.page_count:
                ret = False
                for x in self.files:
                    if (x['w'] < 0 or x['h'] < 0) and load_size(x):
                        ret = True
                return ret

            self.files = self.data['files'] = []
            for x in self.data['meta_pages']:
                url = x['image_urls']['original']
                f = {
                    'fn': to_filename(url),
                    'url': url
                }
                load_size(f)
                self.files.append(f)

        return True

    def __repr__(self):
        return repr(self.intro)
    def __str__(self):
        return str(self.intro)
    def __getattr__(self, item):
        return self.data[item]
    def _open(self):
        return webbrowser.open(f'https://www.pixiv.net/artworks/{self.id}')

# remote db

def login(force=False):
    if force or not api.user_id:
        print('Logining with', conf_username, conf_passwd)
        retry_def(api.login)(conf_username, conf_passwd)
        print('Logined, uid =', api.user_id)

@use_lock
def greendam(quick=False):
    login()
    update(quick)
    # que = list(reversed([x for x in fav if 'R-18' in x.tags and x.bookmark_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    add_handler = retry_def(api.illust_bookmark_add)
    que = [pix for pix in fav if 'R-18' in pix.tags and pix.bookmark_restrict == 'public']
    tot = len(que)
    for i, pix in enumerate(reversed(que), 1):
        print(f'{i}/{tot}: {pix.title} ({pix.id})')
        add_handler(pix.id, restrict='private')
        pix.data['bookmark_restrict'] = 'private' # Be careful when assigning to "attributes" of Works.. maybe we can remove the "data" field
    fav_save()
    # update()

# local db

def key_of_work(pix):
    return -pix.id

def fav_save(): # call after local db is modified
    fav.sort(key=key_of_work)
    if os.path.exists('fav.json'):
        force_move('fav.json', f'{conf_tmp_path}/fav-old.json')
    with uopen('fav.json', 'w') as f:
        json.dump([pix.data for pix in fav], f, separators=(',', ':'))
    fav_load()

def fav_load():
    global fav #, CLEAR_FILES_META
    try:
        with uopen('fav.json', 'r') as fp:
            fav = list(map(Work, json.load(fp, encoding='utf-8')))
    except Exception as e:
        fav = []
        print('Cannot load from local fav:', type(e).__name__, e)

    cnt = 0
    changed = False
    for pix in fav:
        if pix.gen_files():
            changed = True
            cnt += 1
            print(cnt, pix.id)

    # CLEAR_FILES_META = False
    if changed:
        fav_save()
    else:
        build_fav()

    # fav.sort(key=lambda pix: -pix.likes)

@use_lock
def update(quick=False):
    global fav
    if quick:
        ids = {pix.id for pix in fav}
    nfav = []

    login()

    for restrict in ('public', 'private'):
        @retry_def
        def bookmarks_handler(**kwargs):
            depth = kwargs.pop('depth')
            res = api.user_bookmarks_illust(**kwargs)
            if 'error' in res or 'illusts' not in res:
                print('bad request, ', res)
                sleep(30 * (1 + depth))
                login(True)
                raise BadRequestError
            return res
        cnt = icnt = rcnt = 0
        r = bookmarks_handler(user_id=api.user_id, restrict=restrict, depth=0)
        while True:
            cnt += 1
            print(f'{len(r.illusts)} on {restrict} page #{cnt}')

            for data in r.illusts:
                if data['user']['id']:
                    # data['ugoira_metadata'] = api.ugoira_metadata(data['id'])['ugoira_metadata'] # disable it
                    if quick and data['id'] in ids:
                        print(f'{rcnt} {restrict} new in total, {icnt} invalid')
                        return
                    data = dict(data)
                    data['bookmark_restrict'] = restrict
                    nfav.append(Work(data)) # no need to add id to ids
                    rcnt += 1
                else:
                    icnt += 1

            if r.next_url is None:
                break
            r = bookmarks_handler(**api.parse_qs(r.next_url), depth=0)
        print(f'{rcnt} {restrict} in total, {icnt} invalid')

    files = {}
    for pix in fav:
        fs = pix.data.get('files')
        if fs:
            files[pix.id] = fs
    ids = set()
    for pix in nfav:
        ids.add(pix.id)
        fs = files.get(pix.id)
        if fs:
            pix.files = pix.data['files'] = fs
    for pix in fav:
        if pix.id not in ids:
            ids.add(pix.id)
            nfav.append(pix)
    fav = nfav

    fav_save()

# file operation

def _move_unused_files():
    clean_aria2()
    print('Cleaning unused files..')
    cnt = 0
    for path in conf_pix_path:
        for fn in os.listdir(path):
            fnl = fn.lower()
            if fnl not in pix_files and to_ext(fnl) in mimes:
                shutil.move(f'{path}/{fn}', conf_unused_path)
                cnt += 1
    print(f'Cleaned {cnt} files.')

def gen_aria2_conf(**kwargs):
    r = aria2_conf_tmpl
    for k, v in kwargs.items():
        if v:
            r += f'{k.replace("_", "-")}={v}\n'
    return r

def clean_aria2():
    for fn in os.listdir(conf_pix_path):
        if fn.endswith('.aria2'):
            print('Found', fn)
            os.remove(f'{conf_pix_path}/{fn}')
            remove_noexcept(f'{conf_pix_path}/{fn[:-6]}')

ls_extra = dict()
@use_lock
def download():
    clean_aria2()
    print('Counting undownloaded files..')
    ls_pix = set(os.listdir(conf_pix_path))
    ls_unused = set(os.listdir(conf_unused_path))

    if not ls_extra and conf_local_source and os.path.exists(conf_local_source):
        print('Local source is avaliable.')
        for x in (conf_pix_path, conf_unused_path):
            try:
                print('Listing ', x)
                ls = os.listdir(x)
                for fn in ls:
                    ls_extra[fn] = x + '/' + fn
                print(f'Found {len(ls)} files from {x}.')
            except FileNotFoundError:
                print(f'{x} does not exist local source!')

    que = []
    cnt = 0
    extcnt = 0
    for fn, (url, pix) in pix_files.items():
        if fn not in ls_pix:
            if fn in ls_unused:
                shutil.move(f'{conf_unused_path}/{fn}', conf_pix_path)
                cnt += 1
            elif fn in ls_extra:
                print(f'Found {fn} from local source!')
                shutil.copy(ls_extra[fn], conf_pix_path)
                extcnt += 1
            else:
                que.append((fn, url, pix))
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
        for i, (fn, url, pix) in enumerate(que, 1):
            print(f'{i}/{tot}: {fn} from {pix.title}')
            fp.write(url + '\n')

    with uopen(aria2_conf_path, 'w') as fp:
        fp.write(gen_aria2_conf(
            dir=os.path.abspath(conf_pix_path),
            input_file=os.path.abspath(urls_path),
            file_allocation=conf_aria2_file_allocation,
            all_proxy=conf_aria2_proxy
        ))
    try:
        en = os.environ.copy()
        en['LANG']='en_US.utf-8'
        proc = subprocess.Popen(
            # (['proxychains'] if conf_proxychains_for_aria2 else []) +
            [conf_aria2c_path, '--conf-path', aria2_conf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=en
        ) # (done) force proxychains now
        print('Aria2c started.')
        cnt = 0
        for line in proc.stdout:
            s = line.decode().strip()
            # print(s)
            if 'Download complete' in s or '下载已完成' in s:
                cnt += 1
                print(f'{cnt}/{tot}', s)
            if cnt >= tot:
                break
        else:
            raise DownloadUncompletedError
        # proc.wait()
        print('All done!')
    except DownloadUncompletedError:
        print('Download not completed.')
        proc.terminate()
        clean_aria2()
        raise DownloadUncompletedError
    else:
        proc.terminate()

def build_fav():
    global nav, pix_files, all_tags, all_tags_list
    nav = {}
    pix_files = {}
    all_tags = Counter()
    for pix in fav:
        if conf_max_page_count < 0 or pix.page_count <= conf_max_page_count:
            is_first = True
            nav_val = []
            for f in pix.files:
                fn = f['fn']
                all_tags.update(pix.tags)
                pix_files[fn.lower()] = (f['url'], pix)
                local_url = conf_pix_path + '/' + fn

                if is_first:
                    is_first = False
                    if_exists = os.path.exists(local_url)
                else:
                    if_exists = f['w'] >= 0

                if if_exists:
                    nav_val.append((local_url, mimes[to_ext(fn)]))
                else:
                    nav_val.append(None)
            nav[pix.id] = nav_val

    all_tags_list = [x[0] for x in all_tags.most_common()]

api = AppPixivAPI()

fav = []
fav_load()
