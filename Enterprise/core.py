# Enterprise/atom.py
"""
Die Engine läd Daten aus der DB in drei Datenbank-Objekte für book, work, serie
Instanzen aus der DB werden immer nur mit ID zurückgeschrieben.
a_core: Was in den Schiffslogbüchern (DB) steht.
Das a_core ist safe, d.h. die Daten sind immer "", 0 oder eben gesetzt.
Die BookTData kann daher überall safe initiiert werden.

Alle anderen cores können none-Werte enthalten!
s_core: Was wir draußen im All (Dateisystem) gefunden haben.
b_core: Was der Commander (User) befohlen hat.
z_core: Die Wahrheit, die am Ende übrig bleibt und gespeichert wird.

Beim Speichern wird ein Attribut entweder gespeichert, dh. überschrieben oder gelöscht oder ignoriert.
atom.genre = "Fantasy" -> Wird gespeichert.
atom.genre = "" -> Wird in der DB gelöscht (Leerstring).
atom.genre = None -> Feld wird beim Update übersprungen (NULL-Regel).
"""

from __future__ import annotations
import copy
import json
from dataclasses import dataclass, asdict, fields, field
from typing import Optional
from Enterprise.database import Database


def to_set(value) -> set:
    """Wandelt Input in ein Set um. Erkennt auch JSON-Strings."""
    if not value: return set()
    if isinstance(value, (set, list, tuple)):
        return {str(x).strip() for x in value if x}
    if isinstance(value, str):
        # Versuch JSON zu laden (für unsere neue Regel)
        if value.startswith('['):
            try:
                data = json.loads(value)
                return set(data) if isinstance(data, list) else {str(data)}
            except: pass
        # Fallback: Komma-Trennung
        return {p.strip() for p in value.split(",") if p.strip()}
    return {str(value).strip()}


def prepare_for_db(atom) -> dict:
    """Bereitet Daten für SQL vor. Sets -> JSON. None -> Überspringen."""
    raw_data = asdict(atom)

    # Wir nehmen nur Felder, die nicht None sind (NULL-Regel)
    # Die ID nehmen wir raus, die wird separat im SQL verbaut
    # inners If: sets werden in Listen umgewandelt und sortiert dann json
    # äußeres If: wenn set, list oder tupel dann json sonst einfach v abspeichern.
    return {
        k: (json.dumps(sorted(list(v)) if isinstance(v, set) else v, ensure_ascii=False)
            if isinstance(v, (set, list, tuple)) else v)
        for k, v in raw_data.items() if v is not None and k != 'id'
    }


# --- UNIVERSELLE SPEICHER-LOGIK ---

def generic_save(atom, table_name: str, cursor):
    """
    Die zentrale Schaltstelle:
    - id = 0 -> INSERT
    - id > 0 -> UPDATE
    """
    data = prepare_for_db(atom)
    if not data: return
    current_id = getattr(atom, 'id', 0)
    try:
        if current_id > 0:
            # UPDATE: Wir setzen voraus, dass die ID existiert
            cols = ", ".join([f"{k}=?" for k in data.keys()])
            sql = f"UPDATE {table_name} SET {cols} WHERE id=?"
            cursor.execute(sql, (*data.values(), current_id))

            # Optional: Prüfen, ob wirklich eine Zeile geändert wurde
            if cursor.rowcount == 0:
                print(
                    f"[WARNUNG] Update für {table_name} ID {current_id} hat keine Zeile geändert (ID nicht gefunden).")
        else:
            # INSERT: Neu anlegen
            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(data.values()))
            atom.id = cursor.lastrowid

    except Exception as e:
        # Hier knallt es jetzt laut, wenn z.B. eine Spalte in der DB fehlt
        print(f"❌ DATABASE CRASH in Tabelle '{table_name}':")
        print(f"   Fehler: {e}")
        print(f"   Versuchte Spalten: {list(data.keys())}")
        raise e  # Den Fehler weiterreichen, damit das Programm stoppt

# --- UNIVERSELLE CORE LOGIK ---

"""
    Extrahiert von einem beliebigem SQL-Ergebnis die Tiele, die für eine atom-Klasse passen.
    Damit es keine Verwechslungen von id von work oder id von book gibt, verwenden wir prefexes beim SQL
    SELECT 
    b.*,                          -- Alle Buch-Spalten (id, title, path...)
    w.id as w_id,                 -- Werk-ID "getarnt" als w_id
    w.title as w_title,           -- Werk-Titel als w_title
    s.id as s_id,                 -- Serien-ID als s_id
    s.name as s_name              -- Serien-Name als s_name
    FROM books b
    LEFT JOIN works w ON b.work_id = w.id
    LEFT JOIN series s ON w.series_id = s.id
    WHERE b.id = ?
 
    # 1. Den Kern aus der DB holen
    kern = Database.query_one(query, [book_id])
    
    # 2. Die Atome montieren
    self.book = kern_to_atom(BookTData, kern)             # Sucht id, title...
    self.work = kern_to_atom(WorkTData, kern, präfix="w_") # Sucht w_id, w_title...
    self.serie = kern_to_atom(SerieTData, kern, präfix="s_") # Sucht s_id, s_name...
"""

def kern_to_atom(cls, kern, prefix=""):
    """Universeller Wandler - steht ganz alleine für sich."""
    if kern is None: return cls()
    reine_energie = {}
    for f in fields(cls):
        db_name = f"{prefix}{f.name}"
        if db_name in kern.keys():
            wert = kern[db_name]
            if f.type is set or str(f.type) == 'set':
                wert = to_set(wert)
            reine_energie[f.name] = wert
    return cls(**reine_energie)



# --- DATEN-ATOME (Die DNA) ---
@dataclass
class BookTData:
    # Einfache Typen mit Default None
    id: int = 0
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
    authors: set = field(default_factory=set)
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)


    def save_with_cursor(self, cursor):
        """
        Gehorsame Persistenz:
        Nur Felder != None werden in der DB überschrieben.
        """
        b_dict = prepare_for_db(self)
        table_id = b_dict.pop('id', 0)

        if table_id > 0:
            cols = ", ".join([f"{k}=?" for k in b_dict.keys()])
            cursor.execute(f"UPDATE books SET {cols} WHERE id=?", (*b_dict.values(), table_id))
        else:
            cols = ", ".join(b_dict.keys())
            placeholders = ", ".join(["?"] * len(b_dict))
            cursor.execute(f"INSERT INTO books ({cols}) VALUES ({placeholders})", tuple(b_dict.values()))
            self.id = cursor.lastrowid

@dataclass
class WorkTData:
    id: int = 0
    title: str = ""
    slug: str = ""
    title_de: str = ""
    title_en: str = ""
    title_fr: str = ""
    title_es: str = ""
    title_it: str = ""
    description: str = ""
    series_id: int = 0
    series_index: float = 0.0
    stars: int = 0
    rating: float = 0.0
    genre: str = ""
    keywords: set = field(default_factory=set)
    regions: set = field(default_factory=set)


@dataclass
class SerieTData:
    id: int = 0      # None = Unbekannt/Neu, 0 = Fehler, >0 = Existiert
    name: str = ""
    slug: str = ""
    name_de: str = ""
    name_en: str = ""
    name_fr: str = ""
    name_es: str = ""
    name_it: str = ""
    notes: str = ""
    link: str = ""
    author_main: str = ""
    author_count: int = 0
    padding: int = 2

@dataclass
class AudioTData:
    id: int = 0
    work_id: int = 0
    title: str = ""
    series_name: str = ""
    series_index: float = 0.0
    year: str = ""
    language: str = ""
    genre: str = ""
    path: str = ""
    cover_path: str = ""
    speaker: str = ""
    stars: int = 0
    length: float = 0.0  # Spalte 'length' als REAL (Stunden)
    description: str = ""
    authors: set = field(default_factory=set)


@dataclass
class AuthorTData:
    id: int = 0
    firstname: str = ""
    lastname: str = ""
    language: str = ""
    birth_year: int = 0
    birth_place: str = ""
    birth_date: str = ""
    slug: str = ""
    url_de: str = ""
    url_en: str = ""
    url_fr: str = ""
    url_es: str = ""
    url_it: str = ""
    vita: str = ""
    country: str = ""
    stars: int = 0
    image_path: str = ""
    # Hier nutzen wir ein Set für die Logik
    aliases: set = field(default_factory=set)


# --- DER CORE (Warp-Drive mit 5 Kerne) ---
class Core:
    """
    Der Warp-Core: Container für alle Daten-Atome.
    Erledigt die Logistik zwischen Python-Objekten und DB-Kernen.
    """
    def __init__(self, book=None, work=None, serie=None, audio=None, author=None):
        self.book = book or BookTData()
        self.work = work or WorkTData()
        self.serie = serie or SerieTData()
        self.audio = audio or AudioTData()
        self.author = author or AuthorTData()

        self.is_in_db = False
        self.db_snapshot = None
        self.author_ids = set()


    """
    Wandelt einen DB-Datensatz (Kern) in eine Klasse (Atom) um.
    Kern = SELECT * FROM books WHERE id = 42, d.h {'id': 42, 'title': 'Die unendliche Geschichte',..}
    Ein JOIN ist super, da ein Kern dann Daten für alle Atome enthält.
    Dann holen wir nur die Felder aus dem dictionary, die in der Klasse z.B. BookTData sind.
    Weil wir @dataclass über unsere Klassen schreiben, passiert im Hintergrund etwas Magisches: Introspektion.
        all_fields = fields(BookTData) und fields haben .name, .type und .defaults.
        
    def kern_to_atom(BookTData, kern):
        if kern is None:
            return cls()
        
        # Wir wandeln den Kern (sqlite3.Row) in ein Dictionary um
        kern_daten = dict(kern)
        
        for f in fields(cls):
            # Automatisches Re-Aktivieren von Sets (aus JSON-Strings)
            if f.type is set or f.type == 'set':
                raw_val = kern_daten.get(f.name)
                kern_daten[f.name] = to_set(raw_val)
        
        # Wir nehmen nur die Daten, die in die Atom-Hülle passen
        mantel = {f.name for f in fields(cls)}
        reine_energie = {k: v for k, v in kern_daten.items() if k in mantel}
        
        return cls(**reine_energie)
        
        SELECT 
        b.*,                          -- Alle Buch-Spalten (id, title, path...)
        w.id as w_id,                 -- Werk-ID "getarnt" als w_id
        w.title as w_title,           -- Werk-Titel als w_title
        s.id as s_id,                 -- Serien-ID als s_id
        s.name as s_name              -- Serien-Name als s_name
        FROM books b
        LEFT JOIN works w ON b.work_id = w.id
        LEFT JOIN series s ON w.series_id = s.id
        WHERE b.id = ?
     
        # 1. Den Kern aus der DB holen
        kern = Database.query_one(query, [book_id])
        
        # 2. Die Atome montieren
        self.book = kern_to_atom(BookTData, kern)             # Sucht id, title...
     
    """


    @classmethod
    def from_kern(cls, kern, *atom_classes):
        """
        Transporter-Raum: Erzeugt einen Core aus einem DB-Kern.
        Beispiel: core = Core.from_kern(mein_kern, BookTData, WorkTData)
        """
        init_dict = {}
        # Mapping von Klasse auf Attributname
        mapping = {
            BookTData: 'book', WorkTData: 'work',
            SerieTData: 'serie', AudioTData: 'audio', AuthorTData: 'author'
        }

        for atom_cls in atom_classes:
            key = mapping.get(atom_cls)
            if key:
                # Nutzt die Logik: Kern -> Atom
                init_dict[key] = kern_to_atom(atom_cls, kern)

        return cls(**init_dict)

    @classmethod
    def load_book_by_path(cls, path: str) -> Optional['Core']:
        # Wir brauchen ALLES von book work und serie
        # 1. Buch laden
        book_data = Database.query_one("SELECT * FROM books WHERE path = ?", [path])
        if not book_data:
            return None

        # 2. Werk laden (falls work_id vorhanden)
        work_data = None
        if book_data.get('work_id'):
            work_data = Database.query_one("SELECT * FROM works WHERE id = ?", [book_data['work_id']])

        # 3. Serie laden (falls series_id im Werk vorhanden)
        series_data = None
        if work_data and work_data.get('series_id'):
            series_data = Database.query_one("SELECT * FROM series WHERE id = ?", [work_data['series_id']])

        # Jetzt kannst du dein 'Core' Objekt aus den drei Puzzleteilen bauen
        book_atom = kern_to_atom(BookTData, book_data)
        work_atom = kern_to_atom(WorkTData, work_data) if work_data else None
        serie_atom = kern_to_atom(SerieTData, series_data) if series_data else None

        # 3. Core Objekt instanziieren
        core = cls(book=book_atom, work=work_atom, serie=serie_atom)

        # 4. Autoren nachladen (Spezialfall n:m)
        if core.work:
            author_query = "SELECT author_id FROM work_to_author WHERE work_id = ?"
            rows = Database.query_all(author_query, [core.work.id])
            core.author_ids = {row['author_id'] for row in rows}
        return core

    @classmethod
    def load_book_by_path_alternative(cls, path: str) -> Optional['Core']:
        """Lädt den kompletten Verbund (Book, Work, Serie) über einen JOIN."""
        query = """
            SELECT b.*, 
                   w.id as w_id, w.title as w_title, w.series_id as w_series_id, 
                   w.stars as w_stars, w.title_de as w_title_de, w.title_en as w_title_en,
                   w.title_fr as w_title_fr, w.title_es as w_title_es, w.title_it as w_title_it,
                   w.description as w_description, w.genre as w_genre,
                   s.id as s_id, s.name as s_name, s.name_de as s_name_de, s.name_en as s_name_en,
                   s.name_fr as s_name_fr, s.name_es as s_name_es, s.name_it as s_name_it
            FROM books b
            LEFT JOIN works w ON b.work_id = w.id
            LEFT JOIN series s ON w.series_id = s.id
            WHERE b.path = ?
        """

        kern = Database.query_one(query, [path])
        if not kern:
            return None

        # --- DIAGNOSE (Korrekt auf den Index/Key zugreifen) ---
        print(f"\n[SENSOR-CHECK] Lade Daten für Pfad: {path}")
        # kern ist ein dict-ähnliches Objekt, kein Objekt mit .book Attribut!
        print(f"ID: {kern['id']} | Titel: {kern['title']} | Genre: {kern.get('genre')}")

        # --- DIE ATOME MONTIEREN ---
        # 1. Book (kein Präfix, da b.*)
        book_atom = kern_to_atom(BookTData, kern)

        # 2. Work (mit w_ Präfix aus dem SQL)
        work_atom = kern_to_atom(WorkTData, kern, prefix="w_")

        # 3. Serie (mit s_ Präfix aus dem SQL)
        serie_atom = kern_to_atom(SerieTData, kern, prefix="s_")

        # Core instanziieren
        core = cls(book=book_atom, work=work_atom, serie=serie_atom)

        # 4. Autoren-IDs nachladen (n:m Verknüpfung)
        if core.work and core.work.id:
            author_query = "SELECT author_id FROM work_to_author WHERE work_id = ?"
            rows = Database.query_all(author_query, [core.work.id])
            core.author_ids = {row['author_id'] for row in rows}

        # Status sichern für späteren Vergleich (Dirty-Checking)
        core.capture_db_state()
        return core

    @classmethod
    def load_audio_by_path(cls, path: str) -> Optional['Core']:
        """
        Lädt den kompletten Verbund basierend auf einem Hörbuch-Pfad.
        Reihenfolge: Audio -> Werk -> Serie -> Autoren
        """

        # 1. Das Audio-Atom laden
        audio_kern = Database.query_one("SELECT * FROM audios WHERE path = ?", [path])
        if not audio_kern:
            return None

        audio_atom = kern_to_atom(AudioTData, audio_kern)

        # 2. Das zugehörige Werk laden (über die work_id des Audios)
        work_atom = WorkTData()
        if audio_atom.work_id > 0:
            work_kern = Database.query_one("SELECT * FROM works WHERE id = ?", [audio_atom.work_id])
            if work_kern:
                work_atom = kern_to_atom(WorkTData, work_kern)

        # 3. Die zugehörige Serie laden (über die series_id des Werks)
        serie_atom = SerieTData()
        if work_atom.series_id > 0:
            serie_kern = Database.query_one("SELECT * FROM series WHERE id = ?", [work_atom.series_id])
            if serie_kern:
                serie_atom = kern_to_atom(SerieTData, serie_kern)

        # 4. Core instanziieren und mit Atomen bestücken
        core = cls(audio=audio_atom, work=work_atom, serie=serie_atom)
        core.is_in_db = True

        # 5. Autoren-IDs nachladen (wichtig für den LogicService Match)
        if core.work.id > 0:
            author_rows = Database.query_all(
                "SELECT author_id FROM work_to_author WHERE work_id = ?",
                [core.work.id]
            )
            core.author_ids = {row['author_id'] for row in author_rows}

        # Snapshot für Dirty-Checking erstellen
        core.capture_db_state()
        return core



#-----------SAVE LOGIK ---------------

    def save_book_only(self) -> bool:
        """
        Schnittstelle für externe Scans.
        Speichert NUR das Buch-Atom, ohne Rücksicht auf Work oder Serie.
        """
        try:
            with Database.conn() as conn:
                cursor = conn.cursor()

                # Wir nutzen die universelle Logik
                # Sie entscheidet anhand von book.id selbst: INSERT oder UPDATE
                generic_save(self.book, "books", cursor)

                conn.commit()
                self.capture_db_state()
                return True
        except Exception as e:
            print(f"❌ Fehler beim schnellen Buch-Save: {e}")
            return False


    def save(self) -> bool:
        """Der Dirigent: Öffnet die Transaktion und delegiert die Arbeit."""
        try:
            with Database.conn() as conn:
                cursor = conn.cursor()

                # Wir rufen die interne Logik auf und geben ihr den Cursor
                if self._do_save_all(cursor):
                    conn.commit()
                    self.capture_db_state()
                    return True
        except Exception as e:
            print(f"❌ Transaktion gescheitert: {e}")
            raise e
        return False


    def _do_save_all(self, cursor) -> bool:
        """Die eigentliche Logik: Schreibt Atome in strikter Reihenfolge."""
        # 1. Serie
        if self.serie.name:
            generic_save(self.serie, "series", cursor)

        # 2. Work
        if self.work.title:
            if self.serie.id > 0:
                self.work.series_id = self.serie.id
            generic_save(self.work, "works", cursor)
            self._sync_work_authors(cursor)  # Wichtig: nutzt denselben cursor!

        # 3. Book
        if self.book.path:
            if self.work.id > 0:
                self.book.work_id = self.work.id
            generic_save(self.book, "books", cursor)

        # 4. Audio
        if self.audio.path:
            if self.work.id > 0:
                self.audio.work_id = self.work.id
            generic_save(self.audio, "audios", cursor)

        return True

    def _sync_work_authors(self, cursor):
        """
        Synchronisiert die m:n Verknüpfungstabelle 'work_to_author'.
        Löscht alte Verbindungen und setzt neue basierend auf self.author_ids.
        """
        # Ohne Werk-ID können wir nichts verknüpfen
        if not self.work.id:
            return

        # 1. Alle bisherigen Autoren-Verknüpfungen für dieses Werk löschen
        # (Tabula Rasa, damit wir nicht doppelt buchführen)
        cursor.execute("DELETE FROM work_to_author WHERE work_id = ?", (self.work.id,))

        # 2. Neue Verknüpfungen eintragen
        # Wir gehen davon aus, dass in self.author_ids reine Integers (IDs) liegen
        for a_id in self.author_ids:
            if a_id and a_id > 0:
                cursor.execute(
                    "INSERT OR IGNORE INTO work_to_author (work_id, author_id) VALUES (?, ?)",
                    (self.work.id, a_id)
                )

    def capture_db_state(self):
        """Erstellt ein Backup der aktuellen Atome."""
        self.db_snapshot = copy.deepcopy({
            'book': self.book, 'work': self.work, 'serie': self.serie,
            'audio': self.audio, 'author': self.author
        })
        self.is_in_db = True
