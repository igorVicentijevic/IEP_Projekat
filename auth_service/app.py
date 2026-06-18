import re
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from models import db, User

app = Flask(__name__)

# Konfiguracija baze (izmeni string po potrebi za produkciju/K8s)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://auth_user:auth_password@localhost:5432/auth_db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "super-tajni-kljuc-promeni-ovo"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

db.init_app(app)
jwt = JWTManager(app)


def is_valid_email(email):
    # Jednostavan regex za validaciju formata email-a
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


# --- RUTE ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    # 1. Provera da li polja nedostaju ili su prazna
    for field in ["forename", "surname", "email", "password"]:
        if field not in data or str(data[field]).strip() == "":
            return jsonify({"message": f"Field {field} is missing."}), 400

    email = data["email"]
    password = data["password"]

    # 2. Validacija email formata
    if not is_valid_email(email):
        return jsonify({"message": "Invalid email."}), 400

    # 3. Validacija lozinke (dužina mora biti >= 8)
    if len(password) < 8:
        return jsonify({"message": "Invalid password."}), 400

    # 4. Provera da li email već postoji
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already exists."}), 400

    # Kreiranje novog zaposlenog
    new_user = User(
        forename=data["forename"],
        surname=data["surname"],
        email=email,
        password=password,
        role="employee"
    )
    db.session.add(new_user)
    db.session.commit()

    return "", 200


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}

    # 1. Provera da li polja nedostaju
    for field in ["email", "password"]:
        if field not in data or str(data[field]).strip() == "":
            return jsonify({"message": f"Field {field} is missing."}), 400

    email = data["email"]
    password = data["password"]

    # 2. Validacija email formata
    if not is_valid_email(email):
        return jsonify({"message": "Invalid email."}), 400

    # 3. Provera kredencijala
    user = User.query.filter_by(email=email, password=password).first()
    if not user:
        return jsonify({"message": "Invalid credentials."}), 400

    # Kreiranje JWT tokena (identifikator je email, a u claims stavljamo profil bez lozinke)
    additional_claims = user.to_json()
    token = create_access_token(identity=email, additional_claims=additional_claims)

    return jsonify({"accessToken": token}), 200


@app.route('/delete', methods=['POST'])
@jwt_required()
def delete_user():
    # Flask-JWT-Extended automatski vraća 401 i "Missing Authorization Header"
    # ako token nije poslat ili je nevalidan, što pokriva zahteve specifikacije.

    current_user_email = get_jwt_identity()
    user = User.query.filter_by(email=current_user_email).first()

    if not user:
        return jsonify({"message": "Unknown user."}), 400

    db.session.delete(user)
    db.session.commit()

    return "", 200


if __name__ == '__main__':
    app.run(debug=True, port=5001)