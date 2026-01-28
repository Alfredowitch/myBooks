"""
DATEI: migration.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Zweistufiges Reparatur-System.
              1. logic_repair_detachment(): Stellt saubere Werk-IDs sicher.
              2. fast_migrate_content_and_titles(): Aggregiert Daten im RAM.
"""
import sqlite3
import os
import re
from collections import defaultdict
from tqdm import tqdm
from Zoom.utils import DB_PATH, slugify
from Audio.book_data import BookData

def clean_split(text, separator=','):
    if not text: return set()
    return {item.strip() for item in text.split(separator) if item.strip()}

def to_int(val):
    """Gibt einen Integer zurück, oder None wenn das Feld wirklich leer/undefiniert ist."""
    if val is None or str(val).strip() == "":
        return None
    try:
        # Sicherstellen, dass auch "5.0" als String korrekt wird
        num = int(float(str(val)))
        # Deine 7-Sterne Grenze absichern
        return min(max(num, 0), 7)
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# Schnelle Migrationslogik im RAM
# Für die Prüfung schreiben wir eigene schnellere Routinen als im BookManager.
# SQL Zugriffe sind langsam, weil immer die Festplatte bestätigen muss
# ----------------------------------------------------------------------
def fast_logic_repair_detachment():
    """
    Prüft ob Bücher zu Werken verknüpft sind mit anderen Autoren.
    Wenn ja, werden die Bücher getrennt w_id in Book = 0
    Scanned alle unverknüpften Bücher (w_id = 0) neu.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🚀 Phase 1 (Brute-Force): Starte RAM-Vergleich...")
    # 1. Schritt: Bestehende Werk-Autoren-Struktur ins RAM laden
    cursor.execute("""
        SELECT wa.work_id, a.firstname, a.lastname 
        FROM work_to_author wa
        JOIN authors a ON wa.author_id = a.id
    """)
    # Erstellt ein Mapping: { work_id: set([ (Vorname, Nachname), ... ]) }
    # Dictionary {:} mit work_id und ein Set {,} von Autorentuples.
    db_structure = defaultdict(list)
    for row in cursor.fetchall():
        w_id = row[0]
        ln = (row[1] or "").lower().strip()
        if ln:
            db_structure[w_id].append(ln)

    # 2. Alle Bücher laden
    cursor.execute("SELECT id, path, work_id FROM books")
    all_books = cursor.fetchall()

    detach_ids = []  # Liste für falsche IDs (müssen in DB auf NULL)
    books_to_fix = []  # Liste für Pfade, die wir dem Manager übergeben

    pbar = tqdm(all_books, desc="RAM-Check", unit="Buch")
    for row in pbar:
        b_id, b_path, b_wid = row['id'], row['path'], row['work_id']
        b_wid = b_wid if b_wid else 0  # SQL-None zu 0

        # 3. Der Detektiv-Modus
        is_corrupt = False

        if b_wid != 0:
            # A: Phantom-Check
            if b_wid not in db_structure:
                is_corrupt = True
            # B: Autoren-Check (z.B. Tanja Voosen vs. Alexander Oetker)
            else:
                filename = os.path.basename(b_path).lower()
                work_authors = db_structure[b_wid]
                if not any(nachname in filename for nachname in work_authors):
                    is_corrupt = True

        # 4. Die Weichenstellung (ohne elif!)
        if is_corrupt:
            detach_ids.append((b_id,))
            b_wid = 0  # Im RAM sofort auf 0 setzen, damit der nächste Check greift

        if b_wid == 0:
            # Alles was 0 war oder gerade 0 wurde, muss zum Manager
            books_to_fix.append(b_path)

    # 4. Schritt: Massen-Update (Executemany)
    if detach_ids:
        print(f"⚡ Trenne {len(detach_ids)} falsche Zuordnungen in der DB...")
        # Wir setzen work_id auf NULL, damit die DB wieder sauber ist
        cursor.executemany("UPDATE books SET work_id = NULL WHERE id = ?", detach_ids)
        conn.commit()

    if books_to_fix:
        print(f"🆕 Re-Analyse durch BookData-Manager für {len(books_to_fix)} Bücher...")
        for p in tqdm(books_to_fix, desc="Manager-Fixing"):
            try:
                # Nutzt deine load_by_path Methode aus book_data_old.py
                mgr = BookData.load_by_path(p)
                if mgr:
                    # Da work_id in DB jetzt NULL ist, erkennt dein System
                    # es als neues Buch und sucht/erstellt ein passendes Werk.
                    mgr.work.id = 0
                    mgr.save()  # Führt deine komplette Sync-Logik aus
            except Exception as e:
                # Falls Datei fehlt oder Pfad kaputt
                continue

    conn.close()
    print("✅ Phase 1 (Brute-Force) abgeschlossen.")


def fast_migrate_content_and_titles():
    # Fällt Werke mit Daten aus den verknüpften Büchern (Beschreibung, Sterne, Ratings etc.)
    #SQL-Anfragen sind teuer: Jedes execute() ist wie ein kleiner Postbote, der losläuft.
    # - Ermittelt die Hauptsprache des Autors (Anzahl Bücher).
    # - Befüllt title_de bis title_es in 'works' aus den 'books'-Daten.
    # - Setzt den Master-'title' und generiert den 'slug' via slugify.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print("\n🚀 Phase 2: Datentypen fixen & Werk-Inhalte konsolidieren...")

    # SCHRITT 0: Der Staubsauger (Datentyp-Cleanup)
    # Wir zwingen SQLite, alle Sterne und IDs als echte Zahlen zu speichern
    # Nur zur Sicherheit einmalig die IDs glattziehen (optional)
    cursor.execute("UPDATE books SET stars = CAST(stars AS INTEGER) WHERE stars IS NOT NULL")
    cursor.execute("UPDATE books SET work_id = CAST(work_id AS INTEGER) WHERE work_id > 0")
    conn.commit()

    # Ein einziger Zugriff auf die DB
    cursor.execute("SELECT work_id, stars, description FROM books WHERE work_id > 0")
    all_books = cursor.fetchall()  # Alles in den RAM

    # Gruppieren im RAM (Blitzschnell)
    works_map = defaultdict(list)
    for b in all_books:
        works_map[b['work_id']].append(b)
    work_updates = []

    # Berechnung im RAM
    for w_id, books in tqdm(works_map.items(), desc="Konsolidierung", unit="Werk"):
        best_stars = None
        best_desc = ""
        for b in books:
            # 1. Wert sicher holen (to_int haben wir ja definiert)
            s = to_int(b['stars'])
            # 2. Logischer Vergleich mit None-Check
            if s is not None:
                if best_stars is None or s > best_stars:
                    best_stars = s

            d = b['description'] or ""
            if len(d) > len(best_desc):
                best_desc = d
        work_updates.append((best_stars, best_desc, w_id))

    # SCHRITT 3: Alles zurückschreiben
    if work_updates:
        print(f"\n💾 Speichere Ergebnisse für {len(work_updates)} Werke...")
        conn.execute("BEGIN")
        cursor.executemany("UPDATE works SET stars = ?, description = ? WHERE id = ?", work_updates)
        conn.commit()

    conn.close()
    print("✅ Phase 2 abgeschlossen. Die Datenbank ist jetzt typ-rein und konsolidiert.")



def process_series():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Zähler initialisieren
    count_series_books = 0
    count_single_books = 0

    # 2. Bekannte Kürzel-Mappings (Erweiterbar)
    mapping = {
        "hp": "Harry Potter",
        "pjo": "Percy Jackson",
        "lotr": "Lord of the Rings"
    }

    # 3. Alle Bücher mit Serien-Hinweisen abrufen
    # Wir holen auch den Nachnamen des Autors für den Fallback (01-)
    query = """
        SELECT b.work_id, b.series_name, b.series_number,b.path, b.language, a.lastname 
        FROM books b
        JOIN works w ON b.work_id = w.id
        JOIN work_to_author wta ON w.id = wta.work_id
        JOIN authors a ON wta.author_id = a.id
    """
    cursor.execute(query)
    books = cursor.fetchall()

    series_cache = {}  # normalized_name -> series_id

    for wid, s_name, s_num, path, lan, a_name in books:
        raw_name = s_name.strip() if s_name else ""

        # Fallback-Logik: 'name01-' oder '01-'
        if not raw_name and re.search(r'(\d{1,3}-| - \d{1,3} -)', path):
            raw_name = a_name if a_name else "Unbekannte Serie"
        # Wenn kein Serienname und keine Seriennummer (auch nicht im Dateinamen, dann keine Serie!
        if not raw_name:
            count_single_books += 1
            continue

        count_series_books += 1
        # Normalisierung & Mapping (z.B. HP -> Harry Potter)
        norm_key = raw_name.lower()
        master_name = mapping.get(norm_key, raw_name)
        lookup_key = master_name.lower()

        if lookup_key not in series_cache:
            # Prüfen, ob Serie bereits in DB (via Slug)
            s_slug = slugify(master_name)
            cursor.execute("SELECT id FROM series WHERE slug = ?", (s_slug,))
            row = cursor.fetchone()

            if row:
                s_id = row[0]
            else:
                # Neue Serie anlegen
                cursor.execute("INSERT INTO series (name, slug) VALUES (?, ?)", (master_name, s_slug))
                s_id = cursor.lastrowid

            series_cache[lookup_key] = s_id
        s_id = series_cache[lookup_key]

        # 4. Sprachspezifischen Namen aktualisieren
        # Wir ordnen den gefundenen Namen dem entsprechenden Sprachfeld zu
        if lan and lan.lower() in ['de', 'en', 'fr', 'it', 'es']:
            col_name = f"name_{lan.lower()}"
            cursor.execute(f"UPDATE series SET {col_name} = ? WHERE id = ? AND {col_name} IS NULL", (raw_name, s_id))

        # 5. Buch verknüpfen
        try:
            # Extrahiere nur die Zahl, falls Schrott im String steht
            clean_num = re.findall(r"[-+]?\d*\.\d+|\d+", str(s_num))
            s_index = float(clean_num[0]) if clean_num else None
        except (ValueError, IndexError):
            s_index = None

        cursor.execute("""
                    UPDATE works 
                    SET series_id = ?, series_index = ? 
                    WHERE id = ?
                """, (s_id, s_index, wid))

    conn.commit()
    print("Migration der Serien zu den Works abgeschlossen.")
    print("-" * 30)
    print(f"Migration abgeschlossen:")
    print(f"Bücher in Serien:  {count_series_books}")
    print(f"Einzelbände:       {count_single_books}")
    print(f"Serien-Objekte:    {len(series_cache)}")
    print("-" * 30)





# ----------------------------------------------------------------------
# Langsame Migrationslogik pro Buch.
# Hier verwenden wir die bewährte Logik von BookData.
# SQL Zugriffe sind langsam, weil immer die Festplatte bestätigen muss
# ----------------------------------------------------------------------

def slow_logic_repair_detachment():
    """
    Stufe 1: Stellt sicher, dass jedes Buch die richtige work_id hat.
    Trennt Bücher von Werken, wenn die Autoren nicht übereinstimmen.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n🛠️ Phase 1: Logische Werk-Trennung...")

    # 1. Alle Bücher laden
    cursor.execute("SELECT id, path, work_id, title FROM books")
    books = cursor.fetchall()

    # tqdm Fortschrittsbalken für die langsame Phase 1
    pbar = tqdm(books, desc="Analysiere Bücher", unit="Buch")

    detached_count = 0
    new_works_count = 0

    for b_id, b_path, b_wid, b_title in pbar:
        # Kurze Info im Balken anzeigen (optional)
        pbar.set_postfix({"file": b_title[:20]}, refresh=False)

        # Manager lädt Autoren aus dem Pfad (unser Soll-Zustand)
        manager = BookData.load_by_path(b_path)
        if not manager: continue

        path_authors = set(manager.authors)

        if b_wid > 0:
            # Prüfen gegen Ist-Zustand in der DB
            cursor.execute("""
                SELECT a.firstname, a.lastname FROM authors a
                JOIN work_to_author wa ON a.id = wa.author_id
                WHERE wa.work_id = ?
            """, (b_wid,))
            db_authors = set(cursor.fetchall())

            if path_authors != db_authors and len(db_authors) > 0:
                # Mismatch! Detach Buch vom Werk
                cursor.execute("UPDATE books SET work_id = 0 WHERE id = ?", (b_id,))
                b_wid = 0
                detached_count += 1

        # 2. Wenn Buch kein Werk hat -> Neues erstellen
        if b_wid == 0:
            manager.work.id = 0
            manager.save()
            new_works_count += 1

    conn.commit()
    conn.close()
    print(f"\n✅ Phase 1 Logic Repair beendet: {detached_count} Trennungen, {new_works_count} neue Werke.")


def refine_titles_langsam():
    # Dauert ca. 90 min
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"[{os.path.basename(__file__)}] Analysiere Hauptsprachen der Autoren...")

    # 1. Hauptsprache pro Autor bestimmen (nach Anzahl der Bücher)
    # Beispiel: J.K. Rowling + "en" -> 40 Bücher; J.K. Rowling + "de" -> 7 Bücher.
    cursor.execute("""
        SELECT a.id, b.language, COUNT(b.id) as cnt
        FROM authors a
        JOIN work_to_author wta ON a.id = wta.author_id
        JOIN books b ON wta.work_id = b.work_id
        WHERE b.language IS NOT NULL AND b.language != ''
        GROUP BY a.id, b.language
        ORDER BY a.id, cnt DESC
    """)

    # cursor.fetchall() führt erst alles aus und läd das in den Speicher. Dauert lange.
    # for row in cursor   - würde den cursor als Iterator benutzen.
    author_languages = {}
    for row in cursor.fetchall():
        a_id, lan, _ = row
        if a_id not in author_languages:
            # Wir nehmen die ersten zwei Buchstaben (de, en, fr, it, es)
            author_languages[a_id] = lan.lower()[:2]

    # 2. Alle Werke laden, die wir bearbeiten müssen
    cursor.execute("SELECT id FROM works")
    work_ids = [r[0] for r in cursor.fetchall()]

    print(f"Verarbeite {len(work_ids)} Werke...")

    for w_id in work_ids:
        # Alle Buchtitel und Sprachen zu diesem Werk sammeln
        cursor.execute("SELECT title, language FROM books WHERE work_id = ?", (w_id,))
        books_for_work = cursor.fetchall()

        # Mapping der Sprachen auf die DB-Spalten
        titles_by_lan = {'de': None, 'en': None, 'fr': None, 'it': None, 'es': None}

        for b_title, b_lan in books_for_work:
            if b_lan and b_title:
                l_code = b_lan.lower()[:2]
                if l_code in titles_by_lan and not titles_by_lan[l_code]:
                    titles_by_lan[l_code] = b_title

        # Hauptautor finden, um die Master-Sprache zu bestimmen
        cursor.execute("SELECT author_id FROM work_to_author WHERE work_id = ? LIMIT 1", (w_id,))
        auth_row = cursor.fetchone()

        master_title = None
        if auth_row:
            a_id = auth_row[0]
            main_lang = author_languages.get(a_id, 'de')  # Default de
            master_title = author_languages.get(main_lang)

        # Fallback: Falls in der Hauptsprache kein Titel existiert, nimm den ersten verfügbaren
        if not master_title:
            for t in titles_by_lan.values():
                if t:
                    master_title = t
                    break

        # Falls wir gar keinen Titel finden (unwahrscheinlich), nehmen wir einen Platzhalter
        if not master_title:
            continue

        work_slug = slugify(master_title)

        cursor.execute("""
            UPDATE works SET 
                title = ?,
                title_de = ?,
                title_en = ?,
                title_fr = ?,
                title_it = ?,
                title_es = ?,
                slug = ?
            WHERE id = ?
        """, (
            master_title,
            titles_by_lan['de'], titles_by_lan['en'],
            titles_by_lan['fr'], titles_by_lan['it'],
            titles_by_lan['es'],
            work_slug,
            w_id
        ))

    conn.commit()
    print("✅ Titel-Refining und Slugs abgeschlossen.")
    conn.close()



# ----------------------------------------------------------------------
# Testen der Migrationslogik mit J.K. Rowling.
# Hier verwenden wir die bewährte Logik von BookData.
# SQL Zugriffe sind langsam, weil immer die Festplatte bestätigen muss
# ----------------------------------------------------------------------

def migrate_rowling_to_1_4_0():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Serie anlegen (Blau)
    cursor.execute("""
        INSERT OR IGNORE INTO series (series_name, series_name_de, series_name_en, series_slug)
        VALUES ('Harry Potter', 'Harry Potter', 'Harry Potter', 'harry-potter')
    """)
    series_id = cursor.execute("SELECT id FROM series WHERE series_name = 'Harry Potter'").fetchone()[0]

    # 2. Liste der HP-Bände für die Werk-Erstellung (Grün)
    hp_volumes = [
        (1, "Harry Potter und der Stein der Weisen", "Harry Potter and the Philosopher's Stone"),
        (2, "Harry Potter und die Kammer des Schreckens", "Harry Potter and the Chamber of Secrets"),
        (3, "Harry Potter und der Gefangene von Askaban", "Harry Potter and the Prisoner of Azkaban"),
        (4, "Harry Potter und der Feuerkelch", "Harry Potter and the Goblet of Fire"),
        (5, "Harry Potter und der Orden des Phönix", "Harry Potter and the Order of the Phoenix"),
        (6, "Harry Potter und der Halbblutprinz", "Harry Potter and the Half-Blood Prince"),
        (7, "Harry Potter und die Heiligtümer des Todes", "Harry Potter and the Deathly Hallows")
    ]

    for index, title_de, title_en in hp_volumes:
        # Werk anlegen
        cursor.execute("""
            INSERT OR IGNORE INTO works (master_title, title_de, title_en, series_id, series_index, genre_fixed)
            VALUES (?, ?, ?, ?, ?, 'Fantasy')
        """, (title_de, title_de, title_en, series_id, index))

        work_id = cursor.lastrowid or cursor.execute("SELECT id FROM works WHERE title_de = ?", (title_de,)).fetchone()[
            0]

        # 3. Bestehende Bücher verknüpfen (Gelb -> Grün Link)
        # Wir suchen nach Titeln, die den deutschen oder englischen Namen enthalten
        cursor.execute("""
            UPDATE books 
            SET work_id = ? 
            WHERE (title LIKE ? OR title LIKE ?) 
            AND (series_name LIKE '%Harry Potter%' OR title LIKE '%Harry Potter%')
        """, (work_id, f"%{title_de}%", f"%{title_en}%"))

    conn.commit()
    print("✅ Rowling-Migration auf 1.4.0 abgeschlossen (Series & Works verknüpft).")
    conn.close()


if __name__ == "__main__":
    # Erst die Logik geradeziehen (langsameres Zeilen-Processing)
    fast_logic_repair_detachment()
    # Dann die Daten aggregieren (schnelles RAM-Processing)
    fast_migrate_content_and_titles()

