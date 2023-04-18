import json
import logging

from Key import Key
from flask_cors import CORS
from flask import Flask, request, render_template, make_response, jsonify
from bingX.perpetual.v1 import Perpetual
from Service import PerpetualService
from flask_socketio import SocketIO, emit
from Cache import Cache


class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('logs', log_entry)


app = Flask(__name__, static_folder=f'./webapp/dist/')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logger = logging.getLogger('BingXBot')
socketio_handler = SocketIOHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
socketio_handler.setFormatter(formatter)
socketio_handler.setLevel(logging.INFO)
logger.addHandler(socketio_handler)


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


@app.route('/keys', methods=['POST'])
def set_keys():
    firstTime = Key.public_key == "" or Key.secret_key == ""
    data = json.loads(request.data)
    Key.public_key = data['public']
    Key.secret_key = data['private']
    logger.info(f'API Keys were successfully {"added" if firstTime else "updated"}')
    response = make_response(jsonify({'status': 'SUCCESS'}))
    response.headers['Content-Type'] = "application/json"

    return response, 200


@app.route('/perpetual/trade', methods=['POST'])
def perpetual_order():
    client = Perpetual(Key.public_key, Key.secret_key)
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
    client = Perpetual(Key.public_key, Key.secret_key)
    data = json.loads(request.data)
    service = PerpetualService(client=client,
                               symbol=data['symbol'],
                               leverage=data['leverage'])
    service.set_leverage()
    return f'{{"symbol":"{service.symbol}", "leverage":"{service.leverage}"}}'


@app.route('/logs', methods=['GET'])
def get_logs():
    with open('logs.log', 'r') as f:
        logs = f.read()
    return logs


if __name__ == '__main__':
    from waitress import serve

    socketio.run(app)
    serve(app, host='0.0.0.0', port=3000)
