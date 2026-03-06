from __future__ import annotations
import sqlite3
import copy
import traceback
from dataclasses import dataclass, asdict, fields, field
from typing import List, Optional, Union

# --- DER EINZIGE IMPORT AUS UTILS ---
from Scotty.utils import Scotty


def force_set(value, label: str = None) -> set:
    """Wandelt Eingaben sicher in ein Set von Strings um."""
    if not value: return set()
    if isinstance(value, (set, list, tuple)):
        return {str(x).strip() for x in value if x is not None and str(x).strip()}
    if isinstance(value, str):
        if "," in value:
            return {p.strip() for p in value.split(",") if p.strip()}
        return {value.strip()} if value.strip() else set()
    return {str(value).strip()}


# --- DATEN-ATOME (Die DNA) ---

@dataclass
class BookTData:
    id: Optional[int] = None
    work_id: int = 0
    path: str = ""
    title: str = ""
    ext: str = ""
    isbn: str = ""
    genre: str = ""
    stars: int = 0
    description: str = ""
    notes: str = ""
    language: str = ""
    series_name: str = ""
    series_index: float = 0.0
    series_number: str = ""
    is_complete: int = 0
    is_read: int = 0
    scanner_version: str = ""
    rating_ol: float = 0.0
    rating_ol_count: int = 0
    rating_g: float = 0.0
    rating_g_count: int = 0
    is_manual_description: int = 0
    year: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)
    authors: list = field(default_factory=list)

    def __post_init__(self):
        self.keywords = force_set(self.keywords)
        self.regions = force_set(self.regions)

    def merge_with(self, data: Union[dict, 'BookTData']):
        if not data: return
        source = data if isinstance(data, dict) else asdict(data)
        for key, value in source.items():
            if value is None or value == "": continue
            if hasattr(self, key):
                if key in ['keywords', 'regions']:
                    getattr(self, key).update(force_set(value))
                else:
                    setattr(self, key, value)

    def get_transient_fields(self):
        """Felder, die Spock beim Hygiene-Check ignorieren darf."""
        return ['temp_scan_error']

    def save(self, conn: sqlite3.Connection) -> bool:
        """
        Das Buch-Atom persistiert sich selbst.
        Verantwortlich NUR für die Tabelle 'books'.
        """
        cursor = conn.cursor()

        # 1. Transformation: Sets/Listen zu Strings für SQLite
        b_dict = asdict(self)
        b_dict['keywords'] = ",".join(self.keywords) if self.keywords else ""
        b_dict['regions'] = ",".join(self.regions) if self.regions else ""

        # Autoren werden hier ignoriert, da sie in die Verknüpfungstabelle gehören
        if 'authors' in b_dict: del b_dict['authors']

        # 2. Hygiene: Nur Spalten nehmen, die es in der DB auch wirklich gibt
        cursor.execute("PRAGMA table_info(books)")
        db_cols = [row[1] for row in cursor.fetchall()]
        safe_data = {k: v for k, v in b_dict.items() if k in db_cols}

        # 3. SQL Logic: ON CONFLICT für das 'Book-Only' Szenario
        # Wir nutzen den 'path' als Unique-Identifier (dein Anker im All)
        columns = ", ".join(safe_data.keys())
        placeholders = ", ".join([f":{k}" for k in safe_data.keys()])

        sql = f"""
            INSERT INTO books ({columns})
            VALUES ({placeholders})
            ON CONFLICT(path) DO UPDATE SET
                title = excluded.title,
                year = excluded.year,
                language = excluded.language,
                keywords = excluded.keywords,
                regions = excluded.regions,
                description = CASE 
                    WHEN books.description IS NULL OR books.description = '' THEN excluded.description 
                    ELSE books.description 
                END,
                notes = CASE 
                    WHEN (books.description IS NOT NULL AND books.description != '') 
                         AND (excluded.description IS NOT NULL AND excluded.description != '')
                         AND (excluded.description != books.description)
                    THEN COALESCE(books.notes, '') || '\n\n-- Alt. Info --\n' || excluded.description 
                    ELSE COALESCE(books.notes, excluded.description) 
                END,
                scanner_version = excluded.scanner_version,
                is_complete = 1
        """

        try:
            cursor.execute(sql, safe_data)
            # Falls wir ein Insert hatten, ID im Objekt setzen
            if not self.id:
                self.id = cursor.lastrowid
            return True
        except Exception as e:
            print(f"💥 BookTData: Fehler beim Atomspeichern: {e}")
            return False

@dataclass
class WorkTData:
    id: int = 0
    title: str = ""
    slug: str = ""
    title_de: str = ""
    title_en: str = ""
    description: str = ""
    series_id: Optional[int] = None
    series_index: float = 0.0
    stars: int = 0
    rating: float = 0.0
    genre: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)

    def __post_init__(self):
        self.keywords = force_set(self.keywords)
        self.regions = force_set(self.regions)


@dataclass
class SerieTData:
    id: int = 0
    name: str = ""
    slug: str = ""
    notes: str = ""


# --- DER CORE (Spock) ---

class Core:
    """
    Der Logik-Offizier der Enterprise.
    Verwaltet die Atome und spricht mit der Datenbank.
    """

    def __init__(self, book_obj=None, work_obj=None, serie_obj=None):
        self.book = book_obj or BookTData()
        self.work = work_obj or WorkTData()
        self.serie = serie_obj or SerieTData()
        self.is_in_db = False
        self.db_snapshot = None

    @classmethod
    def load_db_by_path(cls, file_path: str) -> Optional['Core']:
        """Lädt ein existierendes Buch-System anhand des Pfads."""
        clean_path = Scotty.sanitize_path(file_path)
        with Scotty.conn() as conn:
            res_book = conn.execute("SELECT * FROM books WHERE path = ?", (clean_path,)).fetchone()
            if not res_book: return None

            row_b = dict(res_book)
            book_atom = BookTData(**{f.name: row_b[f.name] for f in fields(BookTData) if f.name in row_b})

            # Werk & Serie nachladen
            work_atom = WorkTData()
            if book_atom.work_id:
                res_w = conn.execute("SELECT * FROM works WHERE id = ?", (book_atom.work_id,)).fetchone()
                if res_w: work_atom = WorkTData(**{f.name: res_w[f.name] for f in fields(WorkTData) if f.name in res_w})

            serie_atom = SerieTData()
            if work_atom.series_id:
                res_s = conn.execute("SELECT * FROM series WHERE id = ?", (work_atom.series_id,)).fetchone()
                if res_s: serie_atom = SerieTData(
                    **{f.name: res_s[f.name] for f in fields(SerieTData) if f.name in res_s})

            instance = cls(book_atom, work_atom, serie_atom)
            instance.is_in_db = True
            instance.capture_db_state()
            return instance

    def save_book_only(self) -> bool:
        """
        Schnittstelle für Scotty oder externe Scans.
        Speichert nur die reinen Buchdaten ohne Work/Serie zu berühren.
        """
        with Scotty.conn() as conn:
            try:
                success = self.book.save(conn)
                if success:
                    conn.commit()
                    self.capture_db_state()
                    return True
            except Exception as e:
                print(f"🖖 Spock: Fehler in save_book_only: {e}")
            return False

    def save(self) -> bool:
        """Das große Ganze: Speichert alles kaskadierend."""
        with Scotty.conn() as conn:
            cursor = conn.cursor()
            try:
                # 1. & 2. Serie/Work Logik (bleibt wie in deinem Code)
                self._db_save_serie(cursor)
                if self.serie.id: self.work.series_id = self.serie.id

                if not self.work.id or self.work.id == 0:
                    self.work.id = self._db_insert_work(cursor)
                else:
                    self._db_update_work_defensive(cursor)

                # 3. Book: Nutzt jetzt die interne Methode des Atoms!
                self.book.work_id = self.work.id
                self.book.save(conn)  # <--- Spock delegiert an BookTData

                # 4. Autoren
                if self.book.authors:
                    self._db_sync_authors(cursor)

                conn.commit()
                self.capture_db_state()
                return True
            except Exception as e:
                conn.rollback()
                traceback.print_exc()
                return False

    def _db_save_serie(self, cursor):
        if not self.serie.name: return
        self.serie.slug = Scotty.slugify(self.serie.name)
        res = cursor.execute("SELECT id FROM series WHERE name = ?", (self.serie.name,)).fetchone()
        s_id = res[0] if res else None

        s_dict = {k: v for k, v in asdict(self.serie).items() if k != 'id'}
        if s_id:
            cursor.execute(f"UPDATE series SET {', '.join([f'{k}=?' for k in s_dict.keys()])} WHERE id=?",
                           (*s_dict.values(), s_id))
            self.serie.id = s_id
        else:
            cursor.execute(f"INSERT INTO series ({', '.join(s_dict.keys())}) VALUES ({','.join(['?'] * len(s_dict))})",
                           tuple(s_dict.values()))
            self.serie.id = cursor.lastrowid

    def _db_insert_work(self, cursor) -> int:
        w_dict = {k: v for k, v in asdict(self.work).items() if not isinstance(v, (list, dict, set)) and k != 'id'}
        w_dict['slug'] = Scotty.slugify(self.work.title)
        cols = ", ".join(w_dict.keys())
        cursor.execute(f"INSERT INTO works ({cols}) VALUES ({','.join(['?'] * len(w_dict))})", list(w_dict.values()))
        return cursor.lastrowid

    def _db_update_work_defensive(self, cursor):
        w_dict = {k: v for k, v in asdict(self.work).items() if not isinstance(v, (list, dict, set)) and k != 'id'}
        for col, val in w_dict.items():
            if val is not None and val != '' and val != 0.0:
                sql = f"UPDATE works SET {col} = CASE WHEN {col} IS NULL OR {col} = '' OR {col} = 0.0 THEN ? ELSE {col} END WHERE id = ?"
                cursor.execute(sql, (val, self.work.id))

    def _db_save_book_raw(self, cursor):
        b_dict = {k: v for k, v in asdict(self.book).items() if k != 'authors' and not isinstance(v, (set, list))}
        b_dict['keywords'] = ",".join(self.book.keywords)
        b_dict['regions'] = ",".join(self.book.regions)
        if self.book.id:
            cols = ", ".join([f"{k}=?" for k in b_dict.keys() if k != 'id'])
            cursor.execute(f"UPDATE books SET {cols} WHERE id=?",
                           (*[v for k, v in b_dict.items() if k != 'id'], self.book.id))
        else:
            if 'id' in b_dict: del b_dict['id']
            cursor.execute(f"INSERT INTO books ({', '.join(b_dict.keys())}) VALUES ({','.join(['?'] * len(b_dict))})",
                           list(b_dict.values()))
            self.book.id = cursor.lastrowid

    def _db_sync_authors(self, cursor):
        cursor.execute("DELETE FROM work_to_author WHERE work_id = ?", (self.work.id,))
        for fn, ln in self.book.authors:
            slug = Scotty.slugify(f"{fn} {ln}")
            cursor.execute("INSERT OR IGNORE INTO authors (firstname, lastname, slug) VALUES (?,?,?)", (fn, ln, slug))
            aid = cursor.execute("SELECT id FROM authors WHERE slug=?", (slug,)).fetchone()[0]
            cursor.execute("INSERT OR IGNORE INTO work_to_author (work_id, author_id) VALUES (?,?)",
                           (self.work.id, aid))

    def capture_db_state(self):
        self.db_snapshot = copy.deepcopy({'book': self.book, 'work': self.work, 'serie': self.serie})
        self.is_in_db = True