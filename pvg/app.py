import os, subprocess
from functools import wraps

from requests import get as req_get
from flask import Flask, render_template, request, abort, send_file, url_for, jsonify, make_response, send_from_directory
from flask_cors import CORS

from .util import *
from .core import fav, nav, user_info, update, greendam, download, download_url, qudg
from .workfilters import wf_hat, wfs
from .locking import locked, Lock
from .env import conf_username, conf_static_path, conf_pix_path, conf_thumb_path, conf_tmp_path, conf_use_thumbnails, conf_waifu2x_cmd_noise_scale, conf_waifu2x_cmd_scale

def fix(s):
    return fixed_path(os.path.abspath(s))

static_path = fix(conf_static_path)
# template_path = fix(conf_template_path)
pix_path = fix(conf_pix_path)
pix_pre = pix_path + '/'
thumb_path = fix(conf_thumb_path)
thumb_pre = thumb_path + '/'
tmp_path = fix(conf_tmp_path)
tmp_pre = tmp_path + '/'

app = Flask(__name__,
            static_url_path='',
            static_folder=static_path)

app.config['CORS_HEADERS'] = 'Content-Type'

cors = CORS(app)

actions = {
    'download': download,
    'update': update,
    'qupd': lambda: update(True),
    'greendam': greendam,
    'qudg': qudg
}

def short_cache(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        r = make_response(f(*args, **kwargs))
        r.cache_control.public = True
        r.cache_control.max_age = 300
        return r
    return wrapper

def no_cache(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        r = make_response(f(*args, **kwargs))
        r.cache_control.no_cache = True
        r.cache_control.no_store = True
        r.cache_control.must_revalidate = True
        return r
    return wrapper

def long_cache(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        r = make_response(f(*args, **kwargs))
        r.cache_control.public = True
        r.cache_control.max_age = 31536000
        return r
    return wrapper

@app.route('/action/<opt>')
@no_cache
def route_action(opt):
    try:
        act = actions.get(opt)
        if act:
            r = act()
            return 'locked' if r == locked else 'ok'
        else:
            abort(400)
    except Exception as e:
        print(500, type(e).__name__, e)
        raise e

error_fn = 'error.jpg'
error_path = static_path + '/error.jpg'

@app.route('/img/<int:pix_id>/<int:page_id>')
@long_cache
def get_image(pix_id, page_id):
    try:
        r = nav[pix_id][page_id]
    except:
        abort(400)

    meta, mime = r
    fn = meta.um.fn
    path = pix_pre + fn
    if not meta.exists and not os.path.exists(path):
        lock = Lock(fn)
        if not lock.lock():
            abort(404)
        try:
            if download_url(meta.um.url, pix_path, fn):
                meta.downloaded()
        finally:
            lock.unlock()
    elif not get_size(path):
        print('Empty file', path)
        abort(500)

    return send_file(path, attachment_filename=fn, mimetype=mime)

@app.route('/thumb/<int:pix_id>/<int:page_id>')
@long_cache
def get_thumb(pix_id, page_id):
    try:
        r = nav[pix_id][page_id]
    except:
        abort(400)

    meta = r[0]
    fn = meta.umt.fn
    mime = mimes[to_ext(fn)]
    path = thumb_pre + fn
    if not os.path.exists(path):
        lock = Lock('thu-' + fn)
        if not lock.lock():
            abort(404)
        try:
            if not download_url(meta.umt.url, thumb_path, fn):
                print('failed to get thumb')
                abort(500)
        finally:
            lock.unlock()
    elif not get_size(path):
        print('Empty thumb file', path)
        abort(500)

    return send_file(path, attachment_filename=fn, mimetype=mime)

def parse_wf(s):
    r = wfs.get(s)
    return r if r else wf_hat(s)

@app.route('/select', methods=['POST'])
def select():
    try:
        req = request.get_json(silent=True)['filters']
    except:
        abort(400)

    print('Requesting', req)
    filts = [~parse_wf(s[1:]) if s.startswith('!') else parse_wf(s)
            for s in req]

    res = []
    cnt_pix = 0
    for pix in fav:
        if all(map(lambda f: f(pix), filts)):
            cnt_pix += 1
            for i, meta in enumerate(pix.metas):
                w, h = meta.size
                pre = 'img'
                if w < 0 or (not meta.exists and conf_use_thumbnails):
                    w = h = 360
                    pre = 'thumb'

                res.append([pix.id, i, pre, w, h, pix.title, pix.author, pix.author_id, pix.tags, meta.um.fn])
                '''
                nav = f'/{pix.id}/{i}'
                    'ori': 'img' + nav,
                    'thu': pre + nav,
                '''

    print(f'Selected {len(res)} images.')
    return jsonify({'items': res})

@app.route('/upscale', methods={'POST'})
def upscale():
    form = request.form
    print('Upscale', form)

    try:
        ratio = form['ratio']
        float(ratio)

        noise_level = int(form['noise-level'])
    except (KeyError, ValueError):
        abort(400)

    if noise_level < 0 or noise_level > 4:
        abort(400)

    if 'pid' in form:
        try:
            pid = form['pid']
            ind = form['ind']
            print(pid, ind)
            input_path = pix_pre + nav[int(pid)][int(ind)][0].um.fn
        except (KeyError, IndexError):
            abort(400)

        output_fn = f'{pid}_{ind}_{noise_level}n_{ratio}x.png'
        output_path = tmp_pre + output_fn
        if not os.path.exists(output_path):
            dic = {
                '$scale_ratio': ratio,
                '$input': input_path,
                '$output': output_path,
            }
            if noise_level:
                dic['$noise_level'] = str(noise_level - 1)
                cmd = conf_waifu2x_cmd_noise_scale
            else:
                cmd = conf_waifu2x_cmd_scale

            def mapper(s):
                v = dic.get(s)
                return s if v is None else v

            cmd = list(map(mapper, cmd))
            print(' '.join(cmd))
            if subprocess.run(cmd).returncode:
                abort(500)

        return send_from_directory(tmp_path, output_fn, as_attachment=True, attachment_filename=output_fn)
    else:
        return 'QAQ'


avatar_path = tmp_pre + 'avatar.jpg'
@app.route('/avatar')
@short_cache
def get_avatar():
    if user_info:
        r = req_get(user_info['profile_image_urls']['px_170x170'], headers=pixiv_headers)
        if r.ok:
            with open(avatar_path, 'wb') as fp:
                fp.write(r.content)
            return send_file(avatar_path, mimetype='image/jpeg')
        else:
            print('Failed to fetch the avatar')
    if os.path.exists(avatar_path):
        return send_file(avatar_path, mimetype='image/jpeg')
    return app.send_static_file(error_fn)

user_info_resp = {
    'nick': user_info['name'],
    'name': conf_username,
    'mail': user_info['mail_address']
} if user_info else {'name': conf_username}

@app.route('/user')
@no_cache
def get_user_info():
    if user_info:
        return jsonify(user_info_resp)

if os.path.exists('ver.txt'):
    try:
        with uopen('ver.txt') as fp:
            ver = fp.read().strip()
    except:
        ver = 'Unknown'
else:
    ver = 'Rolling'

@app.route('/ver')
@no_cache
def get_ver():
    return jsonify({'ver': ver})

@app.route('/')
def index():
    return app.send_static_file('index.html')
