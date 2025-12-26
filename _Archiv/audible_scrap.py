from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import time
from dotenv import load_dotenv
import os

# Variablen, zu Beginn der Programmlaufzeit iniizieren.
# Findet nur einmal statt, daher außerhalb des Programmaufrufs.
driver = None  # Flag, um zu prüfen, ob ein Browserfenster offen ist (Objekt, daher none)
logged_in = False  # Flag, um zu prüfen, ob wir eingeloggt sind (Zustand/Wert, daher false)


def scrap_audible(book_info):
    """
    Scraps Audible for Description and Rating on audiobooks.
    We first login, then search with keywords for the audiobook, then search for description.
    We give a dictionary with multiple information, like ("titel", "firstname", "lastname", "description")
    We return the same dictionary, but with revised potentially new values.
    """
    # Globale Variable, die wiederverwendet wird bei wiederholtem Funktionsaufruf
    global driver, logged_in
    if driver is None:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Falls du den Browser sichtbar haben willst, entferne diese Zeile
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # Login to Amazon Account
    # Anmerkung:
    # if not driver: prüft, ob driver ein falsy-Wert ist (also None, False, 0, "", [], {}, set(), usw.).
    if not logged_in:
        driver.get("https://www.audible.de/")
        # Lade die Variablen aus der .env-Datei
        load_dotenv()
        email = os.getenv("AUDIBLE_EMAIL")
        password = os.getenv("AUDIBLE_PASSWORD")

        login_button = driver.find_element(By.LINK_TEXT, "Anmelden")
        login_button.click()
        time.sleep(2)  # Wartezeit für das Laden der Login-Seite

        email_input = driver.find_element(By.ID, "ap_email")
        email_input.send_keys(email)  # Ersetze mit deiner Audible-E-Mail
        email_input.send_keys(Keys.RETURN)
        time.sleep(2)

        password_input = driver.find_element(By.ID, "ap_password")
        password_input.send_keys(password)  # Ersetze mit deinem Audible-Passwort
        password_input.send_keys(Keys.RETURN)
        time.sleep(5)  # Wartezeit für vollständiges Login
        logged_in = True
        print("Logged in - success")

    # Search Keywords
    print(book_info)
    title = book_info['title']
    author = f"{book_info['firstname']} {book_info['lastname']}"
    #print(author)
    # author = " ".join([book_info.get('firstname', ''), book_info.get('lastname', '')]) # Alternativ
    search_url = f"https://www.audible.de/search?keywords={title} + {author}"
    print(f'SearchURL = {search_url}')
    time.sleep(5)  # Wartezeit für das Laden der Seite
    #driver.get("https://www.wikipedia.org/")
    time.sleep(5)  # 5 Sekunden warten
    try:
        driver.set_page_load_timeout(10)  # Maximal 10 Sekunden warten
        driver.get(search_url)
    except TimeoutException:
        print(f"Timeout bei {search_url}")
        return None

    print("Zielseite wurde geöffnet")
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    result = soup.select_one("a[href*='/pd/']")  # Verbesserter Selektor für Hörbuch-Links
    if result and 'href' in result.attrs:
        book_url = "https://www.audible.de" + result["href"]
    else:
        print(f"Keine Ergebnisse für {title} - {author}")
        driver.quit()
        return
    print(f'Search Result: {book_url}')
    #print(type(book_info))
    #book_info.update({'url': book_url})
    book_info['url'] = book_url

    # Extract Description
    driver.get(book_url)
    time.sleep(2)  # Wartezeit für das Laden der Seite
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Sprachniveau extrahieren
    language_level_tag = soup.find(string=lambda text: text and "Niveau" in text)
    if language_level_tag:
        book_info["genre"] = language_level_tag.strip()

    # Beschreibung extrahieren
    description_tag = soup.select_one("adbl-text-block[slot='summary']")
    if description_tag:
        book_info["description"] = " ".join(description_tag.stripped_strings)

    # Rating extrahieren
    rating_tag = soup.select_one(".averageRating")
    if rating_tag:
        book_info["official_rating"] = rating_tag.get_text(strip=True)

    driver.quit()
    return book_info


"""
    # Weitere mögliche Daten extrahieren
    publisher_tag = soup.find(string=lambda text: text and "Verlag" in text)
    if publisher_tag:
        details["Verlag"] = publisher_tag.strip()
    else:
        details["Verlag"] = "Nicht verfügbar"

    release_date_tag = soup.find(string=lambda text: text and "Erscheinungsdatum" in text)
    if release_date_tag:
        details["Erscheinungsdatum"] = release_date_tag.strip()
    else:
        details["Erscheinungsdatum"] = "Nicht verfügbar"

    duration_tag = soup.find(string=lambda text: text and "Dauer" in text)
    if duration_tag:
        details["Dauer"] = duration_tag.strip()
    else:
        details["Dauer"] = "Nicht verfügbar"
"""
def split_name(author_name):
    # Hier gehen wir davon aus, dass der Autor im Format "Vorname Nachname" kommt
    name_parts = author_name.split()
    if len(name_parts) > 1:
        firstname = name_parts[0]
        lastname = " ".join(name_parts[1:])
    else:
        firstname = name_parts[0]
        lastname = ''
    return firstname, lastname

if __name__ == "__main__":
    # Beispielaufruf
    print("Beispiel-Aufruf von Scrap Audible...")
    title = "Blausäure"
    author = "Agatha Christie"
    firstname, lastname = split_name(author)
    book_info = {
        'title': title,
        'firstname': firstname,
        'lastname': lastname,
    }
    res = scrap_audible(book_info)
    if res:
        print(f"Title: {res['title']}")
        print(f"First Name: {res['firstname']}")
        print(f"Last Name: {res['lastname']}")
        print(f"Description: {res['description']}")
        print(f"Sprachniveau: {res.get('sprachniveau')}")
        print(f"Amazon Rating: {res.get('original_rating')}")
        print(f"Series: {res.get('series')}")