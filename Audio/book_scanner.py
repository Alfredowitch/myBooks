import os
import re
import sqlite3
import unicodedata
from typing import Optional, List, Dict

# --- Werkzeuge ---
from Zoom.scan_file import extract_info_from_filename, derive_metadata_from_path
from Zoom.scan_epub import get_epub_metadata
from Zoom.scan_check import check_for_mismatch
from Zoom.utils import sanitize_path, DB_PATH

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
        """
        Zentrale Methode: Analysiert eine Datei und befüllt das BookData-Aggregat.
        """
        if not os.path.exists(file_path):
            return None

        file_path = sanitize_path(file_path)

        # --- SCHRITT A: DB CHECK & Initialisierung ---
        # Versuche existierende Daten zu laden (lädt book, work, serie Atome)
        manager = BookData.load_by_path(file_path)

        if not manager:
            manager = BookData()
            manager.book.path = file_path

        db_version = manager.book.scanner_version or "NEU"
        is_current = (str(db_version) == str(cls.CURRENT_SCANNER_VERSION))

        # Überspringen, wenn Version aktuell und kein Force-Update
        if manager.is_in_db and manager.book.is_complete and is_current and not force_update:
            return manager

        manager.book.scanner_version = cls.CURRENT_SCANNER_VERSION

        # --- SCHRITT B: DATEI & PFAD ANALYSE (HÖCHSTE PRIORITÄT)---
        file_info = extract_info_from_filename(file_path)
        manager.book.merge_with(file_info)

        path_info = derive_metadata_from_path(file_path)
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
        """
        Scannt ein Verzeichnis unabhängig vom Browser.
        Robust gegenüber Speicherfehlern mit manueller Interaktionsmöglichkeit.
        """
        from tqdm import tqdm
        cls.mismatch_list = []
        stats = {"sync": 0, "new": 0, "errors": 0}

        # 1. Dateiliste vorbereiten
        all_files = []
        for root, _, files in os.walk(base_path):
            all_files.extend([os.path.join(root, f) for f in files
                              if f.lower().endswith(('.epub', '.pdf', '.mobi', '.azw3'))])

        if not all_files:
            print(f"ℹ️ Keine unterstützten Buchformate in {base_path} gefunden.")
            return stats

        print(f"🚀 Starte Smart-Scan für {len(all_files)} Dateien...")

        # 2. Iteration mit Fortschrittsbalken
        for full_path in tqdm(all_files, desc="Verarbeite Bücher", unit="file"):
            full_path = sanitize_path(full_path)

            # Vorab-Check um Last zu sparen
            if not force_update and cls.is_already_in_db(full_path):
                continue

            try:
                manager = cls.scan_single_book(full_path, force_update=force_update)
                if not manager:
                    continue

                is_new = (manager.book.id == 0)

                # 3. Speicher-Versuch mit Fehler-Handling
                if manager.save():
                    if is_new:
                        stats["new"] += 1
                    else:
                        stats["sync"] += 1
                else:
                    # Fehlermeldung und Weiche für den User
                    print(f"\n❌ SPEICHERFEHLER: {os.path.basename(full_path)}")
                    print(f"   Pfad: {full_path}")

                    choice = input(
                        "Fehler beim Speichern in DB. (i)gnorieren, (a)bbrechen oder (d)etails? [i/a/d]: ").lower()

                    if choice == 'd':
                        # Debug-Info ausgeben (Attribute des Managers prüfen)
                        print(f"--- DEBUG INFO ---")
                        print(f"Book-ID: {manager.book.id}, Title: {manager.book.title}")
                        print(f"Authors: {manager.book.authors}")
                        input("Drücke Enter zum Fortfahren...")
                    elif choice == 'a':
                        print("Scan durch Benutzer abgebrochen.")
                        return stats

                    stats["errors"] += 1

            except Exception as e:
                print(f"\n💥 KRITISCHER FEHLER bei {os.path.basename(full_path)}:")
                print(f"   Typ: {type(e).__name__} | Nachricht: {e}")

                if input("Weiter machen? (y/n): ").lower() != 'y':
                    return stats
                stats["errors"] += 1

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
        if b.series_name:
            # Index formatieren (z.B. "01")
            try:
                idx = float(b.series_number)
                num = f"{int(idx):02d}" if idx.is_integer() else f"{idx:04.1f}"
            except (ValueError, TypeError):
                num = str(b.series_number)
            series_part = f"{b.series_name} {num}-"

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
        filename = f"{auth_str} {EM_DASH} {series_part}{clean_title}{year_part}{ext}"

        # 5. OS-Spezifische Reinigung
        clean_name = re.sub(r'[:?*<>|"/\\\r\n]', '', filename)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        perfect_name = unicodedata.normalize('NFC', clean_name)

        # 6. Rückgabe: Pfad (falls vorhanden) + Name, sonst nur Name
        if b.path:
            directory = os.path.dirname(os.path.abspath(b.path))
            return sanitize_path(os.path.join(directory, perfect_name))

        return perfect_name