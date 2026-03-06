# Engineering.health_service.py
import os
import re
from tqdm import tqdm
import pandas as pd
from Enterprise.database import Database
from Engineering.author_service import AuthorService  # Der neue Spezialist


class HealthDiagnosis:
    """
    Der Reinigungs-Trupp der Enterprise.
    Verantwortlich für physische Integrität und logische Konsistenz.
    """

    @classmethod
    def deep_repair_library(cls):
        """Phase 1: Löscht tote Dateireferenzen und verwaiste DB-Einträge."""
        print(f"\n--- 🛠️ START DEEP REPAIR (V2.0) ---")

        # 1. BÜCHER: HDD-Check & Dubletten-Check
        all_books = Database.query_all("SELECT id, path FROM books")
        cleaned_books = 0
        for book in tqdm(all_books, desc="Prüfe Dateien auf HDD"):
            b_id, b_path = book['id'], book['path']

            if not b_path or not os.path.exists(b_path):
                Database.execute("DELETE FROM books WHERE id = ?", [b_id])
                cleaned_books += 1
            else:
                # Dubletten-Pfad: Behalte nur die älteste ID
                Database.execute("DELETE FROM books WHERE path = ? AND id > ?", [b_path, b_id])
        print(f"✅ {cleaned_books} tote Bucheinträge entfernt.")

        # 2. WERKE: Verwaiste Werke löschen
        # Ein Werk ist verwaist, wenn kein Buch mehr darauf zeigt
        deleted_works = Database.execute("""
            DELETE FROM works 
            WHERE id NOT IN (SELECT DISTINCT work_id FROM books WHERE work_id IS NOT NULL)
        """)
        print(f"🧹 {deleted_works} herrenlose Werke gelöscht.")

        # 3. SERIEN: Verwaiste Serien löschen
        deleted_series = Database.execute("""
            DELETE FROM series 
            WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)
        """)
        print(f"🧹 {deleted_series} herrenlose Serien gelöscht.")

        # 4. AUTOREN: Aufräumen der n:m Tabelle und verwaiste Autoren
        Database.execute("DELETE FROM work_to_author WHERE work_id NOT IN (SELECT id FROM works)")
        deleted_authors = Database.execute("""
            DELETE FROM authors 
            WHERE id NOT IN (SELECT DISTINCT author_id FROM work_to_author)
        """)
        print(f"🧹 {deleted_authors} verwaiste Autoren entfernt.")

        Database.execute("VACUUM")


    @staticmethod
    def run_full_migration():
        """
        Iteriert über alle Bücher in der Datenbank und korrigiert die Werk-
        und Serienzuordnungen basierend auf der LogicService-Logik.
        """
        # Statistiken für das Protokoll
        stats = {
            "total_books": 0,
            "works_already_correct": 0,
            "works_remapped": 0,
            "series_already_correct": 0,
            "series_linked": 0,
            "errors": 0
        }

        # 1. Alle Buch-IDs und Pfade aus der DB holen
        # Wir laden hier nur die IDs, um den Speicher nicht zu sprengen
        all_books = Database.query_all("SELECT id, path, work_id FROM books")
        stats["total_books"] = len(all_books)

        print(f"🚀 Starte Migration für {stats['total_books']} Bücher...\n")

        # --- Die tqdm Umhüllung ---
        for book_entry in tqdm(all_books, desc="Migriere Buch-Identitäten", unit="book"):
            try:
                b_id = book_entry['id']
                b_path = book_entry['path']
                old_work_id = book_entry['work_id']

                # 2. Core-Objekt für dieses Buch laden
                # (Nutzt deine bestehende Scan-Logik)
                from Engineering.book_service import BookService
                s_core = BookService.scan_file_basic(b_path)

                # Vorher den aktuellen Serienstand prüfen (für Statistik)
                # Wir schauen, ob das Werk aktuell schon eine serie_id hat
                old_series_id = None
                if old_work_id:
                    res = Database.query_one("SELECT series_id FROM works WHERE id = ?", [old_work_id])
                    old_series_id = res['series_id'] if res else None

                # 3. Identität auflösen & Speichern (Punkt 1-8 deiner Liste)
                # Das führt get_or_create_by_name, resolve_series, find_by_triple und save() aus
                from Engineering.logic_services import LogicService  # Import falls in anderer Datei
                new_work_id = LogicService.resolve_book_identity(s_core, commit=True)

                # 4. Statistik: Werk-Verknüpfung
                if old_work_id == new_work_id:
                    stats["works_already_correct"] += 1
                else:
                    stats["works_remapped"] += 1

                # 5. Statistik: Serien-Verknüpfung
                # Wir prüfen das neue Werk nach der Bearbeitung
                res_new = Database.query_one("SELECT series_id FROM works WHERE id = ?", [new_work_id])
                new_series_id = res_new['series_id'] if res_new else None

                if new_series_id:
                    if new_series_id == old_series_id:
                        stats["series_already_correct"] += 1
                    else:
                        stats["series_linked"] += 1

            except Exception as e:
                print(f"❌ Fehler bei Buch ID {book_entry['id']}: {e}")
                stats["errors"] += 1

        # 6. Protokoll-Ausgabe
        HealthDiagnosis.print_report(stats)

    @staticmethod
    def print_report(stats):
        print("\n" + "=" * 50)
        print("📊 MIGRATIONS-PROTOKOLL")
        print("=" * 50)
        print(f"Verarbeitete Bücher gesamt:  {stats['total_books']}")
        print(f"Fehlgeschlagen:              {stats['errors']}")
        print("-" * 50)
        print(f"Werke bereits korrekt:       {stats['works_already_correct']}")
        print(f"Werke neu/umverknüpft:       {stats['works_remapped']}")
        print("-" * 50)
        print(f"Serien bereits korrekt:      {stats['series_already_correct']}")
        print(f"Serien neu zugeordnet:       {stats['series_linked']}")
        print("=" * 50 + "\n")


def analyze_problematic_book(book_id):
    """
    Analysiert einen spezifischen Datensatz auf Inkompatibilitäten.
    """
    print(f"--- Analyse für Buch ID: {book_id} ---")
    from Enterprise.database import Database
    from Engineering.book_service import BookService
    from Engineering.logic_services import LogicService
    import traceback

    print(f"\n" + "=" * 60)
    print(f"🔍 TIEFENANALYSE FÜR BUCH ID: {book_id}")
    print("=" * 60)

    # 1. Datenbank-Eintrag prüfen
    book_entry = Database.query_one("SELECT * FROM books WHERE id = ?", [book_id])

    if book_entry:
        print(f"✅ Buch gefunden: {book_entry['path']}")

        from Engineering.book_service import BookService
        from Engineering.logic_services import LogicService
        import traceback

        try:
            print("\n--- 1. Scan-Test ---")
            s_core = BookService.scan_file_basic(book_entry['path'])

            # Wir schauen uns an, was in s_core steckt
            # s_core ist wahrscheinlich ein Objekt deiner Core-Klasse
            fields = vars(s_core) if hasattr(s_core, '__dict__') else s_core
            for key, val in fields.items():
                print(f"Feld: {key:15} | Typ: {type(val).__name__:10} | Inhalt: {val}")

            print("\n--- 2. Logik-Test (Hier sollte der Fehler knallen) ---")
            LogicService.resolve_book_identity(s_core, commit=False)
            print("✅ Überraschung: Kein Fehler im Testlauf!")

        except Exception:
            print("\n💥 FEHLER GEFUNDEN:")
            traceback.print_exc()
    else:
        print("❌ ID 23990 nicht in der DB gefunden.")

# Beispielaufruf (Passe 'meine_datenbank' an dein Objekt an)
#

if __name__ == "__main__":
    # Erst die grobe Reinigung (Tote Links)
   # HealthDiagnosis.run_full_migration()
   HealthDiagnosis.deep_repair_library()
   # analyze_problematic_book(23990)