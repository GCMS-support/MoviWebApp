# MoviWeb App

Flask-Webanwendung für persönliche Lieblingsfilmlisten, erstellt für das Projekt **Flask + SQLAlchemy**.

## Funktionen

- Profile anlegen und auswählen; Nutzerliste auf der Startseite.
- Filme über ihren Titel aus OMDb hinzufügen (Regie, Jahr, Poster).
- Filmtitel selbst bearbeiten und Filme aus der Sammlung entfernen.
- SQLite-Persistenz mit SQLAlchemy und separater DataManager-Klasse.
- Deutsche, responsive Jinja-Oberfläche, leere Zustände und eigene Fehlerseiten.
- Eingabeprüfung, CSRF-Schutz, Schutz vor doppelten Profilen/Filmen und Prüfung der Filmzuordnung.

Die Profile sind gemäß Aufgabenstellung frei auswählbar. Dies ist **keine Benutzeranmeldung**; die App sollte nur für freigegebene Übungsdaten verwendet werden.

## Einrichtung

Python 3.10 oder neuer:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
~~~

In der lokalen Datei .env eintragen:

~~~dotenv
OMDB_API_KEY=dein_omdb_api_schluessel
SECRET_KEY=ein_langer_zufaelliger_wert
~~~

Einen zufälligen SECRET_KEY kannst du mit folgendem Befehl erstellen:

~~~bash
python -c "import secrets; print(secrets.token_hex(32))"
~~~

OMDb-Schlüssel: https://www.omdbapi.com/apikey.aspx
Die Datei .env und lokale Datenbanken sind in .gitignore ausgeschlossen. API-Schlüssel niemals auf GitHub veröffentlichen.

~~~bash
python app.py
~~~

Lokal: http://localhost:5000. In Codio: **Run**, danach **Open Flask Application**. Die Tabellen werden beim Start angelegt. Die Standarddatenbank ist instance/moviweb.db; eine bestehende instance/movies.db wird nicht verändert. Ohne OMDb-Schlüssel funktionieren Profile und bereits gespeicherte Sammlungen; das Hinzufügen zeigt einen Einrichtungshinweis.

## Projektstruktur

~~~text
app.py                 App-Factory, Routen, Fehlerbehandlung, CSRF
models.py              User- und Movie-Modelle
data_manager.py        Datenbankzugriffe und Transaktionen
omdb.py                OMDb-Client mit Timeout und Antwortprüfung
templates/             Basislayout, Profile, Filme, Fehlerseiten
static/style.css       Responsive Oberfläche
tests/test_app.py      Isolierte Integrations- und Fehlertests
~~~

Ein User besitzt mehrere Movie-Einträge. Jeder Film hat id, name, director, year, poster_url, imdb_id und user_id. Die Kombination aus user_id und imdb_id ist eindeutig; derselbe Film kann zu mehreren persönlichen Sammlungen gehören.

## Routen

| Methode | Route | Funktion |
| --- | --- | --- |
| GET | / und /users | Profile anzeigen |
| POST | /users | Profil anlegen |
| GET | /users/<user_id>/movies | Sammlung anzeigen |
| POST | /users/<user_id>/movies | Film über OMDb hinzufügen |
| POST | /users/<user_id>/movies/<movie_id>/update | Titel bearbeiten |
| POST | /users/<user_id>/movies/<movie_id>/delete | Film entfernen |

Alle POST-Formulare enthalten ein CSRF-Token. Änderungen werden nur für Filme ausgeführt, deren user_id zur Route passt. Schreibfehler führen zu einem Rollback; Fehlermeldungen enthalten keine Schlüssel oder SQL-Daten.

## Tests

~~~bash
pip install -r requirements-dev.txt
python -m pytest -q
~~~

Die Tests verwenden eigene temporäre SQLite-Datenbanken und simulierte OMDb-Antworten. Sie testen CRUD, dauerhafte Speicherung, getrennte Sammlungen, Duplikate, ungültige Eingaben, falsche IDs, CSRF, HTML-Escaping, API-Ausfälle und Datenbank-Rollback. Ein echter OMDb-Abruf benötigt zusätzlich einen gültigen Schlüssel.

## Bereitstellung (optional)

~~~bash
gunicorn --bind 0.0.0.0:5000 app:app
~~~

Für mehrere Worker einen festen SECRET_KEY setzen. Für SQLite muss instance/ auf dauerhaftem beschreibbarem Speicher liegen. Unter HTTPS sollte SESSION_COOKIE_SECURE aktiviert werden. Für PythonAnywhere kann in der WSGI-Datei nach Hinzufügen des Projektpfads verwendet werden: from app import app as application.

## Referenzen

- Flask-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/
- OMDb-API: https://www.omdbapi.com/
