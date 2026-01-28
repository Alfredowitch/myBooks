"""
DATEI: book_data_old.py
PROJEKT: MyBook-Management (v1.4.0)
BESCHREIBUNG: Book_Data     rDas Herzstück.	Kennt das DB-Schema, verwaltet die ID und speichert sich selbst.
              Book_Scanner	Neue Dateien finden & Metadaten extrahieren.	Erstellt BookData-Objekte und ruft .save() auf.
              Book_Browser	GUI für Anzeige und manuelle Korrektur.	Ruft .load_by_path() auf und modifiziert Attribute.
              BookCleaner	Statistiken, Dubletten-Check, KI-Auswertung.	Liest BookData-Listen für Berechnungen

              Book          physikalisches Buch mit Dateinamen und Pfad und Sprache
              Work          abstraktes sprachunabhängiges Werk mit Autor, Titel, Serienname und Seriennummer, Bewertung, Beschreibung
              Serie         Serien für Werke
"""
import os
import sqlite3
import unicodedata
from dataclasses import dataclass, asdict, is_dataclass, field
from typing import Any

from Gemini.file_utils import DB_PATH, slugify

@dataclass
class BookData:
    db_path = DB_PATH
    id: int = 0
    path: str = ""
    work_id: int = 0
    authors: list = field(default_factory=list)
    # Hier definieren wir die Standard-Felder, damit sie 'echt' existieren:
    title: str = ""
    genre: str = ""
    language: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)
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
    extension: str = ".epub"

    @staticmethod
    def normalize_path(p: str) -> str:
        """Normalisiert Pfade auf den NFC-Standard (wichtig für Mac/Windows Kompatibilität)."""
        if not isinstance(p, str):
            return p
        return unicodedata.normalize('NFC', p)

    @classmethod
    def load_by_path(cls, file_path):
        clean_path = cls.normalize_path(file_path)
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM books WHERE path = ?", (clean_path,))
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
                # Wir machen direkt ein SET daraus
                clean_data['keywords'] = {k.strip() for k in kw_string.split(',')}
            else:
                clean_data['keywords'] = set()
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

    @classmethod
    def search(cls, title_term="", author_term=""):
        """Sucht Bücher und gibt eine Liste von BookData-Objekten zurück."""
        conn = sqlite3.connect(DB_PATH)
        # SQL-Query (angepasst auf deine Struktur)
        sql_query = """
                SELECT DISTINCT b.*
                FROM books b
                LEFT JOIN book_authors ba ON b.id = ba.book_id
                LEFT JOIN authors a ON ba.author_id = a.id
                WHERE (?1 = '' OR b.title LIKE '%' || ?1 || '%')
                  AND (?2 = '' OR a.lastname LIKE '%' || ?2 || '%' OR a.firstname LIKE '%' || ?2 || '%')
            """
        results = []
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql_query, (title_term, author_term))
            rows = cursor.fetchall()

            for row in rows:
                # Wir nutzen deine vorhandene Logik: Dict aus Row erstellen
                data = dict(row)
                # Autoren für dieses Buch laden
                cursor.execute("""
                        SELECT a.firstname, a.lastname FROM authors a
                        JOIN book_authors ba ON a.id = ba.author_id
                        WHERE ba.book_id = ?""", (data['id'],))
                data['authors'] = [(r[0], r[1]) for r in cursor.fetchall()]

                # Wir nutzen from_dict oder den Constructor, um das Objekt zu bauen
                # Zuerst filtern wir wieder die erlaubten Keys
                allowed_keys = cls.__annotations__.keys()
                clean_data = {k: v for k, v in data.items() if k in allowed_keys}

                # Keywords Fix (String -> Liste), falls in DB als String
                if 'keywords' in clean_data and isinstance(clean_data['keywords'], str):
                    kw = clean_data['keywords'].strip()
                    clean_data['keywords'] = [k.strip() for k in kw.split(',')] if kw else []
                results.append(cls(**clean_data))

        except sqlite3.Error as e:
            print(f"Fehler bei Suche: {e}")
        finally:
            if conn:
                conn.close()
        return results

    @classmethod
    def search_sql(cls, sql_query: str, params: tuple = ()):
        """
        Führt ein beliebiges SQL-Statement aus und gibt eine Liste
        von BookData-Objekten zurück.
        """
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        results = []
        try:
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()

            # Wir holen die erlaubten Felder der Klasse
            allowed_keys = cls.__annotations__.keys()

            for row in rows:
                data = dict(row)
                # Nur die Felder nehmen, die im SQL-Ergebnis UND in der Klasse sind
                clean_data = {k: v for k, v in data.items() if k in allowed_keys}

                # Spezialfall Keywords (String -> Set)
                if 'keywords' in clean_data and isinstance(clean_data['keywords'], str):
                    kw = clean_data['keywords'].strip()
                    clean_data['keywords'] = {k.strip() for k in kw.split(',')} if kw else set()

                # Wir erstellen das Objekt (unvollständige Felder werden durch Defaults ersetzt)
                results.append(cls(**clean_data))
        except sqlite3.Error as e:
            print(f"Fehler bei search_sql: {e}")
        finally:
            conn.close()
        return results

    @classmethod
    def update_file_path(cls, old_path, new_path):
        # 1. Pfade normalisieren (Sicherheit zuerst!)
        old_path = cls.normalize_path(old_path)
        new_path = cls.normalize_path(new_path)

        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()

            # 2. UPDATE ausführen
            cursor.execute("UPDATE books SET path = ? WHERE path = ?", (new_path, old_path))

            if cursor.rowcount == 0:
                # ... dein (sehr guter!) Fehler-Check mit dem LIKE %filename ...
                # (hier weggelassen für die Übersicht)
                return False
            else:
                conn.commit()
                print(f"DEBUG: Update erfolgreich.")

        except sqlite3.Error as e:
            print(f"Datenbankfehler: {e}")
            return False
        finally:
            conn.close()

    # __init__ wird bei Datenklassen ja im Hintergrund automatisch erledigt.
    # Aber wir müssen uns danach um die Normalisierung des Pfadnamen kümmern.
    def __post_init__(self):
        """Wird sofort nach der Erstellung des Objekts aufgerufen."""
        # Wir nutzen unsere statische Methode, um den Pfad zu säubern
        self.path = self.normalize_path(self.path)
        # Falls keywords als Liste reingekommen ist (z.B. aus JSON),
        # wandeln wir es sofort in ein Set um.
        if isinstance(self.keywords, list):
            self.keywords = set(self.keywords)

        if isinstance(self.regions, list):
            self.regions = set(self.regions)

    def is_field_empty(self, field_name: str, value: Any) -> bool:
        """
        Zentrale Logik: Prüft, ob ein Wert für ein bestimmtes Feld als 'leer' gilt.
        Berücksichtigt Strings, Listen, Zahlen und deine Platzhalter.
        """
        if value is None:
            return True

        # 1. Strings (inkl. Platzhalter-Texte)
        if isinstance(value, str):
            v = value.strip()
            return v == "" or v.lower() == "none" or v in ["Unbekannt", "Unbekannter Titel", "Kein Autor"]

        # 2. Listen / Dicts (inkl. Autoren-Tupel-Check)
        if isinstance(value, (list, tuple, dict, set)):
            if not value:
                return True
            if field_name == 'authors' and isinstance(value, list):
                # Checkt ob nur Platzhalter-Tupel in der Liste sind
                return all(a in {("", "Unbekannt"), ("", "Kein Autor"), ()} for a in value)
            return False

        # 3. Zahlen (Jahr 0 oder Rating 0 ist 'leer')
        if isinstance(value, (int, float)):
            return value == 0

        return False

    def get_if_not_empty(self, field_name: str) -> Any:
        """
        Nutzt is_field_empty, um zu entscheiden, ob der Wert zurückgegeben
        oder durch None ersetzt wird.
        """
        value = getattr(self, field_name, None)
        if self.is_field_empty(field_name, value):
            return None
        return value

    def merge_with(self, other_metadata: 'BookData'):
        """
        Führt Metadaten zusammen. Schützt kritische Felder und sammelt
        Kategorien in Keywords.
        """
        if not other_metadata:
            return

        # Felder, die die Identität oder User-Eingaben schützen
        protected_fields = ['id', 'db_id', 'is_read', 'scanner_version', 'stars', 'notes']

        # Wir wandeln das andere Objekt in ein Dictionary um
        if is_dataclass(other_metadata):
            other_dict = asdict(other_metadata)
        else:
            # Falls es ein normales Objekt oder Dict ist
            other_dict = other_metadata.__dict__ if hasattr(other_metadata, '__dict__') else other_metadata

        for field_name, other_value in other_dict.items():
            # 1. Schutz-Check
            if field_name in protected_fields:
                current_val = getattr(self, field_name, None)
                if not self.is_field_empty(field_name, current_val):
                    continue

            # 2. Wert übernehmen, wenn das eigene Feld leer ist
            current_value = getattr(self, field_name, None)
            if self.is_field_empty(field_name, current_value):
                if not self.is_field_empty(field_name, other_value):
                    setattr(self, field_name, other_value)

            # SPEZIALFALL: image_path (Cover-Pfad immer von Quelle übernehmen)
            if field_name == 'image_path' and other_value is not None:
                setattr(self, field_name, other_value)

        # --- LOGIK FÜR DAS GENRE-BACKUP ---
        if self.is_field_empty("genre", self.genre):
            # 1. Versuch: genre_epub nutzen (falls vorhanden)
            if hasattr(other_metadata, 'genre_epub') and not self.is_field_empty("genre", other_metadata.genre_epub):
                self.genre = other_metadata.genre_epub
            # 2. Versuch: Erste Kategorie nutzen
            elif hasattr(other_metadata, 'categories') and other_metadata.categories:
                self.genre = other_metadata.categories[0]

        # --- DATEN-SAMMLER: Kategorien -> Keywords ---
        if hasattr(other_metadata, 'categories') and other_metadata.categories:
            for cat in other_metadata.categories:
                if cat not in self.keywords:
                    self.keywords.add(cat)

        if hasattr(other_metadata, 'genre_epub') and other_metadata.genre_epub:
            if other_metadata.genre_epub not in self.keywords:
                self.keywords.add(other_metadata.genre_epub)

    def save(self):
        """Das Objekt speichert sich selbst in die Datenbank – mit Typ-Korrektur."""
        self.path = self.normalize_path(self.path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Struktur-Check & Alarm (Dein Code - super wichtig!)
        cursor.execute("PRAGMA table_info(books)")
        db_cols = [row[1] for row in cursor.fetchall()]

        current_data = self.to_dict()
        # Typ-Korrektur für die Datenbank: Sets oder Listen zu Strings konvertieren
        for field in ['keywords', 'regions']:
            if field in current_data:
                val = current_data[field]
                # Wir prüfen auf Set ODER Liste
                if isinstance(val, (set, list)):
                    # Wir sortieren für eine saubere Optik in der DB
                    current_data[field] = ", ".join(sorted(list(val)))
                elif val is None:
                    current_data[field] = ""

        ignored = {'authors', 'image_path', 'extension'}  # keywords jetzt nicht mehr ignorieren, da sie in die DB sollen
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

            # --- 2. KORRIGIERTE AUTOREN-VERKNÜPFUNG (mit Slug-Logik) ---
            cursor.execute("DELETE FROM book_authors WHERE book_id = ?", (self.id,))
            for fname, lname in self.authors:
                cursor.execute("SELECT id FROM authors WHERE firstname=? AND lastname=?", (fname, lname))
                res = cursor.fetchone()
                if res:
                    a_id = res[0]
                else:
                    # Neuen Autor anlegen: Slug generieren & Kollisionen prüfen
                    full_name = f"{fname} {lname}".strip()
                    base_slug = slugify(full_name) or f"author-{self.id}"
                    new_slug = base_slug
                    counter = 1
                    # Prüfen, ob der Slug bereits von einem anderen Autor belegt ist
                    while True:
                        cursor.execute("SELECT id FROM authors WHERE name_slug = ?", (new_slug,))
                        if not cursor.fetchone():
                            break  # Slug ist frei
                        counter += 1
                        new_slug = f"{base_slug}-{counter}"

                    cursor.execute(
                        "INSERT INTO authors (firstname, lastname, name_slug) VALUES (?,?,?)",
                        (fname, lname, new_slug)
                    )
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

    @classmethod
    def fix_path_ext(cls, old_path, new_path):
        """Ändert den Pfad eines Buches in der DB, wenn die Endung korrigiert wurde."""
        old_path = cls.normalize_path(old_path)
        new_path = cls.normalize_path(new_path)

        conn = sqlite3.connect(cls.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE books SET path = ? WHERE path = ?", (new_path, old_path))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"DB-Fehler bei Pfad-Fix: {e}")
            return False
        finally:
            conn.close()


    @classmethod
    def vacuum(cls):
        """
        Komprimiert die Datenbank und optimiert die Speicherstruktur.
        Sollte nach großen Lösch- oder Update-Aktionen (wie dem Repair-Scan)
        aufgerufen werden.
        """
        import time
        print(f"--- STARTE DATENBANK-OPTIMIERUNG (VACUUM) ---")
        start_time = time.time()

        conn = sqlite3.connect(cls.db_path)
        try:
            # VACUUM kann nicht innerhalb einer Transaktion ausgeführt werden,
            # daher stellen wir sicher, dass autocommit aktiv ist oder schließen die Verbindung kurz.
            conn.isolation_level = None
            cursor = conn.cursor()

            # 1. Größe vor dem Vacuum
            cursor.execute("PRAGMA page_count")
            pages_before = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            size_before_mb = (pages_before * page_size) / (1024 * 1024)

            print(f"Aktuelle Größe: {size_before_mb:.2f} MB. Bitte warten...")

            # Der eigentliche Befehl
            cursor.execute("VACUUM")

            # 2. Größe nach dem Vacuum
            cursor.execute("PRAGMA page_count")
            pages_after = cursor.fetchone()[0]
            size_after_mb = (pages_after * page_size) / (1024 * 1024)

            duration = time.time() - start_time
            print(f"✅ Optimierung abgeschlossen ({duration:.1f}s).")
            print(f"Neue Größe: {size_after_mb:.2f} MB (Ersparnis: {size_before_mb - size_after_mb:.2f} MB).")

        except sqlite3.Error as e:
            print(f"❌ Fehler beim Vacuum: {e}")
        finally:
            conn.close()

    @classmethod
    def get_book_counts_per_folder(cls, base_filter=None):
        """
        Zählt Bücher pro Ordner innerhalb eines base_filter Pfades.
        Nutzt die Klassen-Logik, bleibt aber speichereffizient.
        """
        folder_counts = {}

        # SQL-Teil: Wir holen nur den Pfad.
        # Wenn ein Filter gesetzt ist, schränken wir die Suche direkt in der DB ein.
        if base_filter:
            sql_filter = os.path.normpath(base_filter).replace('\\', '/') + '%'
            sql = "SELECT path FROM books WHERE path LIKE ?"
            # WICHTIG: Wir nutzen hier eine Methode, die idealerweise einen Generator liefert
            # Falls search_sql fetchall() nutzt, ist das hier der Flaschenhals bei 100k Einträgen.
            results = cls.search_sql(sql, (sql_filter,))
        else:
            results = cls.search_sql("SELECT path FROM books")

        for book in results:
            # Falls search_sql Objekte zurückgibt, greifen wir auf .path zu, sonst auf Index [0]
            full_path = getattr(book, 'path', book[0] if isinstance(book, (list, tuple)) else None)

            if full_path:
                # Schnelles String-Splitting statt os.path.dirname
                norm_path = os.path.abspath(os.path.normpath(full_path))
                folder = os.path.dirname(norm_path)
                folder_counts[folder] = folder_counts.get(folder, 0) + 1

        return folder_counts


    @classmethod
    def get_all_paths_in_folder(cls, folder_path):
        """Gibt eine Liste aller Pfade zurück, die in der DB unter diesem Ordner liegen."""
        # Wir nutzen ein LIKE Statement, um alle Unterpfade zu finden
        # Wir normalisieren die Slashes, damit der Vergleich klappt
        search_path = folder_path.replace('\\', '/')
        if not search_path.endswith('/'):
            search_path += '/'

        sql = "SELECT path FROM books WHERE path LIKE ?"
        results = cls.search_sql(sql, (search_path + '%',))

        # search_sql liefert oft Objekte zurück, wir brauchen nur die Strings
        return [book.path for book in results]
