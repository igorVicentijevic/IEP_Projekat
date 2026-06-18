import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required
from pymongo import MongoClient
from bson import ObjectId
import redis

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "super-tajni-kljuc-promeni-ovo"
jwt = JWTManager(app)

mongo_client = MongoClient("mongodb://localhost:27017/")
db_mongo = mongo_client["fond_db"]
assets_collection = db_mongo["assets"]

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)



@app.route('/pending_orders', methods=['GET'])
@jwt_required()
def pending_orders():
    orders = []

    #Dohvati sve kljuceve u redisu koji pocinju sa order
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

    #proveravamo da li postoje polja
    for field in ["uuid", "approved"]:
        if field not in data or data[field] is None:
            return jsonify({"message": f"Field {field} is missing."}), 400
        if field == "uuid" and str(data[field]).strip() == "":
            return jsonify({"message": "Field uuid is missing."}), 400

    uuid_str = data["uuid"]
    approved = data["approved"]

    #proveravamo da li je polje approved tipa bool
    if not isinstance(approved, bool):
        return jsonify({"message": "Invalid decision."}), 400

    #proveravamo da li postoji order sa poslatim uuid
    redis_key = f"order:{uuid_str}"
    raw_order = redis_client.get(redis_key)
    if not raw_order:
        return jsonify({"message": "Invalid uuid."}), 400

    order = json.loads(raw_order)

    # Ako je odbijen zahtev, brisemo ga
    if not approved:
        redis_client.delete(redis_key)
        return "", 200

    # Ako je odobren, dalja obrada zavisi od BUY ili SELL
    current_time_iso = datetime.utcnow().isoformat() + "Z"

    if order["order_type"] == "BUY":
        # Ako je BUY ubacujemo u bazu
        new_asset = {
            "name": order["name"],
            "categories": order["categories"],
            "buying_price": order["buying_price"],
            "buying_date": current_time_iso,
            "info": order["info"]
        }
        assets_collection.insert_one(new_asset)

    elif order["order_type"] == "SELL":
        # Ako je sel azuriramo postojeci dokument u bazi i azuriramo polja vezana za prodaju
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

    #Nakon sto smo obradili zahtev brisemo ga iz redisa
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
                "spent": {"$sum": "$buying_price"},  # Sabiramo sve kupovne cene u toj kategoriji
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
                "earned": -1,  # Opadajuće
                "spent": 1,  # Rastuće
                "category": 1  # Rastuće (alfabetski)
            }
        }
    ]

    report_data = list(assets_collection.aggregate(pipeline))

    return jsonify({"categories": report_data}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5003)