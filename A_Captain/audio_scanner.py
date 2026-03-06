"""
Audio-Scanner
Level 0 = Wir stehen im Sprachordner (Hörbuch-De) -> Nächster Ordner ist Autor.
Level 1 = Wir stehen im Autorenordner (Alexander Hartung) -> Nächster Ordner ist Serie/Buch.
"""

import os
from tqdm import tqdm
from Engineering import Engineering as Eng
from Enterprise.core import Core, AudioTData
from Bridge.audio_manager import AudioManager

class AudioScanner:
    def __init__(self):
        self.total_audios = 0
        self.total_gb = 0.0
        self.total_hrs = 0.0
        self.found_folders = []


    # ----------------------------------------------------------------------
    # Dry-Run Scan: es werden globale Variablen gefüllt und Metadaten der Audiobooks ausggeben.
    # ----------------------------------------------------------------------
    def run_dry_scan(self, start_path):
        print(f"\n{'=' * 125}")
        print(f"{'AUTOR':<20} | {'SERIE':<20} | {'IDX':<5} | {'JAHR':<5} | {'TITEL':<35} | {'STATS'}")
        print(f"{'=' * 125}")

        # 1. Wir erstellen ein minimales Start-Dict
        # Initialen Context über die Pfadanalyse holen
        # (Erkennt Sprache 'De', Region etc.)
        initial_context = Eng.Audios.analyze_path_context(start_path)

        # 2. Wir jagen den anchor_path sofort durch die Brücke
        self._recursive_dry_walk(start_path, initial_context)

        # 3. Zusammenfassung
        print(f"{'=' * 125}")
        print(f"ERGEBNIS: {self.total_audios} Hörbücher gefunden.")
        print(f"GESAMT:   {self.total_gb:.2f} GB | {self.total_hrs:.1f} Stunden Material.")
        print(f"{'=' * 125}\n")


    def _recursive_dry_walk(self, current_path, _ignore_context):
        # 1. Wir ignorieren den übergebenen Kontext und fragen die Wahrheit des Pfades ab
        context = Eng.Audios.analyze_path_context(current_path)

        # 2. Typ bestimmen
        folder_type = Eng.Audios.get_folder_type(current_path)
        folder_name = os.path.basename(current_path)

        if folder_type == "AUDIOBOOK":
            # Hier ist unser Ziel!
            # Der Parser bekommt den Kontext, den analyze_path_context gerade ermittelt hat.
            res = Eng.Audios.parse_audio_folder_name(folder_name, context)

            gb, hrs = Eng.Audios.get_physical_stats(current_path)
            self.total_audios += 1
            self.total_gb += gb
            self.total_hrs += hrs

            self._print_line(res, context, gb, hrs)
            return  # Ein Hörbuch hat keine Unterordner mehr, die wir scannen

        elif folder_type == "CONTAINER":
            # Wir tauchen tiefer
            try:
                for entry in sorted(os.listdir(current_path)):
                    sub_path = os.path.join(current_path, entry)
                    if os.path.isdir(sub_path):
                        # Wir rufen uns selbst auf
                        self._recursive_dry_walk(sub_path, context)
            except PermissionError:
                pass

    def _print_line(self, res, context, gb, hrs):
        author = res.get("author") or context.get("author") or "Unbekannt"[:20]
        series = (res["series"] or "---")[:20]
        idx = f"{res['index']:>5.1f}"
        year = f"{res['year'] if res['year'] else '----':>5}"
        title = res["title"][:35]
        stats = f"{gb:>6.2f}GB | {hrs:>5.1f}h"

        print(f"{author:<20} | {series:<20} | {idx} | {year} | {title:<35} | {stats}")


    # ----------------------------------------------------------------------
    # LIVE SCAN  es wird ein s_core angelegt und gespeichert
    # ----------------------------------------------------------------------
    def run_live_scan(self, start_path):
        """Der echte Scan, der die Datenbank befüllt."""
        print(f"🔍 Sammle Ordnerstruktur in {start_path}...")

        # 1. Zuerst alle Hörbuch-Ordner finden (Rekursion ohne Logik)
        self.found_folders = []
        initial_context = Eng.Audios.analyze_path_context(start_path)
        self._find_audiobooks_recursive(start_path, initial_context)
        total = len(self.found_folders)
        print(f"🚀 Starte Live-Scan für {total} Hörbücher...")

        for folder_path, context in tqdm(self.found_folders, desc="Scanning Audios", unit="book"):
            try:
                # S_CORE erzeugen
                s_core = self.create_scan_core(folder_path, context)
                # Identität auflösen & in DB speichern (commit=True)
                # Das erledigt jetzt alles: Werk-Suche, Heilung, m:n Autoren
                Eng.Logic.resolve_identity(s_core, commit=True)

            except Exception as e:
                # Wir wollen nicht, dass der ganze Scan bei einem Fehler abbricht
                tqdm.write(f"❌ Fehler bei {os.path.basename(folder_path)}: {e}")

        print(f"\n✅ Scan abgeschlossen. {total} Einträge verarbeitet.")

    def _find_audiobooks_recursive(self, current_path, context):
        """Reiner Sammler für die Pfade."""
        # Kontext für diesen Level aktualisieren
        current_context = Eng.Audios.analyze_path_context(current_path)
        folder_type = Eng.Audios.get_folder_type(current_path)

        if folder_type == "AUDIOBOOK":
            self.found_folders.append((current_path, current_context))
        elif folder_type == "CONTAINER":
            try:
                for entry in sorted(os.listdir(current_path)):
                    sub_path = os.path.join(current_path, entry)
                    if os.path.isdir(sub_path):
                        self._find_audiobooks_recursive(sub_path, current_context)
            except PermissionError:
                pass

    def _recursive_walk_live(self, current_path, context):
        # Das ist die Recursion ohne TQDM
        context = Eng.Audios.analyze_path_context(current_path)
        folder_type = Eng.Audios.get_folder_type(current_path)

        if folder_type == "AUDIOBOOK":
            # 1. S_CORE erzeugen
            s_core = self.create_scan_core(current_path, context)

            # 2. Identität auflösen und Speichern (Heilung inklusive!)
            # Hier nutzen wir die universelle Methode aus dem LogicService
            Eng.Logic.resolve_identity(s_core, commit=True)

            # 3. Feedback
            print(f"✅ Gespeichert: {s_core.audio.title} ({s_core.audio.path})")
            return

        elif folder_type == "CONTAINER":
            for entry in sorted(os.listdir(current_path)):
                sub_path = os.path.join(current_path, entry)
                if os.path.isdir(sub_path):
                    self._recursive_walk_live(sub_path, context)

    def create_scan_core(self, folder_path, context) -> Core:
        dir_name = os.path.basename(folder_path)
        res = Eng.Audios.parse_audio_folder_name(dir_name, context)
        gb, hrs = Eng.Audios.get_physical_stats(folder_path)

        s_core = Core()

        # 1. Das physische Audio-Atom
        s_core.audio = AudioTData(
            title=res["title"],
            path=folder_path,
            length=hrs,
            year=str(res["year"]) if res["year"] else "",
            series_index=res["index"],
            description=f"{gb:.2f} GB"
        )

        # 2. Der Metadaten-Container (Book-Atom)
        s_core.book.title = res["title"]
        s_core.book.series_name = res["series"]
        s_core.book.series_index = res["index"]

        # 3. Autoren für die Logik aufbereiten
        # Wir zerlegen den Namen (z.B. "Annie Coutelle") in (Vorname, Nachname)
        raw_author = res.get("author_override") or context.get("author") or "Unbekannt"

        # Nutze deine bestehende Logik zum Splitten von Namen
        fn, ln = Eng.Authors.split_name(raw_author)
        s_core.book.authors = {(fn, ln)}  # Als Set von Tupeln für resolve_identity

        return s_core

"""
class AudioTData:
    id: int = 0
    work_id: int = 0
    title: str = ""
    series_id: int = 0
    series_index: float = 0.0
    year: str = ""
    language: str = ""
    genre: str = ""
    path: str = ""
    cover_path: str = ""
    speaker: str = ""
    stars: int = 0
    length: float = 0.0  # Spalte 'length' als REAL (Stunden)
    description: str = ""
"""

if __name__ == "__main__":
    scanner = AudioScanner()
    scanner.run_dry_scan(r"M:\Hörbuch-Es")