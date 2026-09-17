"""OMDb integration with bounded requests and safe, actionable errors."""
import re
import requests


class OMDbError(Exception):
    """An OMDb lookup could not be completed."""


def fetch_movie(title, api_key):
    if not api_key:
        raise OMDbError('Die Filmsuche ist noch nicht eingerichtet. Bitte OMDB_API_KEY in der .env-Datei setzen.')
    try:
        response = requests.get('https://www.omdbapi.com/', params={'apikey': api_key, 't': title, 'type': 'movie'}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        raise OMDbError('OMDb ist momentan nicht erreichbar. Bitte versuche es später erneut.') from None
    if not isinstance(data, dict):
        raise OMDbError('OMDb hat eine ungültige Antwort geliefert.')
    if data.get('Response') != 'True':
        error = str(data.get('Error', ''))
        if 'not found' in error.lower():
            raise OMDbError('Kein Film gefunden. Bitte prüfe den Titel.')
        raise OMDbError('Die Filmsuche ist nicht verfügbar. Bitte API-Schlüssel und OMDb-Kontingent prüfen.')
    name, imdb_id = data.get('Title'), data.get('imdbID')
    if not isinstance(name, str) or not name.strip() or not isinstance(imdb_id, str) or not re.fullmatch(r'tt[0-9]+', imdb_id):
        raise OMDbError('OMDb hat unvollständige Filmdaten geliefert.')
    year_match = re.match(r'^[0-9]{4}', str(data.get('Year', '')))
    poster = data.get('Poster')
    director = data.get('Director')
    return {'name': name[:250], 'imdb_id': imdb_id, 'year': int(year_match.group()) if year_match else None,
            'director': director[:500] if isinstance(director, str) and director != 'N/A' else 'Unbekannt',
            'poster_url': poster if isinstance(poster, str) and poster.startswith('https://') and len(poster) <= 2000 else None}
