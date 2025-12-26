"""
DATEI: book_scanner.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Scannt E-Book-Dateien, extrahiert Metadaten, fragt APIs ab
              und setzt einen Versionsstempel für die Datenqualität.
"""

import os
import sys
import re
import html
from typing import List

# IMPORTIEREN DER FUNKTIONEN AUS DEINEN MODULEN
MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Gemini'))
sys.path.append(MODULES_DIR)

try:
    from read_db_ebooks import get_db_metadata, search_books
    from save_db_ebooks import save_book_with_authors
    from read_file import extract_info_from_filename, derive_metadata_from_path
    from read_epub import get_epub_metadata
    from check import check_for_mismatch
    from read_pdf import get_book_cover

    # API Tools
    from google_books import get_book_data_by_isbn, search_isbn_only
    from open_library import fetch_open_library_data

    # Mappings & Models
    from regionMapping import determine_region
    from genreMapping import determine_single_genre
    from book_data_model import BookData
except ImportError as e:
    print(f"Fehler beim Modul-Import. Bitte Dateinamen prüfen: {e}")

# --- KONSTRUKTION ---
DB_PATH = r'M://books.db'
CURRENT_SCANNER_VERSION = "1.2.0"  # Dein neuer Versionsstempel
mismatch_list = []


def format_authors_for_display(normalized_authors):
    if not normalized_authors: return ""
    sorted_authors = sorted(normalized_authors, key=lambda x: x[1])
    author_strings = [f"{lastname} {firstname}".strip() for firstname, lastname in sorted_authors]
    return " & ".join(author_strings)


def clean_description(text):
    if not text:
        return ""
    # 1. HTML-Entities umwandeln (&lt; -> <, &nbsp; -> Leerzeichen)
    text = html.unescape(text)
    # 2. Block-Elemente durch Zeilenumbrüche ersetzen (bevor sie gelöscht werden)
    # Erwischt auch Tags mit Attributen wie <p class="description">
    text = re.sub(r'<(div|p|br|li|h[1-6])[^>]*>', '\n', text, flags=re.IGNORECASE)
    # 3. Alle verbleibenden Tags restlos entfernen
    text = re.sub(r'<[^>]+>', '', text)
    # 4. Whitespace-Kosmetik
    # Verhindert, dass 10 Leerzeilen entstehen, falls viele <p> hintereinander waren
    text = re.sub(r'\n\s*\n+', '\n\n', text)

    return text.strip()


def scan_ebooks(base):
    """
    Scannt E-Book-Dateien und reichert sie mit API-Daten an.
    """
    for root, dirs, files in os.walk(base):
        for file in files:
            file_path = os.path.join(root, file)

            if not file.endswith(('.epub', '.pdf', '.mobi')):
                continue

            print("\n" + "=" * 40)
            print(f"VERARBEITE: {file}")

            # --- SCHRITT A: DB PRÜFUNG ---
            db_data_dict = get_db_metadata(file_path, db_path=DB_PATH)

            # Optimierung: Wir scannen neu, wenn Version < 1.1.0 oder unvollständig
            existing_version = db_data_dict.get('scanner_version') if db_data_dict else None

            if db_data_dict and db_data_dict.get('is_complete') and existing_version == CURRENT_SCANNER_VERSION:
                print(f"INFO: Bereits mit {CURRENT_SCANNER_VERSION} erfasst. Überspringe.")
                continue

            # Initialisiere Objekt
            if db_data_dict:
                book_data = BookData.from_dict(db_data_dict)
            else:
                book_data = BookData()
                book_data.file_path = file_path

            # Setze den aktuellen Scanner-Versionsstempel
            book_data.scanner_version = CURRENT_SCANNER_VERSION

            # --- SCHRITT B: DATEINAME & PFAD ---
            # Info vom Pfad
            lang, reg, gen, path_keywords = derive_metadata_from_path(file_path)
            book_data.language = lang or book_data.language
            book_data.genre = gen or book_data.genre
            book_data.region = reg or book_data.region
            if path_keywords:
                book_data.keywords = list(set((book_data.keywords or []) + path_keywords))
            # Info vom Filenamen
            file_info = extract_info_from_filename(file_path)
            file_metadata = BookData.from_dict(file_info)
            book_data.merge_with(file_metadata)

            if book_data.description and getattr(book_data, 'is_manual_description', 0) == 0:
                book_data.description = clean_description(book_data.description)

            # --- SCHRITT C: EPUB-METADATEN ---
            if file.endswith('.epub'):
                try:
                    epub_raw = get_epub_metadata(file_path)
                    epub_metadata = BookData.from_dict(epub_raw)

                    # Mismatch Check
                    mismatch_entry = check_for_mismatch(
                        file_path=file_path,
                        file_title=file_info.get('title'),
                        epub_title=epub_raw.get('title'),
                        file_authors=file_info.get('authors', []),
                        epub_authors=epub_raw.get('authors', [])
                    )
                    if mismatch_entry:
                        mismatch_list.append(mismatch_entry)

                    book_data.merge_with(epub_metadata)
                except Exception as e:
                    print(f"Fehler beim EPUB-Lesen: {e}")

            # --- SCHRITT D: API-LOGIK (DER "VERSTAND") ---
            # 1. ISBN-Suche falls nötig
            if not book_data.isbn:
                last_name = book_data.authors[0][1] if book_data.authors else ""
                found_isbn = search_isbn_only(book_data.title, last_name, lang=book_data.language)
                if found_isbn:
                    book_data.isbn = found_isbn
                    print(f"  -> ISBN gefunden: {found_isbn}")

            # 2. Google Books Details mit ISBN
            if book_data.isbn:
                api_data = get_book_data_by_isbn(book_data.isbn)

                # Ratings & Jahr (immer aktualisieren/ergänzen)
                book_data.average_rating = api_data.get('average_rating') or book_data.average_rating
                book_data.ratings_count = api_data.get('ratings_count') or book_data.ratings_count
                book_data.year = api_data.get('year') or book_data.year
                print(f"  -> Rating von GoogleBooks gefunden: {book_data.average_rating}")

                # Beschreibung (Smart Merge)
                new_desc = api_data.get('description')
                clean_desc = clean_description(new_desc)
                if new_desc and getattr(book_data, 'is_manual_description', 0) == 0:
                    book_data.description = clean_desc

            # 3. OpenLibrary als Fallback für Beschreibung
            ol_data = fetch_open_library_data(book_data.title, book_data.authors, book_data.isbn)
            if ol_data:
                # 1. ISBN ergänzen, falls wir vorher keine hatten
                if not book_data.isbn and ol_data.get('ol_isbn'):
                    book_data.isbn = ol_data['ol_isbn']
                    print(f"  -> ISBN gefunden mit OpenLibrary: {found_isbn}")
                # 2. Ratings IMMER übernehmen (Zusatzinfo)
                book_data.rating_ol = ol_data.get('ol_rating', 0.0)
                print(f"  -> Rating von OpenLibrary: {book_data.rating_ol}")
                book_data.ratings_count_ol = ol_data.get('ol_count', 0)
                # 3. Description von Google bleibt, aber wir notieren dann Open Library in Notizen
                if clean_desc:
                    # Fall A: Google hat schon eine Description geliefert
                    if book_data.description or getattr(book_data, 'is_manual_description', 0) == 1:
                        # NUR ergänzen, wenn der Text nicht schon in den Notizen steht
                        current_notes = book_data.notes or ""
                        # Wir prüfen auf die ersten 100 Zeichen, um Duplikate zu vermeiden
                        if clean_desc[:100] not in current_notes:
                            header = "--- API ERGÄNZUNG (OpenLibrary) ---"
                            book_data.notes = f"{current_notes}\n\n{header}\n{clean_desc}".strip()
                    # Fall B: Google war leer, also wird OL die Haupt-Description
                    elif getattr(book_data, 'is_manual_description', 0) == 0:
                        book_data.description = clean_desc

            # --- SCHRITT E: MAPPING ---
            if not book_data.region:
                book_data.region = determine_region(getattr(book_data, 'categories', []),
                                                        book_data.description or "")
            if not book_data.genre:
                book_data.genre = determine_single_genre([getattr(book_data, 'genre_epub', None)],
                                                             getattr(book_data, 'categories', []),
                                                             book_data.description or "") or "Unbekannt"

            # --- SCHRITT G: SPEICHERN ---
            try:
                save_book_with_authors(book_data, db_path=DB_PATH)
                print(f"✓ Gespeichert [v{CURRENT_SCANNER_VERSION}]: {book_data.title}")
            except Exception as e:
                print(f"❌ Fehler beim Speichern: {e}")

    # --- REPORTING ---
    if mismatch_list:
        report_path = os.path.join(base, 'Metadaten_Report.txt')
        with open(report_path, 'w', encoding="utf-8") as f:
            for item in mismatch_list:
                # Wir nutzen jetzt den im Dictionary gespeicherten Pfad
                f.write(f"Pfad: {item['full_path']}\n")
                f.write(f"Datei: {item['filename']}\n")

                if 'file_author' in item:
                    # Hier nutzen wir das & Format für die Anzeige im Report
                    f_auth = format_authors_for_display(item['file_author'])
                    e_auth = format_authors_for_display(item['epub_author'])
                    f.write(f" ❌ Autor: {f_auth} vs. {e_auth}\n")

                # (Optional) Titel-Mismatch mitschreiben
                if 'file_title' in item:
                    f.write(f" ❌ Titel: {item['file_title']} vs. {item['epub_title']}\n")

                f.write("-" * 30 + "\n")  # Trenner für bessere Übersicht


if __name__ == "__main__":
    base_path = (r"D:\Bücher\Business")
    scan_ebooks(base_path)