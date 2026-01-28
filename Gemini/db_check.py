"""
DATEI: db_check.py
VERSION: 1.4.0
BESCHREIBUNG: Hilft bei der Migration und Überprüfung der Struktur (transient-Modul)
     - Wir haben books mit der Verbindung zur Filestruktur, mit separaten Büchern für jeden Autor, Sprache und evtl. Thema
       Hier steht auch der Dateiname und Pfadname für jedes Buch, damit auch reduntant die Autoren und Titel etc.
     - Davon abstrahiert haben wir das abstrakte Werk, z.B. Herry Potter Band 1. unabhängig von Sprache und Format.
       Hier speichern wir Beschreibung, Rating, Serienname und Seriennummer und Autorenverbindungen über work_author.
       Zum besserer Übersicht stehen ihr redundant alle Titel in den 5 Sprachen, soweit vorhanden
     - In der Serie fassen wir die Info über wieviele Bücher es gibt.
       Wichtig über die Ermittlung noch fehlender Bücher. Auch eine generelle Beschreibung der Serie.

     - Daneben gibt es noch die Autoren mit einem slug-namen und Pseudonyme der Autoren.
       Die Main-Sprache der Autoren in meiner Sammlung und ein paar interessante Infos, Date, ild und Vita.
"""
import os
import sqlite3
from tqdm import tqdm
from collections import defaultdict
from Apps.book_data import BookData
from Apps.book_scanner import scan_single_book, mismatch_list, write_mismatch_report
from Gemini.file_utils import DB_PATH, sanitize_path




class BookCleaner:
    @staticmethod
    def check_db_entry(file_path):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Die korrigierte Abfrage mit Joins zu den Autoren
        query = """
                SELECT b.*, a.firstname, a.lastname
                FROM books b
                LEFT JOIN book_authors ba ON b.id = ba.book_id
                LEFT JOIN authors a ON ba.author_id = a.id
                WHERE b.path = ?
                """
        cursor.execute(query, (file_path,))
        row = cursor.fetchone()

        if row:
            print("--- Datenbank-Eintrag gefunden ---")
            # Wir wandeln es in ein Dictionary um, um bequem damit zu arbeiten
            data = dict(row)

            # Wir berechnen den full_author direkt für die Anzeige
            first = data.get('firstname') or ''
            last = data.get('lastname') or 'Unbekannt'
            full_author = f"{first} {last}".strip()

            print(f"Berechneter Autor: {full_author}")
            print("-" * 34)

            # Alle Spalten ausgeben
            for key in data.keys():
                print(f"{key}: {data[key]}")
        else:
            print(f"⚠️ Kein Eintrag für diesen Pfad gefunden:\n{file_path}")
        conn.close()

    @staticmethod
    def check_db_simple_entry(file_path):
        conn = sqlite3.connect(DB_PATH)
        # Wir stellen um auf Row, damit wir Spaltennamen sehen
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Suche genau nach diesem Buch
        query = "SELECT * FROM books WHERE path = ?"
        cursor.execute(query, (file_path,))
        row = cursor.fetchone()

        if row:
            print("--- Datenbank-Eintrag gefunden ---")
            # Wir geben die wichtigsten Spalten aus
            for key in row.keys():
                print(f"{key}: {row[key]}")
        else:
            print("⚠️ Kein Eintrag für diesen Pfad in der Datenbank gefunden.")

        conn.close()

    @staticmethod
    def intelligent_rescan(base_path):
        """Der schnelle Abgleich über Ordner-Anzahlen (für 100k Files)."""
        print(f"🚀 Starte intelligenten Rescan ab: {base_path}")
        db_counts = BookData.get_book_counts_per_folder(base_path)
        # db_counts ist ein Dictionnary mit allesn directorien und den Anzahl der Bücher:
        """
        {
            "/home/user/books/scifi": 42,
            "/home/user/books/thriller": 12,
            "/home/user/books/fantasy": 305
        }
        """
        print(f"In der DB sind {len(db_counts)} Ordner")
        stats = {"added": 0, "cleaned": 0}

        for root, dirs, files in os.walk(base_path):
            # os.walk liefert (rrot, dirs, files zurück) zurück.
            # root =akt. Dir, dirs = Liste der Unterordner, files = Liste der Files in root
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
        print(f"--- START DEEP REPAIR (Multi-Path Cleanup) ---")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Wir holen alle aktuellen Pfad-Buch-Kombinationen
        # (Noch aus der books-Tabelle, da dort die 'alten' Master-Pfade stehen)
        all_books = BookData.search_sql("SELECT id, path, isbn FROM books")

        cleaned_files = 0

        for book in tqdm(all_books, desc="Bereinige Dateileichen"):
            # 1. Existenzprüfung
            if not book.path or not os.path.exists(book.path):
                # A) Lösche alle Links zu diesem Pfad in der NEUEN Tabelle
                cursor.execute("DELETE FROM book_authors WHERE path = ?", (book.path,))

                # B) Lösche den Eintrag in der ALTEN Link-Tabelle (book_authors_old)
                # Falls du sie noch hast, sonst diesen Teil weglassen:
                try:
                    cursor.execute("DELETE FROM book_authors_old WHERE book_id = ?", (book.id,))
                except:
                    pass

                # C) Lösche das Buch selbst
                cursor.execute("DELETE FROM books WHERE id = ?", (book.id,))

                cleaned_files += 1
                continue

            # 2. Falls Datei existiert: Sicherstellen, dass sie in der NEUEN Link-Tabelle steht
            # (Jeder-mit-Jedem Logik für diesen Pfad)
            authors = BookData.get_author_ids_for_book(book.id)  # Hilfsmethode
            for a_id in authors:
                cursor.execute("""
                    INSERT OR IGNORE INTO book_authors (book_id, author_id, path) 
                    VALUES (?, ?, ?)""", (book.id, a_id, book.path))

        conn.commit()
        print(f"✅ {cleaned_files} tote Einträge entfernt.")

        # 3. Der ISBN-MERGE (Jetzt, wo die Leichen weg sind)
        BookData.merge_duplicates_by_isbn()

        # 4. Finales Vacuum
        BookData.vacuum()

    @staticmethod
    def deep_clean_library():
        """
        Löscht Bücher mit ungültigem Pfad und bereinigt die Verknüpfungen.
        """
        print(f"--- START DEEP CLEAN SCAN ---")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Alle Pfade holen
        cursor.execute("SELECT id, path FROM books")
        all_books = cursor.fetchall()
        ids_to_delete = []

        # Test für den allerersten Pfad
        test_id, test_path = all_books[0]
        print(f"Test-Pfad: {test_path}")
        print(f"Existiert: {os.path.exists(test_path)}")

        # Falls False, probieren wir die Normalisierung
        normalized = os.path.normpath(test_path)
        print(f"Normalisiert: {normalized}")
        print(f"Existiert normalisiert: {os.path.exists(normalized)}")

        # 2. Filesystem-Check (nur das ist in Python nötig)
        for b_id, b_path in tqdm(all_books, desc="Prüfe Dateipfade", unit="Buch"):
            if not b_path or not os.path.exists(b_path):
                ids_to_delete.append(b_id)

        if not ids_to_delete:
            print("✅ Keine ungültigen Pfade gefunden.")
            return {"cleaned": 0}

        # 3. Massenlöschung in der Datenbank
        print(f"Bereinige {len(ids_to_delete):,} Einträge...")
        if len(ids_to_delete) > (len(all_books) * 0.8):
            print(f"⚠️ STOPP! Das Script will {len(ids_to_delete):,} von {len(all_books):,} Büchern löschen.")
            print("Das sieht nach einem Fehler aus (z.B. Laufwerk D: nicht richtig erkannt).")
            conn.close()
            return


        # id_list = ",".join(map(str, ids_to_delete))
        # 3. Löschen in Chunks (um das SQLite Parameter-Limit zu umgehen)
        for i in range(0, len(ids_to_delete), 900):
            chunk = ids_to_delete[i:i + 900]
            placeholders = ",".join(["?"] * len(chunk))
            # Zuerst die Verknüpfungen in book_authors löschen
            cursor.execute(f"DELETE FROM book_authors WHERE book_id IN ({placeholders})", chunk)
            # Dann das Buch selbst löschen
            cursor.execute(f"DELETE FROM books WHERE id IN ({placeholders})", chunk)
        # Optional: Autoren löschen, die nun kein Buch mehr haben
        cursor.execute("""
                DELETE FROM authors 
                WHERE id NOT IN (SELECT DISTINCT author_id FROM book_authors)
            """)
        conn.commit()
        conn.close()
        BookData.vacuum()
        print(f"✅ Deep Clean beendet. Bereinigt: {len(ids_to_delete)}")
        return {"cleaned": len(ids_to_delete)}


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


    @staticmethod
    def update_book_paths():
        # Wir haben physikalisch die Ordner umbenannt von _sortiertGenre -> _byGenre
        # Um ein Re-Scanning zu vermeiden, ändern wir einfach in allen Pfaden den entsprechenden Teil.
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Definition der Änderungen: (Alter Teil, Neuer Teil)
        replacements = [
            ('_sortiertGenre', '_byGenre'),
            ('_sortierteRegion', '_byRegion')
        ]

        print("Starte Pfad-Aktualisierung...")

        try:
            for old_term, new_term in replacements:
                # SQL: SET path = REPLACE(path, 'alt', 'neu')
                # Das wirkt sich nur auf Zeilen aus, die den alten Begriff enthalten
                query = f"UPDATE books SET path = REPLACE(path, ?, ?) WHERE path LIKE ?"
                cursor.execute(query, (old_term, new_term, f"%{old_term}%"))

                print(
                    f"Abgeschlossen: '{old_term}' wurde durch '{new_term}' ersetzt. ({cursor.rowcount} Zeilen geändert)")

            conn.commit()
            print("\nErfolgreich gespeichert. Die Pfade im Analyser sollten jetzt wieder stimmen.")

        except sqlite3.Error as e:
            print(f"Ein Fehler ist aufgetreten: {e}")
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def print_report():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Anzahl der Verknüpfungen (Autor <-> Buch)
        cursor.execute("SELECT COUNT(*) FROM book_authors")
        links_neu = cursor.fetchone()[0]

        # 2. Anzahl der tatsächlichen Bucheinträge
        cursor.execute("SELECT COUNT(*) FROM books")
        books_neu = cursor.fetchone()[0]

        # 3. Anzahl der Autoren
        cursor.execute("SELECT COUNT(*) FROM authors")
        authors_count = cursor.fetchone()[0]

        print(f"Bücher in 'books':         {books_neu:>15,}")
        print(f"Links in 'book_authors':   {links_neu:>15,}")
        print(f"Autoren in 'authors':      {authors_count:>15,}")

        # 4. Stichprobe: Pfade kommen aus der Tabelle 'books'
        cursor.execute("SELECT path FROM books WHERE path IS NOT NULL AND path != '' LIMIT 1")
        print("\nÜberlebende Pfade (Stichprobe aus 'books'):")
        paths = cursor.fetchall()
        if paths:
            for row in paths:
                print(f" - {row[0]}")
        else:
            print(" - Keine Pfade gefunden!")

        conn.close()





if __name__ == "__main__":
    analyser = BookCleaner()

    # 1. Erstmal schauen, wo ganze Ordner fehlen
    #r = analyser.analyze_directories()
    #analyser.print_dir_report(r)

    # 2. Wenn du einen Ordner fixen willst, einkommentieren:
    # analyser.fix_moved_directory("C:/Alte/Pfad", "D:/Neue/Pfad")

    # 3. Danach die Dubletten-Prüfung
    # analyser.find_isbn_duplicates()
    # target_path = sanitize_path("D:/Bücher/Deutsch/_byGenre")
    target_path = sanitize_path("D:/Bücher/Business")
    analyser.print_report()
    analyser.deep_clean_library()
    analyser.print_report()
    analyser.intelligent_rescan(target_path)
    # analyser.deep_repair_library(target_path)
    analyser.print_report()
    #  analyser.print_report()