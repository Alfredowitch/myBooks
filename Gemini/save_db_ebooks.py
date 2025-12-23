import sqlite3
import json
from typing import Dict, Any, Optional, List, Tuple

# WICHTIG: Import der zentralen Datenstruktur
from book_data_model import BookMetadata

# Interner Fallback-Pfad für Tests oder wenn kein Pfad übergeben wird
_DEFAULT_DB_PATH = r'M://books.db'


def _get_db_connection(db_path):
    """Stellt die Verbindung zur SQLite-Datenbank her."""
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"FATAL: Fehler beim Verbinden zur Datenbank {db_path}: {e}")
        return None


def save_book_with_authors(book_data: BookMetadata, db_path=None):  # <<< Signatur auf BookMetadata geändert
    """
    Fügt ein Buch und seine Autoren in die Datenbank ein oder aktualisiert
    vorhandene Datensätze, wobei nur leere Felder überschrieben werden.

    Args:
        book_data (BookMetadata): Die vollständig angereicherte Metadaten-Instanz.
    """
    # ZUGRIFF ÜBER ATTRIBUTE DER BOOKMETADATA-INSTANZ
    title = book_data.title or '[Titel fehlt]'
    file_path = book_data.file_path
    authors = book_data.authors or []  # Liste von Tupeln [(Vorname, Nachname), ...]

    if not file_path:
        print(f" FEHLER: Buch '{title}' kann nicht gespeichert werden, da der Pfad fehlt.")
        return

    # Nutze den übergebenen Pfad oder den Fallback
    db_path = db_path if db_path else _DEFAULT_DB_PATH
    conn = _get_db_connection(db_path)
    if not conn:
        return

    cursor = conn.cursor()

    try:
        print(f"  DB: Verarbeite '{title}' ({file_path})")

        # --- DATEN FÜR SQL VORBEREITEN ---

        # HINWEIS: Das Feld 'categories' (Google Books) wurde entfernt,
        # da es nicht Teil der BookMetadata-Klasse war.

        # Das finale, konsolidierte Genre kommt jetzt direkt aus book_data.genre
        final_genre = book_data.genre

        # Das endgültige Jahr
        final_year = book_data.year

        # Das finale, konsolidierte 'region'
        final_region = book_data.region

        # Das finale, konsolidierte 'description' und 'notes'
        final_description = book_data.description
        final_notes = book_data.notes

        # MAPPING DER ATTRIBUTE ZU DEN DB-SPALTEN
        scan_fields = {
            'title': title,
            'path': file_path,
            'language': book_data.language,
            'genre': final_genre,
            'series_name': book_data.series_name,
            'series_number': book_data.series_number,
            'isbn': book_data.isbn,
            'region': final_region,
            'year': final_year,
            'average_rating': book_data.average_rating,
            'ratings_count': book_data.ratings_count,

            # KORREKTE FELDER FÜR KLAPPENTEXT UND NOTIZEN
            'description': final_description,
            'notes': final_notes,

            'is_complete': book_data.is_complete,
            'is_read': book_data.is_read,  # Wenn es ein Feld in der DB gibt, sollten wir es speichern
            'stars': book_data.stars,
        }

        # Entferne None-Werte für eine sauberere Verarbeitung (optional, aber hilfreich)
        # Behalte 'path' und 'title' immer bei.
        clean_scan_fields = {}
        for k, v in scan_fields.items():
            if v is not None or k in ['title', 'path']:
                # Konvertiere 'None' in Stringfeldern zu None für SQLite, wenn es der intention nach leer ist.
                if isinstance(v, str) and v.strip() == '':
                    clean_scan_fields[k] = None
                else:
                    clean_scan_fields[k] = v

        scan_fields = clean_scan_fields

        # 1. Buch-ID anhand des 'path' suchen
        cursor.execute("SELECT * FROM books WHERE path = ?", (file_path,))
        book_row = cursor.fetchone()

        # 2. UPDATE-LOGIK: Buch existiert bereits
        if book_row:
            book_id = book_row[0]
            column_names = [description[0] for description in cursor.description]
            old_book_data = dict(zip(column_names, book_row))

            print(f"  DB: Buch '{title}' existiert bereits (ID: {book_id}). Führe UPDATE durch.")

            set_clauses = []
            params = []
            updated_count = 0

            # Iteriere über die Felder, die das Scan-Skript liefert
            for db_col, new_val in scan_fields.items():

                if db_col == 'path':
                    continue

                old_val = old_book_data.get(db_col)

                # Prüfen, ob der alte Wert als "leer" gilt (None, leerer String, 0, oder 0.0)
                is_old_val_empty = (old_val is None) or \
                                   (isinstance(old_val, str) and old_val.strip() == '') or \
                                   (str(old_val).strip() == '0.0') or \
                                   (str(old_val).strip() == '0')

                # Wenn der neue Wert None ist, wird er nur gespeichert, wenn es ein manuelles Feld ist (z.B. Notes/Description)
                # Ansonsten gilt: Neuer Wert ist gültig (nicht None, nicht leerer String)
                is_new_val_valid = (new_val is not None) and not (isinstance(new_val, str) and new_val.strip() == '')

                # UPDATE-Kriterium:
                # 1. title MUSS immer aktualisiert werden, wenn er sich unterscheidet
                # 2. ODER: Neuer Wert ist gültig UND der alte Wert ist leer (Datenlücke füllen)
                # 3. ODER: Es ist eines der manuellen Felder (description, notes, stars, is_read, is_complete)
                #          und wir müssen den Wert überschreiben (auch wenn er leer ist),
                #          da diese Felder in der GUI bearbeitet werden können.
                is_manual_field = db_col in ['description', 'notes', 'stars', 'is_read', 'is_complete']

                # Spezialfall: Notes und Description müssen von der GUI überschrieben werden,
                # auch wenn sie von leer auf leer gesetzt werden (um alte Daten zu löschen).

                if (db_col == 'title' and new_val != old_val) or \
                        (is_new_val_valid and is_old_val_empty) or \
                        (is_manual_field and new_val != old_val):
                    # Wenn das Feld Notes oder Description ist, speichern wir den neuen Wert,
                    # da er aus der GUI kommt und die neueste Information darstellt.
                    set_clauses.append(f"{db_col} = ?")
                    params.append(new_val)
                    updated_count += 1

            # Führe das Update aus
            if set_clauses:
                params.append(book_id)
                sql_update = f"UPDATE books SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(sql_update, params)
                print(f"  DB: {updated_count} Felder aktualisiert.")
            else:
                print("  DB: Keine Felder benötigten eine Aktualisierung.")

        # 3. INSERT-LOGIK: Buch ist neu
        else:
            print(f"  DB: Füge neues Buch '{title}' in die Datenbank ein.")

            columns = []
            params = []

            for col, val in scan_fields.items():
                columns.append(col)
                # Der Wert wurde bereits in clean_scan_fields zu None konvertiert,
                # falls es ein leerer String war.
                params.append(val)

            placeholders = ", ".join(["?"] * len(columns))

            sql_insert = f"INSERT INTO books ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(sql_insert, params)
            book_id = cursor.lastrowid

        # 4. Autoren-Verknüpfungen (wird bei INSERT und UPDATE ausgeführt)
        # LÖSCHE und füge neu ein (sicherer bei Updates)
        cursor.execute('DELETE FROM book_authors WHERE book_id = ?', (book_id,))

        for firstname, lastname in authors:
            # 1. Autor suchen oder einfügen
            cursor.execute('SELECT id FROM authors WHERE firstname = ? AND lastname = ?', (firstname, lastname))
            author_res = cursor.fetchone()
            if not author_res:
                cursor.execute('INSERT INTO authors (firstname, lastname) VALUES (?, ?)', (firstname, lastname))
                author_id = cursor.lastrowid
            else:
                author_id = author_res[0]

            # 2. Verknüpfung erstellen
            cursor.execute('INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)', (book_id, author_id))

        print("  DB: Autoren neu verknüpft.")

    except sqlite3.Error as e:
        print(f" FATAL: Fehler bei der Datenbankoperation für '{title}': {e}")
        conn.rollback()
    finally:
        # 5. Verbindung schließen
        conn.commit()
        print(f"  ✅ DB: '{title}' erfolgreich gespeichert/aktualisiert.")
        conn.close()


def delete_book_from_db(file_path, db_path):
    """Löscht ein Buch und alle seine Verknüpfungen aus der Datenbank."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Die ID des Buches anhand des Pfades finden
        cursor.execute("SELECT id FROM books WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()

        if result:
            book_id = result[0]

            # 2. Verknüpfungen in der Zwischentabelle (book_authors) löschen
            # Das verhindert "Orphan"-Einträge
            cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (book_id,))

            # 3. Den eigentlichen Bucheintrag löschen
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))

            conn.commit()
            return True
        else:
            print(f"Löschen fehlgeschlagen: Buch unter {file_path} nicht in DB gefunden.")
            return False

    except sqlite3.Error as e:
        print(f"Datenbankfehler beim Löschen: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

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