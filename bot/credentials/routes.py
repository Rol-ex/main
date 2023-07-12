import json
import os

from .. import logger
from ..utils.credentials import Credentials
from ..credentials import bp
from flask import make_response, jsonify, request, g
from ..db import mongo, store_user_credentials

db = mongo.db[os.environ['COLLECTION_NAME']]


@bp.before_request
def find_user_credentials():
    store_user_credentials()


@bp.route('/credentials/<exchange>/status', methods=['GET'])
def get_credential_status(exchange: str):
    credentials = get_credentials(exchange)
    is_first_login = credentials.public_key == '' and credentials.private_key == ''
    user = 'NEW_USER' if is_first_login else 'CURRENT_USER'
    response = make_response(jsonify({'user': user}))
    response.headers['Content-Type'] = "application/json"
    return exchange, 200


@bp.route('/credentials/<exchange>', methods=['POST'])
def post_credentials(exchange: str):
    data = json.loads(request.data)
    new_credentials = Credentials(data['public_key'], data['private_key'], data['exchange'])
    credentials = get_credentials(exchange)
    is_first_login = credentials.public_key == '' and credentials.private_key == ''
    is_wrong_private_key = data['private_key_current'] != credentials.private_key
    is_blank_credential = credentials.public_key == '' or credentials.private_key == ''

    if is_wrong_private_key and not is_first_login:
        response = make_response(jsonify({'status': 'WRONG_PRIVATE_KEY'}))
        response.headers['Content-Type'] = "application/json"
        logger.info(f'API Keys were not updated. Wrong Private Key.')

        return response, 403

    if is_blank_credential and not is_first_login:
        response = make_response(jsonify({'status': 'NO_EMPTY_KEYS'}))
        response.headers['Content-Type'] = "application/json"
        logger.info(f'API Keys were not updated. Empty keys are not allowed.')

        return response, 403

    update_credentials(new_credentials)
    logger.info(f'API Keys were successfully {"added" if is_first_login else "updated"}')
    response = make_response(jsonify({'status': 'SUCCESS'}))
    response.headers['Content-Type'] = "application/json"

    return response, 200


def get_credentials(exchange: str):
    credentials = next((credential for credential in g.user_credentials if credential.exchange == exchange), None)
    if credentials is not None:
        return credentials
    else:
        return create_new_empty_credentials(exchange)


def create_new_empty_credentials(exchange: str):
    _credentials = Credentials('', '', exchange)
    create_credentials(_credentials)
    return _credentials


def update_credentials(credentials: Credentials):
    new_keys = {"$set": {
        "public_key": credentials.public_key,
        "private_key": credentials.private_key
    }}
    db.update_one({"exchange": credentials.exchange}, new_keys)


def create_credentials(credentials: Credentials):
    db.insert_one({"exchange": credentials.exchange,
                   "public_key": credentials.public_key,
                   "private_key": credentials.private_key
                   })
