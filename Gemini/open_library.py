"""
DATEI: open_library.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um die Daten von Open Library via ISBN oder Autor Titel zu finden.
              Holt das Rating-ol, Rating Count-ol und Description und evtl. ISBN.
              Falls Description von Google schon gefüllt ist, oder manuell erstellt wurde
              Schreiben wir die OpenLibrary Description in das Feld Notes.
"""
import requests

OL_API_URL = "https://openlibrary.org/api/books"
OL_SEARCH_URL = "https://openlibrary.org/search.json"


def fetch_open_library_data(title, authors, isbn=None):
    """
    Sucht bei Open Library. Erst via ISBN, dann via Suche.
    """
    # 1. Direkter Weg (Deine funktionierende URL)
    if isbn and len(str(isbn)) in (10, 13):
        return _get_details_via_api(isbn)

    # 2. Such-Weg (Falls keine ISBN da ist)
    if title:
        author_name = authors[0][1] if authors else ""
        try:
            # Wir suchen nach Titel und Autor
            params = {'q': f'title:{title} author:{author_name}', 'limit': 1}
            resp = requests.get(OL_SEARCH_URL, params=params, timeout=10)
            data = resp.json()

            if data.get('docs'):
                # Wir nehmen die erste ISBN, die wir im Treffer finden
                found_isbns = data['docs'][0].get('isbn', [])
                if found_isbns:
                    return _get_details_via_api(found_isbns[0])
        except Exception as e:
            print(f"  WARN: OL Suche fehlgeschlagen: {e}")

    return None


def _get_details_via_api(isbn):
    """Deine bewährte Logik zum Abrufen der Daten."""
    url = f"{OL_API_URL}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        ol_key = f'ISBN:{isbn}'
        book_info = data.get(ol_key, {})
        if not book_info:
            return None

        # Beschreibung extrahieren (kann String oder Dict sein)
        raw_desc = book_info.get('description', "")
        description = raw_desc.get('value', raw_desc) if isinstance(raw_desc, dict) else raw_desc

        # Ratings extrahieren
        details = book_info.get('details', book_info)
        rating_data = details.get('ratings', {})

        return {
            'ol_isbn': isbn,
            'description': description,
            'ol_rating': rating_data.get('average'),
            'ol_count': rating_data.get('count')
        }
    except Exception:
        return None

# -------------------------------------------------------------------------
# if __name__ == "__main__":
#     # Beispiel-Daten: ISBN vorhanden, Ratings fehlen
#     test_data = {
#         'isbn': '9783596181971', # Beispiel-ISBN für einen Apps
#         'average_rating': None,
#         'ratings_count': None,
#     }
#
#     updated_data = read_open_library(test_data)
#     import pprint
#     pprint.pprint(updated_data)