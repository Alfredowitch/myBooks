import sqlite3


def save_audiobook_db(book, db_path='M://audiobooks.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Schritt 0: Sicherstellen, dass alle neuen Attribute in der Datenbank existieren
    cursor.execute("PRAGMA table_info(audiobooks);")
    valid_authors_columns = ['author_id', 'firstname', 'lastname']
    existing_columns = [column[1] for column in cursor.fetchall()]
    columns = []
    values = []
    params = []
    # Für alle Keys in book prüfen, ob sie in der Tabelle existieren
    for key, value in book.items():
        if value is not None:
            if key not in valid_authors_columns:
                columns.append(key)
                values.append("?")
                params.append(value)
                if key not in existing_columns:
                    cursor.execute(f"ALTER TABLE audiobooks ADD COLUMN {key} TEXT")
                    conn.commit()
    print(existing_columns)
    print(columns)
    print(params)
    print(values)
    # Schritt 1: Prüfen, ob der Autor existiert
    cursor.execute("""
        SELECT id FROM authors WHERE firstname = ? AND lastname = ?""",
        (book.get('firstname'), book.get('lastname')))
    res = cursor.fetchone()
    # Wenn ein Autor gefunden wird, ist es das erste Element des Tupels. Wenn nicht ist res = None.
    if not res:
        cursor.execute("""
        INSERT INTO authors (firstname, lastname) VALUES (?, ?)""",
        (book.get('firstname'), book.get('lastname')))
        conn.commit()
        author_id = cursor.lastrowid
        author_id = res[0]
        # Da der Autor neu ist, müssen wir auch das Hörbuch anlegen
        sql = f'''
        INSERT INTO audiobooks ({", ".join(columns)})
        VALUES ({", ".join(values)})
        '''
        cursor.execute(sql, params)
        conn.commit()

    else:
        # Fall 2: Autor ist bekannt
        author_id = res[0]
        # Jetzt prüfen, ob das Hörbuch des bekannten Autors existiert
        sql = 'SELECT id FROM audiobooks WHERE author_id = ? AND title = ?'
        cursor.execute(sql, (author_id, book['title']))
        book_row = cursor.fetchone()

        if not book_row:
            # Fall 2: Hörbuch nicht bekannt, neues Hörbuch anlegen
            sql = f'''
            INSERT INTO audiobooks ({", ".join(columns)})
            VALUES ({", ".join(values)})
            '''
            cursor.execute(sql, params)
            conn.commit()

        else:
            # Fall 3: Autor und Hörbuch sind bekannt, update des Hörbuchs
            print(book_row[0])
            set_clause = ', '.join([f"{col} = ?" for col in columns])
            sql = f'UPDATE audiobooks SET {set_clause} WHERE id = ?'
            print(sql)
            cursor.execute(sql, (*params, book_row[0]))
            # Hier wird die Params Liste automatisch entpackt.
            # Alternativ könnte man auch bock_row zur Liste hinzufügen:
            # cursor.execute(sql, params + [book_row[0]])
            # oder:
            # cursor.execute(sql, params.append(book_row[0])
            # letzteres verändert jedoch die Params Liste!
            # Das SQL kann auch direkt im Aufruf gebaut werden...
            """
            set_clause = ', '.join([f"{col} = ?" for col in columns])
            cursor.execute(f'''UPDATE audiobooks
                               SET {set_clause}
                               WHERE id = ?''',
                           (*params, book_row[0]))
            """
            conn.commit()

    conn.close()

if __name__ == "__main__":
    # Beispielaufruf
    book = {
        'firstname': 'Max',
        'lastname':  'Mustermann',
        'title': 'Das neue Hörbuch',
        'description': 'Eine spannende Geschichte',
        'url': 'http://example.com',
        'official_rating': 4.5,
        'rating': 4.2,
        'genre': 'Thriller',
        'new_attribute': 'Zusätzliche Info'  # Ein neu hinzugefügtes Attribut
    }

    save_audiobook_db(book)




