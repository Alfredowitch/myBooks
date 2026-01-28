"""
DATEI: maintenance.py
VERSION: 1.4.3 (v1.3 Portierung + Orphan Cleanup)
BESCHREIBUNG: Bereinigt Pfadleichen, Dubletten und herrenlose Werke/Serien.
"""
import os
import sqlite3
from tqdm import tqdm
from Zoom.utils import DB_PATH


class Maintenance:
    @classmethod
    def deep_repair_library(cls):
        print(f"--- START DEEP REPAIR (Atom-Cleanup & Orphan-Hunt) ---")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. SCHRITT: Bücher-Check (Gelbe Zone)
        cursor.execute("SELECT id, path FROM books")
        all_books = cursor.fetchall()
        cleaned_books = 0

        for b_id, b_path in tqdm(all_books, desc="Prüfe Dateiexistenz"):
            # A) Geister-Pfade löschen (Datei existiert nicht mehr)
            if not b_path or not os.path.exists(b_path):
                cursor.execute("DELETE FROM books WHERE id = ?", (b_id,))
                cleaned_books += 1
                continue

            # B) Dubletten-Check (Gleicher Pfad mehrfach in DB)
            cursor.execute("SELECT id FROM books WHERE path = ? AND id > ?", (b_path, b_id))
            if cursor.fetchone():
                cursor.execute("DELETE FROM books WHERE id = ?", (b_id,))
                cleaned_books += 1

        conn.commit()
        print(f"✅ {cleaned_books} Bucheinträge (Leichen/Dubletten) entfernt.")

        # 2. SCHRITT: Herrenlose Werke (Grüne Zone)
        # Ein Werk ist "herrenlos", wenn kein Buch (gelb) mehr darauf verweist.
        cursor.execute("""
            DELETE FROM works 
            WHERE id NOT IN (SELECT DISTINCT work_id FROM books WHERE work_id IS NOT NULL)
        """)
        cleaned_works = cursor.rowcount
        print(f"🧹 {cleaned_works} herrenlose Werke gelöscht.")

        # 3. SCHRITT: Herrenlose Serien (Blaue Zone)
        # Eine Serie ist "herrenlos", wenn kein Werk (grün) mehr darauf verweist.
        cursor.execute("""
            DELETE FROM series 
            WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)
        """)
        cleaned_series = cursor.rowcount
        print(f"🧹 {cleaned_series} herrenlose Serien gelöscht.")

        # 4. SCHRITT: Verwaiste Autoren-Mappings
        # Löscht Einträge in work_to_author, deren Werk nicht mehr existiert.
        cursor.execute("""
            DELETE FROM work_to_author 
            WHERE work_id NOT IN (SELECT id FROM works)
        """)

        # 5. ABSCHLUSS
        conn.commit()
        conn.execute("VACUUM")
        conn.close()
        print("✨ Datenbank-Hygiene abgeschlossen. Alles ist nun konsistent.")


@classmethod
def check_health(cls, conn=None):
    """Führt eine Qualitätsprüfung der Datenbank durch."""
    should_close = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        should_close = True

    cursor = conn.cursor()
    print("\n--- 🩺 Datenbank Health Check ---")

    # 1. Werke ohne Autoren
    cursor.execute("""
            SELECT COUNT(*) FROM works 
            WHERE id NOT IN (SELECT work_id FROM work_to_author)
        """)
    no_author = cursor.fetchone()[0]
    print(f"Werke ohne Autor:        {no_author}")

    # 2. Werke ohne Beschreibung
    cursor.execute("SELECT COUNT(*) FROM works WHERE description IS NULL OR description = ''")
    no_desc = cursor.fetchone()[0]
    print(f"Werke ohne Beschreibung:  {no_desc}")

    # 3. Werke ohne Genre
    cursor.execute("SELECT COUNT(*) FROM works WHERE genre IS NULL OR genre = ''")
    no_genre = cursor.fetchone()[0]
    print(f"Werke ohne Genre:         {no_genre}")

    # 4. Fehlende Serien-Verknüpfungen (Gelb zu Blau)
    cursor.execute("""
            SELECT COUNT(DISTINCT b.series_name) 
            FROM books b
            LEFT JOIN series s ON b.series_name = s.name
            WHERE b.series_name IS NOT NULL AND b.series_name != '' AND s.id IS NULL
        """)
    missing_series = cursor.fetchone()[0]
    print(f"Unbekannte Serien-Namen:  {missing_series}")

    # 5. Herrenlose Atome (Zusatz-Check)
    cursor.execute("SELECT COUNT(*) FROM works WHERE id NOT IN (SELECT DISTINCT work_id FROM books)")
    orphan_works = cursor.fetchone()[0]
    print(f"Herrenlose Werke:         {orphan_works}")

    if should_close:
        conn.close()

if __name__ == "__main__":
    Maintenance.deep_repair_library()
