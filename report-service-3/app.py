import os

from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)


MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fond_db")

mongo_client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
db_mongo = mongo_client[MONGO_DB_NAME]
assets_collection = db_mongo["assets"]

DEFAULT_LIMIT = 10
MAX_LIMIT = 100

# Imovina koja je prodata ima popunjen "selling_date".
SOLD_CONDITION = {"$ne": [{"$ifNull": ["$selling_date", None]}, None]}

PROFIT_EXPRESSION = {
    "$cond": [
        SOLD_CONDITION,
        {"$subtract": [{"$ifNull": ["$selling_price", 0]}, "$buying_price"]},
        0
    ]
}


def parse_positive_int(value, default, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def status_fields_stage():
    """$addFields sa izvedenim poljima koja koristi vise reportova.

    Datumi se u kolekciji cuvaju kao ISO stringovi, pa se konvertuju u
    prave datume kako bi datumski operatori mogli da se koriste.
    """
    return {
        "$addFields": {
            "is_sold": SOLD_CONDITION,
            "status": {"$cond": [SOLD_CONDITION, "SOLD", "HELD"]},
            "profit": PROFIT_EXPRESSION,
            "buying_date_parsed": {
                "$dateFromString": {
                    "dateString": {"$ifNull": ["$buying_date", None]},
                    "onError": None,
                    "onNull": None
                }
            },
            "selling_date_parsed": {
                "$dateFromString": {
                    "dateString": {"$ifNull": ["$selling_date", None]},
                    "onError": None,
                    "onNull": None
                }
            }
        }
    }


def run_pipeline(pipeline):
    return list(assets_collection.aggregate(pipeline))


@app.route('/aggregate/summary', methods=['GET'])
def aggregate_summary():
    """$facet: ukupne statistike, raspodela po statusu i najskuplja imovina."""
    pipeline = [
        status_fields_stage(),
        {
            "$facet": {
                "totals": [
                    {
                        "$group": {
                            "_id": None,
                            "assets": {"$sum": 1},
                            "spent": {"$sum": "$buying_price"},
                            "earned": {"$sum": {"$ifNull": ["$selling_price", 0]}},
                            "profit": {"$sum": "$profit"},
                            "average_buying_price": {"$avg": "$buying_price"},
                            "max_buying_price": {"$max": "$buying_price"},
                            "min_buying_price": {"$min": "$buying_price"}
                        }
                    },
                    {"$project": {"_id": 0}}
                ],
                "by_status": [
                    {"$sortByCount": "$status"},
                    {"$project": {"_id": 0, "status": "$_id", "assets": "$count"}}
                ],
                "most_expensive": [
                    {"$sort": {"buying_price": -1, "name": 1}},
                    {"$limit": 3},
                    {
                        "$project": {
                            "_id": 0,
                            "name": 1,
                            "categories": 1,
                            "buying_price": 1,
                            "status": 1
                        }
                    }
                ],
                "assets_count": [{"$count": "count"}]
            }
        },
        {
            "$replaceWith": {
                "totals": {
                    "$ifNull": [
                        {"$first": "$totals"},
                        {
                            "assets": 0,
                            "spent": 0,
                            "earned": 0,
                            "profit": 0,
                            "average_buying_price": None,
                            "max_buying_price": None,
                            "min_buying_price": None
                        }
                    ]
                },
                "by_status": "$by_status",
                "most_expensive": "$most_expensive",
                "assets_count": {"$ifNull": [{"$first": "$assets_count.count"}, 0]}
            }
        }
    ]

    result = run_pipeline(pipeline)
    return jsonify(result[0] if result else {}), 200


@app.route('/aggregate/by_category', methods=['GET'])
def aggregate_by_category():
    """$unwind + $group po kategorijama, sa paginacijom ($skip/$limit)."""
    skip = parse_positive_int(request.args.get("skip"), 0)
    limit = parse_positive_int(request.args.get("limit"), DEFAULT_LIMIT, MAX_LIMIT)

    pipeline = [
        status_fields_stage(),
        {"$unwind": "$categories"},
        {
            "$group": {
                "_id": "$categories",
                "assets": {"$sum": 1},
                "sold": {"$sum": {"$cond": ["$is_sold", 1, 0]}},
                "spent": {"$sum": "$buying_price"},
                "earned": {"$sum": {"$ifNull": ["$selling_price", 0]}},
                "profit": {"$sum": "$profit"},
                "average_buying_price": {"$avg": "$buying_price"}
            }
        },
        {
            "$addFields": {
                "held": {"$subtract": ["$assets", "$sold"]},
                "roi_percent": {
                    "$cond": [
                        {"$gt": ["$spent", 0]},
                        {"$round": [{"$multiply": [{"$divide": ["$profit", "$spent"]}, 100]}, 2]},
                        None
                    ]
                }
            }
        },
        {"$sort": {"profit": -1, "spent": 1, "_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "assets": 1,
                "sold": 1,
                "held": 1,
                "spent": 1,
                "earned": 1,
                "profit": 1,
                "average_buying_price": {"$round": ["$average_buying_price", 2]},
                "roi_percent": 1
            }
        }
    ]

    return jsonify({"statistics": run_pipeline(pipeline), "skip": skip, "limit": limit}), 200


@app.route('/aggregate/category_counts', methods=['GET'])
def aggregate_category_counts():
    """$sortByCount: koliko puta se svaka kategorija pojavljuje."""
    pipeline = [
        {"$unwind": "$categories"},
        {"$sortByCount": "$categories"},
        {"$project": {"_id": 0, "category": "$_id", "count": 1}}
    ]

    return jsonify({"categories": run_pipeline(pipeline)}), 200


@app.route('/aggregate/top_profit', methods=['GET'])
def aggregate_top_profit():
    """$match nad prodatom imovinom i rangiranje po profitu ($sort/$limit)."""
    limit = parse_positive_int(request.args.get("limit"), DEFAULT_LIMIT, MAX_LIMIT)

    pipeline = [
        {"$match": {"selling_date": {"$exists": True, "$ne": None}}},
        status_fields_stage(),
        {
            "$addFields": {
                "holding_days": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$buying_date_parsed", None]},
                                {"$ne": ["$selling_date_parsed", None]}
                            ]
                        },
                        {
                            "$dateDiff": {
                                "startDate": "$buying_date_parsed",
                                "endDate": "$selling_date_parsed",
                                "unit": "day"
                            }
                        },
                        None
                    ]
                }
            }
        },
        {"$sort": {"profit": -1, "name": 1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "categories": 1,
                "buying_price": 1,
                "selling_price": 1,
                "profit": 1,
                "holding_days": 1,
                "profit_percent": {
                    "$cond": [
                        {"$gt": ["$buying_price", 0]},
                        {"$round": [{"$multiply": [{"$divide": ["$profit", "$buying_price"]}, 100]}, 2]},
                        None
                    ]
                }
            }
        }
    ]

    return jsonify({"assets": run_pipeline(pipeline), "limit": limit}), 200


@app.route('/aggregate/price_buckets', methods=['GET'])
def aggregate_price_buckets():
    """$bucket (fiksne granice) i $bucketAuto (automatska raspodela)."""
    pipeline = [
        {"$match": {"buying_price": {"$gt": 0}}},
        {
            "$facet": {
                "fixed": [
                    {
                        "$bucket": {
                            "groupBy": "$buying_price",
                            "boundaries": [0, 10000, 100000, 1000000],
                            "default": "1000000+",
                            "output": {
                                "assets": {"$sum": 1},
                                "spent": {"$sum": "$buying_price"},
                                "names": {"$push": "$name"}
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "bucket": {"$toString": "$_id"},
                            "assets": 1,
                            "spent": 1,
                            "names": 1
                        }
                    }
                ],
                "automatic": [
                    {
                        "$bucketAuto": {
                            "groupBy": "$buying_price",
                            "buckets": 3,
                            "output": {
                                "assets": {"$sum": 1},
                                "average_buying_price": {"$avg": "$buying_price"}
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "min": "$_id.min",
                            "max": "$_id.max",
                            "assets": 1,
                            "average_buying_price": {"$round": ["$average_buying_price", 2]}
                        }
                    }
                ]
            }
        }
    ]

    result = run_pipeline(pipeline)
    return jsonify(result[0] if result else {"fixed": [], "automatic": []}), 200


@app.route('/aggregate/monthly_activity', methods=['GET'])
def aggregate_monthly_activity():
    """Grupisanje kupovina po mesecu uz datumske expression operatore."""
    pipeline = [
        status_fields_stage(),
        {"$match": {"buying_date_parsed": {"$ne": None}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m", "date": "$buying_date_parsed"}},
                "assets": {"$sum": 1},
                "spent": {"$sum": "$buying_price"},
                "profit": {"$sum": "$profit"}
            }
        },
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "month": "$_id", "assets": 1, "spent": 1, "profit": 1}}
    ]

    return jsonify({"months": run_pipeline(pipeline)}), 200


@app.route('/aggregate/info_keys', methods=['GET'])
def aggregate_info_keys():
    """$objectToArray + $unwind + $sortByCount nad dinamickim "info" poljem."""
    pipeline = [
        {"$match": {"info": {"$type": "object"}}},
        {"$project": {"info_pairs": {"$objectToArray": "$info"}}},
        {"$unwind": "$info_pairs"},
        {"$sortByCount": "$info_pairs.k"},
        {"$project": {"_id": 0, "key": "$_id", "count": 1}}
    ]

    return jsonify({"info_keys": run_pipeline(pipeline)}), 200


@app.route('/aggregate/category_overview', methods=['GET'])
def aggregate_category_overview():
    """$lookup: za svaku kategoriju se dovlaci imovina koja se jos drzi."""
    pipeline = [
        {"$unwind": "$categories"},
        {"$group": {"_id": "$categories", "assets": {"$sum": 1}}},
        {
            "$lookup": {
                "from": "assets",
                "let": {"category": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$in": ["$$category", {"$ifNull": ["$categories", []]}]},
                                    {"$eq": [{"$ifNull": ["$selling_date", None]}, None]}
                                ]
                            }
                        }
                    },
                    {"$sort": {"buying_price": -1, "name": 1}},
                    {"$project": {"_id": 0, "name": 1, "buying_price": 1}}
                ],
                "as": "held_assets"
            }
        },
        {
            "$addFields": {
                "held": {"$size": "$held_assets"},
                "held_value": {"$sum": "$held_assets.buying_price"}
            }
        },
        {"$sort": {"held_value": -1, "_id": 1}},
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "assets": 1,
                "held": 1,
                "held_value": 1,
                "held_assets": 1
            }
        }
    ]

    return jsonify({"categories": run_pipeline(pipeline)}), 200


@app.route('/aggregate/assets', methods=['GET'])
def aggregate_assets():
    """Paginirana lista imovine sa opcionim $match filterom po kategoriji."""
    skip = parse_positive_int(request.args.get("skip"), 0)
    limit = parse_positive_int(request.args.get("limit"), DEFAULT_LIMIT, MAX_LIMIT)
    category = request.args.get("category")

    match_stage = {"categories": category} if category else {}

    pipeline = [
        {"$match": match_stage},
        status_fields_stage(),
        {"$sort": {"buying_date": -1, "name": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "id": {"$toString": "$_id"},
                "name": 1,
                "categories": 1,
                "buying_date": 1,
                "buying_price": 1,
                "selling_date": 1,
                "selling_price": 1,
                "status": 1,
                "profit": 1,
                "info": {"$ifNull": ["$info", {}]}
            }
        }
    ]

    total = run_pipeline([{"$match": match_stage}, {"$count": "count"}])

    return jsonify({
        "assets": run_pipeline(pipeline),
        "total": total[0]["count"] if total else 0,
        "skip": skip,
        "limit": limit
    }), 200


if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", debug=debug_mode, port=int(os.environ.get("PORT", 5300)))
