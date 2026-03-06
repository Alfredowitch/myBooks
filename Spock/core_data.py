"""
s_core: Was wir draußen im All (Dateisystem) gefunden haben.
b_core: Was der Commander (User) befohlen hat.
a_core: Was in den Schiffslogbüchern (DB) steht.
z_core: Die Wahrheit, die am Ende übrig bleibt und gespeichert wird.
"""

from __future__ import annotations
import sqlite3
import traceback
import re
import json
import os
import logging
import unicodedata
from tqdm import tqdm
from typing import Optional
from dataclasses import asdict, fields
from Spock.enterprise import BookTData, WorkTData, SerieTData


class Spock:
    # Der Ankerpunkt für das Schiff
    DB_PATH = r"C:\DB\books.db"
    EBOOK_BASE = r"D:\Bücher"

    @staticmethod
    def get_connection():
        """Zentrale Methode für den DB-Zugriff."""
        conn = sqlite3.connect(Spock.DB_PATH)
        # Wir nutzen row_factory für den Zugriff via Spaltennamen
        conn.row_factory = sqlite3.Row
        return conn

    def __init__(self, book_obj=None, work_obj=None, serie_obj=None):
        self.book = book_obj or BookTData()
        self.work = work_obj or WorkTData()
        self.serie = serie_obj or SerieTData()
        self.is_in_db = False

    # ----------------------------------------------------------------------
    # Laden eines Buches
    # ----------------------------------------------------------------------
    @classmethod
    def load(cls, file_path: str) -> Optional[Spock]:
        """
        Spock scannt die Datenbank nach einem existierenden Pfad.
        Gibt None zurück, wenn das Buch neu im Sektor ist.
        """
        with cls.get_connection() as conn:
            res = conn.execute("SELECT * FROM books WHERE path = ?", (file_path,)).fetchone()
            if not res:
                return None

            # Buch-Atom füllen
            # (Hier nutzen wir deine Logik zum Mapping der Felder)
            book_atom = BookTData(**dict(res))
            instance = cls(book_obj=book_atom)
            instance.is_in_db = True

            # Falls bereits verknüpft, laden wir Werk und Serie direkt in den Speicher
            if book_atom.work_id:
                instance.energize_work(book_atom.work_id)
                if instance.work.series_id:
                    instance.energize_serie(instance.work.series_id)
            return instance


    def _energize_atom(self, atom, table_name: str, identifier: int):
        """Interne Hilfsmethode, um ein beliebiges Atom mit DB-Daten zu laden."""
        if not identifier: return

        with self.get_connection() as conn:
            row = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (identifier,)).fetchone()
            if row:
                # Wir mappen die Spalten auf die Felder des Atoms (Book, Work oder Serie)
                for f in fields(atom):
                    if f.name in row.keys():
                        setattr(atom, f.name, row[f.name])
                # Sicherstellen, dass die ID im Objekt fixiert ist
                atom.id = identifier

    def energize_book(self, book_id: int):
        print(f"⚡ Energizing Book {book_id}...")
        self._energize_atom(self.book, "books", book_id)

    def energize_work(self, work_id: int):
        print(f"⚡ Energizing Work {work_id}...")
        self._energize_atom(self.work, "works", work_id)

    def energize_serie(self, serie_id: int):
        print(f"⚡ Energizing Serie {serie_id}...")
        self._energize_atom(self.serie, "series", serie_id)

    def _db_update_work_defensive(self, cursor):
        """Aktualisiert ein bestehendes Werk, ohne die ID zu ändern."""
        w_dict = {k: v for k, v in asdict(self.work).items() if not isinstance(v, (list, dict, set)) and k != 'id'}
        #w_dict['slug'] = Scotty.slugify(self.work.title or "unbekannt")

        cols = ", ".join([f"{k}=?" for k in w_dict.keys()])
        cursor.execute(f"UPDATE works SET {cols} WHERE id=?", (*w_dict.values(), self.work.id))

    def _get_db_columns(self, cursor, table_name: str) -> list:
        """Hilfsmethode: Holt die tatsächlich existierenden Spalten der DB-Tabelle."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row[1] for row in cursor.fetchall()]

    @staticmethod
    def get_all_known_paths() -> set:
        """Holt alle Pfade aus der DB und gibt sie als Set zurück."""
        try:
            with Spock.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT path FROM books WHERE path IS NOT NULL AND path != ''")
                return {row['path'] for row in cursor.fetchall()}
        except Exception as e:
            logging.error(f"Fehler beim Laden der bekannten Pfade: {e}")
            return set()

    # ----------------------------------------------------------------------
    # Speichern eines Buches
    # ----------------------------------------------------------------------
    @classmethod
    def save_scan_package(cls, data_dict: dict):
        """
        Der Empfänger für Scotties Datenpaket.
        Wandelt das Dict in ein Atom um und speichert es.
        """
        from Spock.enterprise import Core
        # 1. Neues Buch erstellen
        s_core = Core()
        # 2. Daten aus dem Dict in das Atom übertragen
        for key, value in data_dict.items():
            if hasattr(s_core.book, key):
                setattr(s_core.book, key, value)
        # 4. Speichern via Klassen-Verbindung
        spooky = Spock(s_core.book)
        return spooky.save_book_only()

    def save_book_only(self) -> bool:
        """
        PHASE 1 SPEICHERUNG:
        Schreibt NUR das Buch-Atom weg. Verwendet die 'Safe-Merge' Logik
        für Beschreibungen und schützt Commander-Notizen.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Vorbereitung der Daten aus dem Atom
            book_dict = asdict(self.book)
            for key, value in book_dict.items():
                if isinstance(value, list):
                    if key == 'authors':
                        # Autoren als JSON speichern (unser Plan für Phase 1)
                        book_dict[key] = json.dumps(value)
                    else:
                        # Keywords, Regions etc. als Komma-String
                        book_dict[key] = ", ".join(map(str, value))

                # Hygiene-Check (nur existierende Spalten)
            db_cols = self._get_db_columns(cursor, "books")
            safe_data = {k: v for k, v in book_dict.items() if k in db_cols}

            # Listen für SQL-Textfelder konvertieren
            book_dict['keywords'] = ",".join(self.book.keywords) if self.book.keywords else ""
            book_dict['regions'] = ",".join(self.book.regions) if self.book.regions else ""

            # Hygiene-Check
            db_cols = self._get_db_columns(cursor, "books")
            safe_data = {k: v for k, v in book_dict.items() if k in db_cols}

            # Das SQL mit COALESCE und Schutzlogik
            # Wir nutzen Named Placeholders (:name) für bessere Lesbarkeit
            sql = f"""
                    INSERT INTO books ({", ".join(safe_data.keys())})
                    VALUES ({", ".join([":" + k for k in safe_data.keys()])})
                    ON CONFLICT(path) DO UPDATE SET
                        -- 1. DIE KRITISCHEN METADATEN (Das was vorher gefehlt hat)
                        authors = excluded.authors,
                        title = excluded.title,
                        series_name = excluded.series_name,
                        series_index = excluded.series_index,
                        series_number = excluded.series_number,
                        year = excluded.year,
                        language = excluded.language,
                        keywords = excluded.keywords,

                        -- 2. DEINE SPEZIAL-LOGIK FÜR BESCHREIBUNGEN (Beibehalten)
                        description = CASE 
                            WHEN description IS NULL OR description = '' THEN excluded.description 
                            ELSE description 
                        END,
                        notes = CASE 
                            WHEN (description IS NOT NULL AND description != '') 
                                 AND (excluded.description IS NOT NULL AND excluded.description != '')
                                 AND (excluded.description != description)
                            THEN notes || '\n\n-- Alternative Info --\n' || excluded.description 
                            ELSE COALESCE(notes, excluded.description) 
                        END,

                        -- 3. RATINGS & VERSION
                        rating_g = COALESCE(excluded.rating_g, rating_g),
                        rating_g_count = COALESCE(excluded.rating_g_count, rating_g_count),
                        rating_ol = COALESCE(excluded.rating_ol, rating_ol),
                        rating_ol_count = COALESCE(excluded.rating_ol_count, rating_ol_count),
                        scanner_version = excluded.scanner_version,
                        is_complete = 1;
                """
            try:
                cursor.execute(sql, safe_data)
                conn.commit()
                return True
            except Exception as e:
                print(f"💥 Spock: Fehler beim Safe-Save: {e}")
                return False

    def save(self) -> bool:
        """
        Der Befehl zum Sichern. Spock führt die SQL-Operationen strikt aus,
        nachdem Pille die Diagnose gestellt hat.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # A. Serie sichern
                self._db_save_serie(cursor)
                if self.serie.id:
                    self.work.series_id = self.serie.id

                # B. Work sichern (Pille hat work.id auf 0 oder eine echte ID gesetzt)
                if not self.work.id or self.work.id == 0:
                    self.work.id = self._db_insert_work(cursor)
                else:
                    self._db_update_work_defensive(cursor)

                # C. Book sichern und mit Work verknüpfen
                self.book.work_id = self.work.id
                self._db_save_book_raw(cursor)

                # D. Autoren-Verknüpfung synchronisieren
                if self.book.authors:
                    self._db_sync_authors(cursor)

                conn.commit()
                print(f"💾 Spock: System-Matrix gespeichert (Book-ID: {self.book.id}, Work-ID: {self.work.id})")
                return True
            except Exception as e:
                conn.rollback()
                print(f"🖖 Spock: Schwerer Fehler in der Datenbank-Matrix: {e}")
                traceback.print_exc()
                return False

    # --- Die Hilfsmethoden (stumpfe SQL-Ausführung) ---
    def _db_save_serie(self, cursor):
        if not self.serie.name: return
        self.serie.slug = self.slugify(self.serie.name)
        # Suche ID falls noch nicht da
        res = cursor.execute("SELECT id FROM series WHERE name = ?", (self.serie.name,)).fetchone()
        s_id = res[0] if res else None

        s_dict = {k: v for k, v in asdict(self.serie).items() if k != 'id'}
        if s_id:
            cols = ", ".join([f"{k}=?" for k in s_dict.keys()])
            cursor.execute(f"UPDATE series SET {cols} WHERE id=?", (*s_dict.values(), s_id))
            self.serie.id = s_id
        else:
            cols = ", ".join(s_dict.keys())
            cursor.execute(f"INSERT INTO series ({cols}) VALUES ({','.join(['?'] * len(s_dict))})",
                           tuple(s_dict.values()))
            self.serie.id = cursor.lastrowid

    def _db_insert_work(self, cursor) -> int:
        w_dict = {k: v for k, v in asdict(self.work).items() if not isinstance(v, (list, dict, set)) and k != 'id'}
        w_dict['slug'] = self.slugify(self.work.title or "unbekannt")
        cols = ", ".join(w_dict.keys())
        cursor.execute(f"INSERT INTO works ({cols}) VALUES ({','.join(['?'] * len(w_dict))})", list(w_dict.values()))
        return cursor.lastrowid

    def _db_save_book_raw(self, cursor):
        """Spock schreibt das Buch-Atom und führt Hygiene-Checks durch."""
        book_dict = asdict(self.book)

        # 1. Bekannte 'Nicht-Spalten' transformieren oder entfernen
        book_dict['keywords'] = ",".join(self.book.keywords)
        book_dict['regions'] = ",".join(self.book.regions)
        if 'authors' in book_dict: del book_dict['authors']

        # 2. Hygiene-Check: Was hat Platz in der DB?
        db_cols = self._get_db_columns(cursor, "books")
        # Finden wir Felder im Atom, die die DB (noch) nicht hat?
        orphans = [k for k in book_dict.keys() if k not in db_cols]
        if orphans:
            print(f"⚠️  Spock Hygiene-Warnung: Felder {orphans} sind im Core, aber nicht in der DB.")
            print(f"   -> Diese Daten werden momentan NICHT persistent gespeichert.")

        # 3. Nur sichere Daten behalten
        safe_data = {k: v for k, v in book_dict.items() if k in db_cols}

        # 4. Jetzt erst das SQL bauen
        if self.book.id:
            cols = ", ".join([f"{k}=?" for k in safe_data.keys() if k != 'id'])
            vals = [v for k, v in safe_data.items() if k != 'id']
            cursor.execute(f"UPDATE books SET {cols} WHERE id=?", (*vals, self.book.id))
        else:
            if 'id' in safe_data: del safe_data['id']
            cols = ", ".join(safe_data.keys())
            cursor.execute(f"INSERT INTO books ({cols}) VALUES ({','.join(['?'] * len(safe_data))})",
                           list(safe_data.values()))
            self.book.id = cursor.lastrowid

    def _db_sync_authors(self, cursor):
        """Verknüpft Autoren. Spock führt die Anweisungen stur aus."""
        # Bestehende Verknüpfungen für dieses Werk lösen, um Dubletten zu vermeiden
        cursor.execute("DELETE FROM work_to_author WHERE work_id = ?", (self.work.id,))

        for fn, ln in self.book.authors:
            slug = self.slugify(f"{fn} {ln}")
            # Autor anlegen, falls er noch nicht existiert
            cursor.execute(
                "INSERT OR IGNORE INTO authors (firstname, lastname, slug) VALUES (?,?,?)",
                (fn, ln, slug)
            )
            # Die ID des Autors holen
            res = cursor.execute("SELECT id FROM authors WHERE slug=?", (slug,)).fetchone()
            if res:
                aid = res[0]
                # Werk mit Autor verknüpfen
                cursor.execute(
                    "INSERT OR IGNORE INTO work_to_author (work_id, author_id) VALUES (?,?)",
                    (self.work.id, aid)
                )

    @staticmethod
    def slugify(value: str) -> str:
        if not value: return "unknown"
        value = str(value)
        repls = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}
        for char, replacement in repls.items():
            value = value.replace(char, replacement)
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value).strip().lower()
        return re.sub(r'[-\s]+', '-', value)

    def ghost_cleaner(self):
        """Sucht nach verwaisten Datenbankeinträgen mit tqdm Fortschrittsbalken."""
        stats = {
            'total_checked': 0,
            'removed_books': 0,
            'removed_works': 0,
            'removed_series': 0,
            'removed_authors': 0
        }

        print("\n" + "=" * 50)
        print("👻 GHOST-CLEANER: Starte System-Bereinigung")
        print("=" * 50)

        with self.get_connection() as conn:
            # 1. Alle Bücher laden
            cursor = conn.execute("SELECT id, path, title FROM books")
            all_books = cursor.fetchall()
            stats['total_checked'] = len(all_books)

            dead_ids = []

            # Hier kommt tqdm zum Einsatz:
            # desc = Text vor dem Balken, unit = Maßeinheit
            for b_id, path, title in tqdm(all_books, desc="🔍 Dateiprüfung", unit="Datei"):
                if not path or not os.path.exists(path):
                    dead_ids.append((b_id,))

            # 2. Löschvorgänge
            if dead_ids:
                print(f"\n🗑️  Lösche {len(dead_ids)} verwaiste Einträge aus 'books'...")
                conn.executemany("DELETE FROM books WHERE id = ?", dead_ids)
                stats['removed_books'] = len(dead_ids)

            # 3. Kaskadierender Hausputz (Meta-Daten)
            # Wir nutzen hier print, da diese SQL-Statements meist blitzschnell sind
            print("⚙️  Bereinige Werke...")
            res_w = conn.execute("""
                DELETE FROM works 
                WHERE id NOT IN (SELECT DISTINCT work_id FROM books WHERE work_id IS NOT NULL)
            """)
            stats['removed_works'] = res_w.rowcount

            print("📚 Bereinige Serien...")
            res_s = conn.execute("""
                DELETE FROM series 
                WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)
            """)
            stats['removed_series'] = res_s.rowcount

            print("✍️  Bereinige Autoren...")
            conn.execute("DELETE FROM work_to_author WHERE work_id NOT IN (SELECT id FROM works)")
            res_a = conn.execute("""
                DELETE FROM authors 
                WHERE id NOT IN (SELECT DISTINCT author_id FROM work_to_author)
            """)
            stats['removed_authors'] = res_a.rowcount

            conn.commit()

        # Die Statistik-Ausgabe am Ende
        print("=" * 40)
        print("📊 GHOST-CLEANER ABSCHLUSS-BERICHT")
        print("-" * 40)
        print(f"  Geprüfte Einträge:    {stats['total_checked']:>6}")
        print(f"  Gelöschte Bücher:     {stats['removed_books']:>6} 🗑️")
        print(f"  Bereinigte Werke:     {stats['removed_works']:>6} ⚙️")
        print(f"  Bereinigte Serien:    {stats['removed_series']:>6} 📚")
        print(f"  Bereinigte Autoren:   {stats['removed_authors']:>6} ✍️")
        print("-" * 40)
        print("💎 Datenbank ist jetzt wieder blitzblank.")
        print("=" * 40)


if __name__ == "__main__":
    sanitizer = Spock()
    sanitizer.ghost_cleaner()