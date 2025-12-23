import os

# IMPORTIEREN DER FUNKTIONEN AUS DEINEN NEUEN MODULEN
# --- Importiere vorhandene Funktionen ---
try:
    # Passe diese Importe an deine tatsächlichen Modulnamen an
    # Füge google_books hinzu!
    from read_db_ebooks import get_db_metadata, search_books, get_first_book_entry
    from save_db_ebooks import save_book_with_authors, delete_book_from_db
    from read_file import extract_info_from_filename, derive_metadata_from_path
    from read_epub import get_epub_metadata
    from check import check_for_mismatch
    from read_pdf import get_book_cover
    from google_books import get_book_data_by_isbn  # <<< NEU: Für API-Daten
    from googleBooks import read_google_books
    from openLibrary import read_open_library
    from regionMapping import determine_region
    from genreMapping import determine_single_genre
    from book_data_model import BookMetadata
except ImportError as e:
    # Kritischer Fehler: Zeige eine Meldung und beende das Programm
    print(f"Fehler beim Modul-Import. Bitte Dateinamen prüfen: {e}")
    # messagebox.showerror("Importfehler", f"Wichtige Module fehlen. App kann nicht starten: {e}")
    # sys.exit(1)


# --- GLOBALE VARIABLEN ---
# Hinweis: Du musst DB_PATH und die Funktionen aus den Modulen importieren
DB_PATH = r'M://books.db'
mismatch_list = []  # Liste für problematische Dateien


def format_authors_for_display(normalized_authors):
    # ... (Code, der die Autoren nach Nachnamen sortiert) ...
    sorted_authors = sorted(normalized_authors, key=lambda x: x[1])

    author_strings = []
    # ... (Schleife, die 'Nachname Vorname' erzeugt) ...
    for firstname, lastname in sorted_authors:
        formatted_name = f"{lastname} {firstname}".strip()
        if formatted_name:
            author_strings.append(formatted_name)

    # 🚨 Wichtig: Verwendung von ' & ' als Trennzeichen
    return " & ".join(author_strings)

# --- DEINE FUNKTIONEN HIER EINFÜGEN (für diesen Kontext) ---
# Hier füge ich die neu entwickelten Funktionen (check_db_for_isbn, etc.) nur als Platzhalter ein.
# In deinem finalen Skript musst du sie als Imports verwenden!
# ... (Hier die Platzhalter für check_db_for_isbn, extract_metadata_from_filename, etc.) ...
# ... (Hier die neuen Mapping-Funktionen, da sie für die Konsolidierung benötigt werden) ...
# FÜGE HIER DIE FUNKTIONEN determine_single_genre und determine_region EIN
# ...

def scan_ebooks(base, sp=None, genre=None, region=None, series=None):
    """
    Scannt E-Book-Dateien, extrahiert Metadaten, fragt APIs ab (nur bei fehlenden Daten)
    und speichert alles in der Datenbank.
    """


    for root, dirs, files in os.walk(base):
        for file in files:
            file_path = os.path.join(root, file)

            if not file.endswith(('.epub', '.pdf', '.mobi')):
                continue

            print("----------------------")
            print(f"Verarbeite: {file}")
            
            # --- SCHRITT A: DB PRÜFUNG (READ_DB) ---
            # get_db_metadata ist die neue, saubere Funktion (ersetzt check_db_for_isbn)
            db_data_dict = get_db_metadata(file_path, db_path=DB_PATH)

            if db_data_dict and db_data_dict.get('is_complete'):
                print("INFO: Buch in DB als komplett markiert. Überspringe.")
                continue

            # INITIALISIERE DAS OBJEKT STATT EINEM DICT
            # Wir nutzen from_dict, um vorhandene DB-Daten (falls da) direkt zu laden
            if db_data_dict:
                book_metadata = BookMetadata.from_dict(db_data_dict)
            else:
                book_metadata = BookMetadata()
                book_metadata.file_path = file_path

            # --- SCHRITT B: DATEINAMEN-EXTRAKTION (READ_FILE) ---

            # Initialisiere der anderen Buch-Informationen aus dem Dateinamen
            file_info = extract_info_from_filename(file_path)  # Nutze die neue, korrekte Funktion
            # Wir erstellen ein temporäres Buch-Objekt für die Dateinamen-Daten und mergen es
            file_metadata = BookMetadata.from_dict(file_info)
            # aus dem Pfad holen wir die Sprache, Region, Genre und Keywords aus Business-Unterordner
            lang, reg, gen, path_keywords = derive_metadata_from_path(file_path)
            # Manuelle Pfad-Daten ergänzen
            if lang:
                book_metadata.language = lang
            if gen:
                book_metadata.genre = gen
            if reg:
                book_metadata.region = reg
            if path_keywords:
                if not book_metadata.keywords:
                    book_metadata.keywords = []
                for kw in path_keywords:  # Verhindert Dubletten
                    if kw not in book_metadata.keywords:
                        book_metadata.keywords.append(kw)


            # Merge: Dateiname hat hohe Priorität für Titel/Autor
            book_metadata.merge_with(file_metadata)


            # --- SCHRITT C: EPUB-METADATEN (READ_EPUB) ---
            if file.endswith('.epub'):
                try:
                    epub_raw = get_epub_metadata(file_path)
                    epub_metadata = BookMetadata.from_dict(epub_raw)

                    # Mismatch Check (bevor wir mergen)
                    mismatch_entry = check_for_mismatch(
                        file_path=file_path,
                        file_title=file_info.get('title'),
                        epub_title=epub_raw.get('title'),
                        file_authors=file_info.get('authors', []),
                        epub_authors=epub_raw.get('authors', [])
                    )
                    if mismatch_entry:
                        mismatch_list.append(mismatch_entry)

                        # Jetzt die EPUB-Daten einpflegen
                    book_metadata.merge_with(epub_metadata)
                except Exception as e:
                    print(f"Fehler beim EPUB-Lesen: {e}")


            # --- SCHRITT D: API-SCAN (READ_GOOGLE_BOOKS, READ_OPEN_LIBRARY) ---
            # Wir prüfen die Attribute direkt am Objekt
            is_api_scan_needed = (book_metadata.ratings_count is None or
                                  book_metadata.description is None or
                                  book_metadata.isbn is None)

            if is_api_scan_needed:
                read_google_books(book_metadata, language=book_metadata.language)
                read_open_library(book_metadata)

            # --- SCHRITT E: DATEN-KONSOLIDIERUNG UND MAPPING ---
            # 1. Region-Mapping (Nur, wenn keine manuelle Region gesetzt wurde)
            if not book_metadata.region:
                book_metadata.region = determine_region(
                    getattr(book_metadata, 'categories', []),
                    book_metadata.description or ""
                )
            # 2. Genre-Konsolidierung (Das Genre, das in der DB gespeichert wird)
            if not book_metadata.genre:
                book_metadata.genre = determine_single_genre(
                    [getattr(book_metadata, 'genre_epub', None)],
                    getattr(book_metadata, 'categories', []),
                    book_metadata.description or ""
                )

            # --- SCHRITT F: DATENBANK-SPEICHERUNG ---
            try:
                # JETZT ÜBERGEBEN WIR DAS OBJEKT -> Fehler behoben!
                save_book_with_authors(book_metadata, db_path=DB_PATH)
                print(f"Gespeichert: {book_metadata.title}")
            except Exception as e:
                print(f"Fehler beim Speichern in DB: {e}")

    # ... (Rest der Funktion für den Mismatch-Report) ...
    print("\nAlle Prüfschritte abgeschlossen.")


    # Ausgabe der Liste von Dateien mit Problemen
    if mismatch_list:
        print("-" * 40)
        print("🚨 Metadaten-Diskrepanzen gefunden (Report.txt erstellt) 🚨")

        # Definiere den Pfad zur Report-Datei
        report_path = os.path.join(base, 'Metadaten_Report.txt')
        print(report_path)

        with open(report_path, 'w', encoding="utf-8") as f:
            for item in mismatch_list:
                f.write("-" * 50 + "\n")
                f.write(f"Datei: {item['filename']}\n")

                # 🚨 KORREKTUR DER AUTORENPRÜFUNG 🚨
                # Wir prüfen, ob der Schlüssel 'file_author' im Report-Item existiert.
                if 'file_author' in item and 'epub_author' in item:
                    # Wenn die Schlüssel existieren, wenden wir die Formatierung an.
                    # Die Formatierung (format_authors_for_display) muss natürlich auch in
                    # diesem Modul verfügbar sein (importiert oder definiert).
                    file_display = format_authors_for_display(item['file_author'])
                    epub_display = format_authors_for_display(item['epub_author'])

                    f.write(f"  ❌ Autor: Dateiname '{file_display}' vs. EPUB '{epub_display}'\n")

                # Titelprüfung (bleibt unverändert, da diese Felder immer zusammen existieren)
                if 'file_title' in item:
                    f.write(f"  ❌ Titel: Dateiname '{item['file_title']}' vs. EPUB '{item['epub_title']}'\n")

        print(f"Details wurden in '{report_path}' gespeichert.")

    else:
        print("\nAlle geprüften Autoren/Titel stimmen überein oder EPUB-Daten fehlen.")

    print("-" * 40)


if __name__ == "__main__":

    # Beispielaufruf
    # Pfad zu deinem Bücherverzeichnis auf BigDaddy
    #base_path = 'D:\\Bücher\\Business\\Biographien'
    #base_path = r'D:\Bücher\Deutsch\A\Alexander Oetker'
    # base_path = r'D:\Bücher\Deutsch\A'
    # Pfad zu deinem Bücherverzeichnis auf der Synology
    base_path = r"D:\Bücher\French\_sortiertGenre"
    scan_ebooks(base_path)