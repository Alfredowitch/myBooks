import os
import sqlite3
import json
import requests

# ... (Weitere Imports, falls nötig) ...

# Konstanter Pfad zur Datenbank (sollte am Anfang des Skripts stehen)
DB_PATH = r'M://books.db'


# HINWEIS: Die Funktion check_db_for_api_metadata muss auch hier im Skript definiert sein!

def scan_ebooks(base, sp, genre='Krimi', region=None, series=None):
    """
    Scannt E-Book-Dateien, extrahiert Metadaten, fragt APIs ab (nur bei fehlenden Daten)
    und speichert alles in der Datenbank.
    """

    # Initialisierung der Pfade und manueller Vorgaben
    current_region_manuell = region
    # current_series = series # Nicht benötigt, da series_name_extracted verwendet wird

    for root, dirs, files in os.walk(base):
        for file in files:
            file_path = os.path.join(root, file)

            # 1. Initialisierung der Variablen für den Durchlauf
            # Diese Variablen werden entweder durch DB, interne Metadaten oder API befüllt
            determined_region = None
            determined_genres = []
            published_date = None
            average_rating = None
            ratings_count = None
            isbn = None
            final_search_title = None

            if file.endswith(('.epub', '.pdf', '.mobi')):

                # --- A. FRÜHESTE DB-PRÜFUNG: METADATEN KOMPLETT? ---
                existing_api_data = check_db_for_api_metadata(file_path)

                if existing_api_data:
                    # Metadaten sind in der DB vorhanden und vollständig. Variablen befüllen und API-Call überspringen.
                    isbn = existing_api_data.get('isbn')
                    published_date = existing_api_data.get('published_year')
                    try:
                        # JSON String aus DB -> Python Liste
                        determined_genres = json.loads(existing_api_data.get('api_genres', '[]'))
                    except:
                        determined_genres = []

                    average_rating = existing_api_data.get('api_average_rating')
                    ratings_count = existing_api_data.get('api_ratings_count')

                    # Wichtig: Die Funktion muss trotzdem den internen Scan durchlaufen,
                    # um Titel/Autoren/Serien aus Dateinamen zu prüfen (falls noch nicht in DB).
                    # 'is_api_scan_needed' wird unten auf False gesetzt.

                # --- B. INTERNE EXTRAKTION UND TITELBESTIMMUNG ---
                print("----------------------")
                print(file)
                authors, title_from_filename, series_name_extracted, series_number_extracted = extract_metadata_from_filename(
                    file)

                epub_isbn = None

                if file.endswith('.epub'):
                    title_from_epub = extract_title_from_epub(file_path)
                    final_search_title = title_from_epub if title_from_epub else title_from_filename

                    # Interne ISBN aus EPUB
                    epub_isbn = get_isbn_from_epub(file_path)

                    # Autoren-Fallback (wie in vorheriger Logik besprochen)
                    epub_author = extract_author_from_epub(file_path)
                    if authors is None or authors[0] == ("unknown", "author"):
                        if epub_author:
                            parts = [p.strip() for p in epub_author.split(',')]
                            if len(parts) == 2:
                                authors = [(parts[1], parts[0])]
                            else:
                                authors = [(epub_author, "")]
                        else:
                            authors = [("unknown", "author")]

                else:  # Für PDF/MOBI, verwenden wir den Titel aus dem Dateinamen
                    final_search_title = title_from_filename
                    if authors is None:
                        authors = [("no", "author")]

                if not final_search_title:
                    print(f"WARN: Kein Titel gefunden. Überspringe Datei: {file}")
                    continue

                # Setze die finale ISBN-Quelle: DB > EPUB > None
                if isbn is None and existing_api_data and existing_api_data.get('isbn'):
                    isbn = existing_api_data.get('isbn')  # Aus unvollständiger DB
                elif isbn is None:
                    isbn = epub_isbn  # Aus EPUB

                # --- C. EXTERN: API-Suche (NUR WENN DATEN UNVOLLSTÄNDIG) ---

                # Prüfen, ob wir die APIs noch aufrufen müssen.
                # Nur, wenn die DB beim initialen Check keine vollständigen Metadaten geliefert hat (existing_api_data is None).
                is_api_scan_needed = existing_api_data is None

                if is_api_scan_needed:

                    if isbn is None or "ISBN nicht gefunden" in str(isbn):
                        print("INFO: ISBN intern nicht gefunden. Starte externe Suche...")

                    if authors and authors[0][1] and final_search_title:
                        author_lastname = authors[0][1]

                        google_books_data = get_isbn_from_google_books(final_search_title, author_lastname)

                        if isinstance(google_books_data, dict):

                            # 1. Metadaten von Google Books übernehmen
                            google_isbn = google_books_data.get('isbn')
                            if google_isbn:
                                isbn = google_isbn  # Überschreibe interne/alte ISBN mit der API-ISBN

                            # 2. Datum auf das Jahr kürzen
                            raw_date = google_books_data.get('published_date')
                            published_year = raw_date.split('-')[0] if raw_date else None
                            published_date = published_year  # Befüllt die zentrale Variable

                            # 3. Genres von Google Books übernehmen
                            determined_genres = google_books_data.get('categories', [])

                            # 4. Region bestimmen
                            determined_region = determine_region(
                                determined_genres,
                                google_books_data.get('description')
                            )

                            # 5. Open Library Rating abrufen
                            if isbn:
                                average_rating, ratings_count = get_rating_from_open_library(isbn)
                                print(f"  INFO: Open Library Rating: {average_rating} ({ratings_count} Stimmen)")
                            else:
                                print("  WARN: ISBN extern auch nicht gefunden.")

                        else:
                            print("  WARN: Externe Suche (Google Books) lieferte keine Daten.")

                # --- D. DATENBANK-SPEICHERUNG ---

                # 4. Buch-Dictionary zur Speicherung zusammenstellen (nutzt die aktuell befüllten Variablen)
                book = {
                    'title': final_search_title,
                    'language': sp,
                    'path': file_path,
                    'isbn': isbn,
                    'genre': genre,
                    'series_number': series_number_extracted,
                    'series_name': series_name_extracted,

                    # API-Metadaten
                    'published_date': published_date,
                    'genres_api': determined_genres,
                    'average_rating': average_rating,
                    'ratings_count': ratings_count,

                    # WICHTIG: Manuelle Region hat Vorrang, sonst die automatisch bestimmte Region
                    'region_manuell': current_region_manuell if current_region_manuell else determined_region
                }

                # Buch mit Autoren in die Datenbank einfügen
                save_book_with_authors(book, authors)