import sqlite3
import os
import re
from pathlib import Path
from Zoom.utils import AUDIO_BASE, DB_PATH, slugify

# Nutze deine bestehenden Atome
from Audio.book_data import BookData

def scan_audiobooks_to_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 0. Sicherstellen, dass die Tabelle existiert
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_id INTEGER,
            title TEXT,
            language TEXT,
            path TEXT UNIQUE,
            cover_path TEXT,
            length_hours REAL,
            size_gb REAL,
            year INTEGER,
            speaker TEXT,
            description TEXT
        );
    """)

    audio_root = Path(AUDIO_BASE) / "Hörbuch-De"
    extensions = {'.mp3', '.m4b', '.m4a'}

    for root, dirs, files in os.walk(audio_root):
        audio_files = [f for f in files if Path(f).suffix.lower() in extensions]
        if not audio_files:
            continue

        path_obj = Path(root)
        folder_name = path_obj.name

        # Pfad-Analyse
        parts = path_obj.relative_to(audio_root).parts
        if len(parts) < 2: continue

        author_name = parts[0]
        serie_name = parts[1] if len(parts) == 3 and parts[1].lower() != "romane" else None
        search_title = clean_audio_title(folder_name)

        # 1. Werk finden oder anlegen
        cursor.execute("SELECT id FROM works WHERE title LIKE ?", (f"%{search_title}%",))
        work_res = cursor.fetchone()

        if work_res:
            work_id = work_res[0]
        else:
            new_work = WorkTData(title=search_title)
            temp_mgr = BookData(work=new_work)

            if " " in author_name:
                fn, ln = author_name.rsplit(" ", 1)
                temp_mgr.book.authors = [(fn, ln)]
            else:
                temp_mgr.book.authors = [("", author_name)]

            if serie_name:
                mapped_series = SERIES_MAPPING.get(serie_name, serie_name)
                cursor.execute("SELECT id FROM series WHERE name=? OR name_de=?", (mapped_series, mapped_series))
                s_res = cursor.fetchone()
                if s_res:
                    temp_mgr.work.series_id = s_res[0]

            work_id = temp_mgr._find_or_create_work(cursor)
            temp_mgr.reset_authors(temp_mgr.book.authors, work_id, cursor)

        # 2. Cover & Metadaten
        cover_file = next((f for f in files if Path(f).suffix.lower() in {'.jpg', '.png', '.jpeg'}), "")
        cover_path = str(path_obj / cover_file) if cover_file else ""

        # Größe berechnen (Optional, aber nützlich)
        total_size = sum(os.path.getsize(os.path.join(root, f)) for f in files)
        size_gb = round(total_size / (1024 ** 3), 2)

        # 3. Speichern
        cursor.execute("""
            INSERT OR IGNORE INTO audios (work_id, title, path, cover_path, size_gb, speaker)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (work_id, folder_name, str(path_obj), cover_path, size_gb, ""))

    conn.commit()
    conn.close()
    print("Audio-Scan erfolgreich abgeschlossen.")