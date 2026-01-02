"""
DATEI: book_data.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Book_Data     rDas Herzstück.	Kennt das DB-Schema, verwaltet die ID und speichert sich selbst.
              Book_Scanner	Neue Dateien finden & Metadaten extrahieren.	Erstellt BookData-Objekte und ruft .save() auf.
              Book_Browser	GUI für Anzeige und manuelle Korrektur.	Ruft .load_by_path() auf und modifiziert Attribute.
              Book_Analyser	Statistiken, Dubletten-Check, KI-Auswertung.	Liest BookData-Listen für Berechnungen
"""

import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional, Dict  # Any ist das Wichtigste für deinen Fehler

@dataclass
class BookData:
    db_path = r'M://books.db'
    id: int = 0
    path: str = ""
    work_id: int = 0
    authors: list = field(default_factory=list)
    # Hier definieren wir die Standard-Felder, damit sie 'echt' existieren:
    title: str = ""
    genre: str = ""
    region: str = ""
    language: str = ""
    keywords: list = field(default_factory=list)
    series_name: str = ""
    series_number: str = ""
    isbn: str = ""
    average_rating: float = 0.0
    ratings_count: int = 0
    rating_ol: float = 0.0
    ratings_count_ol: int = 0
    stars: str = ""
    year: str = ""
    description: str = ""
    notes: str = ""
    image_path: str = ""
    is_manual_description: int = 0
    is_read: int = 0
    is_complete: int = 0
    scanner_version: str = "1.2.0"

    @classmethod
    def load_by_path(cls, file_path):
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM books WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # 1. Row in Dict wandeln
        data = dict(row)
        # 2. Autoren separat holen
        cursor.execute("""
            SELECT a.firstname, a.lastname FROM authors a
            JOIN book_authors ba ON a.id = ba.author_id
            WHERE ba.book_id = ?""", (data['id'],))
        authors_list = [(r[0], r[1]) for r in cursor.fetchall()]
        conn.close()
        # 2. AUTOMATISCHES FILTERN
        # Wir nehmen nur Daten aus der DB, die auch als Variable in deiner Klasse stehen
        # cls.__annotations__ enthält alle Felder wie 'title', 'genre', etc.
        allowed_keys = cls.__annotations__.keys()
        clean_data = {k: v for k, v in data.items() if k in allowed_keys}
        # 3. Datentyp-Korrektur: Keywords (String aus DB -> Liste für Objekt)
        if 'keywords' in clean_data and isinstance(clean_data['keywords'], str):
            kw_string = clean_data['keywords'].strip()
            if kw_string:
                # Zerlegen am Komma und Leerzeichen entfernen
                clean_data['keywords'] = [k.strip() for k in kw_string.split(',')]
            else:
                clean_data['keywords'] = []
        # 4. Autoren manuell dazu, da sie in der DB ja aus einer anderen Tabelle kommen
        clean_data['authors'] = authors_list
        return cls(**clean_data)

    @classmethod
    def from_dict(cls, data: dict):
        """Erzeugt ein BookData-Objekt aus einem Dictionary."""
        # Wir filtern nur die Felder heraus, die die Klasse auch wirklich hat
        from dataclasses import fields
        valid_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


    def get_if_not_empty(self, field_name: str) -> Any:
        """
        Gibt den Wert des Feldes zurück, wenn es NICHT leer ist.
        Ansonsten wird None zurückgegeben.
        """
        value = getattr(self, field_name, None)

        # Die eigentliche Logik, was als "leer" gilt
        is_empty = False
        if value is None:
            is_empty = True
        elif isinstance(value, str) and not value.strip():
            is_empty = True
        elif isinstance(value, (list, tuple, dict)) and len(value) == 0:
            is_empty = True
        return None if is_empty else value

    def save(self):
        """Das Objekt speichert sich selbst in die Datenbank – mit Typ-Korrektur."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Struktur-Check & Alarm (Dein Code - super wichtig!)
        cursor.execute("PRAGMA table_info(books)")
        db_cols = [row[1] for row in cursor.fetchall()]

        current_data = self.to_dict()
        # Keywords für DB konvertieren: Liste -> String
        if 'keywords' in current_data and isinstance(current_data['keywords'], list):
            current_data['keywords'] = ", ".join(current_data['keywords'])

        ignored = {'authors', 'image_path'}  # keywords jetzt nicht mehr ignorieren, da sie in die DB sollen
        mismatch = [k for k in current_data.keys() if k not in db_cols and k not in ignored]

        if mismatch:
            print(f"⚠️  ALARM: Spalten fehlen in DB: {mismatch}")

        # Nur Felder nehmen, die wirklich in der DB existieren
        save_dict = {k: v for k, v in current_data.items() if k in db_cols}

        try:
            if self.id and self.id > 0:
                # --- UPDATE-LOGIK (Anker: ID) ---
                # Wir entfernen die ID aus den SET-Werten, sie steht ja im WHERE
                temp_id = save_dict.pop('id')
                set_clause = ", ".join([f"{k} = ?" for k in save_dict.keys()])
                sql = f"UPDATE books SET {set_clause} WHERE id = ?"
                cursor.execute(sql, list(save_dict.values()) + [temp_id])
                save_dict['id'] = temp_id  # ID für später wieder rein
            else:
                # --- INSERT-LOGIK (Neues Buch) ---
                # Falls ID 0 ist, lassen wir SQLite sie vergeben (entfernen aus Dict)
                save_dict.pop('id', None)
                columns = ", ".join(save_dict.keys())
                placeholders = ", ".join(["?"] * len(save_dict))
                sql = f"INSERT INTO books ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, list(save_dict.values()))
                self.id = cursor.lastrowid

            # 2. Autoren-Verknüpfung (n:m)
            cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (self.id,))
            for fname, lname in self.authors:
                cursor.execute("SELECT id FROM authors WHERE firstname=? AND lastname=?", (fname, lname))
                res = cursor.fetchone()
                a_id = res[0] if res else None

                if not a_id:
                    cursor.execute("INSERT INTO authors (firstname, lastname) VALUES (?,?)", (fname, lname))
                    a_id = cursor.lastrowid

                cursor.execute("INSERT INTO book_authors (book_id, author_id) VALUES (?,?)", (self.id, a_id))

            conn.commit()
            return True
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete(self):
        """Das Objekt entfernt sich selbst aus der Datenbank."""
        if self.id == 0:
            print("Fehler: Buch hat keine ID und kann nicht gelöscht werden.")
            return False

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Erst die Verknüpfungen in der n:m Tabelle lösen
            cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (self.id,))
            # 2. Dann den Eintrag in der books-Tabelle löschen
            cursor.execute("DELETE FROM books WHERE id = ?", (self.id,))
            conn.commit()
            # Wir setzen die ID auf 0 zurück, da das Objekt in der DB nicht mehr existiert
            self.id = 0
            return True
        except Exception as e:
            conn.rollback()
            print(f"Fehler beim Löschen des Objekts: {e}")
            return False
        finally:
            conn.close()

    def to_dict(self):
        """Hilfsmethode für SQL - nutzt jetzt die festen Felder der Dataclass."""
        return asdict(self)