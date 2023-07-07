import json
import logging
import eventlet
from eventlet import wsgi
from eventlet.green import socket
from Key import Key
from flask_cors import CORS
from flask import Flask, request, render_template, make_response, jsonify, g
from bingX.perpetual.v1 import Perpetual
from Service import PerpetualService
from flask_socketio import SocketIO, emit
from Cache import Cache


class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('logs', log_entry)


app = Flask(__name__, static_folder='./webapp/dist/')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logger = logging.getLogger('BingXBot')
socketio_handler = SocketIOHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
socketio_handler.setFormatter(formatter)
socketio_handler.setLevel(logging.INFO)
logger.addHandler(socketio_handler)


def get_client():
    if 'client' not in g:
        g.client = Perpetual(Key.public_key, Key.secret_key)

    return g.client


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    with open('logs.log', 'r') as f:
        logs = f.read()
    emit('logs', logs)


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('logs')
def handle_logs():
    print('Client Logging')
    with open('logs.log', 'r') as f:
        logs = f.readlines()[-1]
    emit('logs', logs)


@socketio.on('message')
def handle_message(data):
    print('Received message:', data)
    socketio.emit('response', 'Server response')


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/assets/<path:path>')
def send_assets(path):
    return app.send_static_file(f'assets/{path}')


@app.route('/user', methods=['GET'])
def get_key_status():
    firstTime = Key.public_key == "" or Key.secret_key == ""
    user = 'NEW_USER' if firstTime else 'CURRENT_USER'
    response = make_response(jsonify({'user': user}))
    response.headers['Content-Type'] = "application/json"

    return response, 200


@app.route('/keys', methods=['POST'])
def set_keys():
    firstTime = Key.public_key == "" or Key.secret_key == ""
    data = json.loads(request.data)
    if not firstTime:
        if data['private_current'] != Key.secret_key:
            response = make_response(jsonify({'status': 'WRONG_PRIVATE_KEY'}))
            response.headers['Content-Type'] = "application/json"
            logger.info(f'API Keys were not updated. Wrong Private Key.')

            return response, 403

    Key.public_key = data['public']
    Key.secret_key = data['private']
    logger.info(f'API Keys were successfully {"added" if firstTime else "updated"}')
    response = make_response(jsonify({'status': 'SUCCESS'}))
    response.headers['Content-Type'] = "application/json"

    return response, 200


@app.route('/perpetual/trade', methods=['POST'])
def perpetual_order():
    client = get_client()
    data = json.loads(request.data)
    service = PerpetualService(client=client,
                               symbol=data['symbol'],
                               side=data['side'],
                               action=data['action'],
                               quantity=data['quantity'],
                               trade_type=data['trade_type'],
                               leverage=data['leverage'] if 'leverage' in data else 1)
    if data['action'] == 'Open':
        return service.open_trade()
    if data['action'] == 'Close':
        return service.close_trade()


@app.route('/perpetual/dump', methods=['POST'])
def clear_cache():
    Cache.clear_cache()
    return 'CACHE CLEARED'


@app.route('/perpetual/leverage', methods=['POST'])
def change_leverage():
    client = get_client()
    data = json.loads(request.data)
    service = PerpetualService(client=client,
                               symbol=data['symbol'],
                               leverage=data['leverage'])
    service.set_leverage()
    return f'{{"symbol":"{service.symbol}", "leverage":"{service.leverage}"}}'


@app.route('/perpetual/positions', methods=['POST'])
def get_open_positions():
    client = get_client()
    data = json.loads(request.data)
    service = PerpetualService(client=client,
                               symbol=data['symbol'])
    response = service.get_open_positions_api()
    return response


@app.route('/logs', methods=['GET'])
def get_logs():
    with open('logs.log', 'r') as f:
        logs = f.read()
    return logs


@app.route('/logs', methods=['DELETE'])
def delete_logs():
    with open('logs.log', 'w') as f:
        f.close()
    return {'status': 'DELETED'}


if __name__ == '__main__':
    eventlet.monkey_patch(all=True)
    server = eventlet.listen(('0.0.0.0', 3000))
    wsgi.server(server, app)
