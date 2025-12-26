import sqlite3

# Schritt 1: Verbindung zur SQLite-Datenbank herstellen
# Wenn die Datei 'books_metadata.db' nicht existiert, wird sie erstellt.
audiodb_path = 'M://audiobooks.db'
conn = sqlite3.connect(audiodb_path)
#bookdb_path = 'D://Bücher//books_metadata.db'
#conn = sqlite3.connect(bookdb_path)


# Schritt 2: Cursor-Objekt erstellen
cursor = conn.cursor()

# Schritt 3: Tabelle 'books' erstellen, falls sie nicht existiert
cursor.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_number TEXT,
    title TEXT,
    path TEXT,
    cover_image_url TEXT,
    description TEXT,
    genre TEXT,
    keys TEXT,
    language TEXT,
    year TEXT,
    rating TEXT,
    stars TEXT
)
''')

# Tabelle 'authors' erstellen
cursor.execute('''
CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    firstname TEXT,
    lastname TEXT
)
''')

# Verknüpfungstabelle 'book_authors' erstellen
cursor.execute('''
CREATE TABLE IF NOT EXISTS book_authors (
    book_id INTEGER,
    author_id INTEGER,
    FOREIGN KEY (book_id) REFERENCES books (id),
    FOREIGN KEY (author_id) REFERENCES authors (id)
)
''')

# Tabelle für 'audiobooks' erstellen
cursor.execute('''
CREATE TABLE IF NOT EXISTS audiobooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    series TEXT,
    year INTEGER,
    episode INTEGER,
    length REAL,  -- Länge in Minuten
    language TEXT DEFAULT 'Deutsch',
    description TEXT,  -- Kann später ergänzt werden
    genre TEXT,        -- Kann später ergänzt werden
    region TEXT,       -- Kann später ergänzt werden
    rating REAL,       -- Kann später ergänzt werden
    official_rating TEXT,  -- Kann später ergänzt werden
    cover_path TEXT,
    cover_blob BLOB,
    FOREIGN KEY (author_id) REFERENCES authors(id)
);
''')

# Schritt 4: Änderungen speichern
conn.commit()

# Schritt 5: Verbindung zur Datenbank schließen
conn.close()

print("Datenbank und Tabelle erfolgreich erstellt.")
