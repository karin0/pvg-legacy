import os

from app import app

os.environ['FLASK_ENV'] = 'development'

app.run(host='0.0.0.0', port='5000', debug=True, use_reloader=False)
