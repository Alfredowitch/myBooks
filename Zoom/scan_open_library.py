"""
DATEI: open_library.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Sucht via Titel/Autor nach der ISBN und holt anschließend
              Ratings und Beschreibungen von OpenLibrary.
"""
import requests
from typing import Optional, Dict, Any, List
from Zoom.utils import clean_description

# Basis-URLs
OL_API_URL = "https://openlibrary.org/api/books"
OL_SEARCH_URL = "https://openlibrary.org/search.json"


def _query_ol_search(title: str, author: Any) -> Optional[str]:
    """Sucht via Titel und Autor nach einer ISBN."""
    if not title: return None

    q = title.replace(" ", "+")
    # Autor-String extrahieren (Erwarte List[Tuple] oder String)
    if isinstance(author, list) and author:
        # Wir nehmen den Nachnamen des ersten Autors
        a_str = author[0][1]
        q += f"&author={a_str.replace(' ', '+')}"
    elif isinstance(author, str) and author:
        q += f"&author={author.replace(' ', '+')}"

    try:
        resp = requests.get(OL_SEARCH_URL, params={'q': q, 'limit': 1}, timeout=5)
        data = resp.json()
        if data.get("docs"):
            isbns = data["docs"][0].get("isbn", [])
            return isbns[0] if isbns else None
    except Exception as e:
        print(f"  [API] OL Suche Fehler: {e}")
    return None


def fetch_ol_details(isbn: str) -> Dict[str, Any]:
    """Holt Ratings und Beschreibung via ISBN."""
    if not isbn: return {}

    url = f"{OL_API_URL}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        ol_key = f'ISBN:{isbn}'
        book_info = data.get(ol_key, {})

        if not book_info:
            return {}

        # Beschreibung extrahieren
        raw_desc = book_info.get('description', "")
        description = raw_desc.get('value', raw_desc) if isinstance(raw_desc, dict) else raw_desc

        # Ratings extrahieren
        rating_data = book_info.get('ratings', {})
        if not rating_data and 'details' in book_info:
            rating_data = book_info['details'].get('ratings', {})

        return {
            "isbn": isbn,
            "description": clean_description(description) if description else "",
            "rating_ol": float(rating_data.get("average", 0.0)),
            "rating_ol_count": int(rating_data.get("count", 0))
        }
    except Exception:
        return {}


def get_openlibrary_data(junior: Any) -> Dict[str, Any]:
    """
    Bereitet OpenLibrary-Daten für den merge_with-Prozess vor.
    Beachtet die Regeln für Beschreibungen und Notizen.
    """
    found_isbn = junior.isbn

    # 1. ISBN suchen, falls fehlt
    if not found_isbn:
        found_isbn = _query_ol_search(junior.title, junior.authors)

    if not found_isbn:
        return {}

    # 2. Details abrufen
    api_results = fetch_ol_details(found_isbn)
    if not api_results:
        return {}

    # 3. Logik für Beschreibung & Notizen
    new_desc = api_results.get("description")
    if new_desc:
        # Falls Junior noch keine (relevante) Beschreibung hat:
        if not junior.description or len(junior.description) < 10:
            # Wird via merge_with übernommen
            pass
        else:
            # Falls vorhanden: In Notizen vermerken (Attribut 'notes' in BookTData wird vorausgesetzt)
            header = "\n--- Info (Open Library) ---\n"
            current_notes = getattr(junior, 'notes', "") or ""

            # Nur hinzufügen, wenn nicht schon in Notizen vorhanden
            if new_desc[:50] not in current_notes:
                setattr(junior, 'notes', (current_notes + header + new_desc).strip())

            # Aus Result-Dict entfernen, damit merge_with die Hauptbeschreibung nicht überschreibt
            del api_results["description"]

    # --- 🕵️ DER ENTSCHEIDENDE DEBUG-CHECK ---
    if api_results:
        print("\n--- 🌐 OPEN LIBRARY API RAW DATA ---")
        for k, v in api_results.items():
            print(f"KEY: {k:<15} | VAL: {v} (Typ: {type(v).__name__})")
        print("------------------------------------\n")
    # --- DEBUG ENDE ---

    return api_results