import os
import re
import unicodedata
from typing import Optional, List, Dict

# --- Werkzeuge ---
from Zoom.scan_file import extract_info_from_filename, derive_metadata_from_path
from Zoom.scan_epub import get_epub_metadata
from Zoom.scan_check import check_for_mismatch
from Zoom.utils import sanitize_path

# --- API Tools (Refactored V1.5) ---
from Zoom.scan_google_books import get_google_data
from Zoom.scan_open_library import get_openlibrary_data

# --- Mappings & Models ---
from Zoom.scan_genre_mapping import classify_book
from Zoom.scan_region_mapping import refine_regions
from Audio.book_data import BookData


class Scanner:
    CURRENT_SCANNER_VERSION = "1.5.0"
    mismatch_list: List[Dict] = []

    @classmethod
    def scan_single_book(cls, file_path: str, force_update: bool = False) -> Optional[BookData]:
        if not os.path.exists(file_path):
            return None

        file_path = sanitize_path(file_path)

        # --- SCHRITT A: DB CHECK ---
        # Korrektur: Nutze die neue statische Methode load_db_by_path
        manager = BookData.load_db_by_path(file_path)

        if not manager:
            manager = BookData()
            manager.book.path = file_path
            manager.is_in_db = False  # Wichtig für die UI-Farben später
        else:
            manager.is_in_db = True
            manager.capture_db_state()

        db_version = manager.book.scanner_version or "NEU"
        is_current = (str(db_version) == str(cls.CURRENT_SCANNER_VERSION))

        # Wenn aktuell und kein Force-Update: Finger weg.
        if manager.is_in_db and manager.book.is_complete and is_current and not force_update:
            return manager

        manager.book.scanner_version = cls.CURRENT_SCANNER_VERSION

        # --- SCHRITT B: DATEI & PFAD ANALYSE ---
        # Hier ziehen wir die "Wahrheit" aus dem Dateisystem
        file_info = extract_info_from_filename(file_path)
        manager.book.merge_with(file_info)

        path_info = derive_metadata_from_path(file_path)
        manager.book.merge_with(path_info)

        # WICHTIG: Serie und Index explizit setzen, damit der Funnel in manager.save()
        # später das richtige Werk findet oder trennt.
        if file_info.get('series_name'):
            manager.book.series_name = file_info['series_name']
        if file_info.get('series_index'):
            manager.book.series_index = file_info['series_index']

        print(f"\n--- 🧩 MERGE START: {path_info.get('title', 'Unbekannt')} ---")
        print(f"DEBUG: Eingehende Daten (path_info): {path_info}")
        manager.book.merge_with(path_info)
        print(f"DEBUG: Stand nach Merge - Keywords: {manager.book.keywords} (Typ: {type(manager.book.keywords)})")
        print(f"DEBUG: Stand nach Merge - Year: {manager.book.year} (Typ: {type(manager.book.year)})")
        print(f"--- 🧩 MERGE ENDE ---\n")

        # Extension sicherstellen
        if not manager.book.ext:
            manager.book.ext = os.path.splitext(file_path)[1].lower()

        # --- SCHRITT C: EPUB METADATEN (NUR BEFÜLLEN WENN LEER)---
        if manager.book.ext == '.epub':
            epub_raw = get_epub_metadata(file_path)
            if epub_raw:
                # Mismatch Check (Dateiname vs. EPUB-Tags)
                mismatch = check_for_mismatch(
                    file_path=file_path,
                    file_title=manager.book.title,
                    epub_title=epub_raw.get('title'),
                    file_authors=manager.book.authors,
                    epub_authors=epub_raw.get('authors', [])
                )
                if mismatch:
                    cls.mismatch_list.append(mismatch)

                # Merge EPUB-Daten in das Book-Atom
                for key, value in epub_raw.items():
                    if not getattr(manager.book, key, None):
                        setattr(manager.book, key, value)

        # --- SCHRITT D: API ENRICHMENT (Google & OpenLibrary) ---
        # Wir nutzen die neuen spezialisierten Funktionen, die BookData-konform sind.

        # 1. Google Books (liefert Ratings, Description, ISBN)
        gb_results = get_google_data(manager.book)
        if gb_results:
            for key, value in gb_results.items():
                if not getattr(manager.book, key, None):
                    setattr(manager.book, key, value)

        # 2. Open Library (liefert OL-Ratings und alternative Description/Notes)
        ol_results = get_openlibrary_data(manager.book)
        if ol_results:
            for key, value in ol_results.items():
                if key == 'description' and value:
                    if manager.book.description:
                        # Anhängen mit Herkunft's-Hinweis
                        manager.book.description += f"\n\n-- von OpenLibrary --\n{value}"
                    else:
                        manager.book.description = value
                elif not getattr(manager.book, key, None):
                    setattr(manager.book, key, value)

        # --- SCHRITT E: KLASSIFIZIERUNG (Genre & Regionen) ---
        new_genre, extra_keys = classify_book(
            manager.book.keywords,
            manager.book.description)

        if new_genre != "Unbekannt" and not manager.book.genre:
            manager.book.genre = new_genre
        if extra_keys:
            manager.book.keywords.update(extra_keys)

        r_set = refine_regions(
            manager.book.regions,
            manager.book.keywords,
            manager.book.description
        )
        if r_set:
            manager.book.regions.update(r_set)

        # --- SCHRITT F: KONFLIKTPRÜFUNG (Neu) ---
        conflicts = manager.get_work_conflicts()
        if conflicts:
            print(f"⚠️ Konflikt erkannt für ID {manager.book.id}: Buch gehört zu anderen Autoren in DB.")
            # Option A: In den Report schreiben
            cls.mismatch_list.append({
                'book_id': manager.book.id,
                'file_path': manager.book.path,
                'note': f"Konflikt mit Werk-Autoren: {conflicts[0]['author']}",
                'action': 'WORK_SPLIT'
            })
            # Option B: Sofort heilen (Indem wir die work_id nullen,
            # erzwingt manager.save() eine Neusuche/Erstellung)
            manager.book.work_id = 0

        # --- SCHRITT G: DATEINAMEN OPTIMIERUNG ---
        print("DEBUG: Neuer Filename")
        new_filename = cls.build_perfect_filename(manager)
        directory = os.path.dirname(manager.book.path)
        new_path = sanitize_path(os.path.join(directory, new_filename))
        print(f"DEBUG: Neuer Filename  {new_path} vs. {manager.book.path}")

        if manager.book.path != new_path:
            if os.path.exists(new_path):
                name, ext = os.path.splitext(new_filename)
                new_path = sanitize_path(os.path.join(directory, f"{name}-KOPIE{ext}"))
                cls.mismatch_list.append({
                    'filename': os.path.basename(manager.book.path),
                    'error_type': 'DUPLICATE_FILE',
                    'note': f"Kopie erstellt: {new_filename}"
                })
            try:
                os.rename(manager.book.path, new_path)
                manager.book.path = new_path
            except OSError as e:
                print(f"⚠️ Rename Error: {e}")

        # Markiere als vollständig gescannt
        manager.book.is_complete = 1
        return manager

    @classmethod
    def run_smart_scan(cls, base_path: str, force_update: bool = False):
        from tqdm import tqdm
        cls.mismatch_list = []
        stats = {"sync": 0, "new": 0, "errors": 0}

        all_files = []
        for root, _, files in os.walk(base_path):
            all_files.extend([os.path.join(root, f) for f in files
                              if f.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3'))])

        print(f"🚀 Starte Smart-Scan in: {base_path}")

        for full_path in tqdm(all_files, desc="Scan läuft", unit="file"):
            full_path = sanitize_path(full_path)

            try:
                # Nutzt jetzt die verschärfte Logik
                manager = cls.scan_single_book(full_path, force_update=force_update)
                if not manager: continue

                is_new = not manager.is_in_db

                # In manager.save() greift jetzt dein neuer Funnel!
                if manager.save():
                    stats["new" if is_new else "sync"] += 1
                else:
                    stats["errors"] += 1
            except Exception as e:
                print(f"💥 Fehler bei {os.path.basename(full_path)}: {e}")
                stats["errors"] += 1

        cls.write_mismatch_report(base_path)

        print(f"\n✅ Scan beendet: {stats['new']} neu, {stats['sync']} synchronisiert, {stats['errors']} Fehler.")
        return stats

    @staticmethod
    def build_perfect_filename(manager: BookData) -> str:
        """
        Zentrale Erzeugung des Dateinamens basierend auf dem Book-Atom.
        """
        EM_DASH = "—"
        b = manager.book

        # 1. Autoren String
        if b.authors:
            # authors ist List[Tuple[Vorname, Nachname]]
            auth_str = " & ".join([f"{v} {n}".strip() for v, n in b.authors])
        else:
            auth_str = "Unbekannt"

        # 2. Serien Teil
        series_part = ""
        idx_val = getattr(b, 'series_index', 0.0)
        if b.series_name:
            try:
                idx = float(idx_val)
                # Formatierung: 01 für Ganzzahlen, 01.5 für Zwischenbände
                num = f"{int(idx):02d}" if idx.is_integer() else f"{idx:04.1f}"
            except (ValueError, TypeError):
                num = "00"
            series_part = f"{b.series_name} {num} - "

        # 3. Jahr & Titel
        year_val = 0
        try:
            if b.year:
                year_val = int(b.year)
        except (ValueError, TypeError):
            year_val = 0
        year_part = f" ({year_val})" if year_val > 0 else ""
        title_part = b.title if b.title else "Unbekannter Titel"

        # Reinigung von Dateityp-Anhängseln im Titel
        clean_title = re.sub(r'\s+(mobi|pdf|epub|azw3)\b', '', title_part, flags=re.IGNORECASE)

        # 4. Zusammenbau
        if not b.ext:
            # Fallback: Versuche die Endung aus dem aktuellen Pfad zu holen
            if b.path:
                b.ext = os.path.splitext(b.path)[1]
            # Falls immer noch None oder leer (z.B. bei manuellem Eintrag)
            if not b.ext:
                b.ext = ".epub"  # Vernünftiger Default
        ext = b.ext if b.ext.startswith('.') else f".{b.ext}"
        # filename = f"{auth_str} {EM_DASH} {series_part}{clean_title}{year_part}{ext}"
        filename = f"{auth_str} {EM_DASH} {series_part}{clean_title}{ext}"

        # 5. OS-Spezifische Reinigung
        clean_name = re.sub(r'[:?*<>|"/\\\r\n]', '', filename)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        perfect_name = unicodedata.normalize('NFC', clean_name)

        # 6. Rückgabe: Pfad (falls vorhanden) + Name, sonst nur Name
        if b.path:
            directory = os.path.dirname(os.path.abspath(b.path))
            return sanitize_path(os.path.join(directory, perfect_name))

        return perfect_name

    @classmethod
    def write_mismatch_report(cls, base_path):
        """Schreibt Mismatches und Funnel-Entscheidungen in eine Textdatei."""
        if not cls.mismatch_list:
            print("Keine Mismatches gefunden. Kein Report erstellt.")
            return

        report_path = sanitize_path(os.path.join(base_path, 'Metadaten_Report_V1.5.txt'))
        try:
            with open(report_path, 'w', encoding="utf-8") as f:
                f.write(f"--- 📊 METADATEN & FUNNEL REPORT ({len(cls.mismatch_list)} Einträge) ---\n")
                f.write(f"Version: {cls.CURRENT_SCANNER_VERSION}\n\n")

                for item in cls.mismatch_list:
                    # Identifikation
                    b_id = item.get('book_id', 'NEU')
                    f.write(f"📗 BUCH-ID: {b_id}\n")
                    f.write(f"   Pfad: {item.get('file_path', 'N/A')}\n")

                    # Mismatch-Details (Titel/Autor Konflikte aus EPUB-Check)
                    if 'file_title' in item:
                        f.write(f"   ❌ TITEL-KONFLIKT: '{item['file_title']}' (Datei) vs. '{item['epub_title']}' (EPUB)\n")

                    if 'file_authors' in item:
                        # Formatierung der Autoren-Tupel für den Report
                        f_auth = " & ".join([f"{v} {n}".strip() for v, n in item['file_authors']])
                        e_auth = " & ".join([f"{v} {n}".strip() for v, n in item['epub_authors']])
                        f.write(f"   ❌ AUTOR-KONFLIKT: {f_auth} (Datei) vs. {e_auth} (EPUB)\n")

                    # Funnel-Informationen (Wichtig für deine 6.874 Fälle!)
                    if 'note' in item:
                        f.write(f"   ℹ️ INFO/NOTE: {item['note']}\n")

                    if 'action' in item:
                        f.write(f"   ⚡ AKTION: {item['action']}\n")

                    f.write("-" * 50 + "\n")
            print(f"✅ Report unter {report_path} gespeichert.")
        except Exception as e:
            print(f"❌ Fehler beim Schreiben des Reports: {e}")


if __name__ == "__main__":
    target_path = sanitize_path(r"D:\Bücher\Deutsch\_byGenre\SF\K.H. Scheer")
    # Scanner instanziieren
    scanner = Scanner()
    scanner.run_smart_scan(base_path=target_path)
