"""
DATEI: create_works.py
VERSION: 1.3.0
BESCHREIBUNG: Erstellt eine von physikalischen Büchern unabhängige Liste von Werken

"""
import sqlite3
from Gemini.file_utils import DB_PATH

def build_works_from_books():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Index für Speed
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_works_title ON works(master_title)")

    # 1. Alle Bücher holen, die noch nicht zugeordnet sind
    cursor.execute("SELECT id, title FROM books WHERE work_id IS NULL or work_id = 0")
    unmapped_books = cursor.fetchall()
    print(f"Gefundene Bücher ohne gültiges Werk: {len(unmapped_books)}")

    for book_id, title in unmapped_books:
        # Den Titel normalisieren für den Vergleich
        master_title = title.strip()
        # 2. Prüfen, ob das Werk schon existiert
        cursor.execute("SELECT id FROM works WHERE master_title = ?", (master_title,))
        work_res = cursor.fetchone()  # Tupel als Result
        if work_res:
            work_id = work_res[0]     # work_res is (42,) Tupel -> jetzt holen wir uns die 42
        else:
            # 3. Neues Werk anlegen
            cursor.execute("""
                INSERT INTO works (master_title, mapping_source) 
                VALUES (?, 'AUTO_SCAN')
            """, (master_title,))
            work_id = cursor.lastrowid

        # 4. Buch mit dem Werk verknüpfen
        cursor.execute("UPDATE books SET work_id = ? WHERE id = ?", (work_id, book_id))

    conn.commit()
    conn.close()
    print("Werk-Mapping abgeschlossen.")


def migrate_with_check():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. PRÜFUNG: Gibt es Bücher ohne Werk?
    cursor.execute("SELECT COUNT(*) FROM books WHERE work_id IS NULL OR work_id = 0")
    missing_count = cursor.fetchone()[0]

    if missing_count > 0:
        print(f"⚠️ STOPP: Es gibt noch {missing_count} Bücher ohne Werk-Zuordnung!")
        print("Bitte lass erst das Mapping-Skript (build_works_from_books) laufen.")
        conn.close()
        return

    print(f"✅ Alle {98155} Bücher haben ein Werk. Starte Migration...")

    # 2. MIGRATION: Verknüpfungen erstellen
    # Buch -> Werk
    cursor.execute("""
        INSERT OR IGNORE INTO work_to_book (work_id, book_id)
        SELECT work_id, id FROM books
        WHERE work_id IS NOT NULL AND work_id > 0
    """)
    print(f"-> {cursor.rowcount} Links in work_to_book erstellt.")

    # Autor -> Werk (über das Buch geholt)
    # work_id und author_id bekommen wir aus ba verknüpft mit b.
    # in ba steht die author_id (= ba.author_id) und in b steht die work_id (= b.work_id)
    cursor.execute("""
        INSERT OR IGNORE INTO work_author (work_id, author_id)
        SELECT b.work_id, ba.author_id 
        FROM book_authors ba
        JOIN books b ON ba.book_id = b.id
    """)

    conn.commit()
    conn.close()
    print("✅ Migration erfolgreich abgeschlossen.")


def print_report():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Anzahl der Verknüpfungen (Autor <-> Buch)
    cursor.execute("SELECT COUNT(*) FROM book_authors")
    links_neu = cursor.fetchone()[0]
    # 2. Anzahl der tatsächlichen Bucheinträge
    cursor.execute("SELECT COUNT(*) FROM books")
    books_neu = cursor.fetchone()[0]
    # 3. Anzahl der Autoren
    cursor.execute("SELECT COUNT(*) FROM authors")
    authors_count = cursor.fetchone()[0]
    # 4. NEU: Anzahl der Werke (Works)
    cursor.execute("SELECT COUNT(*) FROM works")
    works_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM work_author")
    wa_neu = cursor.fetchone()[0]  # Das ist die Anzahl Autor-Werk

    cursor.execute("SELECT COUNT(*) FROM work_to_book")
    wb_neu = cursor.fetchone()[0]  # Das ist die Anzahl Buch-Werk

    # 5. NEU: Wie viele Bücher haben noch KEIN Werk? (Sollte nach dem Run 0 sein)
    cursor.execute("SELECT COUNT(*) FROM books WHERE work_id IS NULL")
    unmapped_books = cursor.fetchone()[0]

    print("-" * 40)
    print(f"{'STATISTIK':^40}")
    print("-" * 40)
    print(f"Bücher in 'books':         {books_neu:>15,}")
    print(f"Werke in 'works':          {works_count:>15,}")
    print(f"Autoren in 'authors':      {authors_count:>15,}")
    print(f"Links (Buch-Autor):        {links_neu:>15,}")
    print(f"Links (Werk-Autor):        {wa_neu:>15,}")
    print(f"Links (Werk-Buch):         {wb_neu:>15,}")
    print("-" * 40)

    if works_count > 0:
        ratio = books_neu / works_count
        print(f"Ø Bücher pro Werk:         {ratio:>15.2f}")

    if unmapped_books > 0:
        print(f"⚠️ Unzugeordnete Bücher:    {unmapped_books:>15,}")
    else:
        print("✅ Alle Bücher sind einem Werk zugeordnet.")
    print("-" * 40)

    # 1. Was steht in der works Tabelle?
    cursor.execute("SELECT COUNT(*) FROM works")
    print(f"Echte Anzahl in works: {cursor.fetchone()[0]}")

    # 2. Gibt es Bücher, die eine work_id ungleich NULL haben?
    cursor.execute("SELECT COUNT(*) FROM books WHERE work_id IS NOT NULL")
    print(f"Bücher mit work_id: {cursor.fetchone()[0]}")
    conn.close()


def diagnose_bridge():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- DIAGNOSE ---")
    # 1. Haben wir Einträge in work_author?
    cursor.execute("SELECT count(*), work_id FROM work_author LIMIT 1")
    res = cursor.fetchone()
    print(f"Eintrag in work_author: {res}")

    # 2. Finden wir zu dieser work_id ein Buch?
    if res and res[1]:
        test_id = res[1]
        cursor.execute("SELECT count(*) FROM work_to_book WHERE work_id = ?", (test_id,))
        book_links = cursor.fetchone()[0]
        print(f"Bücher-Links für work_id {test_id}: {book_links}")

        cursor.execute("SELECT language FROM books b JOIN work_to_book wtb ON b.id = wtb.book_id WHERE wtb.work_id = ?",
                       (test_id,))
        langs = cursor.fetchall()
        print(f"Sprachen für dieses Werk: {[l[0] for l in langs]}")

    conn.close()




if __name__ == "__main__":
    # build_works_from_books()
    # migrate_with_check()
    print_report()
    diagnose_bridge()