"""Integration tests use an isolated database and never call the live API."""
from unittest.mock import Mock
import pytest
import requests
from sqlalchemy.exc import SQLAlchemyError
from app import create_app, data_manager
from models import db, Movie
from omdb import fetch_movie, OMDbError


@pytest.fixture
def app(tmp_path):
    application = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'OMDB_API_KEY': 'test-only',
                              'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'test.db')})
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, url, **data):
    client.get('/')
    with client.session_transaction() as session:
        data['csrf_token'] = session['csrf_token']
    return client.post(url, data=data, follow_redirects=True)


def api_reply(monkeypatch, **overrides):
    payload = {'Response': 'True', 'Title': 'Interstellar', 'Director': 'Christopher Nolan',
               'Year': '2014', 'Poster': 'https://example.com/poster.jpg', 'imdbID': 'tt0816692'}
    payload.update(overrides)
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr('omdb.requests.get', Mock(return_value=response))
    return response


def test_complete_movie_lifecycle_and_persistence(client, app, monkeypatch):
    api_reply(monkeypatch)
    assert post(client, '/users', name='Alex').status_code == 200
    page = post(client, '/users/1/movies', title='Interstellar')
    assert page.status_code == 200
    assert b'Christopher Nolan' in page.data and b'2014' in page.data
    assert b'https://example.com/poster.jpg' in page.data
    assert post(client, '/users/1/movies/1/update', new_title='Mein Lieblingsfilm').status_code == 200
    # A new app instance reads the same persisted database.
    other_app = create_app(dict(app.config))
    assert b'Mein Lieblingsfilm' in other_app.test_client().get('/users/1/movies').data
    assert post(client, '/users/1/movies/1/delete').status_code == 200
    with app.app_context():
        assert data_manager.get_movies(1) == []


@pytest.mark.parametrize('name', ['', '   ', 'x' * 81])
def test_invalid_user(client, app, name):
    assert post(client, '/users', name=name).status_code == 400
    with app.app_context():
        assert data_manager.get_users() == []


def test_duplicate_user_case_insensitive(client):
    post(client, '/users', name=' Alex ')
    assert post(client, '/users', name='alex').status_code == 400


def test_duplicate_movie_and_separate_collections(client, app, monkeypatch):
    api_reply(monkeypatch)
    post(client, '/users', name='Alex')
    post(client, '/users', name='Sam')
    assert post(client, '/users/1/movies', title='Interstellar').status_code == 200
    assert post(client, '/users/1/movies', title='Interstellar').status_code == 409
    assert post(client, '/users/2/movies', title='Interstellar').status_code == 200
    with app.app_context():
        assert len(data_manager.get_movies(1)) == len(data_manager.get_movies(2)) == 1


@pytest.mark.parametrize('action, data', [('update', {'new_title': 'Wrong user'}), ('delete', {})])
def test_wrong_user_cannot_modify_movie(client, app, monkeypatch, action, data):
    api_reply(monkeypatch)
    post(client, '/users', name='Alex')
    post(client, '/users', name='Sam')
    post(client, '/users/1/movies', title='Interstellar')
    assert post(client, '/users/2/movies/1/' + action, **data).status_code == 404
    with app.app_context():
        assert data_manager.get_movie(1).name == 'Interstellar'


@pytest.mark.parametrize('path', ['/missing', '/users/999/movies'])
def test_not_found(client, path):
    page = client.get(path)
    assert page.status_code == 404 and b'NICHT IM PROGRAMM' in page.data


@pytest.mark.parametrize('title', ['', ' ', 'x' * 251])
def test_invalid_movie_title(client, title):
    post(client, '/users', name='Alex')
    assert post(client, '/users/1/movies', title=title).status_code == 400


def test_blank_update_preserves_title(client, app, monkeypatch):
    api_reply(monkeypatch)
    post(client, '/users', name='Alex')
    post(client, '/users/1/movies', title='Interstellar')
    assert post(client, '/users/1/movies/1/update', new_title=' ').status_code == 400
    with app.app_context():
        assert data_manager.get_movie(1).name == 'Interstellar'


def test_csrf_required(client):
    assert client.post('/users', data={'name': 'Alex'}).status_code == 400


def test_get_cannot_delete(client):
    assert client.get('/users/1/movies/1/delete').status_code == 405


def test_xss_escaped(client):
    response = post(client, '/users', name='<script>alert(1)</script>')
    assert b'<script>alert(1)</script>' not in response.data
    assert b'&lt;script&gt;' in response.data


def test_api_timeout_leaves_database_unchanged(client, app, monkeypatch):
    monkeypatch.setattr('omdb.requests.get', Mock(side_effect=requests.Timeout))
    post(client, '/users', name='Alex')
    response = post(client, '/users/1/movies', title='Interstellar')
    assert response.status_code == 502
    assert b'OMDb ist momentan nicht erreichbar' in response.data
    with app.app_context():
        assert data_manager.get_movies(1) == []


def test_missing_api_key(client, app):
    app.config['OMDB_API_KEY'] = ''
    post(client, '/users', name='Alex')
    page = post(client, '/users/1/movies', title='Interstellar')
    assert page.status_code == 502 and b'OMDB_API_KEY' in page.data


@pytest.mark.parametrize('payload', [[], {}, {'Response': 'False', 'Error': 'Movie not found!'},
                                      {'Response': 'False', 'Error': 'Invalid API key!'},
                                      {'Response': 'True', 'Title': 'Incomplete'}])
def test_bad_api_payload(monkeypatch, payload):
    response = api_reply(monkeypatch)
    response.json.return_value = payload
    with pytest.raises(OMDbError):
        fetch_movie('Anything', 'test')


def test_missing_optional_metadata(monkeypatch):
    api_reply(monkeypatch, Year='N/A', Poster='N/A', Director='N/A')
    movie = fetch_movie('Interstellar', 'test')
    assert movie['year'] is None and movie['poster_url'] is None
    assert movie['director'] == 'Unbekannt'


def test_non_https_poster_rejected(monkeypatch):
    api_reply(monkeypatch, Poster='javascript:alert(1)')
    assert fetch_movie('Interstellar', 'test')['poster_url'] is None


def test_invalid_json(monkeypatch):
    response = api_reply(monkeypatch)
    response.json.side_effect = ValueError('bad JSON')
    with pytest.raises(OMDbError):
        fetch_movie('Interstellar', 'test')


def test_database_error_rolls_back(client, app, monkeypatch):
    with app.app_context():
        original_commit = db.session.commit
        monkeypatch.setattr(db.session, 'commit', Mock(side_effect=SQLAlchemyError('private details')))
        response = post(client, '/users', name='Fail')
        assert response.status_code == 500
        assert b'private details' not in response.data
        monkeypatch.setattr(db.session, 'commit', original_commit)
        assert data_manager.get_users() == []
        assert post(client, '/users', name='Recovered').status_code == 200


def test_invalid_unicode_csrf_returns_400(client):
    client.get('/')
    assert client.post('/users', data={'name': 'Alex', 'csrf_token': 'ü'}).status_code == 400
