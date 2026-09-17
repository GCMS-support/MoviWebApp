"""Database models for users and their personal movie collections."""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """A selectable profile, not an authenticated account."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    name_key = db.Column(db.String(160), unique=True, nullable=False)
    movies = db.relationship('Movie', back_populates='user', cascade='all, delete-orphan')


class Movie(db.Model):
    """Each favorite belongs to exactly one user."""
    __tablename__ = 'movies'
    __table_args__ = (db.UniqueConstraint('user_id', 'imdb_id'),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    director = db.Column(db.String(500), nullable=False, default='Unbekannt')
    year = db.Column(db.Integer, nullable=True)
    poster_url = db.Column(db.String(2000), nullable=True)
    imdb_id = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    user = db.relationship('User', back_populates='movies')
