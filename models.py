from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_app(app):
    db.init_app(app)

class Bill(db.Model):
    __tablename__ = 'bills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"Bill(id={self.id}, name={self.name}, summary={self.summary})"

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"Subscription(id={self.id}, email={self.email})"

class UserQuery(db.Model):
    __tablename__ = 'user_queries'

    id = db.Column(db.Integer, primary_key=True)
    query_text = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"UserQuery(id={self.id}, query_text={self.query_text})"
    
