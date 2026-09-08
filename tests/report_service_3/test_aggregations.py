"""Testovi agregacionih reportova iz `report-service-3`.

Testovi se preskacu ako MongoDB nije dostupan (npr. `docker run -p 27017:27017 mongo:6.0`).
Podesiti MONGO_HOST/MONGO_PORT ako baza nije na localhost:27017.
"""

import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "report-service-3"),
)

os.environ.setdefault("MONGO_DB_NAME", "fond_test_db")

pytest.importorskip("pymongo")
pytest.importorskip("flask")

import app as report_app  # noqa: E402


def _format_iso(value):
    return value.isoformat() + "Z"


def _dummy_assets():
    now = datetime.utcnow()
    return [
        {
            "name": "Apple Akcije (AAPL)",
            "categories": ["Akcije", "Tehnologija"],
            "buying_price": 50000.0,
            "buying_date": _format_iso(now - timedelta(days=30)),
            "selling_price": 75000.0,
            "selling_date": _format_iso(now - timedelta(days=5)),
            "info": {"tiker": "AAPL", "berza": "NASDAQ"},
        },
        {
            "name": "Zgrada ETF-a Blok 32",
            "categories": ["Nekretnine"],
            "buying_price": 1250000.0,
            "buying_date": _format_iso(now - timedelta(days=15)),
            "info": {"kvadratura": 4500},
        },
        {
            "name": "Bitcoin",
            "categories": ["Kripto", "Tehnologija"],
            "buying_price": 60000.0,
            "buying_date": _format_iso(now - timedelta(days=10)),
            "selling_price": 45000.0,
            "selling_date": _format_iso(now - timedelta(days=2)),
            "info": {"mreza": "Mainnet"},
        },
        {
            "name": "Zlatne poluge 1kg",
            "categories": ["Plemeniti metali"],
            "buying_price": 5000.0,
            "buying_date": _format_iso(now - timedelta(days=45)),
            "info": {"finoca": "999.9"},
        },
    ]


@pytest.fixture(scope="module")
def client():
    try:
        report_app.mongo_client.admin.command("ping")
    except Exception as exc:  # pragma: no cover - zavisi od okruzenja
        pytest.skip(f"MongoDB nije dostupan: {exc}")

    report_app.app.config["TESTING"] = True
    with report_app.app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def populated_collection(client):
    report_app.assets_collection.delete_many({})
    report_app.assets_collection.insert_many(_dummy_assets())
    yield
    report_app.assets_collection.delete_many({})


def test_summary_returns_totals_and_status_distribution(client):
    response = client.get("/aggregate/summary")
    assert response.status_code == 200

    data = response.get_json()
    assert data["assets_count"] == 4
    assert data["totals"]["assets"] == 4
    assert data["totals"]["spent"] == pytest.approx(1365000.0)
    assert data["totals"]["earned"] == pytest.approx(120000.0)
    assert data["totals"]["profit"] == pytest.approx(10000.0)

    by_status = {item["status"]: item["assets"] for item in data["by_status"]}
    assert by_status == {"SOLD": 2, "HELD": 2}
    assert data["most_expensive"][0]["name"] == "Zgrada ETF-a Blok 32"


def test_by_category_groups_and_paginates(client):
    response = client.get("/aggregate/by_category")
    assert response.status_code == 200

    statistics = response.get_json()["statistics"]
    categories = {item["category"]: item for item in statistics}
    assert categories["Tehnologija"]["assets"] == 2
    assert categories["Tehnologija"]["sold"] == 2
    assert categories["Tehnologija"]["profit"] == pytest.approx(10000.0)
    assert categories["Nekretnine"]["held"] == 1
    assert categories["Nekretnine"]["roi_percent"] == 0.0

    paged = client.get("/aggregate/by_category?skip=1&limit=2").get_json()
    assert paged["skip"] == 1 and paged["limit"] == 2
    assert len(paged["statistics"]) == 2
    assert paged["statistics"][0]["category"] == statistics[1]["category"]


def test_category_counts_uses_sort_by_count(client):
    counts = client.get("/aggregate/category_counts").get_json()["categories"]
    assert counts[0] == {"category": "Tehnologija", "count": 2}


def test_top_profit_returns_only_sold_assets(client):
    data = client.get("/aggregate/top_profit?limit=1").get_json()
    assert data["limit"] == 1
    assert len(data["assets"]) == 1

    best = data["assets"][0]
    assert best["name"] == "Apple Akcije (AAPL)"
    assert best["profit"] == pytest.approx(25000.0)
    assert best["profit_percent"] == pytest.approx(50.0)
    assert best["holding_days"] == 25


def test_price_buckets_returns_fixed_and_automatic_buckets(client):
    data = client.get("/aggregate/price_buckets").get_json()

    fixed = {item["bucket"]: item for item in data["fixed"]}
    assert fixed["0"]["assets"] == 1
    assert fixed["10000"]["assets"] == 2
    assert fixed["1000000+"]["names"] == ["Zgrada ETF-a Blok 32"]

    assert len(data["automatic"]) >= 1
    assert sum(item["assets"] for item in data["automatic"]) == 4


def test_monthly_activity_groups_by_month(client):
    months = client.get("/aggregate/monthly_activity").get_json()["months"]
    assert months
    assert sum(item["assets"] for item in months) == 4
    assert months == sorted(months, key=lambda item: item["month"])


def test_info_keys_counts_dynamic_info_fields(client):
    info_keys = client.get("/aggregate/info_keys").get_json()["info_keys"]
    keys = {item["key"]: item["count"] for item in info_keys}
    assert keys["tiker"] == 1
    assert keys["berza"] == 1
    assert len(info_keys) == 5


def test_category_overview_uses_lookup(client):
    categories = client.get("/aggregate/category_overview").get_json()["categories"]
    overview = {item["category"]: item for item in categories}

    assert overview["Nekretnine"]["held"] == 1
    assert overview["Nekretnine"]["held_value"] == pytest.approx(1250000.0)
    assert overview["Nekretnine"]["held_assets"][0]["name"] == "Zgrada ETF-a Blok 32"
    assert overview["Tehnologija"]["held"] == 0
    assert overview["Tehnologija"]["held_assets"] == []


def test_assets_listing_supports_filter_and_pagination(client):
    data = client.get("/aggregate/assets?category=Tehnologija&limit=1").get_json()
    assert data["total"] == 2
    assert len(data["assets"]) == 1
    assert data["assets"][0]["status"] == "SOLD"
    assert "id" in data["assets"][0]

    all_assets = client.get("/aggregate/assets").get_json()
    assert all_assets["total"] == 4
    assert len(all_assets["assets"]) == 4


def test_endpoints_handle_empty_collection(client):
    report_app.assets_collection.delete_many({})

    summary = client.get("/aggregate/summary").get_json()
    assert summary["assets_count"] == 0
    assert summary["totals"]["assets"] == 0
    assert summary["by_status"] == []

    assert client.get("/aggregate/by_category").get_json()["statistics"] == []
    assert client.get("/aggregate/category_counts").get_json()["categories"] == []
    assert client.get("/aggregate/top_profit").get_json()["assets"] == []
    assert client.get("/aggregate/price_buckets").get_json()["fixed"] == []
    assert client.get("/aggregate/monthly_activity").get_json()["months"] == []
    assert client.get("/aggregate/info_keys").get_json()["info_keys"] == []
    assert client.get("/aggregate/category_overview").get_json()["categories"] == []

    assets = client.get("/aggregate/assets").get_json()
    assert assets == {"assets": [], "total": 0, "skip": 0, "limit": 10}
