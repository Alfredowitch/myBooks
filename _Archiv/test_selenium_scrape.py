from get_db_audiobooks import get_audiobooks
from save_db_audiobook import save_audiobook_db
from audible_scrap import scrap_audible
from editor_text import edit_book

# Beispielaufruf
"""
title = "Blausäure"
author = "Agatha Christie"
firstname, lastname = split_name(author)
book_info = {
    'title': title,
    'author': author,
    'firstname': first_name,
    'lastname': last_name,
}
details = scrape_audible(title, author)
book_info.update(details)
"""
books = get_audiobooks(5,0)
for book in books:
    # Das <class 'sqlite3.Row'> Objekt wurde in ein Dictionary umgewandelt
    print(book["title"])
    # print(book.get("firstname"))
    res = None
    # res = scrap_audible(book)
    if res is not None:
        #print(f"Die initiale Beschreibung lautet: {res['description']}")
        print(f"Die initiale Beschreibung lautet: {res.get('description', book.get('description', '-'))}")
        print(f"Amazon Bewertung: {res.get('original_rating')}")
        change = edit_book(res)
        print(f"Die bearbeitete Beschreibung lautet: {res['description']}")
        print(f"Deine Bewertung: {res.get('rating')}")
    else:
        change = edit_book(book)
        print(f"Die bearbeitete Beschreibung lautet: {book['description']}")
        print(f"Deine Bewertung: {book.get('rating')}")

    save_audiobook_db(change)

