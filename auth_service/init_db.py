from app import app
from models import db, User

with app.app_context():
    db.create_all()

    # Provera da li direktor već postoji
    director_email = "onlymoney@gmail.com"
    exists = User.query.filter_by(email=director_email).first()

    if not exists:
        director = User(
            forename="Scrooge",
            surname="McDuck",
            email=director_email,
            password="evenmoremoney",  # U produkciji bi išao hash, ali prati specifikaciju
            role="director"
        )
        db.session.add(director)
        db.session.commit()
        print("Početni direktor uspešno kreiran.")