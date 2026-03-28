from flask import Flask, send_file, make_response, send_from_directory, Response
from pathlib import Path
import requests as req

app = Flask(__name__)
SITE    = Path('/home/ubuntu/rizzi-cms/static/site')
UPLOADS = Path('/home/ubuntu/rizzi-cms/uploads')

@app.route('/')
@app.route('/site')
@app.route('/site/')
def index():
    resp = make_response(send_file(SITE / 'index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/site/<path:f>')
def static_files(f):
    return send_from_directory(SITE, f)

@app.route('/uploads/<path:f>')
def uploads(f):
    return send_from_directory(UPLOADS, f)

@app.route('/api/projects')
def api_projects():
    r = req.get('http://localhost:5151/api/projects')
    return Response(r.content, content_type='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=False)
