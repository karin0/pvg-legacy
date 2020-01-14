import os, sys, webbrowser

os.chdir(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.getcwd() + '/vendor')

from waitress import serve

from pvg.env import conf
from pvg.app import app

host = conf.get('host', '127.0.0.1')
port = int(conf.get('port', 5000))
threads = int(conf.get('waitress_threads', 6))

webbrowser.open(f'http://127.0.0.1:{port}')
serve(app, host=host, port=port, threads=threads)

# os.environ['FLASK_ENV'] = 'development'
# app.run(host='0.0.0.0', port='5000', debug=True, use_reloader=False)
