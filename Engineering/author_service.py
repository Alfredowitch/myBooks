# Engineering.author_services.py
import re
import unicodedata
import pandas as pd
from Enterprise.database import Database


class AuthorService:
    def get_by_id(author_id: int):
        """Holt einen Autor anhand seiner ID."""
        query = "SELECT id, firstname, lastname, slug, vita FROM authors WHERE id = ?"
        return Database.query_one(query, [author_id])


    @staticmethod
    def get_or_create_by_name(firstname: str, lastname: str) -> int:
        """Identifiziert Autor via Slug oder legt ihn neu an."""
        slug = AuthorService.slugify(firstname, lastname)
        # Suche nach existierendem Slug
        query = "SELECT id, firstname, lastname FROM authors WHERE slug = ?"
        existing = Database.query_one(query, [slug])

        if existing:
            # Upgrade-Logik (Regel 2): Wenn wir jetzt eine Version mit Umlaut haben,
            # die DB aber nur ASCII hat, aktualisieren wir die Anzeige-Namen.
            if any(ord(c) > 127 for c in (firstname + lastname)):
                if not any(ord(c) > 127 for c in (existing['firstname'] + existing['lastname'])):
                    Database.execute(
                        "UPDATE authors SET firstname = ?, lastname = ? WHERE id = ?",
                        [firstname, lastname, existing['id']]
                    )
            return existing['id']

        # Neu anlegen, falls Slug unbekannt
        sql = "INSERT INTO authors (firstname, lastname, slug) VALUES (?, ?, ?)"
        return Database.execute(sql, [firstname, lastname, slug])

    @staticmethod
    def generate_match_key(firstname: str, lastname: str) -> str:
        """Normalisiert Namen für den Vergleich (J. K. -> J.K. -> jkrowling)."""
        f = re.sub(r'([A-Z]\.)\s+(?=[A-Z]\.)', r'\1', (firstname or "").strip())
        l = (lastname or "").strip()
        return re.sub(r'[\s.]', '', f"{f}{l}").lower()

    @staticmethod
    def analyze_author_duplicates():
        """Phase 2: Identifiziert Autoren-Dubletten via Pandas (RAM-Safe)."""
        print("🔍 Lade Autoren für Dubletten-Check...")
        raw_data = Database.query_all("SELECT id, firstname, lastname FROM authors")

        if not raw_data: return None

        df = pd.DataFrame(raw_data)
        df['firstname'] = df['firstname'].fillna('')
        df['lastname'] = df['lastname'].fillna('')

        # Wir nutzen die Logik aus dem AuthorService für konsistente Keys
        df['virtual_match_key'] = df.apply(
            lambda r: AuthorService.generate_match_key(r['firstname'], r['lastname']),
            axis=1
        )

        duplicates = df[df.duplicated('virtual_match_key', keep=False)]

        if duplicates.empty:
            print("✅ Keine Autoren-Dubletten gefunden.")
            return None

        print(f"\n--- DIAGNOSE REPORT ---")
        print(f"Dubletten-Gruppen: {duplicates['virtual_match_key'].nunique()}")

        report = duplicates.sort_values(by='virtual_match_key')
        for key, group in report.groupby('virtual_match_key'):
            print(f"\n🔑 Key: [{key}]")
            for _, row in group.iterrows():
                print(f"   ID: {row['id']:<6} | {row['firstname']} {row['lastname']}")

        return report

    @staticmethod
    def execute_author_merge(master_id: int, slave_ids: list):
        """Nutzt den AuthorService, um die physische Zusammenführung zu vollziehen."""
        try:
            for s_id in slave_ids:
                AuthorService.merge(master_id, s_id)
            return True
        except Exception as e:
            print(f"❌ Fehler beim Merge: {e}")
            return False

    @staticmethod
    def interactive_authormerge(master_id: int, slave_id: int):
        """Fusioniert Metadaten und Werke, löscht danach den Slave."""
        with Database.conn() as conn:
            # A) Metadaten-Fusion
            m_row = conn.execute("SELECT * FROM authors WHERE id = ?", [master_id]).fetchone()
            s_row = conn.execute("SELECT * FROM authors WHERE id = ?", [slave_id]).fetchone()

            if not m_row or not s_row:
                return False

            m = dict(m_row)
            s = dict(s_row)

            fields_to_check = ['vita', 'image_path', 'url_de', 'url_en', 'url_fr', 'url_es', 'url_it', 'birth_year',
                               'birth_place']
            updates = {}
            for f in fields_to_check:
                if not m.get(f) and s.get(f):
                    updates[f] = s[f]

            if (s.get('stars') or 0) > (m.get('stars') or 0):
                updates['stars'] = s['stars']

            if updates:
                sql = "UPDATE authors SET " + ", ".join([f"{k} = ?" for k in updates.keys()]) + " WHERE id = ?"
                conn.execute(sql, list(updates.values()) + [master_id])

            # C) n:m Werke umziehen
            conn.execute("""
                    INSERT OR IGNORE INTO work_to_author (work_id, author_id)
                    SELECT work_id, ? FROM work_to_author WHERE author_id = ?
                """, [master_id, slave_id])
            conn.execute("DELETE FROM work_to_author WHERE author_id = ?", [slave_id])

            # D) Slave löschen
            conn.execute("DELETE FROM authors WHERE id = ?", [slave_id])
            return True

    @staticmethod
    def slugify(firstname: str, lastname: str) -> str:
        """
        Erzeugt den Master-Key für DB-Identität und Dateinamen.
        Ziel: 'A. F. Müller' -> 'a-f-mueller'
        """
        # 1. Kombination & Initialen-Normalisierung (J. K. -> J.K.)
        name = f"{firstname} {lastname}".strip()
        name = re.sub(r'([A-Z]\.)\s+(?=[A-Z]\.)', r'\1', name)

        # 2. Punkte zu Bindestrichen für Bild-Kompatibilität (A.F. -> a-f-)
        name = name.replace('.', '-')

        # 3. Umlaute auflösen für Dubletten-Sicherheit (Müller == Mueller)
        repls = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}
        for char, replacement in repls.items():
            name = name.replace(char, replacement)

        # 4. Akzente entfernen (NFKD Normalisierung)
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')

        # 5. Bereinigung: Alles kleinschreiben, nur Buchstaben und Bindestriche
        name = name.lower()
        name = re.sub(r'[^a-z0-9\-]', '-', name)

        # 6. "Säuberung": Keine doppelten Bindestriche, keine führenden/endenden
        # Macht aus 'a--f--morland' -> 'a-f-morland'
        return re.sub(r'-+', '-', name).strip('-')

if __name__ == "__main__":
    # Die feine Reinigung (Autoren)
    df_dups = AuthorService.analyze_author_duplicates()
    if df_dups is not None:
        AuthorService.interactive_author_repair(df_dups)
