import os
import sqlite3
from tqdm import tqdm
from Zoom.utils import DB_PATH

class Maintenance:
    @classmethod
    def deep_repair_library(cls):
        print(f"\n--- 🛠️ START DEEP REPAIR (V1.5 Aggregat-Cleanup) ---")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. SCHRITT: Bücher-Check (Physische Konsistenz)
        cursor.execute("SELECT id, path FROM books")
        all_books = cursor.fetchall()
        cleaned_books = 0

        for b_id, b_path in tqdm(all_books, desc="Prüfe Dateien"):
            # A) Geister-Pfade löschen
            if not b_path or not os.path.exists(b_path):
                cursor.execute("DELETE FROM books WHERE id = ?", (b_id,))
                cleaned_books += 1
                continue

            # B) Dubletten-Check
            cursor.execute("SELECT id FROM books WHERE path = ? AND id > ?", (b_path, b_id))
            if cursor.fetchone():
                cursor.execute("DELETE FROM books WHERE id = ?", (b_id,))
                cleaned_books += 1

        conn.commit()
        print(f"✅ {cleaned_books} tote Bucheinträge entfernt.")

        # 2. SCHRITT: Herrenlose Werke (Orphan Works)
        cursor.execute("""
            DELETE FROM works 
            WHERE id NOT IN (SELECT DISTINCT work_id FROM books WHERE work_id IS NOT NULL)
        """)
        print(f"🧹 {cursor.rowcount} herrenlose Werke gelöscht.")

        # 3. SCHRITT: Herrenlose Serien (Orphan Series)
        cursor.execute("""
            DELETE FROM series 
            WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)
        """)
        print(f"🧹 {cursor.rowcount} herrenlose Serien gelöscht.")

        # 4. SCHRITT: Autoren-Hygiene (Mappings & verwaiste Autoren)
        # Mappings löschen
        cursor.execute("DELETE FROM work_to_author WHERE work_id NOT IN (SELECT id FROM works)")
        # Autoren löschen, die kein Werk mehr haben
        cursor.execute("""
            DELETE FROM authors 
            WHERE id NOT IN (SELECT DISTINCT author_id FROM work_to_author)
        """)
        print(f"🧹 {cursor.rowcount} verwaiste Autoren-Einträge entfernt.")

        # 5. ABSCHLUSS
        conn.commit()
        conn.execute("VACUUM")
        conn.close()
        print("✨ Datenbank-Hygiene abgeschlossen.")

    @classmethod
    def check_health(cls, conn=None):
        """Qualitätsprüfung der V1.5 Datenstruktur."""
        should_close = False
        if conn is None:
            conn = sqlite3.connect(DB_PATH)
            should_close = True

        cursor = conn.cursor()
        print("\n--- 🩺 DATENBANK HEALTH CHECK (V1.5) ---")

        checks = {
            "Werke ohne Autor": "SELECT COUNT(*) FROM works WHERE id NOT IN (SELECT work_id FROM work_to_author)",
            "Werke ohne Beschreibung": "SELECT COUNT(*) FROM works WHERE description IS NULL OR description = ''",
            "Bücher ohne Werk-Link": "SELECT COUNT(*) FROM books WHERE work_id IS NULL OR work_id = 0",
            "Werke ohne Serien-ID (trotz Name)": """
                SELECT COUNT(DISTINCT w.id) FROM works w
                JOIN books b ON b.work_id = w.id
                WHERE b.series_name IS NOT NULL AND b.series_name != '' 
                AND (w.series_id IS NULL OR w.series_id = 0)
            """
        }

        for label, sql in checks.items():
            cursor.execute(sql)
            count = cursor.fetchone()[0]
            print(f"{label:35}: {count}")

        if should_close:
            conn.close()

if __name__ == "__main__":
    Maintenance.deep_repair_library()
    Maintenance.check_health()