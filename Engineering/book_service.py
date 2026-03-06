"""
DATEI: Engineering/book_service.py
BESCHREIBUNG:
    Spezialist für die Extraktion und Aufbereitung von Buch-Metadaten.
    Nutzt Scotty für den Hardware-Zugriff.
"""
import os
import unicodedata
import logging
import re
from typing import List, Dict, Any, Optional
from Enterprise.core import Core
from Enterprise.database import Database
from Enterprise.scan_file import process_local_source
from Enterprise.scan_epub import get_epub_metadata
from Engineering.metadata_service import MetadataService


class BookService:
    EM_DASH = "—"

    def find_files(target_path: str, extensions: list) -> list:
        """
        Durchsucht rekursiv ein Verzeichnis nach Dateien mit bestimmten Endungen.
        """
        found_files = []

        # Prüfen, ob der Pfad überhaupt existiert
        if not os.path.exists(target_path):
            return []

        for root, dirs, files in os.walk(target_path):
            for file in files:
                # Prüfen, ob die Dateiendung in unserer Liste ist
                if any(file.lower().endswith(ext) for ext in extensions):
                    full_path = os.path.join(root, file)
                    # Normalisierung des Pfads für die Datenbank-Konsistenz
                    found_files.append(os.path.abspath(full_path))

        return found_files

    @classmethod
    def scan_file_basic(cls, file_path: str) -> Core:
        """
        Scotty scannt die physische Datei und baut einen Core zusammen.
        Diese Methode macht NUR den Scan, keine DB-Abfrage!
        """
        clean_path = BookService.sanitize_path(file_path)
        # 1. Lokaler Scan (Was sagt uns der Dateiname?)
        package = process_local_source(clean_path)
        package['path'] = clean_path

        # 2. EPUB-Metadaten (Falls vorhanden)
        epub_description = ""
        if package.get('ext') == '.epub':
            epub_data = get_epub_metadata(clean_path)
            if epub_data:
                package['isbn'] = epub_data.get('isbn')
                epub_description = epub_data.get('description', '')
                if epub_data.get('keywords'):
                    package['keywords'].update(epub_data['keywords'])

        # 3. Datenbank-Abgleich via Core
        # Wir nutzen deine Core-Funktion, um alles zu holen (Book, Work, Serie, Autoren)
        s_core = Core.load_book_by_path(clean_path)
        # Falls kein Buch in der DB ist, erzeugen wir ein frisches Core-Objekt
        if not s_core:
            s_core = Core()
            s_core.is_in_db = False
        else:
            s_core.is_in_db = True
        current_description = s_core.book.description.strip() if s_core.book.description else ""
        if not current_description and epub_description:
            current_description = epub_description
        elif current_description and epub_description and epub_description not in current_description:
            # OPTIONAL: Falls du beide kombinieren willst, falls sie sich unterscheiden:
            # current_description += f"\n\n[EPUB Info]: {epub_description}"
            pass

        # 4. Veredelung via MetadataService (Die "Gehirn"-Arbeit)
        # Wir nutzen die Keywords vom Scan und die Beschreibung vom EPUB
        current_keywords = set(package.get('keywords', []))
        main_genre, extra_keys = MetadataService.classify_book(current_keywords, current_description)
        current_regions = set(package.get('regions', []))
        refined_regions = MetadataService.refine_regions(current_regions, current_keywords, current_description)

        # 5. Überschreiben mit Scan-Daten
        b = s_core.book
        b.path = clean_path
        b.title = package.get('title', 'Unbekannt')
        b.series_name = package.get('series_name', '')
        b.series_index = float(package.get('series_index', 0.0))
        b.language = package.get('language', 'de')
        b.genre = main_genre
        b.description = current_description
        b.keywords = current_keywords.union(extra_keys)
        b.regions = refined_regions
        b.authors = package.get('authors')
        if package.get('isbn'):
            b.isbn = package.get('isbn')

        # Werk & Serie für die Anzeige synchronisieren
        s_core.save_book_only()
        return s_core


    @classmethod
    def scan_file_deep(cls, core_obj: Core) -> Core:
        """
        Der Veredelungs-Scan via API.
        Ergänzt das core_obj um externe Daten, ohne DB-Werte zu zerstören.
        """
        from Enterprise.scan_apis import fetch_all_metadata

        b = core_obj.book

        # 1. API Aufruf (fetch_all_metadata erwartet Liste von [Vorname, Nachname])
        # b.authors sollte bereits dieses Format haben
        api_data = fetch_all_metadata(b.title, b.authors, b.isbn)

        if api_data:
            # 2. Vorsichtiges Mergen (DB-Daten haben Vorrang!)
            if not b.description or len(b.description) < 10:
                b.description = api_data.get('description', '')

            if not b.isbn:
                b.isbn = api_data.get('isbn')

            # Keywords sind ein Set im Atom -> Union bilden
            if api_data.get('keywords'):
                new_keywords = set(api_data['keywords'])
                b.keywords = b.keywords.union(new_keywords)

            # Ratings einfach setzen
            b.rating_g = api_data.get('rating_g', 0.0)
            b.rating_ol = api_data.get('rating_ol', 0.0)

            # Scanner-Version updaten zur Erfolgskontrolle
            # (Wichtig für deinen Filter im BookScanner!)
            b.scanner_version = "4.0.0-API-ENRICHED"

        return core_obj


    @staticmethod
    def get_available_paths(author: str = "", title: str = ""):
        return Database.find_book_paths(author, title)

    @staticmethod
    def sanitize_path(path: str) -> str:
        """Normalisiert Pfade (Umlaute & Slashes) für systemübergreifende Konsistenz."""
        if not path:
            return ""
        # 1. Unicode-Normalisierung (Wichtig für macOS vs Linux/Windows Umlaute)
        norm = unicodedata.normalize('NFC', path)
        # 2. Vereinheitlichung der Slashes auf Unix-Style (Standard in DBs)
        norm = norm.replace('\\', '/')
        # 3. Entfernen von doppelten Slashes (außer am Anfang für UNC-Pfade falls nötig)
        while '//' in norm:
            norm = norm.replace('//', '/')
        return norm.strip()


    @staticmethod
    def build_perfect_filename(metadata: Dict[str, Any]) -> str:
        """Generiert den normierten Dateinamen nach System-Standard."""
        authors = metadata.get('authors', [])
        # Formatierung der Autorenliste zu "Vorname Nachname & Vorname Nachname"
        formatted_authors = []
        for a in authors:
            if isinstance(a, (list, tuple)) and len(a) >= 2:
                formatted_authors.append(f"{a[0]} {a[1]}".strip())
            else:
                formatted_authors.append(str(a).strip())

        auth_str = " & ".join(formatted_authors) if formatted_authors else "Unbekannt"

        # Serien-Teil (z.B. "Serie 01 - ")
        series_name = metadata.get('series_name')
        series_part = ""
        if series_name:
            idx = metadata.get('series_index', 0.0)
            series_part = f"{series_name} {idx:02g} - "  # Vereinfachte Formatierung

        title = metadata.get('title', "Unbekannt")
        ext = metadata.get('ext', '.epub')
        if not ext.startswith('.'): ext = f".{ext}"

        filename = f"{auth_str} {BookService.EM_DASH} {series_part}{title}{ext}"
        # Illegale Zeichen für Windows/Linux entfernen
        return re.sub(r'[:?*<>|"/\\\r\n]', '', filename).strip()

    @classmethod
    def smart_rename(cls, old_path: str, core_obj: Core) -> str:
        """Führt die physische Umbenennung basierend auf dem Core-Objekt durch."""
        old_path = cls.sanitize_path(old_path)
        b = core_obj.book

        new_filename = cls.build_filename(
            author_list=b.authors,
            series_name=b.series_name,
            series_index=b.series_index,
            title=b.title,
            extension=os.path.splitext(old_path)[1]
        )

        current_dir = os.path.dirname(old_path)
        new_path = cls.sanitize_path(os.path.join(current_dir, new_filename))

        if old_path != new_path and not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                return new_path
            except Exception as e:
                logging.error(f"Rename fehlgeschlagen: {e}")
        return old_path

    @classmethod
    def smart_save(cls, old_path: str, core_obj: Core) -> str:
        """Alias für die alte Bridge-Logik, leitet an smart_rename weiter."""
        return cls.smart_rename(old_path, core_obj)