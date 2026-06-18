from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    forename = db.Column(db.String(256), nullable=False)
    surname = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='employee')  # 'director' ili 'employee'

    def to_json(self):
        return {
            "forename": self.forename,
            "surname": self.surname,
            "email": self.email,
            "role": self.role
        }