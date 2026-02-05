import sqlite3
import os
from tqdm import tqdm
from Zoom.utils import DB_PATH

class DatabaseSanitizer:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def run_full_cleanup(self):
        """
        Führt den kompletten Reinigungsprozess in der richtigen Reihenfolge aus.
        """
        print("\n🚀 Starte Datenbank-Sanierung (v1.6)...")
        
        # 1. Nicht mehr existierende Pfade markieren
        self.mark_dead_paths()
        # 2. Hard Cleanup (Physisches Löschen der Leichen)
        self.perform_hard_cleanup()
        # 3. Konsistenz-Check
        self.final_consistency_check()

    def mark_dead_paths(self):
        """
        Prüft alle Pfade in der DB. Wenn die Datei weg ist, wird der Pfad auf '' gesetzt.
        """
        print("🔍 Phase 1: Prüfe physikalische Dateipfade...")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, path FROM books WHERE path IS NOT NULL AND path != ''")
            books = cursor.fetchall()

            dead_ids = []
            for book in tqdm(books, desc="Dateiprüfung", unit="Datei"):
                if not os.path.exists(book['path']):
                    dead_ids.append((book['id'],))

            if dead_ids:
                print(f"💀 {len(dead_ids)} tote Pfade gefunden. Markiere für Löschung...")
                # Wir setzen den Pfad auf leer, um im nächsten Schritt sauber zu löschen
                conn.executemany("UPDATE books SET path = '', work_id = NULL WHERE id = ?", dead_ids)
                conn.commit()
            else:
                print("✅ Alle in der DB registrierten Dateien sind physisch vorhanden.")

    def perform_hard_cleanup(self):
        """
        Löscht Bücher ohne Pfad und alle daraus resultierenden verwaisten Einträge.
        """
        print("🔥 Phase 2: Hard Cleanup (Kaskadierendes Löschen)...")
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. Bücher ohne Pfad löschen
            cursor.execute("DELETE FROM books WHERE path = '' OR path IS NULL")
            print(f"  - Bücher gelöscht: {cursor.rowcount}")

            # 2. Works ohne Bücher löschen
            cursor.execute("""
                DELETE FROM works 
                WHERE id NOT IN (SELECT DISTINCT work_id FROM books WHERE work_id IS NOT NULL)
            """)
            print(f"  - Verwaiste Werke gelöscht: {cursor.rowcount}")

            # 3. Work-to-Author Mappings säubern
            cursor.execute("DELETE FROM work_to_author WHERE work_id NOT IN (SELECT id FROM works)")
            print(f"  - Autoren-Verknüpfungen bereinigt: {cursor.rowcount}")

            # 4. Serien ohne Werke löschen
            cursor.execute("""
                DELETE FROM series 
                WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)
            """)
            print(f"  - Leere Serien gelöscht: {cursor.rowcount}")

            # 5. Autoren ohne Works löschen
            cursor.execute("""
                DELETE FROM authors 
                WHERE id NOT IN (SELECT DISTINCT author_id FROM work_to_author)
            """)
            print(f"  - Autoren ohne Werke gelöscht: {cursor.rowcount}")

            conn.commit()

    def final_consistency_check(self):
        """
        Letzte Optimierung der Datenbankdatei.
        """
        print("📦 Phase 3: Datenbank-Vakuumierung...")
        with self._get_conn() as conn:
            conn.execute("VACUUM")
        print("✨ System ist jetzt blitzsauber und konsistent.")

if __name__ == "__main__":
    sanitizer = DatabaseSanitizer()
    sanitizer.run_full_cleanup()