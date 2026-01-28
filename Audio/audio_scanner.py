import os
from Gemini.file_utils import AUDIO_BASE, DB2_PATH, sanitize_path
from Zoom.authors import AuthorManager


class AudiobookScanner:
    def __init__(self, language_suffix="De"):
        # M:/Hörbuch-De
        self.root_path = os.path.join(AUDIO_BASE, f"Hörbuch-{language_suffix}")
        self.manager = AuthorManager(DB2_PATH)
        self.ignore_list = ["_byRegion", "000-049", "050-099", "_Favoriten"]

    def scan_all(self):
        if not os.path.exists(self.root_path):
            print(f"Pfad nicht gefunden: {self.root_path}")
            return

        for author_folder in os.listdir(self.root_path):
            if author_folder in self.ignore_list or author_folder.startswith("."):
                continue

            author_path = os.path.join(self.root_path, author_folder)
            if not os.path.isdir(author_path):
                continue

            # 1. Autor zuordnen (Nutzt bereits NFC-Normalisierung im Manager)
            author = self.manager.get_author_by_name(author_folder)

            if not author:
                # Hier könnten wir später entscheiden: Autor automatisch anlegen?
                print(f"Skipping: {author_folder} (Nicht in DB)")
                continue

            # 2. Unterordner (Hörbücher) scannen
            for book_folder in os.listdir(author_path):
                book_path = os.path.join(author_path, book_folder)
                if not os.path.isdir(book_path):
                    continue

                self.process_audiobook_folder(author, book_folder, book_path)

    def process_audiobook_folder(self, author, folder_name, full_path):
        # Pfad für DB normalisieren (NFC + /)
        db_path = sanitize_path(full_path)

        # Titel-Reinigung (Autor-Name vorne entfernen)
        title = folder_name.replace(author.display_name, "").strip()
        title = title.lstrip(" -–—")  # Entfernt versch. Bindestriche

        print(f"Found: {author.display_name} -> {title}")

        # Hier suchen wir nach dem Cover (Größte Bilddatei)
        cover_file = self.find_largest_image(full_path)
        cover_db_path = sanitize_path(cover_file) if cover_file else None

        # TODO: Hier rufen wir jetzt die Logik auf:
        # 1. Check/Create Work (basiert auf title & author_id)
        # 2. Create Audio Entry (verknüpft mit path und work_id)

    def find_largest_image(self, folder_path):
        images = [f for f in os.listdir(folder_path)
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not images:
            return None

        # Den Pfad mit der größten Dateigröße finden
        full_images = [os.path.join(folder_path, img) for img in images]
        return max(full_images, key=os.path.getsize)