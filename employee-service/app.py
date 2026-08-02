import json
import os
import re
import uuid
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, get_jwt, jwt_required
from pymongo import MongoClient
from bson import ObjectId
import redis

app = Flask(__name__)

# Konfiguracija JWT-a (Mora imati ISTI tajni ključ kao Auth servis)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-tajni-kljuc")
jwt = JWTManager(app)
MAX_FIELD_LENGTH = 256
ALLOWED_INFO_FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}

# Inicijalizacija klijenata za baze podataka
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fond_db")

mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_mongo = mongo_client[MONGO_DB_NAME]
assets_collection = db_mongo["assets"]

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


def is_valid_object_id(id_str):
    return ObjectId.is_valid(id_str)


def is_missing_field(data, field_name):
    return field_name not in data or data[field_name] == ""


def is_valid_short_string(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= MAX_FIELD_LENGTH


def is_valid_positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def normalize_iso_datetime(value):
    if not isinstance(value, str) or len(value.strip()) == 0:
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if parsed.tzinfo else parsed.isoformat() + "Z"


def employee_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "employee":
            return jsonify({"msg": "Missing Authorization Header"}), 401
        return fn(*args, **kwargs)

    return wrapper


@app.route('/create_buy_order', methods=['POST'])
@employee_required
def create_buy_order():
    data = request.get_json() or {}

    if is_missing_field(data, "name"):
        return jsonify({"message": "Field name is missing."}), 400
    if not isinstance(data["name"], str) or len(data["name"]) > MAX_FIELD_LENGTH:
        return jsonify({"message": "Field name is missing."}), 400

    for field in ["categories", "buying_price", "info"]:
        if field not in data or data[field] is None:
            return jsonify({"message": f"Field {field} is missing."}), 400

    if not isinstance(data["categories"], list):
        return jsonify({"message": "Field categories is missing."}), 400

    if not isinstance(data["info"], dict):
        return jsonify({"message": "Field info is missing."}), 400

    if len(data["categories"]) == 0:
        return jsonify({"message": "Categories list is empty."}), 400

    if not is_valid_positive_number(data["buying_price"]):
        return jsonify({"message": "Invalid buying price."}), 400
    buying_price = float(data["buying_price"])

    order_id = str(uuid.uuid4())
    order_data = {
        "uuid": order_id,
        "order_type": "BUY",
        "name": data["name"],
        "categories": data["categories"],
        "buying_price": buying_price,
        "info": data["info"]
    }

    redis_client.set(f"order:{order_id}", json.dumps(order_data))
    return "", 200



@app.route('/create_sell_order', methods=['POST'])
@employee_required
def create_sell_order():
    data = request.get_json() or {}

    if is_missing_field(data, "id"):
        return jsonify({"message": "Field id is missing."}), 400
    asset_id_str = data["id"]
    if not is_valid_object_id(asset_id_str):
        return jsonify({"message": "Invalid id."}), 400

    asset = assets_collection.find_one({"_id": ObjectId(asset_id_str)})
    if not asset:
        return jsonify({"message": "Invalid id."}), 400

    if "selling_price" not in data or data["selling_price"] is None:
        return jsonify({"message": "Field selling_price is missing."}), 400

    if not is_valid_positive_number(data["selling_price"]):
        return jsonify({"message": "Invalid selling price."}), 400
    selling_price = float(data["selling_price"])

    order_id = str(uuid.uuid4())
    order_data = {
        "uuid": order_id,
        "order_type": "SELL",
        "id": asset_id_str,
        "selling_price": selling_price
    }

    redis_client.set(f"order:{order_id}", json.dumps(order_data))
    return "", 200



@app.route('/search', methods=['POST'])
@employee_required
def search_assets():
    data = request.get_json() or {}
    query = {}


    if is_valid_short_string(data.get("name")):
        query["name"] = {"$regex": re.escape(data["name"]), "$options": "i"}

    if is_valid_short_string(data.get("category")):
        query["categories"] = data["category"]

    buying_date = normalize_iso_datetime(data.get("buying_date"))
    if buying_date:
        query["buying_date"] = {"$gt": buying_date}

    selling_date = normalize_iso_datetime(data.get("selling_date"))
    if selling_date:
        query["selling_date"] = {"$lt": selling_date}

    elif "selling_date" in data:
        query["selling_date"] = {"$exists": True}

    if "info_filters" in data and isinstance(data["info_filters"], list):
        for f in data["info_filters"]:
            if not isinstance(f, dict):
                continue

            field = f.get("field")
            operator = f.get("operator")
            if not is_valid_short_string(field) or not isinstance(operator, str) or operator not in ALLOWED_INFO_FILTER_OPERATORS or "value" not in f:
                continue

            field_path = f"info.{field}"
            if field_path not in query:
                query[field_path] = {}
            query[field_path][f"${operator}"] = f["value"]


    assets = assets_collection.find(query)
    result = []

    for a in assets:
        asset_obj = {
            "id": str(a["_id"]),
            "name": a["name"],
            "categories": a["categories"],
            "buying_date": a["buying_date"],
            "buying_price": a["buying_price"],
            "info": a.get("info", {})
        }

        # Polja vezana za prodaju se dodaju samo ako imovina ima definisanu prodaju
        if "selling_date" in a:
            asset_obj["selling_date"] = a["selling_date"]
            asset_obj["selling_price"] = a["selling_price"]

        result.append(asset_obj)

    return jsonify({"assets": result}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=int(os.environ.get("PORT", 5002)))