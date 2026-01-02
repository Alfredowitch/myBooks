"""
DATEI: In save_db_ebooks.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Schreibt die Daten aus der Datenbank (SQL-Light), einschließlich scanner_version .
              Sicherheit eingebaut, dass bestehende id übernommen wird, aber id= 0 ignoriert wird.
"""
import sqlite3
import os
from dataclasses import asdict
from Apps.book_data import BookData

_DEFAULT_DB_PATH = r'M://books.db'

def update_db_path(old_path, new_path, db_path=None): # self raus, db_path rein
    """Ändert den Pfad eines Buch-Eintrags, behält aber die ID bei."""
    db_path = db_path or _DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path) # Nutzt das übergebene Argument
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE books SET path = ? WHERE path = ?", (new_path, old_path))
        if cursor.rowcount == 0:
            print(f"!!! KRITISCH: Update fehlgeschlagen für Pfad: {repr(data.path)}")
            # Gegenprobe: Existiert der Pfad überhaupt in der DB?
            cursor.execute("SELECT path FROM books WHERE path LIKE ?", (f"%{os.path.basename(data.path)}",))
            match = cursor.fetchone()
            if match:
                print(f"    Gefunden in DB: {repr(match[0])}")
                print(f"    Vergleich: {'IDENTISCH' if match[0] == data.path else 'UNTERSCHIEDLICH'}")
            else:
                print("    Pfad existiert gar nicht in der Datenbank (auch nicht per LIKE).")
        else:
            print(f"DEBUG: Update erfolgreich. {cursor.rowcount} Zeile(n) geändert.")
        conn.commit()
    finally:
        conn.close()

def save_book_with_authors(book: BookData, db_path=None):
    """
    Speichert oder aktualisiert ein Buch.
    Schützt manuelle Beschreibungen vor dem Überschreiben durch den Scanner.
    """
    db_path = db_path or _DEFAULT_DB_PATH
    title = book.title or "[Unbekannter Titel]"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # In deiner Datenbank ist die Spalte path mit Sicherheit als PRIMARY KEY definiert.
        # INSERT OR REPLACE INTO books erstellt entweder einen neuen Eintrag oder überschreibt den bestehenden.

        # 1. Das Buch-Objekt in ein Dictionary wandeln
        data = asdict(book)
        # Die Autoren nehmen wir kurz raus, weil sie in die Link-Tabelle müssen
        authors = data.pop('authors')

        # Falls wir eine leere id mitübergeben, nehmen wir diese Zeile raus:
        # Andernfalls zwingt "INSERT OR REPLACE" dazu, den alten Datensatz zu überschreiben,
        if hasattr(book, 'db_id') and book.db_id:
            data['id'] = book.db_id
        elif 'id' in data and (data['id'] is None or data['id'] == 0):
            # Falls eine leere ID drinsteht, nehmen wir sie raus,
            # damit SQLite sie nicht als "0" festschreibt.
            data.pop('id')

        # 2. BoodData Reinigen in clean_data, dh. nur keys übernehmen, die auch in der DB sind = db_columns.
        cursor.execute("PRAGMA table_info(books)")
        db_columns = [row[1] for row in cursor.fetchall()]
        clean_data = {k: v for k, v in data.items() if k in db_columns}

        # Falls 'keywords' oder andere Listen drin sind, müssen sie für SQLite zu Strings werden
        for key, value in clean_data.items():
            if isinstance(value, list):
                clean_data[key] = ", ".join(value)

        # 2. In die 'books' Tabelle schreiben
        columns = ", ".join(clean_data.keys())
        placeholders = ", ".join(["?"] * len(clean_data))
        sql = f"INSERT OR REPLACE INTO books ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, list(clean_data.values()))
        if cursor.rowcount == 0:
            print(f"!!! KRITISCH: SAVE ohne Autors fehlgeschlagen für Pfad: {repr(clean_data.path)}")
            # Gegenprobe: Existiert der Pfad überhaupt in der DB?
            cursor.execute("SELECT path FROM books WHERE path LIKE ?", (f"%{os.path.basename(clean_data.path)}",))
            match = cursor.fetchone()
            if match:
                print(f"    Gefunden in DB: {repr(match[0])}")
                print(f"    Vergleich: {'IDENTISCH' if match[0] == clean_data.path else 'UNTERSCHIEDLICH'}")
            else:
                print("    Pfad existiert gar nicht in der Datenbank (auch nicht per LIKE).")
        else:
            print(f"DEBUG: Update erfolgreich. {cursor.rowcount} Zeile(n) geändert.")

        # 3. DIE ID HOLEN (Der wichtige Teil für die Autoren!)
        book_id = cursor.lastrowid
        if not book_id or book_id == 0:
            # Sicherheits-Check: Falls lastrowid nicht greift, über den Pfad holen
            cursor.execute("SELECT id FROM books WHERE path = ?", (book.path,))
            book_id = cursor.fetchone()[0]

        # 4. Autoren verarbeiten (n:m Verknüpfung)
        # Wir löschen die alten Links und setzen sie neu (sauberster Weg für n Autoren)
        cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (book_id,))

        # book.authors ist Liste von Tupeln: [('Boris', 'Gloger'), ('Dieter', 'Rösner')]
        if book.authors:
            for fname, lname in book.authors:
                cursor.execute("SELECT id FROM authors WHERE firstname = ? AND lastname = ?", (fname, lname))
                a_row = cursor.fetchone()
                if a_row:
                    author_id = a_row['id']
                else:
                    cursor.execute("INSERT INTO authors (firstname, lastname) VALUES (?, ?)", (fname, lname))
                    author_id = cursor.lastrowid

                cursor.execute("INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)", (book_id, author_id))

        conn.commit()
        print(f"✓ DB: '{title}' gespeichert.")

    except sqlite3.Error as e:
        print(f"❌ DB FEHLER bei '{title}': {e}")
        conn.rollback()
    finally:
        conn.close()

def delete_orphan_authors(cursor):
    """Löscht Autoren, die mit keinem Buch mehr verknüpft sind."""
    cursor.execute("""
        DELETE FROM authors 
        WHERE id NOT IN (SELECT DISTINCT author_id FROM book_authors)
    """)
    return cursor.rowcount  # Gibt zurück, wie viele gelöscht wurden

# -------------------------------------------------------------------------
# if __name__ == "__main__":
#     # Beispiel-Daten für einen Testlauf (setze DB_PATH korrekt)
#     test_data = {
#         'file_path': 'D:\\Bücher\\Apps\\Ein neues Buch.epub',
#         'title': "Ein neues Buch",
#         'language': 'de',
#         'authors': [('Max', 'Mustermann'), ('Erika', 'Musterfrau')],
#         'isbn': '9781234567890',
#         'series_name': None,
#         'genre_manuell': 'Thriller',
#         'published_date': '2023',
#         'categories': ['Fiction / Thrillers / General'],
#         'average_rating': 4.5,
#         'ratings_count': 150,
#         'description': 'Ein spannender Thriller.'
#     }
#
#     # Du musst die DB und Tabellen vorher erstellen, um dies zu testen.
#     # save_book_with_authors(test_data)