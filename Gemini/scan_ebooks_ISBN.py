import os
import re
import json
from epub_api_alt import get_isbn_from_epub, extract_author_from_epub, extract_title_from_epub
from googleBooks import get_isbn_from_google_books
from googleBooks import get_description_and_genres_from_google_books
from openLibrary import get_rating_from_open_library
from save_db_ebooks import save_book_with_authors
from regionMapping import determine_region
from read_db_ebooks import check_db_for_isbn


# Liste für problematische Dateien, falls der Autor nicht übereinstimmt
mismatch_list = []

def scan_ebooks(base, sp, genre='Krimi', region=None, series=None):
    """
    Scannt E-Book-Dateien, extrahiert Metadaten, fragt APIs ab (nur bei fehlenden Daten)
    und speichert alles in der Datenbank.
    """

    # Initialisierung der manuellen Vorgaben aus dem Funktionsaufruf
    current_region_manuell = region  # Manuell gesetzte Region (oder None)
    current_genre_manuell = genre  # Manuell gesetztes Genre (oder 'Krimi')
    current_sp_manuell = sp  # Manuell gesetzte Sprache

    for root, dirs, files in os.walk(base):
        for file in files:
            file_path = os.path.join(root, file)

            # --- 1. INITIALISIERUNG DER VARIABLEN FÜR DIESEN BUCHDURCHLAUF ---
            determined_region = None
            determined_genres = []
            published_date = None
            average_rating = None
            ratings_count = None
            isbn = None
            final_search_title = None
            epub_isbn = None  # Interne EPUB ISBN

            authors = [("unknown", "author")]  # Default-Initialisierung
            title_from_filename = None
            series_name_extracted = None
            series_number_extracted = None

            if file.endswith(('.epub', '.pdf', '.mobi')):

                # --- A. FRÜHE DB-PRÜFUNG: METADATEN KOMPLETT? ---
                # check_db_for_api_metadata gibt das Dict zurück, wenn Metadaten da sind.
                existing_db_data = check_db_for_isbn(file_path)

                # Wenn Daten in der DB existieren, werden die Variablen hier befüllt
                if existing_db_data:
                    isbn = existing_db_data.get('isbn')
                    published_date = existing_db_data.get('published_year')
                    try:
                        determined_genres = json.loads(existing_db_data.get('api_genres', '[]'))
                    except:
                        determined_genres = []
                    average_rating = existing_db_data.get('api_average_rating')
                    ratings_count = existing_db_data.get('api_ratings_count')
                    # HINWEIS: determined_region wird NICHT geladen, da es nicht in der DB gespeichert wurde.

                # --- B. INTERNE EXTRAKTION (Muss immer laufen für Mismatch-Check/Titel) ---
                print("----------------------")
                print(file)
                authors, title_from_filename, series_name_extracted, series_number_extracted = extract_metadata_from_filename(
                    file)

                if file.endswith('.epub'):
                    title_from_epub = extract_title_from_epub(file_path)
                    final_search_title = title_from_epub if title_from_epub else title_from_filename

                    epub_isbn = get_isbn_from_epub(file_path)

                    # Autoren-Fallback (sollte die Logik in extract_metadata_from_filename ergänzen)
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

                if not final_search_title:
                    print(f"WARN: Kein Titel gefunden. Überspringe Datei: {file}")
                    continue

                # Setze die finale ISBN-Quelle: DB > EPUB > None
                if isbn is None and epub_isbn:
                    isbn = epub_isbn

                # --- C. EXTERN: API-Suche (Wird übersprungen, wenn DB-Daten da sind) ---

                # API-Scan wird nur benötigt, wenn die DB keine vollständigen Metadaten geliefert hat.
                is_api_scan_needed = existing_db_data is None

                if is_api_scan_needed:

                    # 1. Prüfen, ob ISBN fehlt, um extern zu suchen
                    if isbn is None or "ISBN nicht gefunden" in str(isbn):
                        print("INFO: ISBN intern nicht gefunden. Starte externe Suche...")

                    # Suche nur starten, wenn Autor und Titel bekannt sind
                    if authors and authors[0][1] and final_search_title:
                        author_lastname = authors[0][1]

                        google_books_data = get_isbn_from_google_books(final_search_title, author_lastname)

                        if isinstance(google_books_data, dict):

                            # Metadaten von Google Books übernehmen
                            google_isbn = google_books_data.get('isbn')
                            if google_isbn:
                                isbn = google_isbn  # Wichtig: Überschreibe interne/alte ISBN

                            # Datum, Genres, Region
                            raw_date = google_books_data.get('published_date')
                            published_year = raw_date.split('-')[0] if raw_date else None
                            published_date = published_year

                            determined_genres = google_books_data.get('categories', [])

                            determined_region = determine_region(
                                determined_genres,
                                google_books_data.get('description')
                            )

                            # Open Library Rating
                            if isbn:
                                average_rating, ratings_count = get_rating_from_open_library(isbn)
                                print(f"  INFO: Open Library Rating: {average_rating} ({ratings_count} Stimmen)")

                        else:
                            print("  WARN: Externe Suche (Google Books) lieferte keine Daten.")

                # --- D. DATENBANK-SPEICHERUNG ---

                # 4. Buch-Dictionary zur Speicherung zusammenstellen (nutzt die aktuell befüllten Variablen)
                book = {
                    'title': final_search_title,
                    'language': current_sp_manuell,  # Manuelle Sprache aus Aufruf
                    'path': file_path,
                    'isbn': isbn,
                    'genre': current_genre_manuell,  # Manuelles Genre aus Aufruf
                    'series_number': series_number_extracted,
                    'series_name': series_name_extracted,

                    # API-Metadaten
                    'published_date': published_date,
                    'genres_api': determined_genres,
                    'average_rating': average_rating,
                    'ratings_count': ratings_count,

                    # Manuelle Region aus Aufruf
                    'region_manuell': current_region_manuell if current_region_manuell else determined_region
                }

                # Buch mit Autoren in die Datenbank einfügen
                # Die save_book_with_authors-Funktion muss die Logik zum Überschreiben der manuellen Felder enthalten!
                save_book_with_authors(book, authors)

    # Ausgabe der Liste von Dateien mit Problemen
    if mismatch_list:
        print("-" * 40)
        print("🚨 Metadaten-Diskrepanzen gefunden (Report.txt erstellt) 🚨")
        f = os.path.join(base, 'Metadaten_Report.txt')
        print (f)
        with open(f, 'w', encoding="utf-8") as file:
            for item in mismatch_list:
                file.write("-" * 50 + "\n")
                file.write(f"Datei: {item['filename']}\n")

                if 'file_author' in item:
                    file.write(f"  ❌ Autor: Dateiname '{item['file_author']}' vs. EPUB '{item['epub_author']}'\n")

                if 'file_title' in item:
                    file.write(f"  ❌ Titel: Dateiname '{item['file_title']}' vs. EPUB '{item['epub_title']}'\n")

        print(f"Details wurden in '{f}' gespeichert.")

    else:
        print("\nAlle geprüften Autoren/Titel stimmen überein oder EPUB-Daten fehlen.")

    print("-" * 40)


# ... (Ende der scan_ebooks Funktion) ...

def check_for_mismatch(filename, file_authors, epub_author_string, file_title, epub_title):
    """
    Prüft auf Abweichungen zwischen Dateinamen-Metadaten und EPUB-Metadaten
    und fügt sie zur globalen mismatch_list hinzu.
    """
    mismatch = {}

    # Autorenprüfung
    # Da file_authors eine Liste von Tupeln ist, erstellen wir einen String zum Vergleich
    file_author_lastname = file_authors[0][1] if file_authors else "Unbekannt"

    # Vereinfachte Prüfung: EPUB-Autor ist oft "Nachname, Vorname"
    if epub_author_string and file_author_lastname.lower() not in epub_author_string.lower():
        mismatch['file_author'] = ", ".join([f"{v} {n}" for v, n in file_authors])
        mismatch['epub_author'] = epub_author_string

    # Titelprüfung (Hier nutzen wir die Toleranz der externen Suche nicht, sondern prüfen auf Gleichheit)
    if epub_title and file_title and file_title.lower() != epub_title.lower():
        # Ignoriere Umlaute und Akzente für einen sanften Vergleich (z.B. 'Chateau' vs 'Château')
        def normalize_text(text):
            text = text.lower()
            text = text.replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('é', 'e').replace('á', 'a')
            text = text.split(':')[0].split(';')[0].strip()  # Schneide Untertitel ab
            return text

        if normalize_text(file_title) != normalize_text(epub_title):
            mismatch['file_title'] = file_title
            mismatch['epub_title'] = epub_title

    # Wenn Diskrepanzen gefunden wurden, zur Liste hinzufügen
    if mismatch:
        mismatch['filename'] = filename
        mismatch_list.append(mismatch)

if __name__ == "__main__":

    # Beispielaufruf
    # Pfad zu deinem Bücherverzeichnis auf BigDaddy
    #base_path = 'D:\\Bücher\\Business\\Biographien'
    base_path = r'D:\Bücher\Deutsch\A\Alexander Oetker'
    # base_path = r'D:\Bücher\Deutsch\A'
    # Pfad zu deinem Bücherverzeichnis auf der Synology
    # base_path = "B:\\Deutsch"
    scan_ebooks(base_path, "de")