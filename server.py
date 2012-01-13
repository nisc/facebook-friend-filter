#!/usr/bin/python
"""Backend for Friend Filter"""

# monkey patch the whole stupid thing (it works)
from gevent import monkey; monkey.patch_all()
from gevent.pywsgi import WSGIServer
import werkzeug.serving

import logging
logging.basicConfig(level=logging.INFO)
import os
import facebook as fb
import friends

from flask import Flask, request, jsonify, send_file, abort
app = Flask(__name__)

def call_backend(token, params):
    info = friends.get_friends_info(token)
    uids = friends.filter_friends(info, **params)
    if len(uids) < 1:
        return None
    else:
        list_name = params.get('list_name', 'Default')
        return friends.create_friends_list(list_name, uids, token)

@app.errorhandler(404)
def page_not_found(error):
    resp = jsonify({'status':'err', 'msg':'not found'})
    resp.status_code = 404
    return resp

@app.route('/create', methods=['POST', 'GET'])
def create():
    try:
        token = fb.get_user_from_cookie(
                    request.cookies,
                    os.environ['APP_ID'],
                    os.environ['APP_SECRET'])['access_token']
        if not request.form:
            raise Exception('No post data')
    except:
        # Use more 402!
        resp = jsonify({'status':'err', 'msg':'I want (a) a Facebook cookie '
            +'and (b) a lot of POST data. Deliver!'})
        resp.status_code = 402
        return resp

    try:
        list_id = call_backend(token, request.form.to_dict())
        if list_id:
            return jsonify({'status':'ok', 'list_id': list_id})
        else:
            resp = jsonify({'status':'err', 'msg':'No matches!'})
            resp.status_code = 402
            return resp
    except Exception as e: # to the unit tests, please
        logging.error(e)
        resp = jsonify({'status':'err'})
        resp.status_code = 500
        return resp

@app.route('/')
@app.route('/<path:filename>', methods=['GET'])
def static_hack(filename='index.html'):
    try:
        return send_file('static/'+filename)
    except:
        abort(404)

@werkzeug.serving.run_with_reloader
def runServer():
    port = int(os.environ.get('PORT', 5000))
    WSGIServer(('', port), app).serve_forever()
