import requests
import xml.etree.ElementTree as ET

# --- WICHTIG: ERSETZE DIESEN PLATZHALTER ---
# API Key von der Goodreads Developer Seite
GOODREADS_API_KEY = "YOUR_GOODREADS_API_KEY"


def get_rating_from_goodreads(isbn, api_key=GOODREADS_API_KEY):
    """
    Ruft die Buchbewertung von Goodreads über die ISBN ab.
    Gibt ein Tupel (average_rating, ratings_count) zurück oder (None, None) bei Fehlern.
    """

    # 1. API-URL zur Suche nach Buch-Informationen über die ISBN
    search_url = f"https://www.goodreads.com/book/title.xml?key={api_key}&isbn={isbn}"

    try:
        response = requests.get(search_url, timeout=5)
        response.raise_for_status()

        # 2. XML-Antwort parsen
        root = ET.fromstring(response.content)

        # Die Goodreads XML-Struktur ist: <GoodreadsResponse><book>...</book></GoodreadsResponse>
        book_element = root.find('book')
        if book_element is not None:
            # Finde durchschnittliches Rating (average_rating) und Anzahl der Ratings (ratings_count)
            avg_rating = book_element.findtext('average_rating')
            count_rating = book_element.findtext('ratings_count')

            # Konvertiere in numerische Typen
            avg_rating = float(avg_rating) if avg_rating else None
            count_rating = int(count_rating) if count_rating else None

            return avg_rating, count_rating

        return None, None

    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Goodreads Fehler (Netzwerk/HTTP): {e}")
        return None, None
    except ET.ParseError as e:
        print(f"DEBUG: Goodreads Fehler (XML-Parsing, ungültige Antwort): {e}")
        return None, None
    except Exception as e:
        # Fängt Fehler ab, z.B. wenn die ISBN nicht gefunden wurde und die API einen Fehlercode liefert
        print(f"DEBUG: Goodreads Fehler (Allgemein): {e}")
        return None, None