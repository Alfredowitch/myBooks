import os
from tqdm import tqdm
from collections import defaultdict
from Apps.book_data import BookData
from Apps.book_scanner import scan_single_book, mismatch_list, write_mismatch_report
from Gemini.read_epub import get_epub_metadata
from Gemini.read_file import detect_real_extension, is_mobi_readable
from file_utils import sanitize_path


class BookCleaner:

    @staticmethod
    def intelligent_rescan(base_path):
        """Der schnelle Abgleich über Ordner-Anzahlen (für 100k Files)."""
        print(f"🚀 Starte intelligenten Rescan ab: {base_path}")
        db_counts = BookData.get_book_counts_per_folder(base_path)
        print(f"In der DB sind {len(db_counts)} Ordner")
        stats = {"added": 0, "cleaned": 0}

        for root, dirs, files in os.walk(base_path):
            book_files = [f for f in files if f.lower().endswith(('.epub', '.pdf', '.mobi'))]
            if not book_files: continue

            norm_root = os.path.abspath(os.path.normpath(root))
            ll = db_counts.get(norm_root, 0)
            if len(book_files) == ll:
                print(f"-  {norm_root} ist ok")
                continue  # Ordner unverändert -> Überspringen
            print(f"-  {norm_root} synchronising.. {len(book_files)} vs. {ll}")
            # Synchronisation bei Differenz
            paths_in_db = BookData.get_all_paths_in_folder(norm_root)
            set_disk = set([os.path.abspath(os.path.join(norm_root, f)) for f in book_files])
            set_db = set([os.path.abspath(p) for p in paths_in_db])

            # Neue hinzufügen
            for path in (set_disk - set_db):
                if scan_single_book(path): stats["added"] += 1

            # Fehlende bereinigen
            for path in (set_db - set_disk):
                if BookCleaner.cleanup_missing_book(path): stats["cleaned"] += 1

        write_mismatch_report(base_path)
        return stats

    @staticmethod
    def deep_repair_library(base_path):
        """
        Deine bisherige repair_total_library, jetzt als Methode der Klasse.
        Prüft JEDES Buch auf Existenz und EPUB-Korruptheit.
        """
        print(f"--- START DEEP REPAIR SCAN ---")
        all_books = BookData.search_sql("SELECT id, path FROM books")
        fixes = 0
        cleaned = 0

        for book in tqdm(all_books, desc="Deep Repair", unit="Buch"):
            # 1. Existenz-Check
            if not book.path or not os.path.exists(book.path):
                if BookCleaner.cleanup_missing_book(book.path, book):
                    cleaned += 1
                continue
            # 2. Realen Typ bestimmen (Magic Bytes)
            real_ext = detect_real_extension(book.path)
            current_ext = os.path.splitext(book.path)[1].lower()
            # 3. Wenn Endung falsch ist -> Reparieren statt Löschen!
            if real_ext and real_ext != current_ext:
                new_path = book.path.replace(current_ext, real_ext)
                fixes += 1
                if BookData.fix_path_ext(book.path, new_path):
                    print(f"🔧 Endung korrigiert: {os.path.basename(new_path)} (war {current_ext})")
                    book.path = new_path  # Update für den nächsten Schritt
                    current_ext = real_ext
            # 4. Inhalts-Check (Korruptionsprüfung)
            if current_ext == '.epub':
                result = get_epub_metadata(book.path)
                if result is None:
                    cleaned += 1
                    BookCleaner.delete_corrupt_book(book)
                elif current_ext in ['.mobi', '.azw3']:
                    if not is_mobi_readable(book.path):
                        cleaned += 1
                        BookCleaner.delete_corrupt_book(book)

        write_mismatch_report(base_path)
        BookData.vacuum()
        print(f"✅ Deep Repair beendet. Fixes: {fixes}, Bereinigt: {cleaned}")
        return {"fixes": fixes, "cleaned": cleaned}

    # --- PRIVATE HILFSMETHODEN (Interne Logik) ---

    @staticmethod
    def cleanup_missing_book(path, book_obj=None):
        """Setzt Pfad auf leer und schreibt Notiz."""
        full_book = book_obj if (book_obj and hasattr(book_obj, 'notes')) else BookData.load_by_path(path)
        if full_book:
            old_path = path if path else "Kein Pfad"
            msg = f"Datei fehlt bei Scan: {old_path}"
            full_book.notes = f"{full_book.notes}\n{msg}".strip() if full_book.notes else msg
            full_book.path = ""
            mismatch_list.append({'Buch-ID': full_book.id, 'full_path': old_path, 'note': "DATEI FEHLT"})
            return full_book.save()
        return False

    @staticmethod
    def delete_corrupt_book(book):
        """Löscht Datei, Ordner und DB-Eintrag."""
        print(f"🚮 Lösche korrupte Datei: {book.path}")
        try:
            if os.path.exists(book.path):
                folder = os.path.dirname(book.path)
                os.remove(book.path)
                if not os.listdir(folder):
                    os.rmdir(folder)
            return book.delete()
        except Exception as e:
            print(f"⚠️ Fehler beim Löschen von {book.path}: {e}")
            return False

    @staticmethod
    def analyze_directories():
        """
        Gruppiert alle Bücher nach ihren Verzeichnissen und prüft deren Existenz.
        Gibt eine Liste von Verzeichnissen mit Buch-Anzahl und Status zurück.
        """
        print("Lade Daten für Verzeichnis-Report...")
        all_books = BookData.search()
        dir_map = defaultdict(list)

        for book in all_books:
            if book.path:
                directory = os.path.dirname(book.path)
                dir_map[directory].append(book)

        report = []
        for directory, books in dir_map.items():
            exists = os.path.exists(directory)
            report.append({
                "directory": directory,
                "count": len(books),
                "exists": exists
            })

        # Sortieren: Zuerst die Verzeichnisse, die NICHT existieren,
        # dann nach Anzahl der Bücher absteigend.
        report.sort(key=lambda x: (x['exists'], -x['count']))
        return report

    @staticmethod
    def print_dir_report(report):
        print(f"\n{'Status':<10} | {'Bücher':<8} | {'Verzeichnis'}")
        print("-" * 80)
        for entry in report:
            status = "OK" if entry['exists'] else "FEHLT"
            print(f"{status:<10} | {entry['count']:<8} | {entry['directory']}")


    @staticmethod
    def fix_moved_directory(old_prefix, new_prefix):
        """
        Stufe 2: Massen-Update.
        Nutzt deine BookData.update_file_path Logik für maximale Sicherheit.
        """
        all_books = BookData.search()
        affected = [b for b in all_books if b.path and b.path.startswith(old_prefix)]

        if not affected:
            print(f"Keine Bücher unter {old_prefix} gefunden.")
            return

        print(f"\nKorrektur-Vorschlag:")
        print(f"Von: {old_prefix}")
        print(f"Nach: {new_prefix}")
        print(f"Betroffene Bücher: {len(affected)}")

        confirm = input("\nSoll die Korrektur ausgeführt werden? (JA zum Bestätigen): ")
        if confirm == "JA":
            updated = 0
            for book in tqdm(affected, desc="Aktualisiere Pfade"):
                new_path = book.path.replace(old_prefix, new_prefix)
                # Wir nutzen die Klassenmethode für das DB-Update
                if BookData.update_file_path(book.path, new_path):
                    updated += 1
            print(f"Erfolgreich: {updated} Einträge korrigiert.")
        else:
            print("Abgebrochen.")

    @staticmethod
    def find_isbn_duplicates():
        """
        Stufe 3: Findet Dubletten für manuellen Report.
        Gibt Gruppen von Büchern mit gleicher ISBN aus.
        """
        print("Suche nach ISBN-Dubletten...")
        all_books = BookData.search()
        isbn_map = defaultdict(list)

        for book in all_books:
            if book.isbn and len(book.isbn) > 5:  # Nur echte ISBNs
                isbn_map[book.isbn].append(book)

        report = []
        for isbn, books in isbn_map.items():
            if len(books) > 1:
                # Wir prüfen, ob es wirklich unterschiedliche Pfade sind
                # (Mehrere Autoren bei gleichem Pfad sind ja ok)
                paths = {b.path for b in books if b.path}
                if len(paths) > 1 or any(not os.path.exists(b.path) for b in books):
                    report.append((isbn, books))

        if not report:
            print("Keine kritischen ISBN-Dubletten gefunden.")
            return

        print(f"\n{'ISBN':<15} | {'ID':<6} | {'Existiert':<10} | {'Pfad'}")
        print("-" * 100)
        for isbn, books in report:
            for b in books:
                exists = "JA" if (b.path and os.path.exists(b.path)) else "NEIN/LEER"
                print(f"{isbn:<15} | {b.id:<6} | {exists:<10} | {b.path}")
            print("." * 100)  # Trenner zwischen den ISBN-Gruppen

    @staticmethod
    def identify_isbn_duplicates():
        """
        Findet doppelte ISBNs und erstellt einen Report für manuelle Prüfung.
        Berücksichtigt, dass mehrere Autoren die gleiche ISBN haben dürfen.
        """
        print("Analysiere ISBN-Dubletten...")
        all_books = BookData.search()
        isbn_map = defaultdict(list)

        # Gruppiere alle Bücher nach ISBN
        for book in all_books:
            if book.isbn and book.isbn.strip():
                isbn_map[book.isbn].append(book)

        dup_report = []

        for isbn, books in isbn_map.items():
            if len(books) > 1:
                # Prüfen: Haben wir unterschiedliche Pfade oder ist einer leer?
                # Wir sammeln alle Infos für den manuellen Report
                paths = [b.path for b in books if b.path]

                # Wenn mehr als ein Buch mit dieser ISBN existiert:
                # Wir fügen alle betroffenen Bücher dem Report hinzu,
                # damit du sie direkt untereinander siehst.
                entry_group = []
                for b in books:
                    path_exists = os.path.exists(b.path) if b.path else False
                    entry_group.append({
                        "id": b.id,
                        "title": b.title,
                        "author": b.author,
                        "path": b.path,
                        "exists": path_exists
                    })

                dup_report.append({                    "isbn": isbn,
                    "entries": entry_group
                })

        return dup_report

    @staticmethod
    def print_duplicate_report(dup_report):
        """Gibt einen detaillierten Report über ISBN-Dubletten aus."""
        if not dup_report:
            print("Keine ISBN-Dubletten gefunden.")
            return

        print("\n" + "=" * 80)
        print("REPORT: ISBN DUBLETTEN (Manuelle Prüfung erforderlich)")
        print("=" * 80)

        for group in dup_report:
            print(f"\nISBN: {group['isbn']}")
            print(f"{'ID':<8} | {'Existiert':<10} | {'Autor':<20} | {'Pfad'}")
            print("-" * 80)
            for b in group['entries']:
                status = "JA" if b['exists'] else "NEIN/LEER"
                author = (b['author'][:17] + '..') if b['author'] and len(b['author']) > 20 else (
                            b['author'] or "Unbekannt")
                print(f"{b['id']:<8} | {status:<10} | {author:<20} | {b['path']}")



if __name__ == "__main__":
    analyser = BookCleaner()

    # 1. Erstmal schauen, wo ganze Ordner fehlen
    #r = analyser.analyze_directories()
    #analyser.print_dir_report(r)

    # 2. Wenn du einen Ordner fixen willst, einkommentieren:
    # analyser.fix_moved_directory("C:/Alte/Pfad", "D:/Neue/Pfad")

    # 3. Danach die Dubletten-Prüfung
    # analyser.find_isbn_duplicates()
    target_path = sanitize_path("D:/Bücher/Deutsch/_byGenre")
    analyser.intelligent_rescan(target_path)