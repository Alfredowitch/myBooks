import os
from Engineering import Core


class LogicService:
    @staticmethod
    def resolve_identity(s_core: Core, commit: bool = False):
        """
        Der universelle Identitäts-Löser.
        Extrahiert Metadaten aus Audio oder Book, findet/heilt das Werk
        und verknüpft alles im Core.
        """
        from Engineering import Engineering as Eng

        # 1. Die "Drei Goldenen Werte" extrahieren (Priorität: Book > Audio)
        # Wir nehmen das, was vorhanden ist.
        source = s_core.book if s_core.book.authors or s_core.book.title else s_core.audio

        title = source.title
        authors = source.authors  # Set aus (Vorname, Nachname)
        series_name = source.series_name
        series_index = source.series_index

        if not title or not authors:
            print(f"⚠️ Abbruch: Unzureichende Daten für Identität ({title}, {authors})")
            return None

        # 2. Logische Infrastruktur auflösen (Autoren & Serie)
        a_ids = [Eng.Authors.get_or_create_by_name(fn, ln) for fn, ln in authors]
        s_core.author_ids = set(a_ids)

        s_id = Eng.Series.resolve_series(series_name, a_ids)

        # 3. Das Werk-Triple finden (Titel, Index, Autoren)
        w_id = Eng.Works.find_by_triple(title, series_index, a_ids)

        if not w_id:
            if commit:
                # Heilung: Werk existiert nicht -> Neu anlegen
                w_id = Eng.Works.create(title, series_index, s_id, a_ids)
            else:
                w_id = 0  # Markierung für "Neu"

        # 4. Rückschreiben der Identität in ALLE Atome
        # Das ist der Clou: Wir befüllen beides, aber nur das mit Pfad wird gespeichert.
        s_core.work.id = w_id
        s_core.book.work_id = w_id
        s_core.audio.work_id = w_id

        if commit:
            # s_core.save() nutzt _do_save_all und prüft intern "if path",
            # daher wird nur das physisch vorhandene Medium in die DB geschrieben.
            s_core.save()
        return w_id


    @staticmethod
    def sync_test(file_path: str):
        # 1. ARCHIV & SYSTEM laden
        from Engineering import Engineering as Eng  # hier ist die Fassade perfekt
        path = Eng.Books.santize_path(file_path)
        a_core = Core.load_book_by_path(path)
        s_core = Eng.Books.scan_file_basic(path)

        # Logik-Identität auflösen (setzt IDs in s_core)
        LogicService.resolve_book_identity(s_core)

        print(f"\n{'=' * 85}")
        print(f"🩺 HEALING-AUDIT: {os.path.basename(path)}")
        print(f"{'=' * 85}")

        # --- VERGLEICHS-TABELLE ---
        def get_info(core):
            if not core or not core.book: return ("-", "-", [])
            authors = list(core.author_ids) if hasattr(core, 'author_ids') else []
            return (core.book.title, core.book.work_id, authors)

        a_title, a_work, a_auths = get_info(a_core)
        s_title, s_work, s_auths = get_info(s_core)

        print(f"{'Merkmal':<15} | {'Archiv (Ist)':<30} | {'System (Soll)':<30}")
        print("-" * 85)

        # Zeile: Titel
        print(
            f"{'Titel':<15} | {str(a_title)[:28]:<30} | {str(s_title)[:28]:<30} {'✅' if a_title == s_title else '⚠️'}")

        # Zeile: Werk-ID
        print(f"{'Werk-ID':<15} | {str(a_work):<30} | {str(s_work):<30} {'✅' if a_work == s_work else '🚨 RE-MAP'}")

        # Zeile: Autoren-IDs
        a_auths_sorted = sorted(list(a_auths))
        s_auths_sorted = sorted(list(s_auths))
        auth_match = a_auths_sorted == s_auths_sorted
        print(
            f"{'Autoren-IDs':<15} | {str(a_auths_sorted):<30} | {str(s_auths_sorted):<30} {'✅' if auth_match else '🛠️ SYNC'}")

        # --- DETAIL-CHECK: AUTOREN-SLUGS ---
        print(f"\n{'🔍 Detail-Check: Autoren-Konsistenz':<85}")
        print("-" * 85)
        for a_id in s_auths:
            author = Eng.Database.query_one("SELECT firstname, lastname, slug FROM authors WHERE id = ?", [a_id])
            if author:
                correct_slug = Eng.Authors.slugify(author['firstname'], author['lastname'])
                is_valid = (author['slug'] == correct_slug)
                status = "✅ OK" if is_valid else f"❌ FALSCH (Soll: {correct_slug})"
                name = f"{author['firstname']} {author['lastname']}"
                print(f"ID {a_id:<4} | {name:<30} | Slug: {author['slug']:<20} | {status}")

        # --- FAZIT ---
        print(f"\n{'=' * 85}")
        if a_work != s_work and a_work != "-":
            print("🚩 WARNUNG: Dieses Buch würde einem ANDEREN Werk zugeordnet werden!")
        if not auth_match and a_work != "-":
            print("🛠️ HEILUNG: Die Autoren-Verknüpfung dieses Werks würde korrigiert werden.")
        print(f"{'=' * 85}\n")


if __name__ == "__main__":
    # Test-Pfade
    test_file = r"D:/Bücher/Deutsch/K/Katrin Skafte/Katrin Skafte & Erik — Lauter ganz normale Männer.epub"
    # Nur ein Aufruf für den vollen Durchblick
    LogicService.sync_test(test_file)