# Engineering.audio_service.py
import os
import re
from mutagen.mp3 import MP3
from mutagen import File  # Wichtig für generische Tags
from Enterprise.core import Core, AudioTData


class AudioService:

    @staticmethod
    def scan_audio_folder(folder_path: str, context: dict) -> Core:
        """
        Der zentrale Einstiegspunkt für den Scanner.
        Trägt alle Puzzleteile zusammen.
        """
        dir_name = os.path.basename(folder_path)
        # 1. Namen parsen (Logische Basis-Daten)
        res = AudioService.parse_audio_folder_name(dir_name, context)
        # 2. Physische Stats (Größe & Dauer)
        gb, hrs = AudioService.get_physical_stats(folder_path)
        # 3. Metadaten aus Tags extrahieren
        tags = AudioService.extract_audio_tags(folder_path)
        # 4. Bestes Cover finden
        cover = AudioService.find_best_cover(folder_path)

        # --- ZUSAMMENFÜHRUNG IM CORE ---
        core = Core()

        # AudioTData befüllen (Default-Werte über dict.get)
        core.audio = AudioTData(
            id=0,
            title=res["title"],
            path=folder_path,
            length=hrs,
            year=str(res["year"]) if res["year"] else "",
            series_name=res["series"],
            series_index=res["index"],
            genre=tags.get("genre", ""),
            speaker=tags.get("speaker", ""),
            description=tags.get("description") or f"Scan: {gb} GB",
            cover_path=cover,
            language=context.get("language", "")
        )

        # Autoren für die Identitätsauflösung vorbereiten
        author_raw = res.get("author") or context.get("author") or "Unbekannt"
        # Wir nehmen an, der letzte Teil ist der Nachname
        parts = author_raw.strip().split()
        if len(parts) > 1:
            fn, ln = " ".join(parts[:-1]), parts[-1]
        else:
            fn, ln = "", parts[0]
        core.audio.authors = {(fn, ln)}

        return core

    @staticmethod
    def parse_audio_folder_name(audio_subfolder, context):
        """ Analysiert den Ordnernamen (Logik wie besprochen) """
        if "_Easy Reader" in str(context.get("full_path", "")):
            if " - " in audio_subfolder:
                author_part, title_part = audio_subfolder.split(" - ", 1)
                clean_title = re.sub(r'\s*\([A-Z]\d\)\s*', '', title_part).strip()
                return {
                    "author": author_part.strip(),
                    "series": context.get("level") or "Easy Reader",
                    "index": 0.0,
                    "year": None,
                    "title": clean_title
                }

        audio_stripped = audio_subfolder
        author = context.get("author")
        series = context.get("series")
        found_index = 0.0
        found_year = None
        final_series = series if series else ""

        if author:
            pattern = re.compile(r'^' + re.escape(author) + r'[\s\-–—]*', re.IGNORECASE)
            audio_stripped = pattern.sub('', audio_stripped).strip()

        pattern_with_anchor = r'^(.*?)(\d+(?:[.,]\d+)?)\s*[-–—]\s*(.*)$'
        match = re.search(pattern_with_anchor, audio_stripped)

        if match:
            potential_name = match.group(1).strip()
            found_index = float(match.group(2).replace(',', '.'))
            audio_stripped = match.group(3).strip()
            if potential_name:
                final_series = potential_name
            elif series:
                final_series = series
            else:
                final_series = author.split()[-1] if author else "Unbekannte Serie"
        else:
            final_series = series if series else ""
            found_index = 0.0

        if 1900 <= found_index <= 2100:
            found_year = int(found_index)

        year_match = re.search(r'\((19\d{2}|20\d{2})\)', audio_stripped)
        if year_match:
            found_year = int(year_match.group(1))
            audio_stripped = audio_stripped.replace(year_match.group(0), "").strip()

        final_title = audio_stripped if audio_stripped else audio_subfolder

        return {
            "series": final_series,
            "index": found_index,
            "year": found_year,
            "title": final_title,
            "author": context.get("author")  # Fallback
        }

    @staticmethod
    def get_physical_stats(folder_path: str):
        size_bytes, seconds = 0, 0
        for root, _, files in os.walk(folder_path):
            for f in files:
                p = os.path.join(root, f)
                size_bytes += os.path.getsize(p)
                if f.lower().endswith('.mp3'):
                    try:
                        audio = MP3(p)
                        seconds += audio.info.length
                    except:
                        pass
        return round(size_bytes / (1024 ** 3), 3), round(seconds / 3600, 2)

    @staticmethod
    def extract_audio_tags(folder_path: str) -> dict:
        """ Extrahiert Genre, Sprecher und Beschreibung via Mutagen. """
        audio_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp3', '.m4b', '.m4a'))]
        if not audio_files: return {}

        file_path = os.path.join(folder_path, audio_files[0])
        try:
            audio = File(file_path)
            if not audio or not audio.tags: return {}

            tags = audio.tags
            data = {"genre": "", "speaker": "", "description": ""}

            # Genre
            g = tags.get('TCON') or tags.get('©gen')
            data["genre"] = str(g[0] if isinstance(g, list) else g) if g else ""

            # Speaker / Narrator
            for field in ['TCOM', 'TPE3', 'TXXX:narrator', '©wrt']:
                s = tags.get(field)
                if s:
                    data["speaker"] = str(s[0] if isinstance(s, list) else s)
                    break

            # Description / Comment
            for field in ['COMM', 'TXXX:description', '©cmt', 'desc']:
                d = tags.get(field)
                if d:
                    data["description"] = d.text[0] if hasattr(d, 'text') else str(d)
                    break

            return {k: v.strip() for k, v in data.items()}
        except:
            return {}

    @staticmethod
    def find_best_cover(folder_path: str) -> str:
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
        imgs = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
        return max(imgs, key=os.path.getsize) if imgs else ""

    @staticmethod
    def get_folder_type(path: str):
        entries = os.listdir(path)
        if any(e.lower().endswith(('.mp3', '.m4b')) for e in entries): return "AUDIOBOOK"
        if any(os.path.isdir(os.path.join(path, e)) for e in entries): return "CONTAINER"
        return "EMPTY"

    @staticmethod
    def analyze_path_context(full_path):
        parts = full_path.split(os.sep)
        context = {
            "language": None, "region": None, "level": None,
            "author": None, "series": None, "is_special": False, "full_path": full_path
        }
        # 1. Root finden
        root_idx = -1
        for i, p in enumerate(parts):
            if "Hörbuch-" in p:
                context["language"] = p.split("-")[-1]
                root_idx = i
                break

        if root_idx == -1: return context
        rel_parts = parts[root_idx + 1:]
        if not rel_parts: return context

        first_level = rel_parts[0]

        # 2. Spezial-Zweige
        if first_level == "_byRegion":
            context["is_special"] = True
            if len(rel_parts) > 1: context["region"] = rel_parts[1]
            if len(rel_parts) > 2: context["author"] = rel_parts[2]

        elif first_level == "_Easy Reader":
            context["is_special"] = True
            if len(rel_parts) > 1: context["level"] = rel_parts[1]
            # Bei Easy Readern steht der Autor meist erst im Ordnernamen des Buchs,
            # daher bleibt context["author"] hier oft None -> völlig korrekt für deinen Parser!

        elif first_level == "_Sprache":
            context["is_special"] = True

        # 3. Standard-Pfad (Autor -> Serie -> Buch)
        else:
            # rel_parts[0] ist immer der Autor
            context["author"] = rel_parts[0]

            # NEU: Nur wenn wir MINDESTENS 3 Ebenen haben, ist die mittlere eine Serie
            # Beispiel: ["Baricco", "Seta"] -> len=2 -> Keine Serie im Kontext
            # Beispiel: ["Pirincci", "Felidae", "01-Seta"] -> len=3 -> Serie = "Felidae"
            if len(rel_parts) >= 3:
                context["series"] = rel_parts[1]
            else:
                context["series"] = None  # Explizit leer lassen bei Autor/Buch

        return context

    @staticmethod
    def labor_dry_run():
        # Wir definieren den Kontext, wie er vom Scanner käme
        test_context = {
            "author": "Akif Pirinçci",
            "series": ""
        }

        test_cases = [
            "Kommissar Erlendur01 - Menschensöhne",
            "Akif Pirinçci - Felidae 1 - Felidae",
            "01-Nichts als Staub",
            "Felidae 02 - Francis",
            "Der offene Sarg"
        ]

        print(f"\n{'=' * 100}")
        print(f"🧪 CORE-PARSER TESTLAUF (Hörbuch-Logik)")
        print(f"{'=' * 100}")
        print(f"{'Input Ordner':<40} | {'Erkannter Titel':<25} | {'Serie (Index)':<20}")
        print(f"{'-' * 100}")

        for tc in test_cases:
            try:
                # 1. Aufruf der neuen Logik (liefert ein Dictionary!)
                res = AudioService.parse_audio_folder_name(tc, test_context)

                # 2. Daten aus dem Dictionary extrahieren
                titel = res["title"]
                serie = res["series"]
                index = res["index"]

                series_display = f"{str(serie):<12} ({index})"
                print(f"{tc[:40]:<40} | {str(titel):<25} | {series_display}")

            except Exception as e:
                import traceback
                print(f"❌ Fehler bei '{tc}': {e}")
                # traceback.print_exc() # Nur zum Debuggen bei echten Code-Fehlern

        print(f"{'=' * 100}\n")


    def find_best_cover(folder_path):
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
        images = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                  if f.lower().endswith(valid_exts)]

        if not images:
            return ""

        # Nimm die Datei mit den meisten Bytes (das Original-Cover)
        return max(images, key=os.path.getsize)

    def extract_audio_tags(folder_path):
        # Wir nehmen die erste passende Audio-Datei im Ordner
        audio_files = [f for f in os.listdir(folder_path)
                       if f.lower().endswith(('.mp3', '.m4b', '.m4a', '.mp4'))]

        if not audio_files:
            return {}

        file_path = os.path.join(folder_path, audio_files[0])
        try:
            audio = File(file_path)
            if audio is None or audio.tags is None:
                return {}

            tags = audio.tags
            res = {}

            # GENRE (TCON in MP3, ©gen in MP4)
            res['genre'] = str(tags.get('TCON', tags.get('©gen', [""])))

            # SPEAKER (Hörbücher nutzen oft 'composer' (TCOM) oder 'conductor' (TPE3))
            # In M4B ist es oft '©wrt' (Writer/Author)
            speaker_fields = ['TCOM', 'TPE3', 'TXXX:narrator', '©wrt']
            res['speaker'] = ""
            for field in speaker_fields:
                val = tags.get(field)
                if val:
                    res['speaker'] = str(val[0] if isinstance(val, list) else val)
                    break

            # DESCRIPTION (COMM in MP3, ©cmt oder desc in MP4)
            desc_fields = ['COMM', 'TXXX:description', '©cmt', 'desc']
            res['description'] = ""
            for field in desc_fields:
                val = tags.get(field)
                if val:
                    # Bei COMM (MP3) ist das Format oft ein Objekt, wir brauchen .text
                    content = val.text[0] if hasattr(val, 'text') else str(val)
                    res['description'] = content
                    break

            # Cleanup: Mutagen gibt oft Listen oder technisches Format zurück
            return {k: v.strip() for k, v in res.items()}

        except Exception as e:
            print(f"⚠️ Mutagen Fehler bei {file_path}: {e}")
            return {}

# TEST
if __name__ == "__main__":
    audio = AudioService()
    audio.labor_dry_run()