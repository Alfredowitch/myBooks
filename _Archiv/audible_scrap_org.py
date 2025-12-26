from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
from dotenv import load_dotenv
import os

# Globale Variablen, die für die gesamte Anwendung zugänglich sind
driver = None
logged_in = False


def setup_browser():
    global driver
    if driver is None:  # Wenn der Driver noch nicht gesetzt wurde, erstelle ihn
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Falls du den Browser sichtbar haben willst, entferne diese Zeile
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


def login_audible():
    global logged_in
    if not logged_in:  # Wenn noch nicht eingeloggt, führe den Login durch
        driver.get("https://www.audible.de/")
        time.sleep(2)
        login_button = driver.find_element(By.LINK_TEXT, "Anmelden")
        login_button.click()

        load_dotenv()
        email = os.getenv("AUDIBLE_EMAIL")
        password = os.getenv("AUDIBLE_PASSWORD")

        email_input = driver.find_element(By.ID, "ap_email")
        email_input.send_keys(email)  # Ersetze mit deiner Audible-E-Mail
        email_input.send_keys(Keys.RETURN)
        password_input = driver.find_element(By.ID, "ap_password")
        password_input.send_keys(password)  # Ersetze mit deinem Audible-Passwort
        password_input.send_keys(Keys.RETURN)

        time.sleep(3)  # Wartezeit für vollständiges Login
        logged_in = True
    else:
        print("Bereits eingeloggt.")


def search_audible(book_title, author):
    search_url = f"https://www.audible.de/search?keywords={book_title}+{author}"
    driver.get(search_url)

    time.sleep(3)  # Wartezeit für das Laden der Seite

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    result = soup.select_one("a[href*='/pd/']")  # Verbesserter Selektor für Hörbuch-Links

    if result and 'href' in result.attrs:
        return "https://www.audible.de" + result["href"]

    print(f"Keine Ergebnisse für {book_title} - {author}")
    return None


def extract_audible_details(book_url):
    driver.get(book_url)

    time.sleep(3)  # Wartezeit für das Laden der Seite

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    details = {}
    details["url"] = book_url

    # Beschreibung extrahieren
    description_tag = soup.select_one("adbl-text-block[slot='summary']")
    if description_tag:
        details["Beschreibung"] = " ".join(description_tag.stripped_strings)

    return details


# Die Hauptfunktion, die alle Schritte zusammenfasst
def scrape_audible(book_title, author):
    # Setup des Browsers und Login falls notwendig
    setup_browser()  # Browser wird nur einmal eingerichtet
    login_audible()  # Login wird nur einmal durchgeführt

    # Suchvorgang und URL finden
    book_url = search_audible(book_title, author)
    if book_url:
        time.sleep(random.uniform(1, 3))  # Zufällige Pause zur Vermeidung von Blockierungen
        details = extract_audible_details(book_url)
        return details

    return None

if __name__ == "__main__":
    # Beispielaufruf
    book_info = scrape_audible("Compagni di viaggio", "Alessandra Felici Puccetti")
    print(book_info)
