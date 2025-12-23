import requests

# Basis-URL für die Open Library API
# Dient zum Abrufen von Buchinformationen basierend auf ISBN, OLID, etc.
OL_BASE_URL = "https://openlibrary.org/api/books"


def read_open_library(book_metadata):
    """
    Ergänzt Ratings über die Open Library API direkt im BookMetadata-Objekt.
    """
    if not book_metadata:
        return book_metadata

    isbn = book_metadata.isbn

    # Prüfung, ob Ratings fehlen (None oder 0)
    ratings_missing = (book_metadata.average_rating is None or
                       book_metadata.ratings_count is None or
                       book_metadata.ratings_count == 0)

    if not isbn or len(str(isbn)) not in (10, 13):
        return book_metadata

    if not ratings_missing:
        return book_metadata

    print(f"  -> Suche Ratings via Open Library für ISBN: {isbn}")

    params = {
        'bibkeys': f'ISBN:{isbn}',
        'format': 'json',
        'jscmd': 'data'
    }

    try:
        response = requests.get(OL_BASE_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        ol_key = f'ISBN:{isbn}'
        book_info = data.get(ol_key, {})

        if book_info:
            details = book_info.get('details', book_info)
            rating_data = details.get('ratings', {})

            ol_avg = rating_data.get('average')
            ol_count = rating_data.get('count')

            if ol_avg is not None:
                book_metadata.average_rating = ol_avg
            if ol_count is not None:
                book_metadata.ratings_count = ol_count

            if ol_avg is not None or ol_count is not None:
                print("  INFO: Ratings via Open Library ergänzt.")

    except Exception as e:
        print(f"  WARN: Open Library Fehler: {e}")

    return book_metadata

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