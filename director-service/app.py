import json
import os
import threading
import time
import uuid as uuid_module
from datetime import datetime
from functools import wraps

import redis
from bson import ObjectId
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, get_jwt, jwt_required
from pymongo import MongoClient
from web3 import Web3
from web3.exceptions import Web3Exception

from contract_loader import load_voting_contract_artifact

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-tajni-kljuc")
jwt = JWTManager(app)

MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fond_db")

mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_mongo = mongo_client[MONGO_DB_NAME]
assets_collection = db_mongo["assets"]

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

BLOCKCHAIN_HOST = os.environ.get("BLOCKCHAIN_HOST", "localhost")
BLOCKCHAIN_RPC_PORT = int(os.environ.get("BLOCKCHAIN_RPC_PORT", "8545"))
web3 = Web3(Web3.HTTPProvider(f"http://{BLOCKCHAIN_HOST}:{BLOCKCHAIN_RPC_PORT}"))
VOTING_POLL_INTERVAL_SECONDS = float(os.environ.get("VOTING_POLL_INTERVAL_SECONDS", "1"))
VOTING_CONTRACT_ABI, VOTING_CONTRACT_BYTECODE = load_voting_contract_artifact()


def _parse_uuid(uuid_value):
    try:
        uuid_module.UUID(str(uuid_value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _now_iso():
    return datetime.utcnow().isoformat() + "Z"


def _apply_approved_order(order):
    current_time_iso = _now_iso()

    if order["order_type"] == "BUY":
        new_asset = {
            "name": order["name"],
            "categories": order["categories"],
            "buying_price": order["buying_price"],
            "buying_date": current_time_iso,
            "info": order["info"]
        }
        assets_collection.insert_one(new_asset)
        return

    if order["order_type"] == "SELL":
        assets_collection.update_one(
            {"_id": ObjectId(order["id"])},
            {"$set": {"selling_price": order["selling_price"], "selling_date": current_time_iso}}
        )


def _process_finished_voting():
    voting_keys = redis_client.keys("voting:*")
    for voting_key in voting_keys:
        raw_voting_data = redis_client.get(voting_key)
        if not raw_voting_data:
            redis_client.delete(voting_key)
            continue

        voting_data = json.loads(raw_voting_data)
        contract_address = voting_data["contract_address"]
        order_uuid = voting_data["uuid"]

        contract = web3.eth.contract(
            address=web3.to_checksum_address(contract_address),
            abi=VOTING_CONTRACT_ABI
        )

        ended, approved, _, _, _ = contract.functions.getStatus().call()
        if not ended:
            continue

        redis_order_key = f"order:{order_uuid}"
        raw_order_data = redis_client.get(redis_order_key)
        if raw_order_data:
            order_data = json.loads(raw_order_data)
            if approved:
                _apply_approved_order(order_data)
            redis_client.delete(redis_order_key)

        redis_client.delete(voting_key)


def _voting_worker():
    while True:
        try:
            _process_finished_voting()
        except Exception:
            pass
        time.sleep(VOTING_POLL_INTERVAL_SECONDS)


def start_background_workers():
    voting_thread = threading.Thread(target=_voting_worker, name="voting-worker", daemon=True)
    voting_thread.start()


def director_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "director":
            return jsonify({"msg": "Missing Authorization Header"}), 401
        return fn(*args, **kwargs)

    return wrapper


@app.route('/pending_orders', methods=['GET'])
@director_required
def pending_orders():
    _process_finished_voting()

    orders = []
    for order_key in redis_client.keys("order:*"):
        raw_order = redis_client.get(order_key)
        if not raw_order:
            continue

        order = json.loads(raw_order)
        if redis_client.exists(f"voting:{order['uuid']}"):
            continue
        orders.append(order)

    return jsonify({"orders": orders}), 200


@app.route('/decision', methods=['POST'])
@director_required
def decision():
    _process_finished_voting()

    if not web3.is_connected():
        return jsonify({"message": "Blockchain is unavailable."}), 500

    data = request.get_json() or {}

    if "uuid" not in data or str(data["uuid"]).strip() == "":
        return jsonify({"message": "Field uuid is missing."}), 400

    uuid_str = data["uuid"]
    if not _parse_uuid(uuid_str):
        return jsonify({"message": "Invalid uuid."}), 400

    order_key = f"order:{uuid_str}"
    raw_order = redis_client.get(order_key)
    if not raw_order or redis_client.exists(f"voting:{uuid_str}"):
        return jsonify({"message": "Invalid uuid."}), 400

    if "voters" not in data or not isinstance(data["voters"], list) or len(data["voters"]) == 0:
        return jsonify({"message": "Field voters is missing."}), 400

    checksum_voters = []
    seen_voters = set()
    for voter in data["voters"]:
        if not isinstance(voter, str) or not web3.is_address(voter):
            return jsonify({"message": "Invalid voter address."}), 400
        checksum_voter = web3.to_checksum_address(voter)
        if checksum_voter in seen_voters:
            return jsonify({"message": "Invalid voter address."}), 400
        seen_voters.add(checksum_voter)
        checksum_voters.append(checksum_voter)

    if len(checksum_voters) % 2 == 0:
        return jsonify({"message": "Even number of voters."}), 400

    try:
        deployer_address = web3.eth.accounts[0]
        contract_factory = web3.eth.contract(abi=VOTING_CONTRACT_ABI, bytecode=VOTING_CONTRACT_BYTECODE)
        deployment_tx_hash = contract_factory.constructor(checksum_voters).transact({"from": deployer_address})
        deployment_receipt = web3.eth.wait_for_transaction_receipt(deployment_tx_hash)
    except (IndexError, ValueError, Web3Exception):
        return jsonify({"message": "Blockchain is unavailable."}), 500

    contract_address = deployment_receipt.contractAddress
    contract = web3.eth.contract(address=contract_address, abi=VOTING_CONTRACT_ABI)

    redis_client.set(
        f"voting:{uuid_str}",
        json.dumps({"uuid": uuid_str, "contract_address": contract_address, "voters": checksum_voters})
    )

    approve_transaction = {
        "to": contract_address,
        "data": contract.encode_abi("voteApprove", args=[]),
        "value": "0x0"
    }
    reject_transaction = {
        "to": contract_address,
        "data": contract.encode_abi("voteReject", args=[]),
        "value": "0x0"
    }

    return jsonify({
        "approve_transaction": approve_transaction,
        "reject_transaction": reject_transaction
    }), 200


@app.route('/report', methods=['GET'])
@director_required
def get_report():
    _process_finished_voting()

    pipeline = [
        {"$unwind": "$categories"},
        {
            "$group": {
                "_id": "$categories",
                "spent": {"$sum": "$buying_price"},
                "earned": {
                    "$sum": {
                        "$cond": [
                            {"$ifNull": ["$selling_date", False]},
                            "$selling_price",
                            0
                        ]
                    }
                }
            }
        },
        {"$project": {"_id": 0, "category": "$_id", "spent": 1, "earned": 1}},
        {"$sort": {"earned": -1, "spent": 1, "category": 1}}
    ]

    report_data = list(assets_collection.aggregate(pipeline))
    return jsonify({"statistics": report_data}), 200


if __name__ == '__main__':
    start_background_workers()
    app.run(host="0.0.0.0", debug=True, port=int(os.environ.get("PORT", 5003)), use_reloader=False)