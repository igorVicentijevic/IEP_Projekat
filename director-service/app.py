import json
import os
import uuid as uuid_module
from datetime import datetime

import redis
from bson import ObjectId
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, jwt_required
from pymongo import MongoClient
from web3 import Web3
from web3.exceptions import Web3Exception

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-tajni-kljuc-promeni-ovo")
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

VOTING_CONTRACT_ABI = [
    {"inputs": [{"internalType": "address[]", "name": "voters", "type": "address[]"}], "stateMutability": "nonpayable", "type": "constructor"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "allowedVoters", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "approveCount", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "approved", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "ended", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getStatus", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}, {"internalType": "bool", "name": "", "type": "bool"}, {"internalType": "uint256", "name": "", "type": "uint256"}, {"internalType": "uint256", "name": "", "type": "uint256"}, {"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "", "type": "address"}], "name": "hasVoted", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "majority", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "rejectCount", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "voteApprove", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "voteReject", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

VOTING_CONTRACT_BYTECODE = "60806040523480156200001157600080fd5b506040516200106a3803806200106a833981810160405281019062000037919062000387565b6000815190506000811162000083576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016200007a9062000439565b60405180910390fd5b600160028262000094919062000494565b14620000d7576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401620000ce906200051c565b60405180910390fd5b6001600282620000e891906200056d565b620000f49190620005a5565b60048190555060005b8181101562000190576001600080858481518110620001215762000120620005e0565b5b602002602001015173ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff021916908315150217905550808062000187906200060f565b915050620000fd565b5050506200065c565b6000604051905090565b600080fd5b600080fd5b600080fd5b6000601f19601f8301169050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b620001fd82620001b2565b810181811067ffffffffffffffff821117156200021f576200021e620001c3565b5b80604052505050565b60006200023462000199565b9050620002428282620001f2565b919050565b600067ffffffffffffffff821115620002655762000264620001c3565b5b602082029050602081019050919050565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b6000620002a8826200027b565b9050919050565b620002ba816200029b565b8114620002c657600080fd5b50565b600081519050620002da81620002af565b92915050565b6000620002f7620002f18462000247565b62000228565b905080838252602082019050602084028301858111156200031d576200031c62000276565b5b835b818110156200034a5780620003358882620002c9565b8452602084019350506020810190506200031f565b5050509392505050565b600082601f8301126200036c576200036b620001ad565b5b81516200037e848260208601620002e0565b91505092915050565b600060208284031215620003a0576200039f620001a3565b5b600082015167ffffffffffffffff811115620003c157620003c0620001a8565b5b620003cf8482850162000354565b91505092915050565b600082825260208201905092915050565b7f4e6f20766f746572732e00000000000000000000000000000000000000000000600082015250565b600062000421600a83620003d8565b91506200042e82620003e9565b602082019050919050565b60006020820190508181036000830152620004548162000412565b9050919050565b6000819050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601260045260246000fd5b6000620004a1826200045b565b9150620004ae836200045b565b925082620004c157620004c062000465565b5b828206905092915050565b7f4576656e206e756d626572206f6620766f746572732e00000000000000000000600082015250565b600062000504601683620003d8565b91506200051182620004cc565b602082019050919050565b600060208201905081810360008301526200053781620004f5565b9050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b60006200057a826200045b565b915062000587836200045b565b9250826200059a576200059962000465565b5b828204905092915050565b6000620005b2826200045b565b9150620005bf836200045b565b9250828201905080821115620005da57620005d96200053e565b5b92915050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052603260045260246000fd5b60006200061c826200045b565b91507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff82036200065157620006506200053e565b5b600182019050919050565b6109fe806200066c6000396000f3fe608060405234801561001057600080fd5b506004361061009e5760003560e01c80634e69d560116100665780634e69d5601461014957806356c2a0a11461016b5780639fe7717d14610175578063b6e54bdf14610193578063fb6ff96e146101b15761009e565b806309eef43e146100a357806312fa6feb146100d357806319d40b08146100f15780631baf0f1e1461010f578063255adfd414610119575b600080fd5b6100bd60048036038101906100b89190610726565b6101cf565b6040516100ca919061076e565b60405180910390f35b6100db6101ef565b6040516100e8919061076e565b60405180910390f35b6100f9610202565b604051610106919061076e565b60405180910390f35b610117610215565b005b610133600480360381019061012e9190610726565b610432565b604051610140919061076e565b60405180910390f35b610151610452565b6040516101629594939291906107a2565b60405180910390f35b610173610494565b005b61017d6106b1565b60405161018a91906107f5565b60405180910390f35b61019b6106b7565b6040516101a891906107f5565b60405180910390f35b6101b96106bd565b6040516101c691906107f5565b60405180910390f35b60016020528060005260406000206000915054906101000a900460ff1681565b600560009054906101000a900460ff1681565b600560019054906101000a900460ff1681565b6000803373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff166102a0576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016102979061086d565b60405180910390fd5b600560009054906101000a900460ff16156102f0576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016102e7906108d9565b60405180910390fd5b600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff161561037d576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161037490610945565b60405180910390fd5b60018060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055506001600260008282546103e79190610994565b9250508190555060045460025410610430576001600560006101000a81548160ff0219169083151502179055506001600560016101000a81548160ff0219169083151502179055505b565b60006020528060005260406000206000915054906101000a900460ff1681565b6000806000806000600560009054906101000a900460ff16600560019054906101000a900460ff16600254600354600454945094509450945094509091929394565b6000803373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff1661051f576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016105169061086d565b60405180910390fd5b600560009054906101000a900460ff161561056f576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610566906108d9565b60405180910390fd5b600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900460ff16156105fc576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016105f390610945565b60405180910390fd5b60018060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548160ff0219169083151502179055506001600360008282546106669190610994565b92505081905550600454600354106106af576001600560006101000a81548160ff0219169083151502179055506000600560016101000a81548160ff0219169083151502179055505b565b60025481565b60045481565b60035481565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006106f3826106c8565b9050919050565b610703816106e8565b811461070e57600080fd5b50565b600081359050610720816106fa565b92915050565b60006020828403121561073c5761073b6106c3565b5b600061074a84828501610711565b91505092915050565b60008115159050919050565b61076881610753565b82525050565b6000602082019050610783600083018461075f565b92915050565b6000819050919050565b61079c81610789565b82525050565b600060a0820190506107b7600083018861075f565b6107c4602083018761075f565b6107d16040830186610793565b6107de6060830185610793565b6107eb6080830184610793565b9695505050505050565b600060208201905061080a6000830184610793565b92915050565b600082825260208201905092915050565b7f496e76616c696420616464726573732e00000000000000000000000000000000600082015250565b6000610857601083610810565b915061086282610821565b602082019050919050565b600060208201905081810360008301526108868161084a565b9050919050565b7f566f74696e6720656e6465642e00000000000000000000000000000000000000600082015250565b60006108c3600d83610810565b91506108ce8261088d565b602082019050919050565b600060208201905081810360008301526108f2816108b6565b9050919050565b7f416c726561647920766f7465642e000000000000000000000000000000000000600082015250565b600061092f600e83610810565b915061093a826108f9565b602082019050919050565b6000602082019050818103600083015261095e81610922565b9050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b600061099f82610789565b91506109aa83610789565b92508282019050808211156109c2576109c1610965565b5b9291505056fea2646970667358221220ae2032a7f81375e43ac28c3a26630697b0643efc2d2db8a6fee57d463b6f701b64736f6c63430008130033"


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


@app.route('/pending_orders', methods=['GET'])
@jwt_required()
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
@jwt_required()
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
    for voter in data["voters"]:
        if not isinstance(voter, str) or not web3.is_address(voter):
            return jsonify({"message": "Invalid voter address."}), 400
        checksum_voters.append(web3.to_checksum_address(voter))

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
@jwt_required()
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
    app.run(host="0.0.0.0", debug=True, port=int(os.environ.get("PORT", 5003)))