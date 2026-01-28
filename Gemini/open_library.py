"""
DATEI: open_library.py
PROJEKT: MyBook-Management
BESCHREIBUNG: Sucht erst via Titel/Autor, um die ISBN zu validieren/finden,
              und holt dann mit der ISBN die vollen Details (Ratings, Description).
"""
import requests
from Gemini.file_utils import clean_description

OL_API_URL = "https://openlibrary.org/api/books"
OL_SEARCH_URL = "https://openlibrary.org/search.json"

def search_open_library(title: str = None, author: str = None, isbn: str = None):
    """
    Sucht immer erst breit (Suche) und dann tief (ISBN-Details).
    """
    final_data = {}
    found_isbn = isbn

    # 1. SCHRITT: Suche via Titel/Autor (immer, um ISBN zu finden/bestätigen)
    if title:
        q = title.replace(" ", "+")
        if author:
            # Autor-String sauber aufbereiten
            a_str = author[0][1] if isinstance(author, list) else str(author)
            q += f"&author={a_str.replace(' ', '+')}"

        try:
            resp = requests.get(OL_SEARCH_URL, params={'q': q, 'limit': 1}, timeout=5)
            data = resp.json()
            if data.get("docs"):
                doc = data["docs"][0]
                final_data = {
                    "title": doc.get("title"),
                    "authors_raw": ", ".join(doc.get("author_name", [])),
                    "isbn": doc.get("isbn", [None])[0],
                    "series_name": doc.get("series", [None])[0],
                    "language": doc.get("language", [None])[0],
                    "genre_epub": doc.get("subject", [])
                }
                # Wenn wir keine ISBN hatten, nehmen wir die gefundene
                if not found_isbn:
                    found_isbn = final_data["isbn"]
        except Exception as e:
            print(f"  [API] OL Suche Fehler: {e}")

    # 2. SCHRITT: Detail-Abfrage via ISBN (für Ratings & Description)
    if found_isbn:
        details = get_details_via_api(found_isbn)
        if details:
            # Wir mergen die Details in unsere Suchergebnisse
            # Details überschreiben Suche (da meist präziser bei Description)
            for key, value in details.items():
                if value: # Nur befüllte Felder übernehmen
                    final_data[key] = value

            # Sicherstellen, dass die ISBN im Set ist
            if not final_data.get("isbn"):
                final_data["isbn"] = found_isbn

    return final_data if final_data else None


def get_details_via_api(isbn):
    """Holt die 'schweren' Daten: Ratings und Beschreibung."""
    url = f"{OL_API_URL}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        ol_key = f'ISBN:{isbn}'
        book_info = data.get(ol_key, {})

        if not book_info:
            return None

        # Beschreibung extrahieren (kann String oder Dict sein)
        raw_desc = book_info.get('description', "")
        description = raw_desc.get('value', raw_desc) if isinstance(raw_desc, dict) else raw_desc

        # Ratings extrahieren
        # Open Library liefert Ratings oft unter 'details' oder direkt im Buch-Objekt
        rating_data = book_info.get('ratings', {})
        if not rating_data and 'details' in book_info:
            rating_data = book_info['details'].get('ratings', {})

        return {
            "description": clean_description(description) if description else "",
            "stars_ol": rating_data.get("average"),
            "stars_ol_count": rating_data.get("count")
        }
    except Exception:
        return None

def enrich_from_open_library(manager):
    """
    Verarbeitet die Open Library Daten direkt für den Manager.
    """
    ol_results = search_open_library(
        title=manager.book.title,
        author=manager.authors,
        isbn=manager.book.isbn
    )

    if not ol_results:
        return

    # 1. Daten-Merge
    if not manager.book.isbn:
        manager.book.isbn = ol_results.get("isbn")

    # Ratings
    if ol_results.get("stars_ol"):
        manager.book.stars_ol = ol_results["stars_ol"]
    if ol_results.get("stars_ol_count"):
        manager.book.stars_ol_count = ol_results["stars_ol_count"]

    # 2. Beschreibung & Notizen (wie besprochen)
    new_desc = ol_results.get("description")
    if new_desc:
        if not manager.book.description or len(manager.book.description) < 10:
            manager.book.description = new_desc
        else:
            # Als Zusatz-Info in die Notes
            header = "\n--- Info (Open Library) ---\n"
            current_notes = manager.book.notes or ""
            if new_desc[:50] not in current_notes:
                manager.book.notes = (current_notes + header + new_desc).strip()

    return