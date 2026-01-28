from typing import Set, Optional
# ==============================================================================
# 2. KORRIGIERTES REGION MAPPING DICTIONARY
#    Priorität: Spezifische Orte/Regionen vor allgemeinen Kontinenten/Ländern
# ==============================================================================

REGION_HIERARCHY = {
    # I. HOHE PRIO: Spezifische Orte/Regionen (mit sprachspezifischer Absicherung)
    "nürnberg": "Franken", "frankisch": "Franken",
    "munich": "München", "bayerisch": "Bayern",
    "berlin": "Deutschland", "frankfurt": "Deutschland",
    "nordsee": "Deutschland", "ostfriesland": "Deutschland",
    "wien": "Österreich", "zurich": "Schweiz",

    "london": "UK", "schottland": "UK",
    "irland": "Irland", "dublin": "Irland",

    "toskana": "Italien", "südtirol": "Italien",
    "venedig": "Italien", "ligurien": "Italien",
    "sizilien": "Italien", "apulien": "Italien",

    "paris": "Frankreich", "provence": "Frankreich",
    "barcelona": "Spanien", "madrid": "Spanien",

    # II. MITTLERE PRIO: Große Länder / Globale Regionen / Kontinente
    "skandinavien": "Skandinavien", "norwegen": "Skandinavien", "schweden": "Skandinavien",
    "afrika": "Afrika", "africa": "Afrika", "kenia": "Afrika", "safari": "Afrika",
    "usa": "Nordamerika", "kanada": "Nordamerika",
    "südamerika": "Südamerika", "brasilien": "Südamerika",
    "karibik": "Südamerika", "polregion": "Polregion",
    "türkei": "Türkei", "griechenland": "Griechenland", "indien": "Indien", "china": "China",

    # III. NIEDRIGE PRIO: Allgemeine Orte / Länder-Fallbacks (zur Vermeidung von Kollisionen)
    "frankreich": "Frankreich", "italien": "Italien", "spanien": "Spanien",
    "deutschland": "Deutschland",

    # Allgemeine Orts- und Länder-Keywords (am Ende)
    "rom": "Italien", "florenz": "Italien",
    # <<< Spezifische, aber potenziell unsichere Keywords am Ende

    # Städte -> Regionen/Bundesländer
    "nürnberg": "Franken",
    "erlangen": "Franken",
    "münchen": "Bayern",
    "regensburg": "Bayern",
    "frankfurt": "Hessen",
    "stuttgart": "Baden-Württemberg",
    "wien": "Österreich",
    "zürich": "Schweiz",
    "london": "England",
    "paris": "Frankreich",

    # Regionen -> Länder
    "franken": "Bayern",
    "oberbayern": "Bayern",
    "bayern": "Deutschland",
    "hessen": "Deutschland",
    "niedersachsen": "Deutschland",
    "england": "Grossbritannien",
    "schottland": "Grossbritannien",
    "toskana": "Italien",
    "sizilien": "Italien",

    # Länder -> Kontinente/Überbegriffe
    "deutschland": "Europa",
    "österreich": "Europa",
    "schweiz": "Europa",
    "frankreich": "Europa",
    "italien": "Europa",
    "spanien": "Europa",
    "grossbritannien": "Europa",
    "usa": "Nordamerika",
    "kanada": "Nordamerika",
    "brasilien": "Südamerika",
    "kenia": "Afrika",
    "china": "Asien"
}


def refine_regions (current_regions: set, keywords: set, description: str, passes: int = 3) -> set:
    """
    Veredelt das Regions-Set in mehreren Durchläufen.
    Jeder Fund triggert im nächsten Durchlauf potenziell seinen 'Vater'.
    """
    # 1. Initiale Suche in Keywords und Beschreibung
    kw_string = " ".join([str(k).lower() for k in keywords])
    desc_lower = description.lower() if description else ""
    search_base = kw_string + " " + desc_lower

    # Erster Scan: Was steht direkt im Text?
    for term, parent in REGION_HIERARCHY.items():
        if term in search_base:
            # Wir fügen sowohl den Fund (normalisiert) als auch den Vater hinzu
            current_regions.add(term.capitalize())
            current_regions.add(parent)

    # 2. Rekursive Veredelung: Wir nutzen das Set selbst als Quelle
    for _ in range(passes):
        new_entries = set()
        # Wir schauen uns an, was wir schon haben
        current_list = [r.lower() for r in current_regions]

        for region_name in current_list:
            if region_name in REGION_HIERARCHY:
                parent = REGION_HIERARCHY[region_name]
                if parent not in current_regions:
                    new_entries.add(parent)

        if not new_entries:
            break  # Nichts Neues gefunden, wir können aufhören

        current_regions.update(new_entries)

    return current_regions

if __name__ == "__main__":
    # ... (Genre Mapping Tests unverändert) ...

    print("\n--- Region Mapping Tests ---")
