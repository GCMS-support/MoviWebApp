"""All database operations used by the web application."""
from sqlalchemy.exc import SQLAlchemyError
from models import db, User, Movie


class DataManager:
    """Read collections and persist changes with transaction rollback."""

    @staticmethod
    def _commit():
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise

    def create_user(self, name):
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError('Bitte einen Namen mit 1 bis 80 Zeichen eingeben.')
        key = name.casefold()
        if db.session.scalar(db.select(User).where(User.name_key == key)):
            raise ValueError('Dieser Nutzername ist bereits vergeben.')
        user = User(name=name, name_key=key)
        db.session.add(user)
        self._commit()
        return user

    def get_users(self):
        return db.session.scalars(db.select(User).order_by(User.name)).all()

    def get_user(self, user_id):
        return db.session.get(User, user_id)

    def get_movies(self, user_id):
        return db.session.scalars(db.select(Movie).where(Movie.user_id == user_id).order_by(Movie.id.desc())).all()

    def get_movie(self, movie_id):
        return db.session.get(Movie, movie_id)

    def add_movie(self, movie):
        existing = db.session.scalar(db.select(Movie).where(Movie.user_id == movie.user_id, Movie.imdb_id == movie.imdb_id))
        if existing:
            raise ValueError('Dieser Film ist bereits in deiner Sammlung.')
        db.session.add(movie)
        self._commit()
        return movie

    def update_movie(self, movie_id, new_title):
        movie = self.get_movie(movie_id)
        if movie is None:
            raise ValueError('Film nicht gefunden.')
        new_title = new_title.strip()
        if not new_title or len(new_title) > 250:
            raise ValueError('Bitte einen Filmtitel mit 1 bis 250 Zeichen eingeben.')
        movie.name = new_title
        self._commit()
        return movie

    def delete_movie(self, movie_id):
        movie = self.get_movie(movie_id)
        if movie is None:
            raise ValueError('Film nicht gefunden.')
        db.session.delete(movie)
        self._commit()
