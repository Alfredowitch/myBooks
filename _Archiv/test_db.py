# Beispiel für eine korrekte Pytest-Funktion:
import sqlite3
import pytest  # Du brauchst Pytest nicht importieren, aber es ist guter Stil

DB_PATH = r'M:\books.db'  # Passe den Pfad an, falls nötig


def test_db_connection():  # 🚨 Funktion muss mit 'test_' beginnen!
    """Prüft, ob die Datenbankdatei existiert und geöffnet werden kann."""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Überprüfe nur, ob die Verbindung hergestellt wird.
        conn.close()
        assert True  # Apps erfolgreich, wenn keine Exception geworfen wird
    except sqlite3.Error as e:
        # Apps fehlgeschlagen, wenn die DB nicht gefunden oder geöffnet werden kann
        pytest.fail(f"Konnte DB-Verbindung nicht herstellen: {e}")


# Wenn du deine Tabellen prüfen willst:
def test_check_required_tables():
    """Prüft, ob die notwendigen Tabellen existieren."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Prüfen, ob die 'books'-Tabelle existiert
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='books';")
    books_table = cursor.fetchone()

    conn.close()

    # Prüfe, ob das Ergebnis nicht None ist
    assert books_table is not None, "Die 'books'-Tabelle fehlt in der Datenbank."