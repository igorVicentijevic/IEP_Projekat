import json
import os
import uuid as uuid_module
from datetime import datetime
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required
from pymongo import MongoClient
from bson import ObjectId
import redis

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


@app.route('/pending_orders', methods=['GET'])
@jwt_required()
def pending_orders():
    orders = []
    keys = redis_client.keys("order:*")

    for key in keys:
        raw_data = redis_client.get(key)
        if raw_data:
            orders.append(json.loads(raw_data))

    return jsonify({"orders": orders}), 200


@app.route('/decision', methods=['POST'])
@jwt_required()
def decision():
    data = request.get_json() or {}

    if "uuid" not in data or str(data["uuid"]).strip() == "":
        return jsonify({"message": "Field uuid is missing."}), 400

    uuid_str = data["uuid"]

    try:
        uuid_module.UUID(str(uuid_str))
    except (ValueError, AttributeError, TypeError):
        return jsonify({"message": "Invalid uuid."}), 400

    redis_key = f"order:{uuid_str}"
    raw_order = redis_client.get(redis_key)
    if not raw_order:
        return jsonify({"message": "Invalid uuid."}), 400

    if "approved" not in data or data["approved"] is None:
        return jsonify({"message": "Field approved is missing."}), 400

    approved = data["approved"]

    if not isinstance(approved, bool):
        return jsonify({"message": "Invalid decision."}), 400

    order = json.loads(raw_order)

    if not approved:
        redis_client.delete(redis_key)
        return "", 200

    current_time_iso = datetime.utcnow().isoformat() + "Z"

    if order["order_type"] == "BUY":
        new_asset = {
            "name": order["name"],
            "categories": order["categories"],
            "buying_price": order["buying_price"],
            "buying_date": current_time_iso,
            "info": order["info"]
        }
        assets_collection.insert_one(new_asset)

    elif order["order_type"] == "SELL":
        asset_id = order["id"]
        assets_collection.update_one(
            {"_id": ObjectId(asset_id)},
            {
                "$set": {
                    "selling_price": order["selling_price"],
                    "selling_date": current_time_iso
                }
            }
        )

    redis_client.delete(redis_key)
    return "", 200


@app.route('/report', methods=['GET'])
@jwt_required()
def get_report():
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
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "spent": 1,
                "earned": 1
            }
        },
        {
            "$sort": {
                "earned": -1,
                "spent": 1,
                "category": 1
            }
        }
    ]

    report_data = list(assets_collection.aggregate(pipeline))

    return jsonify({"categories": report_data}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=int(os.environ.get("PORT", 5003)))