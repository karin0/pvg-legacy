import os, sys, webbrowser

print('Starting local server..')

os.chdir(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.getcwd())
sys.path.append(os.getcwd() + '/vendor')

from waitress import serve

from pvg.env import conf
from pvg.app import app

host = conf.get('host', '127.0.0.1')
port = int(conf.get('port', 5678))
threads = conf.get('waitress_threads')
if threads:
    threads = int(threads)
else:
    from multiprocessing import cpu_count
    threads = max(6, cpu_count())
print('on', host, port)
print('using', threads, 'threads')

url = f'http://127.0.0.1:{port}'
print('Open or refresh', url, 'after "Serving on ..." is prompted...')
webbrowser.open(url)
serve(app, host=host, port=port, threads=threads)

# os.environ['FLASK_ENV'] = 'development'
# app.run(host='0.0.0.0', port='5000', debug=True, use_reloader=False)
