import os
import io
import sqlite3
import mutagen
from mutagen.mp3 import MP3
from PIL import Image
from pathlib import Path

# Stellt sicher, dass der Pfad richtig angeben wird.
audiodb_path = Path('M://audiobooks.db')
# Wir bauen den String für das Verzeichnis erst noch zusammen... und verwenden dann Path()
AUDIOBOOKS_PATH = "M:/Hörbuch-"
print(AUDIOBOOKS_PATH)


def get_audio_length(folder):
    """Berechnet die gesamte Länge aller MP3-Dateien im Ordner."""
    total_length = 0
    for file in os.listdir(folder):
        if file.endswith(".mp3"):
            try:
                audio = MP3(os.path.join(folder, file))
                total_length += audio.info.length
            except mutagen.MutagenError:
                pass
    return round(total_length / 60, 2)


def parse_folder_structure(root, author_folder, title_folder):
    """Extrahiert Autor, Serie, Titel und mögliche Folge aus der Ordnerstruktur."""
    parts = author_folder.split()
    lastname = parts[-1]
    firstname = " ".join(parts[:-1])
    author = (firstname, lastname)
    series = None
    title = title_folder
    year = None
    episode = None

    parts = title_folder.split(" - ", 1)
    if len(parts) == 2:
        if parts[0].isdigit():
            episode = int(parts[0])
            title = parts[1]
        elif parts[0].isnumeric() and len(parts[0]) == 4:
            year = int(parts[0])
            title = parts[1]
        elif parts[0] == author_folder:
            title = parts[1]

    # Wenn es zwischen dem Autoren_path und dem Titel_path = win ein weiteres Verzeichnis gibt
    # dann könnte das die Serie oder Season sein.
    rel_path = os.path.relpath(root, author_folder)
    if "/" in rel_path or "\\" in rel_path:
        series_parts = rel_path.split(os.sep)
        if len(series_parts) >= 2:
            series = series_parts[0]
            title = series_parts[-1]

    return author, series, title, year, episode


def get_or_create_author(conn, author):
    """Prüft, ob ein Autor existiert, und legt ihn falls nötig an."""
    cursor = conn.cursor()
    firstname, lastname = author  # Entpacke das Tupel
    cursor.execute("SELECT id FROM authors WHERE firstname = ? AND lastname = ?", (firstname, lastname))
    author_id = cursor.fetchone()

    if not author_id:
        cursor.execute("INSERT INTO authors (firstname, lastname) VALUES (?, ?)", (firstname, lastname))
        conn.commit()
        author_id = cursor.lastrowid
    else:
        author_id = author_id[0]

    return author_id


def insert_audiobook_data(conn, author, series, title, year, episode, length, cover_path, language="IT"):
    """Fügt ein Audiobook in die Datenbank ein."""
    author_id = get_or_create_author(conn, author)
    if cover_path:
        # Direktes Einlesen des Bildes als Blob
        # with open(cover_path, "rb") as f:
        #    cover_blob = f.read()
        # Alternativ Einlesen mit PIL
        img = Image.open(cover_path)
        # Bild auf 200x200 skalieren, dh. weniger Pixel nach dem Mathematiker Cornelius Lanczos
        img = img.resize((200, 200), Image.LANCZOS)
        # In Bytes konvertieren
        byte_stream = io.BytesIO()
        if img.mode == 'RGBA' or img.mode == 'P':
            print(f"False Image Mode: {cover_path}")
            img = img.convert('RGB')
        img.save(byte_stream, format='JPEG', quality=85)  # Kompression!
        cover_blob = byte_stream.getvalue()
    else:
        cover_blob = None
    cursor = conn.cursor()
    # 1. Buch einfügen - falls nicht schon vorhanden
    sql = 'SELECT id FROM audiobooks WHERE author_id = ? AND title = ?'
    cursor.execute(sql, (author_id, title))
    res = cursor.fetchone()
    if not res:
        cursor.execute("""
            INSERT INTO audiobooks (author_id, title, series, year, episode, length, language, cover_path, cover_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (author_id, title, series, year, episode, length, language, cover_path, cover_blob))
    else:
        book_id = res[0]
        set_clause = "series = ?, year = ?, episode = ?, length = ?, language = ?, cover_path = ?, cover_blob = ?"
        cursor.execute(f'''UPDATE audiobooks
                                       SET {set_clause}
                                       WHERE id = ?''',
                       (series, year, episode, length, language, cover_path, cover_blob, book_id))

    conn.commit()


def finde_coverbild(pfad):
    pfad = Path(pfad)
    #print(pfad)
    for datei in os.listdir(pfad):
        if datei.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            #print(datei)
            cover_path = os.path.join(pfad, datei)
            return cover_path
    return None


def process_audiobooks():
    """Scant das Audiobook-Verzeichnis und speichert die Daten in der Datenbank."""
    conn = sqlite3.connect(audiodb_path)
    scope = ["En", "Fr", "Es", "It", "Business", "New Age", "Kinder"]
    scope2 = ["Business", "New Age", "Kinder"]
    scope2 = ["De"]
    for l in scope:
        start_path = AUDIOBOOKS_PATH + l
        start_path = Path(start_path)
        print(start_path)  # z.B. M:\Hörbuch-De
        old = ""
        for author_folder in os.listdir(start_path):
            # Holt sich alle Einträge im Verzeichnis start_path. Jeder Eintrag heißt hier author_folder.
            author_path = os.path.join(start_path, author_folder)
            #print(f"Author-Path:  {author_path}")
            if not os.path.isdir(author_path):
                continue
            # os.walk() läuft rekursiv durch den author_path-Ordner und liefert:
            # win: aktuelles Verzeichnis
            # dirs: Unterordner
            # files: alle Dateien im aktuellen win (= Author_folder, dann Titel_folder)
            for root, dirs, files in os.walk(author_path):
                #print(f"Root: {win}, Dir: {len(dirs)}, File: {len(files)}")
                """
                z.B. win: M:\Hörbuch-De\.sorted
                z.B: dirs: ['Barcelona', 'Baskenland', 'Bayern']
                z.B: files: File: ['RegionalKrimis.JPG']
                """
                if old != author_folder:
                    print(l + ": " + author_folder)
                    old = author_folder

                if any(f.endswith(".mp3") for f in files):
                    title_folder = os.path.basename(root)
                    #print(f"Root: {win}, A-Folder: {author_folder}, T-Folder: {title_folder}")
                    author, series, title, year, episode = parse_folder_structure(root, author_path, title_folder)
                    length = get_audio_length(root)
                    cover_path = finde_coverbild(root)
                    #print(cover_path)
                    insert_audiobook_data(conn, author, series, title, year, episode, length, cover_path, l)

    conn.close()


if __name__ == "__main__":
    process_audiobooks()
