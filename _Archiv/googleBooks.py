import requests
import re

# Basis-URL für die Google Books API
SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"


# --- Hilfsfunktionen für die interne Logik ---

def _extract_prioritized_isbn(industry_identifiers):
    """
    Extrahiert die ISBN-13, oder wenn nicht vorhanden, die ISBN-10.
    Gibt die bereinigte ISBN (als String) oder None zurück.
    """
    isbn_13 = None
    isbn_10 = None

    for identifier in industry_identifiers:
        id_type = identifier.get('type')
        isbn = identifier.get('identifier')

        if isbn:
            # Bereinigung: Entferne Leerzeichen und Bindestriche
            isbn_clean = re.sub(r'[\s\-]', '', str(isbn))

            # Priorität 1: ISBN-13
            if id_type == 'ISBN_13' and len(isbn_clean) == 13:
                isbn_13 = isbn_clean
            # Priorität 2: ISBN-10 (speichern wir nur, falls keine 13er gefunden wird)
            elif id_type == 'ISBN_10' and len(isbn_clean) in (10, 13):
                isbn_10 = isbn_clean

    # Rückgabe: Bevorzuge ISBN-13
    return isbn_13 if isbn_13 else isbn_10


def _get_isbn_from_google_books(title, author_lastname, lang=None):
    """Sucht die ISBN extern über die Google Books API mit zwei Versuchen."""
    print(f"  -> Suche ISBN via Google Books: '{title}' von {author_lastname}")

    queries = [
        f"intitle:\"{title}\" inauthor:\"{author_lastname}\"",  # Striktere Suche
        f"{title} {author_lastname}"  # Unscharfe Suche
    ]

    for query in queries:
        params = {
            'q': query,
            'maxResults': 5,
        }
        if lang:
            params['langRestrict'] = lang
        try:
            response = requests.get(SEARCH_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get('totalItems', 0) > 0:
                for item in data['items']:
                    volume_info = item.get('volumeInfo', {})
                    industry_ids = volume_info.get('industryIdentifiers', [])

                    # Nutze die neue, priorisierende Extraktionsfunktion
                    isbn = _extract_prioritized_isbn(industry_ids)
                    if isbn:
                        return isbn

        except requests.exceptions.RequestException as e:
            print(f"  WARN: Externer ISBN-Suchfehler (Netzwerk): {e}")
            return None
        except Exception as e:
            print(f"  WARN: Externer ISBN-Suchfehler (Allgemein): {e}")
            return None

    return None


def _get_description_genres_date_from_google_books(title, author_lastname, isbn=None, lang=None):
    """Ruft Beschreibung, Kategorien und das Erscheinungsdatum von Google Books ab."""

    queries_to_try = []
    if isbn:
        queries_to_try.append(f"isbn:{isbn}")
    elif title and author_lastname:
        queries_to_try = [
            f"intitle:\"{title}\" inauthor:\"{author_lastname}\"",
            f"{title} {author_lastname}"
        ]
    else:
        return {}

    for query in queries_to_try:
        params = {'q': query, 'maxResults': 1, }
        if lang:
            params['langRestrict'] = lang
        try:
            response = requests.get(SEARCH_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get('totalItems', 0) > 0:
                item = data['items'][0]
                volume_info = item.get('volumeInfo', {})

                return {
                    'description': volume_info.get('description'),
                    'categories': volume_info.get('categories', []),
                    'published_date': volume_info.get('publishedDate')
                }
        except requests.exceptions.RequestException:
            if not isbn: continue
            return {}
        except Exception:
            if not isbn: continue
            return {}

    return {}


def _get_google_books_ratings(isbn):
    """
    Ruft Ratings und Rating-Zähler über die präzise ISBN-Suche ab.
    """
    if not isbn:
        return {}

    query = f"isbn:{isbn}"
    params = {'q': query, 'maxResults': 1}

    try:
        response = requests.get(SEARCH_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('totalItems', 0) > 0:
            volume_info = data['items'][0].get('volumeInfo', {})

            # Die API-Felder werden auf die vereinfachten Namen in deinem Dictionary gemappt
            return {
                'average_rating': volume_info.get('averageRating'),
                'ratings_count': volume_info.get('ratingsCount')
            }

    except requests.exceptions.RequestException as e:
        print(f"  WARN: Externer Rating-Suchfehler (Netzwerk): {e}")
    except Exception as e:
        print(f"  WARN: Externer Rating-Suchfehler (Allgemein): {e}")

    return {}


# --- Hauptfunktion für den Workflow (read_googleBooks) ---
def read_google_books(book_metadata, language=None):
    """
    Führt den Google Books API-Scan durch und reichert das BookData-Objekt an.
    Nutzt das BookData-Objekt direkt für den Datenzugriff.
    """
    if not book_metadata:
        return book_metadata

    # Initialisiere Variablen für die Suche direkt aus dem Objekt
    title = book_metadata.title
    authors = book_metadata.authors  # Liste von Tupeln [(Vorname, Nachname)]
    isbn = book_metadata.isbn
    search_language = language if language else book_metadata.language

    print("------ google Books Scan ----")
    print(f"Titel: {title}, ISBN: {isbn}, Sprache: {search_language}")

    # Extraktion des Nachnamens für die API-Suche (aus dem Autoren-Tupel)
    author_lastname = None
    if authors and isinstance(authors[0], tuple):
        author_lastname = authors[0][1]
    elif authors and isinstance(authors[0], str):  # Fallback falls doch Strings kommen
        author_lastname = authors[0].split()[-1]

    if not title and not author_lastname:
        print("  WARN: Kein Titel und kein Autor verfügbar für Google Books Suche.")
        return book_metadata

    # ------------------ 1. ISBN-Suche, falls fehlend ------------------
    # Bereinigung der ISBN für die Prüfung
    isbn_clean = re.sub(r'[\s\-]', '', str(isbn)) if isbn else ""

    if not isbn_clean or len(isbn_clean) not in (10, 13):
        if title and author_lastname:
            new_isbn = _get_isbn_from_google_books(title, author_lastname, lang=search_language)
            if new_isbn:
                book_metadata.isbn = new_isbn
                isbn = new_isbn
                print(f"  -> Neue ISBN {isbn} via Google Books gefunden.")

    # ------------------ 2. Detail-Suche (Rating/Genre/Beschreibung) ------------------

    # a) Ratings über die ISBN holen
    if isbn and len(str(isbn)) in (10, 13):
        rating_data = _get_google_books_ratings(isbn)
        # Direkt ins Objekt schreiben
        if rating_data.get('average_rating'):
            book_metadata.average_rating = rating_data['average_rating']
        if rating_data.get('ratings_count'):
            book_metadata.ratings_count = rating_data['ratings_count']

    # b) Genre, Jahr und Beschreibung holen, falls sie noch fehlen
    # Wir nutzen die Attribute des Objekts für die Prüfung
    if not book_metadata.description or not book_metadata.year:
        detail_data = _get_description_genres_date_from_google_books(title, author_lastname, isbn, lang=search_language)

        # Beschreibung ergänzen
        if detail_data.get('description') and not book_metadata.description:
            book_metadata.description = detail_data['description']

        # Kategorien (für späteres Genre-Mapping zwischenspeichern)
        if detail_data.get('categories'):
            # Wir hängen die Kategorien als temporäres Attribut an oder nutzen ein Metadata-Feld
            book_metadata.categories = detail_data['categories']
            # Fallback für das Genre-Feld, falls dieses noch komplett leer ist
            if not book_metadata.genre:
                book_metadata.genre = detail_data['categories'][0]

        # Jahr ergänzen
        published_date = detail_data.get('published_date')
        if published_date and not book_metadata.year:
            book_metadata.year = published_date[:4]

    return book_metadata

# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Beispiel-Daten (wie sie aus read_epub kämen)
    test_data = {
        'file_path': '...',
        'title': "Rue de Paradis",
        'authors': ['Alexander Oetker'],
         'isbn': None, # Beispiel: ISBN fehlt im EPUB
         'description': None,
         'genre_epub': None,
        'year': None,
        'average_rating': None,
         'ratings_count': None,
     }
#
    updated_data = read_google_books(test_data)
    import pprint
    pprint.pprint(updated_data)