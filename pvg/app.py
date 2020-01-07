import os
from itertools import chain

from flask import Flask, render_template, request, abort, send_file, url_for, jsonify
from flask_cors import CORS

from .util import *
from .core import fav, nav, update, greendam, download, download_url, qudg
from .workfilters import wf_hat, wfs
from .locking import locked, Lock
from .env import conf_static_path, conf_pix_path, conf_thumb_path, conf_use_thumbnails

def fix(s):
    return fixed_path(os.path.abspath(s))

static_path = fix(conf_static_path)
# template_path = fix(conf_template_path)
pix_path = fix(conf_pix_path)
pix_pre = pix_path + '/'
thumb_path = fix(conf_thumb_path)
thumb_pre = thumb_path + '/'

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

@app.route('/action/<opt>')
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

error_path = static_path + '/error.jpg'

@app.route('/img/<int:pix_id>/<int:page_id>')
def get_image(pix_id, page_id):
    try:
        r = nav[pix_id][page_id]
    except:
        abort(400)

    meta, mime = r
    fn = meta.um.fn
    if not meta.exists:
        lock = Lock(fn)
        if not lock.lock():
            abort(500)
        try:
            if download_url(meta.um.url, pix_path, fn):
                meta.downloaded()
        finally:
            lock.unlock()

    return send_file(pix_pre + fn, mimetype=mime)

@app.route('/thumb/<int:pix_id>/<int:page_id>')
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
            abort(500)
        try:
            if not download_url(meta.umt.url, thumb_path, fn):
                print('failed to get thumb')
                abort(500)
        finally:
            lock.unlock()

    return send_file(path, mimetype=mime)

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
    for pix in fav:
        if all(map(lambda f: f(pix), filts)):
            for i, meta in enumerate(pix.metas):
                w, h = meta.size
                pre = 'img'
                if w < 0 or (not meta.exists and conf_use_thumbnails):
                    w = h = 360
                    pre = 'thumb'

                nav = f'/{pix.id}/{i}'
                res.append({
                    'pid': pix.id,
                    'ori': 'img' + nav,
                    'thu': pre + nav,
                    'title': pix.title,
                    'author': pix.author,
                    'aid': pix.author_id,
                    'tags': pix.tags,
                    'w': w,
                    'h': h
                })

    print(f'Selected {len(res)} images.')
    return jsonify({'items': res})

@app.route('/')
def index():
    return app.send_static_file('index.html')
