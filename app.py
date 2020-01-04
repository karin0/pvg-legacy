import os
from flask import Flask, render_template, request, abort, send_file, url_for, jsonify
from flask_cors import CORS

from util import fixed_path
from core import *
from workfilters import *
from locking import locked

static_folder = 'frontend/build'
template_folder = 'templates'

static_folder = fixed_path(static_folder)
template_folder = fixed_path(template_folder)
app = Flask(__name__,
            static_url_path='',
            static_folder=static_folder,
            template_folder=template_folder)

app.config['CORS_HEADERS'] = 'Content-Type'

cors = CORS(app)

actions = {
    'download': download,
    'update': update,
    'qupd': lambda: update(True),
    'greendam': greendam,
    'qgreen': lambda: greendam(True),
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

'''
@app.route('/tags')
def get_tags():
    return jsonify({'tags': all_tags_list})
'''

error_path = static_folder + '/error.jpg'

@app.route('/img/<int:pix_id>/<int:page_id>')
def get_image(pix_id, page_id):
    r = nav.get(pix_id)
    if not r:
        return send_file(error_path, mimetype='image/jpeg')

    try:
        url, mime = r[page_id]
    except IndexError:
        return send_file(error_path, mimetype='image/jpeg')

    return send_file(url, mimetype=mime)

@app.route('/select', methods=['POST'])
def select():
    req = request.get_json(silent=True)
    filt = wf_true
    try:
        for s in req['filters']:
            if s.startswith('!'):
                filt &= ~wf_hat(s[1:])
            elif s in wfs:
                filt &= wfs[s]
            else:
                filt &= wf_hat(s)
    except:
        abort(400)

    res = []
    for pix in fav:
        if filt(pix):
            for i, f in enumerate(pix.files):
                res.append({
                    'pid': pix.id,
                    'nav': f'{pix.id}/{i}',
                    'title': pix.title,
                    'author': pix.author,
                    'aid': pix.author_id,
                    'tags': pix.tags,
                    'w': f['w'],
                    'h': f['h']
                })
    print(f'Selected {len(res)} pixs.')
    return jsonify({'items': res})

@app.route('/')
def index():
    return render_template('index.html')
