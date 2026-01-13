import sqlite3
import os
from Gemini.file_utils import DB_PATH, DB2_PATH
from authors import Author, AuthorManager

# Pfade aus deinem Helper
OLD_DB_PATH = DB_PATH  # books.db
NEW_DB_PATH = DB2_PATH  # audiobooks.db


def get_language_stats(old_conn):
    """Ermittelt pro Autor die Anzahl der Bücher pro Sprache."""
    stats = {}
    cursor = old_conn.cursor()

    # SQL-Abfrage über die Verknüpfungstabelle
    query = """
        SELECT ba.author_id, b.language, COUNT(*) as count
        FROM book_authors ba
        JOIN books b ON ba.book_id = b.id
        WHERE b.language IS NOT NULL AND b.language != ''
        GROUP BY ba.author_id, b.language
    """
    cursor.execute(query)

    for row in cursor.fetchall():
        aid = row['author_id']
        lang = row['language'].lower()[:2]  # Nur die ersten 2 Zeichen (de, en, fr...)
        cnt = row['count']

        if aid not in stats:
            stats[aid] = {}
        stats[aid][lang] = cnt
    return stats


def determine_main_lang(author_stats):
    """Wählt die Sprache mit den meisten Einträgen."""
    if not author_stats:
        return "de"  # Fallback
    # Sortiert das Dict nach Werten absteigend und nimmt den ersten Key
    return max(author_stats, key=author_stats.get)


def migrate():
    manager = AuthorManager()

    if not os.path.exists(OLD_DB_PATH):
        print(f"❌ Alte Datenbank nicht gefunden: {OLD_DB_PATH}")
        return

    old_conn = sqlite3.connect(OLD_DB_PATH)
    old_conn.row_factory = sqlite3.Row

    try:
        # 1. Sprach-Statistiken laden
        print("Analysiere Sprachen in der alten Datenbank...")
        all_stats = get_language_stats(old_conn)

        # 2. Autoren laden
        cursor = old_conn.cursor()
        cursor.execute("SELECT id, firstname, lastname FROM authors")
        old_authors = cursor.fetchall()

        print(f"Starte Migration von {len(old_authors)} Autoren...\n")
        print(f"{'Name':<30} | {'Stats':<20} | {'Main'}")
        print("-" * 65)

        for row in old_authors:
            aid = row['id']
            # --- NEU: SICHERUNG / FILTER ---
            # Wenn der Autor keine Einträge in den Stats hat, hat er keine Bücher.
            if aid not in all_stats:
                # Optional: print(f"⏩ Überspringe {row['firstname']} {row['lastname']} (Keine Bücher)")
                continue
            # -------------------------------
            f_name = (row['firstname'] or "").strip()
            l_name = (row['lastname'] or "").strip()
            full_name = f"{f_name} {l_name}".strip() or "Unbekannt"

            # Heuristik anwenden
            stats = all_stats.get(aid, {})
            main_lang = determine_main_lang(stats)

            # Formatierte Ausgabe für dich zur Kontrolle
            stats_str = ", ".join([f"{k}:{v}" for k, v in stats.items()])
            print(f"{full_name:<30} | {stats_str:<20} | {main_lang}")

            # In neue DB schreiben (mit ID-Erhaltung)
            new_author = Author(
                id=aid,
                display_name=full_name,
                main_language=main_lang,  # Hier speichern wir deine 'main_language'
                stars= 1
            )

            try:
                manager.add_author(new_author)
            except sqlite3.IntegrityError:
                # Hier landet er, wenn der Slug (Ali Hazelwood) schon existiert
                print(f"   ⚠️ Überspringe Duplikat: {full_name} (Slug bereits vorhanden)")
            except Exception as e:
                print(f"   ❌ Unerwarteter Fehler bei {full_name}: {e}")

        print("\n✅ Migration erfolgreich abgeschlossen.")

    except sqlite3.Error as e:
        print(f"❌ Fehler: {e}")
    finally:
        old_conn.close()


if __name__ == "__main__":
    migrate()

