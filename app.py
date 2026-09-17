"""MoviWeb: Flask application and HTTP routes."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from data_manager import DataManager
from models import db, Movie
from omdb import OMDbError, fetch_movie

load_dotenv()
data_manager = DataManager()


def create_app(test_config=None):
    """Create an independent app; tests can use an isolated database."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///moviweb.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        OMDB_API_KEY=os.getenv('OMDB_API_KEY', ''),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        db.create_all()

    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return session['csrf_token']

    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect_forms():
        if request.method == 'POST':
            expected = session.get('csrf_token', '')
            supplied = request.form.get('csrf_token', '')
            if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description='Das Formular ist abgelaufen. Bitte lade die Seite neu und versuche es erneut.')

    def require_user(user_id):
        user = data_manager.get_user(user_id)
        if user is None:
            abort(404)
        return user

    def require_movie(user_id, movie_id):
        require_user(user_id)
        movie = data_manager.get_movie(movie_id)
        if movie is None or movie.user_id != user_id:
            abort(404)
        return movie

    def movie_page(user, status=200):
        return render_template('movies.html', user=user, movies=data_manager.get_movies(user.id)), status

    @app.get('/users')
    @app.get('/')
    def index():
        return render_template('index.html', users=data_manager.get_users())

    @app.post('/users')
    def create_user():
        try:
            data_manager.create_user(request.form.get('name', ''))
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('index.html', users=data_manager.get_users()), 400
        flash('Profil angelegt. Wähle es aus und starte deine Sammlung.', 'success')
        return redirect(url_for('index'))

    @app.get('/users/<int:user_id>/movies')
    def list_movies(user_id):
        return movie_page(require_user(user_id))

    @app.post('/users/<int:user_id>/movies')
    def add_movie(user_id):
        user = require_user(user_id)
        title = request.form.get('title', '').strip()
        if not title or len(title) > 250:
            flash('Bitte einen Filmtitel mit 1 bis 250 Zeichen eingeben.', 'error')
            return movie_page(user, 400)
        try:
            details = fetch_movie(title, app.config['OMDB_API_KEY'])
            data_manager.add_movie(Movie(user_id=user_id, **details))
        except OMDbError as error:
            flash(str(error), 'error')
            return movie_page(user, 502)
        except ValueError as error:
            flash(str(error), 'error')
            return movie_page(user, 409)
        flash('Film zur Sammlung hinzugefügt.', 'success')
        return redirect(url_for('list_movies', user_id=user_id))

    @app.post('/users/<int:user_id>/movies/<int:movie_id>/update')
    def update_movie(user_id, movie_id):
        require_movie(user_id, movie_id)
        try:
            data_manager.update_movie(movie_id, request.form.get('new_title', ''))
        except ValueError as error:
            flash(str(error), 'error')
            return movie_page(require_user(user_id), 400)
        flash('Filmtitel aktualisiert.', 'success')
        return redirect(url_for('list_movies', user_id=user_id))

    @app.post('/users/<int:user_id>/movies/<int:movie_id>/delete')
    def delete_movie(user_id, movie_id):
        require_movie(user_id, movie_id)
        data_manager.delete_movie(movie_id)
        flash('Film aus der Sammlung entfernt.', 'success')
        return redirect(url_for('list_movies', user_id=user_id))

    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(400)
    @app.errorhandler(405)
    @app.errorhandler(413)
    def invalid_request(error):
        return render_template('error.html', code=error.code, message=error.description), error.code

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return render_template('error.html', code=409, message='Dieser Eintrag existiert bereits oder konnte nicht gespeichert werden.'), 409

    @app.errorhandler(SQLAlchemyError)
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        app.logger.error('A database or server operation failed (%s).', type(error).__name__)
        return render_template('500.html'), 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
