import json
import os
import re
import uuid
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required
from pymongo import MongoClient
from bson import ObjectId
import redis

app = Flask(__name__)

# Konfiguracija JWT-a (Mora imati ISTI tajni ključ kao Auth servis)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-tajni-kljuc-promeni-ovo")
jwt = JWTManager(app)

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


@app.route('/create_buy_order', methods=['POST'])
@jwt_required()
def create_buy_order():
    data = request.get_json() or {}

    for field in ["name", "categories", "buying_price", "info"]:
        if field not in data or data[field] is None:
            return jsonify({"message": f"Field {field} is missing."}), 400
        if field == "name" and str(data[field]).strip() == "":
            return jsonify({"message": "Field name is missing."}), 400

    if not isinstance(data["categories"], list) or len(data["categories"]) == 0:
        return jsonify({"message": "Categories list is empty."}), 400

    try:
        buying_price = float(data["buying_price"])
        if buying_price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid buying price."}), 400


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
@jwt_required()
def create_sell_order():
    data = request.get_json() or {}


    for field in ["id", "selling_price"]:
        if field not in data or data[field] is None:
            return jsonify({"message": f"Field {field} is missing."}), 400
        if field == "id" and str(data[field]).strip() == "":
            return jsonify({"message": "Field id is missing."}), 400


    asset_id_str = data["id"]
    if not is_valid_object_id(asset_id_str):
        return jsonify({"message": "Invalid id."}), 400

    asset = assets_collection.find_one({"_id": ObjectId(asset_id_str)})
    if not asset:
        return jsonify({"message": "Invalid id."}), 400


    try:
        selling_price = float(data["selling_price"])
        if selling_price <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid selling price."}), 400


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
@jwt_required()
def search_assets():
    data = request.get_json() or {}
    query = {}


    if "name" in data and data["name"]:
        query["name"] = {"$regex": data["name"], "$options": "i"}  # Case-insensitive podstring

    if "category" in data and data["category"]:
        query["categories"] = data["category"]  # MongoDB automatski pretražuje unutar nizova

    if "buying_date" in data and data["buying_date"]:
        query["buying_date"] = {"$gt": data["buying_date"]}

    if "selling_date" in data and data["selling_date"]:
        query["selling_date"] = {"$lt": data["selling_date"]}

        # Specifikacija kaže: "Neprodate imovine ne treba uključiti u rezultat" kada je zadata selling_date
    elif "selling_date" in request.json:
        # Ako je korisnik poslao polje ali je prazno, ili želimo striktno prodate
        query["selling_date"] = {"$exists": True}

    # Obrada info_filters (Pretraga kroz ugnježdene objekte)
    if "info_filters" in data and isinstance(data["info_filters"], list):
        for f in data["info_filters"]:
            field_path = f"info.{f['field']}"  # Pretvaranje u dot-notation (npr. info.field0.field1)
            operator = f"${f['operator']}"  # npr. eq -> $eq
            value = f["value"]

            # Dodavanje filtera u query rečnik
            if field_path not in query:
                query[field_path] = {}
            query[field_path][operator] = value


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