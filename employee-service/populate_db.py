from datetime import timedelta, datetime

from pymongo import MongoClient


def populate_dummy_data():
    # Povezivanje na lokalni MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    db = client["fond_db"]
    assets_collection = db["assets"]

    # Čišćenje kolekcije pre unosa kako nemao duplikate pri svakom pokretanju
    assets_collection.delete_many({})

    # Generisanje vremenskih odrednica u ISO formatu
    now = datetime.utcnow()
    format_iso = lambda dt: dt.isoformat() + "Z"

    dummy_assets = [
        # 1. Imovina: Kupljena i prodata (Generiše profit)
        {
            "name": "Apple Akcije (AAPL)",
            "categories": ["Akcije", "Tehnologija"],
            "buying_price": 50000.0,
            "buying_date": format_iso(now - timedelta(days=30)),
            "selling_price": 75000.0,
            "selling_date": format_iso(now - timedelta(days=5)),
            "info": {
                "tiker": "AAPL",
                "berza": "NASDAQ",
                "kolicina": 300
            }
        },
        # 2. Imovina: Samo kupljena (Zgrada ETF-a iz Faze 2)
        {
            "name": "Zgrada ETF-a Blok 32",
            "categories": ["Nekretnine", "Infrastruktura"],
            "buying_price": 1250000.0,
            "buying_date": format_iso(now - timedelta(days=15)),
            "info": {
                "kvadratura": 4500,
                "lokacija": {
                    "grad": "Beograd",
                    "opstina": "Novi Beograd"
                },
                "parking_mesta": 50
            }
        },
        # 3. Imovina: Kupljena i prodata sa gubitkom (Za testiranje suma)
        {
            "name": "Bitcoin",
            "categories": ["Kripto", "Tehnologija"],
            "buying_price": 60000.0,
            "buying_date": format_iso(now - timedelta(days=10)),
            "selling_price": 45000.0,
            "selling_date": format_iso(now - timedelta(days=2)),
            "info": {
                "mreža": "Mainnet",
                "novčanik": "Cold Storage 1"
            }
        },
        # 4. Imovina: Samo kupljena sitna imovina
        {
            "name": "Zlatne poluge 1kg",
            "categories": ["Plemeniti metali"],
            "buying_price": 72000.0,
            "buying_date": format_iso(now - timedelta(days=45)),
            "info": {
                "finoća": "999.9",
                "sef": "Narodna Banka"
            }
        }
    ]

    # Upisivanje u MongoDB
    result = assets_collection.insert_many(dummy_assets)
    print(f"Baza uspešno osvežena! Uneto {len(result.inserted_ids)} dokumenata imovine.")


if __name__ == "__main__":
    # Pokreće se samo ako direktno pokreneš ovu skriptu
    populate_dummy_data()