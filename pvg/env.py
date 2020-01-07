import os, json

from .error import ConfMissing
from .util import *

def load_conf():
    l = (f'conf-{os.name}.json', 'conf.json')
    for fn in l:
        if os.path.exists(fn):
            with uopen(fn) as fp:
                return json.load(fp, encoding='utf-8')
    raise ConfMissing(f'Cannot load configuration from {l}')

CONF_PATH = 'conf.json'

conf = load_conf()
conf_username = conf['username']
conf_passwd = conf['passwd']
conf_pix_path = fixed_path(conf.get('pix_path', 'pix'))
conf_thumb_path = fixed_path(conf.get('thumb_path', 'thumb'))
conf_tmp_path = fixed_path(conf.get('tmp_path', 'tmp'))
conf_max_page_count = conf.get('max_page_count', -1) # do download after modifying this
conf_aria2_proxy = conf.get('aria2_proxy')
conf_aria2c_path = conf.get('aria2c_path', 'aria2c')
conf_aria2_file_allocation = conf.get('aria2_file_allocation', '')
conf_static_path = fixed_path(conf.get('static_path', 'static'))

r = conf.get('use_thumbnails')
conf_use_thumbnails = False if r is None else (str(r).lower() == 'true')

# conf_local_source = fixed_path(conf['local_source']) if 'local_source' in conf else None
# conf_template_path = fixed_path(conf.get('template_path', 'template'))
# conf_unused_path = fixed_path(conf.get('unused_path', './unused'))
# conf_socks5_addr = conf.get('socks5_addr')
# conf_socks5_port = conf.get('socks5_port')
# conf_proxychains_for_aria2 = conf['proxychains_for_aria2']
# conf_ignore_ugoira = conf['ignore_ugoira'] # it is true
# _conf_nonh_id_except = set(conf.get('_nonh_id_except', ()))

for s in [conf_pix_path, conf_tmp_path, conf_thumb_path]:
    if not os.path.isdir(s):
        os.makedirs(s)

with uopen('aria2-tmpl.conf') as fp:
    aria2_conf_tmpl = fp.read()
if not aria2_conf_tmpl.endswith('\n'):
    aria2_conf_tmpl += '\n'
