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

def determine_single_genre(source_genres, categories, description):
    """
    Bestimmt ein einzelnes Genre basierend auf dem GENRE_MAPPING.

    Priorität: Zuerst Source Genres, dann Beschreibung/Kategorien.
    Gibt den ersten Treffer zurück (wobei die Reihenfolge im Mapping die Priorität steuert).
    """

    # ----------------------------------------------------
    # I. Priorität 1: Suche in der Liste der zugewiesenen Genres (Source Genres)
    # ----------------------------------------------------

    # Wir filtern: Nur Strings, die nicht None sind und nicht leer sind, werden aufgenommen.
    # Diese List Comprehension stellt mit der Bedingung sicher, dass
    # - g is not None: Der Wert ist nicht None
    # - isinstance(g, str): Der Wert ist tatsächlich ein String
    # - g.strip(): Der String ist nicht leer oder besteht nur aus Leerzeichen.
    # Das eliminiert den AttributeError: 'NoneType' object has no attribute 'lower' endgültig.

    valid_source_genres = [
        g.lower() for g in source_genres
        if g is not None and isinstance(g, str) and g.strip()
    ]

    # Erstelle einen durchsuchbaren String aus den Source Genres
    genre_search_string = " ".join(valid_source_genres)
    # print(f"DEBUG Genre Search String: {genre_search_string}")
    for term, target_genre in GENRE_MAPPING.items():
        if term in genre_search_string:
            return target_genre

    # ----------------------------------------------------
    # II. Priorität 2: Suche in Beschreibung und Kategorien
    # ----------------------------------------------------

    # Kombiniere alle Texte zu einem durchsuchbaren String
    search_text_parts = []
    if description:
        search_text_parts.append(description)
    if categories:
        search_text_parts.extend(categories)

    full_search_string = " ".join(search_text_parts).lower()

    for term, target_genre in GENRE_MAPPING.items():
        if term in full_search_string:
            return target_genre

    # ----------------------------------------------------
    # III. Keine Region gefunden
    # ----------------------------------------------------
    return None


def extract_genre_and_keywords(source_genres, categories, description):
    """
    Analysiert Texte und teilt Funde in ein Haupt-Genre und Keywords auf.
    Gibt (str, set) zurück.
    """
    final_main_genre = "Unbekannt"
    additional_keywords = set()

    # 1. Such-Strings vorbereiten
    valid_sources = [str(g).lower() for g in source_genres if g and isinstance(g, str)]
    valid_cats = [str(c).lower() for c in categories if c and isinstance(c, str)]

    # Wir gewichten die Quellen: Source-Genres sind oft präziser als die Beschreibung
    search_text_primary = " ".join(valid_sources)
    search_text_secondary = (description or "").lower() + " " + " ".join(valid_cats)

    # 2. Mapping durchlaufen
    for term, mapped_value in GENRE_MAPPING.items():
        # Suche erst in Primärquellen, dann Sekundär
        if term in search_text_primary or term in search_text_secondary:

            # Extrahiere den Kernbegriff aus dem Mapping
            # (z.B. "Fachbuch" aus "Fachbuch (IT/Digital)")
            core_genre = mapped_value.split('(')[0].strip()

            # A: Ist es ein Whitelist-Genre?
            if core_genre in GENRE_WHITELIST:
                if final_main_genre == "Unbekannt":
                    final_main_genre = core_genre

                # Die Details (z.B. "IT/Digital") packen wir IMMER in die Keywords
                if '(' in mapped_value:
                    detail = mapped_value.split('(')[1].replace(')', '')
                    additional_keywords.update([d.strip() for d in detail.split('/')])
                else:
                    # Wenn es ein Whitelist-Genre ist, aber wir schon eins haben,
                    # wird das zweite zum Keyword (z.B. ein "Krimi" der auch "Spionage" ist)
                    if final_main_genre != core_genre:
                        additional_keywords.add(core_genre)

            # B: Kein Whitelist-Genre (z.B. "Action (Militär/Kampf)")
            else:
                # Alles in die Keywords
                clean_val = mapped_value.replace('(', '/').replace(')', '').replace('/', ' ')
                additional_keywords.update([v.strip() for v in clean_val.split()])

    return final_main_genre, additional_keywords

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