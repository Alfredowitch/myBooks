import re
from typing import Tuple, Set, List, Optional

# Diese Liste definiert, was im "Genre"-Feld deines Browsers stehen darf.
GENRE_WHITELIST = {
    "Krimi", "Thriller", "Science Fiction", "Biographie",
    "Liebesroman", "Spionage", "Horror", "Fantasy", "Roman",
    "Fachbuch", "Sprache", "EasyReader", "Comic", "Sachbuch"
}
GENRE_MAPPING = {
    # ----------------------------------------------------
    # I. Fachbuch (Höchste Priorität für die spezifischen Kategorien)
    # ----------------------------------------------------
    "kommunikation": "Fachbuch (Business/Softskills)", "präsentation": "Fachbuch (Business/Softskills)",
    "wirtschaft": "Fachbuch (Business/Softskills)", "leadership": "Fachbuch (Business/Softskills)",
    "management": "Fachbuch (Business/Softskills)", "coaching": "Fachbuch (Business/Softskills)",
    "softskills": "Fachbuch (Business/Softskills)", "verhandeln": "Fachbuch (Business/Softskills)",
    "politik": "Fachbuch (Business/Softskills)", "interkulturell": "Fachbuch (Business/Softskills)",

    "physik": "Fachbuch (MINT/Wissenschaft)", "mathematik": "Fachbuch (MINT/Wissenschaft)",
    "chemie": "Fachbuch (MINT/Wissenschaft)", "philosophie": "Fachbuch (MINT/Wissenschaft)",
    "logik": "Fachbuch (MINT/Wissenschaft)",

    "digital": "Fachbuch (IT/Digital)", "agile": "Fachbuch (IT/Digital)", "office": "Fachbuch (IT/Digital)",
    "programmieren": "Fachbuch (IT/Digital)", "ai": "Fachbuch (IT/Digital)", "bigdata": "Fachbuch (IT/Digital)",
    "hacking": "Fachbuch (IT/Digital)",

    "erziehung": "Fachbuch (Soziales/Erziehung)", "psychologie": "Fachbuch (Soziales/Erziehung)",
    "religion": "Fachbuch (Soziales/Erziehung)",

    "kunst": "Fachbuch (Kreativ/Kultur)", "spiele": "Fachbuch (Kreativ/Kultur)",

    # ----------------------------------------------------
    # II. Roman & Sonstige (Mittlere Priorität, aufsteigend nach Spezifität)
    # ----------------------------------------------------

    # Krimi (Fokus: Ermittlung, Polizei)
    "krimi": "Krimi", "detektiv": "Krimi", "ermittlung": "Krimi", "polizeiroman": "Krimi",
    "crime": "Krimi", "detective": "Krimi", "police": "Krimi", "polar": "Krimi", "policier": "Krimi",
    "enquête": "Krimi", "crimen": "Krimi", "policía": "Krimi", "giallo": "Krimi", "poliziesco": "Krimi",
    "indagine": "Krimi",

    # Action (Fokus: Militär, Kampf, Waffen, Gewalt)
    "action": "Action (Militär/Kampf)", "spezialeinheit": "Action (Militär/Kampf)", "soldat": "Action (Militär/Kampf)",
    "munition": "Action (Militär/Kampf)", "schießerei": "Action (Militär/Kampf)", "folter": "Action (Militär/Kampf)",
    "blutige kämpfe": "Action (Militär/Kampf)", "paramilitär": "Action (Militär/Kampf)",
    "combat": "Action (Militär/Kampf)",
    "militär": "Action (Militär/Kampf)", "gun": "Action (Militär/Kampf)", "weapon": "Action (Militär/Kampf)",
    "guerra": "Action (Militär/Kampf)", "war": "Action (Militär/Kampf)", "kampf": "Action (Militär/Kampf)",

    # Thriller (Fokus: Psychologie, Verschwörung, Spannung)
    "psychothriller": "Thriller", "mord": "Thriller", "mörder": "Thriller", "mystery": "Thriller",
    "murder": "Thriller", "psychological thriller": "Thriller", "psychologique": "Thriller",
    "suspenso": "Thriller", "psicologico": "Thriller", "thriller": "Thriller", "suspense": "Thriller",
    "spannung": "Thriller",  # <<< Absichtlich am Ende des Blocks

    # Spionage
    "spionage": "Spionage", "agent": "Spionage", "geheimdienst": "Spionage", "geheim": "Spionage",
    "espionage": "Spionage", "spy": "Spionage", "intelligence": "Spionage", "secret agent": "Spionage",
    "espionnage": "Spionage", "renseignement": "Spionage", "espionaje": "Spionage", "agente": "Spionage",
    "spionaggio": "Spionage",

    # ... (Alle weiteren Roman- und Sachbuch-Keywords wie Western, Science Fiction, Biographie, etc. folgen hier in Blöcken) ...
    "science-fiction": "Science Fiction", "scifi": "Science Fiction", "zukunft": "Science Fiction",
    "roboter": "Science Fiction", "alien": "Science Fiction",  # ...
    "biografie": "Biographie", "memoiren": "Biographie",  # ...
    "liebe": "Liebesroman", "romantik": "Liebesroman",  # ...

    # ----------------------------------------------------
    # III. Fallback (Niedrigste Priorität)
    # ----------------------------------------------------
    "fachbuch": "Fachbuch (Allgemein)", "lehrbuch": "Fachbuch (Allgemein)", "wissen": "Fachbuch (Allgemein)",
    "non-fiction": "Fachbuch (Allgemein)", "textbook": "Fachbuch (Allgemein)",  # ...
}


def classify_book(keywords: Set[str], description: str) -> Tuple[str, Set[str]]:
    """
    Analysiert das keywords-Set und die Beschreibung.
    Gibt (Hauptgenre, zusätzliche_keywords) zurück.
    """
    final_main_genre = "Unbekannt"
    extracted_extra_keys = set()

    # 1. Suchtext vorbereiten (Alles lowercase)
    # Da keywords ein Set ist, machen wir einen String daraus für die Teilwortsuche
    kw_string = " ".join([str(k).lower() for k in keywords])
    desc_lower = description.lower() if description else ""

    combined_search = kw_string + " " + desc_lower

    # 2. Mapping durchlaufen (Rehenfolge = Priorität)
    for term, mapped_value in GENRE_MAPPING.items():
        if term in combined_search:

            # Extrahiere Core-Teil (z.B. "Fachbuch")
            core_genre = mapped_value.split('(')[0].strip()

            if core_genre in GENRE_WHITELIST:
                # Nur das erste gefundene Whitelist-Genre wird das Haupt-Genre
                if final_main_genre == "Unbekannt":
                    final_main_genre = core_genre

                # Wenn wir schon ein Hauptgenre haben, wird das neue zum Keyword
                elif final_main_genre != core_genre:
                    extracted_extra_keys.add(core_genre)

                # Klammerinhalte (z.B. IT/Digital) immer in die Keywords
                if '(' in mapped_value:
                    detail = mapped_value.split('(')[1].replace(')', '')
                    extracted_extra_keys.update([d.strip() for d in detail.split('/')])

            else:
                # Kein Whitelist-Genre (z.B. "Action") -> Alles in Keywords
                clean_val = mapped_value.replace('(', ' ').replace(')', '').replace('/', ' ')
                extracted_extra_keys.update([v.strip() for v in clean_val.split()])

    return final_main_genre, extracted_extra_keys

if __name__ == "__main__":
    print("--- Genre Mapping Tests ---")
    # Beispiel 1: Priorität auf Fachbuch
    genre_a = determine_single_genre(
        source_genres=["Fiction", "IT"],
        categories=["Business"],
        description="Ein neuer Ratgeber für effektives Management und Leadership."
    )
    # Erwartet: Fachbuch (Business/Softskills) – da "leadership" im Mapping vor den Roman-Keywords steht
    print(f"Genre A: {genre_a}")

    # Beispiel 2: Fokus auf Action vs. Thriller
    genre_b = determine_single_genre(
        source_genres=[],
        categories=[],
        description="Der Polizist findet bei seinen Ermittlungen eine Schießerei und viel Munition."
    )
    # Erwartet: Krimi – da "polizist" vor "schießerei" (Action) und "spannung" (Thriller) geprüft wird
    print(f"Genre B: {genre_b}")