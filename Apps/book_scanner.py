"""
DATEI: book_scanner.py
PROJEKT: MyBook-Management (v1.3.2)
"""
import os
from tqdm import tqdm


try:
    from Gemini.read_file import extract_info_from_filename, derive_metadata_from_path
    from Gemini.read_epub import enrich_from_epub, get_epub_metadata
    from Gemini.check import check_for_mismatch
    from Gemini.read_pdf import get_book_cover
    from Gemini.file_utils import sanitize_path, build_perfect_filename, DB_PATH, EBOOK_BASE

    # API Tools
    from Gemini.google_books import enrich_from_google_books
    from Gemini.open_library import enrich_from_open_library

    # Mappings & Models
    from Gemini.genreMapping import extract_genre_and_keywords
    from Apps.book_data import BookData

except ImportError as e:
    print(f"Fehler beim Modul-Import. Bitte Dateinamen prüfen: {e}")

# --- KONSTRUKTION ---
CURRENT_SCANNER_VERSION = "1.3.2"
mismatch_list = []

def format_authors_for_display(normalized_authors):
    if not normalized_authors: return ""
    sorted_authors = sorted(normalized_authors, key=lambda x: x[1])
    author_strings = [f"{lastname} {firstname}".strip() for firstname, lastname in sorted_authors]
    return " & ".join(author_strings)


def write_mismatch_report(base_path):
    """Schreibt alle gesammelten Mismatches und Fehler in eine Textdatei."""
    if not mismatch_list:
        print("Keine Mismatches gefunden. Kein Report erstellt.")
        return

    report_path = sanitize_path(os.path.join(base_path, 'Metadaten_Report.txt'))
    try:
        with open(report_path, 'w', encoding="utf-8") as f:
            f.write(f"--- METADATEN REPORT ({len(mismatch_list)} Einträge) ---\n\n")
            for item in mismatch_list:
                # NEU: Buch-ID und Titel ganz oben, falls vorhanden
                if 'Buch-ID' in item:
                    f.write(f"ID: {item['Buch-ID']}\n")
                if 'title' in item:
                    f.write(f"Titel: {item['title']}\n")
                f.write(f"Pfad: {item.get('full_path', 'N/A')}\n")
                f.write(f"Datei: {item.get('filename', 'N/A')}\n")

                # Autor Mismatch
                if 'file_author' in item:
                    f_auth = format_authors_for_display(item['file_author'])
                    e_auth = format_authors_for_display(item['epub_author'])
                    f.write(f" ❌ Autor: {f_auth} vs. {e_auth}\n")

                # Titel Mismatch
                if 'file_title' in item:
                    f.write(f" ❌ Titel: {item['file_title']} vs. {item['epub_title']}\n")

                # NEU: Fehler/Notizen (z.B. DUPLICATE_FILE oder Scan-Fehler)
                if 'note' in item:
                    f.write(f" ℹ️ Info: {item['note']}\n")

                f.write("-" * 30 + "\n")
        print(f"✅ Report unter {report_path} gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Schreiben des Reports: {e}")

# ----------------------------------------------------------------------
# SINGLE SCAN IN SCHRITTEN
# ----------------------------------------------------------------------
def scan_single_book(file_path):
    if not os.path.exists(file_path):
        return None

    # --- SCHRITT A: DB CHECK ---
    book_data = BookData.load_by_path(file_path)
    db_version = book_data.scanner_version if book_data else "NEU"

    if not book_data:
        book_data = BookData(path=file_path)
    elif book_data.is_complete and db_version == CURRENT_SCANNER_VERSION:
        return book_data

    is_upgrade = (str(db_version) != str(CURRENT_SCANNER_VERSION))
    book_data.scanner_version = CURRENT_SCANNER_VERSION

    # --- SCHRITT B: DATEI & PFAD ANALYSE ---
    file_info = extract_info_from_filename(file_path)
    path_info = derive_metadata_from_path(file_path)

    # WICHTIG: Die Endung aus der echten Datei sichern
    book_data.extension = file_info.get('extension', '.epub')

    if db_version == "NEU" or is_upgrade:
        book_data.merge_with(BookData.from_dict(file_info))
        book_data.merge_with(BookData.from_dict(path_info))
    else:
        book_data.merge_with(BookData.from_dict(file_info))

    book_data.path = sanitize_path(file_path)

    # --- SCHRITT C: METADATEN-ANREICHERUNG (EPUB & APIs) ---
    if book_data.extension.lower() == '.epub':
        epub_raw = get_epub_metadata(file_path)

        # RESCUE-CHECK
        if epub_raw and '_RESCUED_AS_PDF' in epub_raw:
            new_path = epub_raw['_RESCUED_AS_PDF']
            if book_data.id > 0:
                BookData.fix_path_ext(file_path, new_path)
            tqdm.write(f"  [RESCUE] Datei war PDF. Neustart als PDF: {os.path.basename(new_path)}")
            return scan_single_book(new_path)

        if epub_raw:
            mismatch_entry = check_for_mismatch(
                file_path=file_path,
                file_title=book_data.title,
                epub_title=epub_raw.get('title'),
                file_authors=book_data.authors,
                epub_authors=epub_raw.get('authors', [])
            )
            if mismatch_entry:
                mismatch_list.append(mismatch_entry)
            book_data.merge_with(BookData.from_dict(epub_raw))

    # APIs
    current_isbn = getattr(book_data, 'isbn', None)
    has_valid_isbn = current_isbn and len(str(current_isbn).strip()) > 5
    if not has_valid_isbn:
        book_data = enrich_from_google_books(book_data)
        if not getattr(book_data, 'isbn', None):
            book_data = enrich_from_open_library(book_data)
    else:
        # Optionaler Log für den Debug-Modus
        # tqdm.write(f"  [CACHE] ISBN {current_isbn} vorhanden – API übersprungen.")
        pass

    # --- SCHRITT D: KLASSIFIZIERUNG ---
    desc = getattr(book_data, 'description', "")
    src_genres = getattr(book_data, 'genre_epub', [])
    if isinstance(src_genres, str): src_genres = [src_genres]
    cats = getattr(book_data, 'categories', [])

    final_genre, extra_keys = extract_genre_and_keywords(src_genres, cats, desc)
    if final_genre and book_data.is_field_empty('genre', book_data.genre):
        book_data.genre = final_genre

    if extra_keys and book_data.keywords is not None:
        if isinstance(book_data.keywords, set):
            book_data.keywords.update(extra_keys)
        else:
            for k in extra_keys:
                if k not in book_data.keywords: book_data.keywords.append(k)

    # --- SCHRITT E: FINALE NORMALISIERUNG (DATEINAME) ---
    new_filename = build_perfect_filename(book_data)
    directory = os.path.dirname(book_data.path)
    new_path = sanitize_path(os.path.join(directory, new_filename))

    if book_data.path != new_path:
        if os.path.exists(new_path):
            # FIX: Hier nutzen wir jetzt new_filename statt der alten file_extension Variable
            name, ext = os.path.splitext(new_filename)
            new_path = sanitize_path(os.path.join(directory, f"{name}-KOPIE{ext}"))
            mismatch_list.append({
                'filename': os.path.basename(book_data.path),
                'full_path': book_data.path,
                'error_type': 'DUPLICATE_FILE',
                'note': f"Kopie erstellt: {new_filename}"
            })
        try:
            os.rename(book_data.path, new_path)
            book_data.path = new_path
            tqdm.write(f"  [RENAME] -> {new_filename}")
        except OSError as e:
            tqdm.write(f"  [ERROR] Rename fehlgeschlagen: {e}")

    return book_data

def scan_ebooks(base):
    print("Sammle Dateien...")
    files_to_scan = []
    for root, _, files in os.walk(base):
        for file in files:
            if file.lower().endswith(('.epub', '.pdf', '.mobi')):
                files_to_scan.append(os.path.join(root, file))

    files_to_scan.sort()
    current_parent = ""
    processed = 0

    for file_path in tqdm(files_to_scan, desc="Scan Fortschritt", unit="Buch"):
        try:
            parent = sanitize_path(os.path.dirname(file_path))
            if parent != current_parent:
                current_parent = parent
                processed = 0

            book_data = scan_single_book(file_path)
            if book_data:
                book_data.save()
                processed += 1
        except Exception as e:
            tqdm.write(f"❌ Fehler bei: {file_path}\n   Grund: {e}")

    write_mismatch_report(base)




if __name__ == "__main__":
    target_path = sanitize_path("D:/Bücher/French")
    # Zum Reparieren: repair_total_library(target_path)
    scan_ebooks(target_path)
    # repair_total_library(target_path)