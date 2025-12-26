import sqlite3
import requests
from bs4 import BeautifulSoup
import json
import re
from get_db_audiobooks import fetch_audiobooks

def split_name(author_name):
    # Hier gehen wir davon aus, dass der Autor im Format "Vorname Nachname" kommt
    name_parts = author_name.split()
    if len(name_parts) > 1:
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])
    else:
        first_name = name_parts[0]
        last_name = ''
    return first_name, last_name

def search_audible_for_book(title, author):
    # URL zur Audible-Suche
    search_url = f"https://www.audible.de/search?keywords={title}+{author.replace(' ', '+')}&ref_=nma_search_srch"
    print(search_url)

    # HTTP-Anfrage an Audible
    response = requests.get(search_url)

    if response.status_code != 200:
        print(f"Fehler beim Abrufen der Seite: {response.status_code}")
        return None

    # BeautifulSoup, um HTML zu parsen
    soup = BeautifulSoup(response.text, 'html.parser')

    # Suche das erste Ergebnis der Bücher
    book_url_tag = soup.find('li', {'class': 'productListItem'})

    if book_url_tag:
        # Extrahiere den Link zur Produktseite
        book_url = "https://www.audible.de" + book_url_tag.find('a')['href']
        return book_url
    else:
        print("Kein Buch gefunden.")
        return None

def map_language_code_to_full(language_code):
    # Mappen von Sprachabkürzungen zu vollständigen Namen
    language_map = {
        'It': 'Italienisch',
        'Fr': 'Französisch',
        'Es': 'Spanisch',
        # Weitere Abkürzungen können hier hinzugefügt werden
    }
    return language_map.get(language_code, 'Unbekannt')  # Standardwert: 'Unbekannt'


def extract_sprachniveau(description):
    # Verwende einen regulären Ausdruck, um das Sprachniveau zu extrahieren
    match = re.search(r'\b(Italienisch|Spanisch|Französisch)\s*-\s*Niveau\s*[A-B][1-2]', description)
    if match:
        return match.group(0)  # Gibt den gefundenen Text zurück
    return 'Kein Sprachniveau gefunden'

def scrape_audible_book_info(book_url):
    response = requests.get(book_url)
    if response.status_code != 200:
        print(f"Fehler beim Abrufen der Seite: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Beschreibung extrahieren (Über diesen Titel)
    try:
        description_block = soup.find('adbl-text-block', {'slot': 'summary'})
        description = description_block.text.strip() if description_block else 'Keine Beschreibung vorhanden'
    except Exception as e:
        description = 'Keine Beschreibung vorhanden'

        # JSON-Daten im <script> Tag extrahieren (für Serie, Sprache, Dauer)
    try:
        description_block = soup.find('adbl-text-block', {'slot': 'summary'})
        description = description_block.text.strip() if description_block else 'Keine Beschreibung vorhanden'
    except Exception as e:
        description = 'Keine Beschreibung vorhanden'

    # Extrahiere das Sprachniveau aus der Beschreibung
    sprachniveau = extract_sprachniveau(description)

    # JSON-Daten im <script> Tag extrahieren (für Serie, Sprache, Dauer)
    try:
        json_data = soup.find('script', type='application/json').string
        product_data = json.loads(json_data)
        series = product_data.get('series', [{'name': 'Keine Serieninformation'}])[0]['name']
        duration = product_data.get('duration', 'Keine Dauer verfügbar')
        language = product_data.get('language', 'Keine Sprache verfügbar')
        release_date = product_data.get('releaseDate', 'Kein Veröffentlichungsdatum verfügbar')
    except Exception as e:
        series = 'Keine Serieninformation'
        duration = 'Keine Dauer verfügbar'
        language = 'Keine Sprache verfügbar'
        release_date = 'Kein Veröffentlichungsdatum verfügbar'

    first_name, last_name = split_name(author)
    book_info = {
        'title': title,
        'author': author,
        'first_name': first_name,
        'last_name': last_name,
        'description': description,
        'sprachniveau': sprachniveau,
        'series': series
    }

    return book_info

def save_to_db(book_info, db_path="audiobooks.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Beispiel-Query für das Einfügen der Buchinformationen
    cursor.execute('''INSERT INTO audiobooks (title, author, description, series)
                      VALUES (?, ?, ?, ?)''',
                   (book_info['title'], book_info['author'], book_info['description'], book_info['series']))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    #books = fetch_audiobooks(audiodb_path)
    #for book in books:
        #print(book)
        #print(f"Titel: {book[1]}, Autor: {book[2] + " " + book[3] if book[2] else 'Unbekannt'}, Language: {book[4]}")
    """
    Titel: Aperitivo Mortale, Autor: Alessandra Felici Puccetti, Language: IT
    Titel: Compagni di viaggio, Autor: Alessandra Felici Puccetti, Language: IT
    Titel: Sinfonia Siciliana, Autor: Alessandra Felici Puccetti, Language: IT
    
    Titel: Blausäure, Autor: Agatha Christie, Language: De
    Titel: Da waren es nur noch neun, Autor: Agatha Christie, Language: De
    Titel: 1920-Das Fehlende Glied In Der Kette, Autor: Agatha Christie, Language: De
    Titel: 1923-Der Mord auf dem Golfplatz, Autor: Agatha Christie, Language: De
    Titel: Hercule Poirot - Das Haus an der Düne, Autor: Agatha Christie, Language: De
    Titel: Akif Pirincci - Felidae 1, Autor: Akif Pirincci, Language: De
    Titel: Lacroix 01 - und die Toten vom Pont Neuf, Autor: Alex Lépic, Language: De
    Titel: Jan Tommen 04-Die Erinnerung so kalt, Autor: Alexander Hartung, Language: De
    Titel: 03-Winteraustern (Luc Verlain), Autor: Alexander Oetker, Language: De
    Titel: Monalbano06-Der Kavalier der späten Stunde, Autor: Andrea Camilleri, Language: De
    Titel: Code Genesis02-Sie werden dich jagen (2020), Autor: Andreas Gruber, Language: De
    
    Titel: Die Inselkommissarin 03-Die alte Dame am Meer, Autor: Anna Johannsen, Language: De
    Titel: Antonio Manzini - Rocco Schiavone 01 - Der Gefrierpunkt des Blutes, Autor: Antonio Manzini, Language: De
    Titel: Kommissar Erlendur07-Frostnacht, Autor: Arnaldur Indriðason, Language: De
    Titel: Arno Strobel -2020- Die APP, Autor: Arno Strobel, Language: De
    
    Titel: Flg. 10 - Die perfekte Welle, Autor: Unbekannt, Language: De
    Titel: Peter Grant 01 - Die Flüsse von London, Autor: Ben Aaronovitch, Language: De
    Titel: C. J. Lyons - Caitlyn Tierney 2 - Schweig still, mein totes Herz, Autor: C J Lyons, Language: De
    Titel: Bücher1-Der Schatten des Windes (2001), Autor: Carlos Ruiz Zafón, Language: De
    Titel: 02-Spanischer Totentanz, Autor: Catalina Ferrera, Language: De
    
    """
    # In unserem Beispiel haben wir die folgenden Werte:
    title = "Compagni di viaggio"
    author = "Alessandra Felici Puccetti"
    # Sprache aus der Abkürzung (z.B. 'It' für Italienisch)
    language = map_language_code_to_full("It")

    #search_url = f"https://www.audible.de/search?keywords={title}+{author.replace(' ', '+')}&ref_=nma_search_srch"
    #print(search_url)

    book_url = search_audible_for_book(title, author)

    if book_url:
        print(f"Gefundene URL: {book_url}")

    # Beispielaufruf mit den Testdaten
    book_info = scrape_audible_book_info(book_url)




    if book_info:
        print(f"Title: {book_info['title']}")
        print(f"Author: {book_info['author']}")
        print(f"First Name: {book_info['first_name']}")
        print(f"Last Name: {book_info['last_name']}")
        print(f"Description: {book_info['description']}")
        print(f"Sprachniveau: {book_info['sprachniveau']}")
        print(f"Series: {book_info['series']}")