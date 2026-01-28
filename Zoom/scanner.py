"""
DATEI: book_scanner.py
PROJEKT: MyBook-Management (v1.4.0)
BESCHREIBUNG: Der neue Scanner, der v1.3 Logik in v1.4 Atome gießt.
"""
import os
import sqlite3
from typing import Optional

# Importe deiner v1.4 Struktur
from Zoom.book_data_old import BookData, BookTData, WorkTData, SerieTData
from Zoom.scan_file import extract_info_from_filename, derive_metadata_from_path, get_final_language
from Zoom.utils import DB_PATH, sanitize_path


def scan_single_book(file_path: str) -> Optional[BookData]:
    """
    Scannt ein Buch und befüllt die v1.4 Atome.
    Sucht automatisch nach existierenden Werken (Heilung).
    """
    if not os.path.exists(file_path):
        return None

    # 1. INITIALISIERUNG
    # Wir starten mit leeren Atomen
    book_atom = BookTData(path=sanitize_path(file_path))
    work_atom = WorkTData()
    serie_atom = SerieTData()

    # 2. EXTRAKTION (Deine v1.3 Logik)
    file_info = extract_info_from_filename(file_path)
    path_info = derive_metadata_from_path(file_path)

    # --- BEFÜLLEN DES GELBEN ATOMS (Book) ---
    book_atom.title = file_info.get('title', '')
    book_atom.series_name = file_info.get('series_name', '')
    book_atom.series_number = file_info.get('series_number', '')
    book_atom.year = file_info.get('year', '')
    book_atom.ext = file_info.get('extension', '.epub')
    book_atom.language = path_info.get('language', 'de')

    # --- BEFÜLLEN DES GRÜNEN ATOMS (Work-Vorschau) ---
    work_atom.title = book_atom.title
    work_atom.genre = path_info.get('genre', '')
    work_atom.regions = path_info.get('region', '')
    # Keywords aus dem Pfad (Business-Hierarchie etc.)
    if path_info.get('keywords'):
        work_atom.keywords = ", ".join(path_info['keywords'])

    # --- BEFÜLLEN DES BLAUEN ATOMS (Serie-Vorschau) ---
    if book_atom.series_name:
        serie_atom.name = book_atom.series_name

    # 3. AUTO-HEILUNG (Re-Migration)
    # Bevor wir ein neues Werk anlegen, schauen wir, ob es das schon gibt
    manager = BookData(book=book_atom, work=work_atom, serie=serie_atom)
    manager.authors = file_info.get('authors', [])

    found_work_id = _find_existing_work(book_atom.title, book_atom.series_name)

    if found_work_id:
        # Buch an bestehendes Werk hängen
        book_atom.work_id = found_work_id
        # Wir laden die echten Werk-Daten aus der DB, um das Vorschau-Atom zu ersetzen
        full_data = _load_work_and_serie_by_id(found_work_id)
        if full_data:
            manager.work = full_data.work
            manager.serie = full_data.serie
            manager.authors = full_data.authors
            print(f"🔗 Buch automatisch an existierendes Werk gekoppelt: {found_work_id}")

    return manager


def _find_existing_work(title: str, series_name: str) -> Optional[int]:
    """Sucht in der DB nach einem passenden Werk."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql = """
        SELECT w.id FROM works w
        LEFT JOIN series s ON w.series_id = s.id
        WHERE (w.title = ? OR w.title_de = ? OR w.title_en = ?)
    """
    params = [title, title, title]

    if series_name:
        sql += " AND s.name = ?"
        params.append(series_name)

    cursor.execute(sql, params)
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None


def _load_work_and_serie_by_id(work_id: int) -> Optional[BookData]:
    """Hilfsmethode, um nur den grünen und blauen Teil zu laden."""
    # Hier nutzen wir eine vereinfachte Version deiner load_by_path Logik,
    # nur dass wir über die work_id gehen.
    # (Implementierung analog zu BookData.load_by_path, nur mit WHERE w.id = ?)
    pass
