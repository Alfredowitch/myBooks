# ==============================================================================
# 2. KORRIGIERTES REGION MAPPING DICTIONARY
#    Priorität: Spezifische Orte/Regionen vor allgemeinen Kontinenten/Ländern
# ==============================================================================

REGION_MAPPING = {
    # I. HOHE PRIO: Spezifische Orte/Regionen (mit sprachspezifischer Absicherung)
    "nürnberg": "Deutschland (Franken)", "frankisch": "Deutschland (Franken)",
    "münchen": "Deutschland (München)", "bayerisch": "Deutschland (Bayern)",
    "berlin": "Deutschland (Berlin)", "frankfurt": "Deutschland (Frankfurt)",
    "nordsee": "Deutschland (Nordsee)", "ostfriesland": "Deutschland (Nordsee)",
    "wien": "Österreich", "zurich": "Schweiz",

    "london": "Grossbritannien (England)", "schottland": "Grossbritannien (Schottland)",
    "irland": "Irland", "dublin": "Irland",

    "toskana": "Italien (Toskana)", "südtirol": "Italien (Südtirol)",
    "venedig": "Italien (Venetien)", "ligurien": "Italien (Ligurien)",
    "sizilien": "Italien (Sizilien)", "apulien": "Italien (Apulien)",

    "paris": "Frankreich (Paris)", "provence": "Frankreich (Provence)",
    "barcelona": "Spanien (Barcelona)", "madrid": "Spanien (Madrid)",

    # II. MITTLERE PRIO: Große Länder / Globale Regionen / Kontinente
    "skandinavien": "Skandinavien", "norwegen": "Skandinavien", "schweden": "Skandinavien",
    "afrika": "Afrika", "africa": "Afrika", "kenia": "Afrika", "safari": "Afrika",
    "usa": "Nordamerika (USA)", "kanada": "Nordamerika (Kanada)",
    "südamerika": "Südamerika", "brasilien": "Südamerika",
    "karibik": "Karibik", "polregion": "Polregion",
    "türkei": "Türkei", "griechenland": "Griechenland", "indien": "Indien", "china": "China",

    # III. NIEDRIGE PRIO: Allgemeine Orte / Länder-Fallbacks (zur Vermeidung von Kollisionen)
    "frankreich": "Frankreich (Allgemein)", "italien": "Italien (Allgemein)", "spanien": "Spanien (Allgemein)",
    "deutschland": "Deutschland (Allgemein)",

    # Allgemeine Orts- und Länder-Keywords (am Ende)
    "rom": "Italien (Rom)", "florenz": "Italien (Toskana)",
    # <<< Spezifische, aber potenziell unsichere Keywords am Ende
}


def determine_region(categories: list, description: str) -> str | None:
    # ... (Funktionskörper unverändert) ...
    search_text_parts = []
    if description and isinstance(description, str):
        search_text_parts.append(description)
    if categories:
        valid_categories = [c for c in categories if c is not None and isinstance(c, str)]
        search_text_parts.extend(valid_categories)
    # Wir prüfen, ob wir überhaupt etwas zum Suchen haben
    if not search_text_parts:
        return None
    full_search_string = " ".join(search_text_parts).lower()

    for term, region_name in REGION_MAPPING.items():
        if term in full_search_string:
            return region_name

    return None


if __name__ == "__main__":
    # ... (Genre Mapping Tests unverändert) ...

    print("\n--- Region Mapping Tests ---")

    # Apps 4: Spezifische deutsche Region (Nürnberg/Franken)
    region_test_4 = determine_region(
        categories=["Reiseführer"],
        description="Die besten Wanderrouten rund um Nürnberg und in Franken."
    )
    print(f"Test 4 (Nürnberg/Franken): {region_test_4}")  # Erwartet: Deutschland (Franken)

    # Apps 5: Spezifische italienische Region (Toskana/Florenz)
    region_test_5 = determine_region(
        categories=["Urlaub"],
        description="Ein Liebesroman spielt in der Toskana bei Florenz."
    )
    print(f"Test 5 (Toskana/Florenz): {region_test_5}")  # Erwartet: Italien (Toskana)

    # Apps 6: Kontinent (Afrika)
    # Erwartet: Afrika (wird jetzt vor "rom" geprüft)
    region_test_6 = determine_region(
        categories=[],
        description="Ein Abenteuerroman auf dem Kontinent Afrika."
    )
    print(f"Test 6 (Afrika): {region_test_6}")