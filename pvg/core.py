import os, json, subprocess
from time import sleep
from shutil import move
from threading import Lock
from typing import Dict, List, Tuple

from pixivpy3 import AppPixivAPI
from PIL import Image, UnidentifiedImageError
from requests import get as req_get

from .util import *
from .error import *
from .env import *
from .locking import use_lock


# CLEAR_FILES_META = False

class URLMeta:
    def __init__(self, url):
        self.url = url
        self.fn = to_filename(url)

    def load_size(self):
        try:
            with Image.open(conf_pix_path + '/' + self.fn) as im:
                return im.size
        except (FileNotFoundError, UnidentifiedImageError):
            return -1, -1


class Page:
    def __init__(self, pix, i, exists):
        self.pix = pix
        self.ind = i
        self.um = pix.ums[i]
        self.url = self.um.url
        self.fn = self.um.fn
        self.umt = pix.ums_thumb[i]
        self.size = pix.sizes[i]
        self.exists = exists
        self.thumb_lock = Lock()
        self.lock = Lock()

    def downloaded(self):
        if self.size[0] < 0:
            self.size = self.pix.sizes[self.ind] = self.um.load_size()
            # todo: fav hook is not called and loaded size will not be saved.
        self.exists = True

    def acquire(self, block = True):
        return self.lock.acquire(block)

    def release(self):
        self.lock.release()

    def try_release(self):
        if self.lock.locked():
            self.lock.release()


class Illust:
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
        if 'order' in data:
            data.pop('order')

        if self.type == 'ugoira' or self.data.get('deleted'):
            self.ums = self.ums_thumb = []
        elif self.page_count == 1:
            self.ums = [URLMeta(data['meta_single_page']['original_image_url'])]
            self.ums_thumb = [URLMeta(data['image_urls']['square_medium'])]
        else:
            self.ums = []
            self.ums_thumb = []
            for x in self.data['meta_pages']:
                xi = x['image_urls']
                self.ums.append(URLMeta(xi['original']))
                self.ums_thumb.append(URLMeta(xi['square_medium']))

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
        self.ums = self.ums_thumb = self.sizes = self.data['sizes'] = []

    def __repr__(self):
        return repr(self.intro)

    def __str__(self):
        return str(self.intro)

    def __getattr__(self, item):
        return self.data[item]


# remote db

api = AppPixivAPI()
login_handler = use_lock(retry(api.login))


def login(force=False):
    if force or not api.user_id:
        print('Logining with', conf_username, conf_passwd)
        r = login_handler(conf_username, conf_passwd)
        if not api.user_id:
            raise PvgError('failed to login')
        dict_copy(user_info, dict(r.response.user))
        print('Logined, uid =', api.user_id)


fav_lock = Lock()


@use_lock
def greendam():
    login()
    # que = list(reversed([x for x in fav if 'R-18' in x.tags and x.bookmark_restrict == 'public' and x.id not in _conf_nonh_id_except]))
    add_handler = retry(api.illust_bookmark_add)
    que = [pix for pix in fav if 'R-18' in pix.tags and pix.bookmark_restrict == 'public']
    tot = len(que)
    for i, pix in enumerate(reversed(que), 1):
        print(f'{i}/{tot}: {pix.title} ({pix.id})')
        add_handler(pix.id, restrict='private')
        pix.data['bookmark_restrict'] = 'private'  # not the attr
    fav_save()


# local db handler, functions calling which should use locks

def fav_save():  # unlocked
    print('Saving to local db..')
    if os.path.exists('fav.json'):
        force_move('fav.json', f'{conf_tmp_path}/fav-old.json')
    with uopen('fav.json', 'w') as f:
        json.dump([pix.data for pix in fav], f, separators=(',', ':'))
    print('Saved')


def fav_hook(force_save=False, new_fav=None):
    # global CLEAR_FILES_META
    print('Running local db hook..')
    # fav.sort(key=key_of_illust)
    cnt = 0
    with fav_lock:
        if new_fav is not None:
            list_copy(fav, new_fav)
        for pix in fav:
            if pix.gen_sizes():
                cnt += 1
                print(cnt, pix.id)

        # CLEAR_FILES_META = False
        if cnt or force_save:
            fav_save()
        build_nav()
    print('Db hook done')


def fav_init():
    clean_aria2()
    print('Loading local db..')
    try:
        with uopen('fav.json', 'r') as fp:
            list_copy(fav, map(Illust, json.load(fp, encoding='utf-8')))
    except Exception as e:
        fav.clear()
        print('Cannot load from local fav:', type(e).__name__, e)
    fav_hook()


def build_nav():  # unlocked
    print('Building fav..')
    nav.clear()
    pages.clear()

    for pix in fav:
        if conf_max_page_count < 0 or pix.page_count <= conf_max_page_count:
            is_first = True
            nav_val = []
            pix.pages = []
            for i, meta in enumerate(pix.ums):
                fn = meta.fn

                if is_first:
                    is_first = False
                    if_exists = os.path.exists(conf_pix_path + '/' + fn)
                else:
                    if_exists = pix.sizes[i][0] >= 0

                page = Page(pix, i, if_exists)
                pages[fn.lower()] = page
                nav_val.append((page, mimes[to_ext(fn)]))
                pix.pages.append(page)

            nav[pix.id] = nav_val


# higher-level db opts

@use_lock
def update(quick=False):
    if quick:
        ids = {pix.id for pix in fav}
    nfav = []

    login()

    def fetch(restrict):
        @retry
        def bookmarks_handler(**kwargs):
            depth = kwargs.pop('depth')
            res = api.user_bookmarks_illust(**kwargs)
            if 'error' in res or 'illusts' not in res:
                print('bad request, ', res)
                t = 180 + 50 * depth
                print('Retrying after', t, 'sec..')
                sleep(t)
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
                    # data['ugoira_metadata'] = api.ugoira_metadata(data['id'])['ugoira_metadata'] # disabled
                    if quick and data['id'] not in ids:
                        quick_ok = False

                    data = dict(data)
                    data['bookmark_restrict'] = restrict
                    nfav.append(Illust(data))
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
    fav_hook(force_save=True, new_fav=nfav)


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


def move_unused():
    files = set()
    for pix in fav:
        for meta in pix.ums:
            files.add(meta.fn)

    fns = []
    for fn in os.listdir(conf_pix_path):
        for suf in mimes.keys():
            if fn.endswith('.' + suf):
                break
        else:
            if fn != 'unused':
                print(fn, 'is not an image')
            continue

        if fn not in files:
            fns.append(fn)
            print(fn, 'is unused!')

    if fns:
        dest = conf_pix_path + '/unused'
        if not os.path.exists(dest):
            os.mkdir(dest)
        for fn in fns:
            move(conf_pix_path + '/' + fn, dest)


class DownloadQueue:
    def __init__(self):
        print('Counting nonexistent files..')
        ls_pix = set(os.listdir(conf_pix_path))
        self.q = q = []
        with fav_lock:
            for fn, page in pages.items():
                if fn not in ls_pix and page.acquire(False):
                    q.append(page)

    def complete(self):
        ls_pix = set(os.listdir(conf_pix_path))
        res = []
        for page in self.q:
            if page.fn in ls_pix:
                page.try_release()
            else:
                res.append(page)
        self.q = res

    def __enter__(self):
        return self

    def __exit__(self, _, __, ___):
        for page in self.q:
            page.try_release()

    def __iter__(self):
        return iter(self.q)

    def __bool__(self):
        return bool(self.q)

    def __len__(self):
        return len(self.q)


illust_detail_handler = retry(api.illust_detail)


@use_lock
def download():
    clean_aria2()
    move_unused()

    with DownloadQueue() as q:
        if not q:
            print('All files are downloaded.')
            return

        urls_path = f'{conf_tmp_path}/urls'
        aria2_conf_path = f'{conf_tmp_path}/aria2.conf'
        tot = len(q)
        print(f'{tot} files to download.')
        with uopen(urls_path, 'w') as fp:
            for i, meta in enumerate(q, 1):
                print(f'{i}/{tot}: {meta.fn} from {meta.pix.title}')
                fp.write(meta.url + '\n')

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
            en['LANG'] = 'en_US.utf-8'
            proc = subprocess.Popen(
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
                fn = find_suffix(s, 'Download complete:')
                if fn is None:
                    fn = find_suffix(s, '下载已完成：')
                if fn is not None:
                    pages[to_filename(fn.strip())].release()
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
                q.complete()
                lost_ids = set()
                lost_pixs = []
                if len(q) == cnt_404:
                    for meta in q:
                        pid = meta.pix.id
                        print('Retrieving all', pid, meta.pix.title)
                        if pid not in lost_ids:
                            lost_ids.add(pid)
                            lost_pixs.append(meta.pix)
                else:
                    if len(q) > 10:
                        print('Too many failures.')
                        raise DownloadUncompletedError
                    for meta in q:
                        pid = meta.pix.id
                        if pid not in lost_ids:
                            print('Fetching', meta.fn, meta.url, '..')
                            r = req_get(meta.url, headers=pixiv_headers)
                            if r.ok:
                                print('OK', r.status_code, 'Writing..')
                                with open(conf_pix_path + '/' + meta.fn, 'wb') as fp:
                                    fp.write(r.content)
                                meta.release()
                            else:
                                print('Error', r.status_code)
                                if r.status_code == 404:
                                    print('404. Retrieving', pid, meta.pix.title)
                                    lost_ids.add(pid)
                                    lost_pixs.append(meta.pix)
                if lost_pixs:
                    login()
                    for pix in lost_pixs:
                        print('Fetching', pix.id)
                        r = illust_detail_handler(pix.id)
                        if 'error' in r:
                            print(r)
                            pix.delete()
                        else:
                            r = r.get('illust')
                            if r and r.is_bookmarked:
                                print(r, 'is back')
                                pix.__init__(dict(r))
                            else:
                                pix.delete()
        except DownloadUncompletedError:
            print('Download not completed!')
            proc.terminate()
            clean_aria2()
        else:
            proc.terminate()
        finally:
            fav_hook()


@use_lock
def qudg():
    update(True)
    download()
    greendam()


def download_url(url, path, name):
    print('downloading', url)
    '''
    try:
        login()
    except Exception as e:
        print('Exception in logging:', type(e).__name__, e)
    '''
    if os.path.exists(path + '/' + name):
        print('Already exists', name)
        return True
    try:
        return api.download(url, path=path, name=name)
    except Exception as e:
        print(type(e).__name__, e)
        return False


user_info = {}
fav = []
nav: Dict[int, List[Tuple[Page, str]]] = {}
pages: Dict[str, Page] = {}

try:
    login()
except Exception as e:
    print('Login failed', type(e).__name__, e,  'Press Enter to continue.')
    input()

fav_init()
