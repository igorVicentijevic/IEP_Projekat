import os

from flask import Flask, jsonify
from pymongo import MongoClient

app = Flask(__name__)


MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fond_db")

mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_mongo = mongo_client[MONGO_DB_NAME]
assets_collection = db_mongo["assets"]


@app.route('/get_all', methods=['GET'])
def get_all_assets():
    query = {}
    assets = assets_collection.find(query)
    results = []
    for a in assets:
        asset_obj = {
            "id": str(a["_id"]),
            "name": a["name"],
            "categories": a["categories"],
            "buying_date": a["buying_date"],
            "buying_price": a["buying_price"],
            "info": a.get("info", {})
        }
        results.append(asset_obj)
    return jsonify({"assets": results}), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=int(os.environ.get("PORT", 5200)))