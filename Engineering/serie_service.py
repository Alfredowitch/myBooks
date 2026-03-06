# Engineering.series_service.py

import pandas as pd
from Engineering.author_service import AuthorService
from Enterprise.database import Database

class SeriesService:
    @staticmethod
    def get_id_by_name(name: str) -> int:
        query = "SELECT id FROM series WHERE LOWER(name) = LOWER(?)"
        res = Database.query_one(query, [name])
        return res['id'] if res else None

    @staticmethod
    def resolve_series(series_name: str, author_ids: list[int]) -> int:
        """
        Findet die richtige Serien-ID oder legt eine neue an.
        Verhindert die Vermischung von Namensdubletten bei unterschiedlichen Autoren.
        """
        if not series_name:
            return 0

        # 1. Alle Serien mit diesem Namen suchen (können mehrere sein!)
        query = "SELECT id FROM series WHERE LOWER(name) = LOWER(?)"
        candidates = Database.query_all(query, [series_name])

        if not candidates:
            # Gar keine Serie mit diesem Namen -> Neu anlegen
            return SeriesService.create(series_name)

        # 2. Bestehende Serien prüfen: Gehört eine davon bereits zu unseren Autoren?
        for cand in candidates:
            s_id = cand['id']

            # Wir suchen ein Werk, das in dieser Serie (s_id) ist
            # UND von einem unserer Autoren (author_ids) verfasst wurde.
            placeholders = ",".join(["?"] * len(author_ids))
            check_sql = f"""
                    SELECT w.id FROM works w
                    JOIN work_to_author wta ON w.id = wta.work_id
                    WHERE w.series_id = ? AND wta.author_id IN ({placeholders})
                    LIMIT 1
                """
            match = Database.query_one(check_sql, [s_id, *author_ids])

            if match:
                # Treffer! Diese Serie 'Psychologie' gehört bereits zu diesem Autor.
                return s_id

        # 3. Wenn zwar Serien existieren, aber keine zu den Autoren passt:
        # Lieber eine neue Serie anlegen, um Punkt (c) zu erfüllen.
        # (Eventuell mit einem Hinweis im Log/Audit)
        return SeriesService.create(series_name)

    @staticmethod
    def create(name: str) -> int:
        # Hier auch den Slug generieren, falls deine DB das Feld 'slug' hat
        slug = AuthorService.slugify("", name)  # Wir nutzen die gleiche Logik
        sql = "INSERT INTO series (name, slug) VALUES (?, ?)"
        return Database.execute(sql, [name, slug])

    @staticmethod
    def merge(master_id: int, slave_id: int):
        """Alle Werke einer Serie zu einer anderen umziehen."""
        sql = "UPDATE works SET series_id = ? WHERE series_id = ?"
        Database.execute(sql, [master_id, slave_id])
        # Slave-Serie als gemergt markieren oder löschen
        Database.execute("UPDATE series SET notes = 'MERGED' WHERE id = ?", [slave_id])


    @staticmethod
    def analyze_series_duplicates():
        print("🔍 Suche nach Serien-Dubletten...")

        # Wir holen Name, ID, die verknüpften Autoren und die Anzahl der Werke
        query = """
            SELECT 
                s.id, s.name, s.name_de, s.name_en,
                GROUP_CONCAT(DISTINCT a.firstname || ' ' || a.lastname) as author_info,
                COUNT(DISTINCT w.id) as count_works
            FROM series s
            LEFT JOIN works w ON s.id = w.series_id
            LEFT JOIN work_to_author wta ON w.id = wta.work_id
            LEFT JOIN authors a ON wta.author_id = a.id
            GROUP BY s.id
        """
        raw_data = Database.query_all(query)
        if not raw_data: return

        df = pd.DataFrame(raw_data)
        df['norm_name'] = df['name'].str.strip().str.lower()

        # Dubletten finden
        duplicates = df[df.duplicated('norm_name', keep=False)].sort_values('norm_name')

        if duplicates.empty:
            print("✅ Keine Serien-Dubletten gefunden.")
            return

        print(f"\n--- SERIEN-DIAGNOSE ({len(duplicates)} Einträge) ---")
        for name, group in duplicates.groupby('norm_name'):
            print(f"\n📂 Serie: '{name.upper()}'")
            for _, row in group.iterrows():
                # Hier siehst du: Gleicher Name, aber vielleicht andere Autoren?
                print(f"   ID: {row['id']:<6} | "
                      f"Autoren: {row['author_info'] if row['author_info'] else '---':<20} | "
                      f"Werke: {row['count_works']}")
        return duplicates

    @staticmethod
    def execute_series_merge(master_id: int, slave_id: int):
        """Verschmilzt Serien und rettet fehlende Sprach-Infos (Rein DB-basiert)."""
        with Database.conn() as conn:
            # 1. Daten für die Fusion laden
            m_row = conn.execute("SELECT * FROM series WHERE id = ?", [master_id]).fetchone()
            s_row = conn.execute("SELECT * FROM series WHERE id = ?", [slave_id]).fetchone()

            if not m_row or not s_row: return

            master = dict(m_row)
            slave = dict(s_row)

            # 2. Sprach-Felder fusionieren (name_de, name_en)
            updates = {}
            for field in ['name_de', 'name_en']:
                if not master.get(field) and slave.get(field):
                    updates[field] = slave[field]

            if updates:
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                conn.execute(f"UPDATE series SET {set_clause} WHERE id = ?", list(updates.values()) + [master_id])

            # 3. Werke auf neue Serien-ID umbiegen
            conn.execute("UPDATE works SET series_id = ? WHERE series_id = ?", [master_id, slave_id])

            # 4. Die leere Slave-Serie löschen
            conn.execute("DELETE FROM series WHERE id = ?", [slave_id])


    @staticmethod
    def interactive_series_repair(df_duplicates):
        print("\n📚 SERIEN-HEILER (Interaktiv)")

        for name, group in df_duplicates.groupby('norm_name'):
            variants = group.to_dict('records')
            print(f"\n--- Gruppe: '{name.upper()}' ---")

            # Autoren-Vergleich für die Warnung
            auth_sets = [set(v['author_info'].split(',')) if v['author_info'] else set() for v in variants]
            # Prüfen, ob es Überschneidungen gibt
            has_overlap = any(len(auth_sets[0] & s) > 0 for s in auth_sets[1:])

            for i, v in enumerate(variants, 1):
                prefix = "⚠️ " if not has_overlap else "   "
                print(
                    f"{prefix}{i}) ID: {v['id']:<6} | Autoren: {v['author_info'] or '---':<30} | Werke: {v['count_works']}")

            if not has_overlap:
                print("❗ ACHTUNG: Keine gemeinsamen Autoren gefunden. Wahrscheinlich KEIN Merge!")

            choice = input(f"Master (1-{len(variants)}) oder s(kip)/q(uit): ").strip().lower()

            if choice == 'q': break
            if choice == 's' or not choice.isdigit(): continue

            idx = int(choice) - 1
            if 0 <= idx < len(variants):
                master_id = variants[idx]['id']
                slave_ids = [v['id'] for i, v in enumerate(variants) if i != idx]

                for s_id in slave_ids:
                    SeriesService.execute_series_merge(master_id, s_id)
                print(f"✅ Merge für '{name}' vollzogen.")

if __name__ == "__main__":
    # 1. Serien-Diagnose starten
    df_series = SeriesService.analyze_series_duplicates()

    # 2. Wenn Dubletten da sind, in den interaktiven Modus wechseln
    if df_series is not None and not df_series.empty:
        SeriesService.interactive_series_repair(df_series)