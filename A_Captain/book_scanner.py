import logging
from tqdm import tqdm
from Engineering.book_service import BookService
from Enterprise.database import Database
from Engineering.logic_services import LogicService
from Enterprise.core import Core


class BookScanner:
    """Die Kommando-Zentrale für alle Scan-Vorgänge im Captain-Verzeichnis."""

    @staticmethod
    def run_folder_scan(target_path: str):
        """
        BASIC SCAN: Findet neue Dateien und bringt sie konsistent in die DB.
        Nutzt die 'Gesetz des Pfades' Logik aus dem BookService.
        """
        logging.info(f"🚀 Starte Folder-Scan in: {target_path}")

        # 1. Alle physischen Dateien finden
        all_files = BookService.find_files(target_path, extensions=['.epub', '.pdf', '.mobi'])

        # 2. Bekannte Pfade aus der DB holen, um Dubletten-Scans zu vermeiden
        existing_paths = {row['path'] for row in Database.query_all("SELECT path FROM books")}
        new_files = [f for f in all_files if f not in existing_paths]

        if not new_files:
            print("✅ Keine neuen Dateien gefunden.")
            return

        print(f"📦 Entdeckt: {len(new_files)} neue Dateien. Initialisiere Core-Verarbeitung...")

        for file_path in tqdm(new_files, desc="Processing Cores"):
            try:
                # 1. Extraktion: Daten aus Pfad/Metadaten lesen
                s_core = BookService.scan_file_basic(file_path)

                # 2. LOGIC-HEALING:
                # Hier werden Autoren angelegt, Werke gesucht/erstellt
                # und die IDs im s_core Objekt fest verdrahtet.
                LogicService.resolve_book_identity(s_core, commit=True)
                # Das Core-Objekt kümmert sich jetzt selbst um die Verknüpfung
                # von Autoren, Werken und Serien beim Speichern.
                s_core.save()

            except Exception as e:
                logging.error(f"❌ Fehler bei {file_path}: {e}", exc_info=True)

        print(f"✨ Folder-Scan abgeschlossen. {len(new_files)} Bücher integriert.")

    @staticmethod
    def run_smart_enrichment(limit: int = 1000):
        """
        SMART SCAN: Veredelt bestehende Einträge mit API-Daten (Google/OpenLibrary).
        Target: Bücher ohne Beschreibung oder mit veralteter Scanner-Version.
        """
        print(f"📡 Starte Smart-Enrichment (Limit: {limit} Bücher)...")

        # Wir suchen Bücher, die Hilfe brauchen (keine Beschreibung)
        query = """
            SELECT path FROM books 
            WHERE (description IS NULL OR description = '') 
            LIMIT ?
        """
        targets = Database.query_all(query, [limit])

        if not targets:
            print("✅ Alle Bücher sind bereits veredelt.")
            return

        for row in tqdm(targets, desc="Enriching via API"):
            file_path = row['path']
            try:
                # 1. Basic Scan lädt den IST-Zustand (inkl. DB-Beschreibungsschutz)
                s_core = BookService.scan_file_basic(file_path)

                # 2. Deep Scan triggert die APIs (fetch_all_metadata)
                # Diese Methode müssen wir im BookService noch kurz definieren
                s_core = BookService.scan_file_deep(s_core)

                # 3. Speichern der neuen Erkenntnisse
                s_core.save()

            except Exception as e:
                logging.warning(f"⚠️ API-Timeout oder Fehler bei {file_path}: {e}")
                # Bei API-Limits (429) sollten wir hier abbrechen
                if "429" in str(e):
                    print("🛑 API-Limit erreicht. Breche Veredelung für heute ab.")
                    break

        print("✅ Smart-Enrichment Batch beendet.")


if __name__ == "__main__":
    # Beispielaufruf
    BookScanner.run_folder_scan(r"D:\Bücher\Business\Art")
    # BookScanner.run_smart_enrichment(1000)
    pass