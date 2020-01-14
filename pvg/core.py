import os, json, shutil, sys, subprocess
from time import sleep

from pixivpy3 import AppPixivAPI
from PIL import Image
from requests import get as req_get

from .util import *
from .error import *
from .env import *
from .locking import use_lock

# CLEAR_FILES_META = False

class URLMeta(object):
    def __init__(self, url):
        self.url = url
        self.fn = to_filename(url)

    def load_size(self):
        try:
            with Image.open(conf_pix_path + '/' + self.fn) as im:
                return im.size
        except:
            return -1, -1

class IllustMeta(object):
    def __init__(self, pix, i, exists):
        self.pix = pix
        self.ind = i
        self.um = pix.ums[i]
        self.umt = pix.umst[i]
        self.size = pix.sizes[i]
        self.exists = exists
    
    def downloaded(self):
        self.exists = True
        if self.size[0] < 0:
            self.size = self.pix.sizes[self.ind] = self.um.load_size()

order_inf = 1 << 60
  
class Illust(object):
    def __init__(self, data):
        # if CLEAR_FILES_META:
        #     data.pop('files')
        self.data = data
        self.title = data['title']
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
        if 'order' not in data:
            data['order'] = order_inf
        
        if self.type == 'ugoira' or self.data.get('deleted'):
            self.ums = self.umst = []
        elif self.page_count == 1:
            self.ums = [URLMeta(data['meta_single_page']['original_image_url'])]
            self.umst = [URLMeta(data['image_urls']['square_medium'])]
        else:
            self.ums = []
            self.umst = []
            for x in self.data['meta_pages']:
                xi = x['image_urls']
                self.ums.append(URLMeta(xi['original']))
                self.umst.append(URLMeta(xi['square_medium']))

    def gen_sizes(self):
        if self.type == 'ugoira':
            self.sizes = []
            return False
        
        if self.page_count == 1:
            self.sizes = [(self.width, self.height)]
            return False
        
        self.sizes = self.data.get('sizes')

        if self.sizes and len(self.sizes) == self.page_count:
            self.sizes = list(map(tuple, self.sizes))
            ret = False
            ns = [(self.width, self.height)]
            for i in range(1, self.page_count):
                x = self.sizes[i]
                if x[0] >= 0:
                    ns.append(x)
                else:
                    y = self.ums[i].load_size()
                    if y[0] >= 0:
                        ns.append(y)
                        ret = True
            if ret:
                self.data['sizes'] = self.sizes = ns
                return True
            return False
        
        ns = [(self.width, self.height)]
        for i in range(1, self.page_count):
            ns.append(self.ums[i].load_size())
        self.sizes = self.data['sizes'] = ns
        return True
    
    def delete(self):
        self.data['deleted'] = True
        self.ums = self.umst = self.sizes = self.data['sizes'] = []

    def __repr__(self):
        return repr(self.intro)
    def __str__(self):
        return str(self.intro)
    def __getattr__(self, item):
        return self.data[item]

# remote db

api = AppPixivAPI()
login_handler = use_lock(retry_def(api.login), name='loginer')
def login(force=False):
    if force or not api.user_id:
        print('Logining with', conf_username, conf_passwd)
        login_handler(conf_username, conf_passwd)
        if not api.user_id:
            raise PvgError('failed to login')
        print('Logined, uid =', api.user_id)

@use_lock
def greendam():
    login()
    # que = list(reversed([x for x in fav if 'R-18' in x.tags and x.bookmark_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    add_handler = retry_def(api.illust_bookmark_add)
    que = [pix for pix in fav if 'R-18' in pix.tags and pix.bookmark_restrict == 'public']
    tot = len(que)
    for i, pix in enumerate(reversed(que), 1):
        print(f'{i}/{tot}: {pix.title} ({pix.id})')
        add_handler(pix.id, restrict='private')
        pix.data['bookmark_restrict'] = 'private' # not the attr
    fav_save()

# local db handler, functions calling which should use locks


def fav_save():
    print('Saving to local db..')
    if os.path.exists('fav.json'):
        force_move('fav.json', f'{conf_tmp_path}/fav-old.json')
    with uopen('fav.json', 'w') as f:
        json.dump([pix.data for pix in fav], f, separators=(',', ':'))
    print('Saved')

def key_of_illust(pix):
    return (pix.data['order'], -pix.id)

def fav_hook(force_save=False):
    # global CLEAR_FILES_META
    print('Running local db hook..')
    fav.sort(key=key_of_illust)
    cnt = 1 if force_save else 0
    for pix in fav:
        if pix.gen_sizes():
            cnt += 1
            print(cnt, pix.id)

    # CLEAR_FILES_META = False
    if cnt:
        fav_save()
    build_fav()
    print('Db hook done')

def fav_load():
    print('Loading local db..')
    try:
        with uopen('fav.json', 'r') as fp:
            list_copy(fav, list(map(Illust, json.load(fp, encoding='utf-8'))))
    except Exception as e:
        fav.clear()
        print('Cannot load from local fav:', type(e).__name__, e)
    fav_hook()

def build_fav():
    print('Building fav..')
    nav.clear()
    pix_files.clear()

    for pix in fav:
        if conf_max_page_count < 0 or pix.page_count <= conf_max_page_count:
            is_first = True
            nav_val = []
            pix.metas = []
            for i, meta in enumerate(pix.ums):
                fn = meta.fn
                furl = meta.url
                pix_files[fn.lower()] = (furl, pix)

                if is_first:
                    is_first = False
                    if_exists = os.path.exists(conf_pix_path + '/' + fn)
                else:
                    if_exists = pix.sizes[i][0] >= 0
                
                imeta = IllustMeta(pix, i, if_exists)
                nav_val.append([imeta, mimes[to_ext(fn)]])
                pix.metas.append(imeta)

            nav[pix.id] = nav_val

# higher-level db manage

@use_lock
def update(quick=False):
    if quick:
        ids = {pix.id for pix in fav}
    nfav = []

    login()

    def fetch(restrict):
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

            quick_ok = True
            for data in r.illusts:
                if data['user']['id']:
                    # data['ugoira_metadata'] = api.ugoira_metadata(data['id'])['ugoira_metadata'] # disable it
                    if quick and data['id'] not in ids:
                        quick_ok = False
                    data = dict(data)
                    data['bookmark_restrict'] = restrict
                    nfav.append(Illust(data)) # no need to add id to ids
                    rcnt += 1
                else:
                    icnt += 1
            
            if (quick and quick_ok) or r.next_url is None:
                break
            r = bookmarks_handler(**api.parse_qs(r.next_url), depth=0)
        print(f'{rcnt} {restrict} in total, {icnt} invalid')

    for restrict in ('public', 'private'):
        fetch(restrict)

    sizes = {}
    for pix in fav:
        fs = pix.data.get('sizes')
        if fs:
            sizes[pix.id] = fs
    ids = set()
    for pix in nfav:
        ids.add(pix.id)
        fs = sizes.get(pix.id)
        if fs:
            pix.sizes = pix.data['sizes'] = fs
    for pix in fav:
        if pix.id not in ids:
            ids.add(pix.id)
            nfav.append(pix)
    list_copy(fav, nfav)
    fav_hook(True)

# file operation

def gen_aria2_conf(**kwargs):
    return ''.join(
        [aria2_conf_tmpl] +
        [f'{k.replace("_", "-")}={v}\n' for k, v in kwargs.items() if v]
    )

def clean_aria2():
    for fn in os.listdir(conf_pix_path):
        if fn.endswith('.aria2'):
            print('Found', fn)
            os.remove(f'{conf_pix_path}/{fn}')
            remove_noexcept(f'{conf_pix_path}/{fn[:-6]}')

def get_download_queue():
    print('Counting nonexistent files..')
    ls_pix = set(os.listdir(conf_pix_path))
    return [(fn, url, pix) for fn, (url, pix) in pix_files.items() if fn not in ls_pix]

illust_detail_handler = retry_def(api.illust_detail)
@use_lock
def download():
    clean_aria2()
    que = get_download_queue()
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
            user_agent=pixiv_headers['user-agent'],
            referer=pixiv_headers['referer'],
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
        )
        print('aria2c started.')
        cnt = 0
        cnt_404 = 0
        aborted = False
        for line in proc.stdout:
            s = line.decode().strip()
            sl = s.lower()
            if 'download complete' in sl or '下载已完成' in s:
                cnt += 1
                print(f'{cnt}/{tot}', s)
            elif 'download aborted' in sl:
                aborted = True
                cnt += 1
                print(f'{cnt}/{tot}', s)
            if 'resource not found' in sl:
                cnt_404 += 1
                print('Got 404: ', cnt_404, s)
            elif 'error' in sl:
                print(s)
            if cnt >= tot:
                break
        else:
            raise DownloadUncompletedError
        # proc.wait()
        print('All done!')
        if aborted:
            que = get_download_queue()
            lost_ids = set()
            lost_pixs = []
            if len(que) == cnt_404:
                for fn, url, pix in que:
                    print('Retrieving all', pix.id, pix.title)
                    if pix.id not in lost_ids:
                        lost_ids.add(pix.id)
                        lost_pixs.append(pix)
            else:
                for fn, url, pix in que:
                    if pix.id not in lost_ids:
                        print('Fetching', fn, url, '..')
                        r = req_get(url, headers=pixiv_headers)
                        if r.ok:
                            print('OK', r.status_code, 'Writing..')
                            with open(conf_pix_path + '/' + fn, 'wb') as fp:
                                fp.write(r.content)
                            print('Done')
                        else:
                            print('Error', r.status_code)
                            if r.status_code == 404:
                                print('Retrieving', pix.id, pix.title)
                                lost_ids.add(pix.id)
                                lost_pixs.append(pix)
            if lost_pixs:
                login()
                repls = {}
                for pix in lost_pixs:
                    print('Fetching', pix.id)
                    r = illust_detail_handler(pix.id)
                    if 'error' in r:
                        print(r)
                        pix.delete()
                    else:
                        r = r.get('illust')
                        if r and r.is_bookmarked:
                            print('ok')
                            repls[pix.id] = Illust(dict(r))
                        else:
                            pix.delete()
                if repls:
                    for i in range(len(fav)):
                        npix = repls.get(fav[i].id)
                        if npix:
                            fav[i] = npix

    except DownloadUncompletedError:
        print('Download not completed!')
        proc.terminate()
        clean_aria2()
    else:
        proc.terminate()
    finally:
        fav_hook(True)

@use_lock
def qudg():
    update(True)
    download()
    greendam()

def download_url(url, path, name):
    print('downloading', url, path, name)
    try:
        login()
    except Exception as e:
        print('Exception in logging:', type(e).__name__, e)
    try:
        return api.download(url, path=path, name=name)
    except Exception as e:
        print(type(e).__name__, e)
        return False

fav = []
nav = {}
pix_files = {}

fav_load()
