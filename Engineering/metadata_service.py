import re
from typing import Tuple, Set


class MetadataService:
    # Deine Whitelist und Mappings (hier verkürzt dargestellt)
    GENRE_WHITELIST = {"Krimi", "Thriller", "Science Fiction", "Biographie", "Fantasy", "Roman", "Fachbuch"}

    GENRE_MAPPING = {
        "krimi": "Krimi", "crime": "Krimi",
        "physic": "Fachbuch (MINT/Wissenschaft)",
        # ... alle anderen Einträge aus deinem Code ...
    }

    @staticmethod
    def classify_book(keywords: Set[str], description: str) -> Tuple[str, Set[str]]:
        """Die von dir gepostete Logik, jetzt als saubere statische Methode."""
        final_main_genre = "Unbekannt"
        extracted_extra_keys = set()

        combined_search = " ".join([str(k).lower() for k in keywords]) + " " + (
            description.lower() if description else "")

        for term, mapped_value in MetadataService.GENRE_MAPPING.items():
            if term in combined_search:
                core_genre = mapped_value.split('(')[0].strip()
                if core_genre in MetadataService.GENRE_WHITELIST:
                    if final_main_genre == "Unbekannt":
                        final_main_genre = core_genre
                    elif final_main_genre != core_genre:
                        extracted_extra_keys.add(core_genre)
                    if '(' in mapped_value:
                        detail = mapped_value.split('(')[1].replace(')', '')
                        extracted_extra_keys.update([d.strip() for d in detail.split('/')])
                else:
                    clean_val = mapped_value.replace('(', ' ').replace(')', '').replace('/', ' ')
                    extracted_extra_keys.update([v.strip() for v in clean_val.split()])

        return final_main_genre, extracted_extra_keys


    REGION_HIERARCHY = {
        "nürnberg": "Franken", "munich": "München", "bayerisch": "Bayern",
        "franken": "Bayern", "bayern": "Deutschland", "deutschland": "Europa",
        "london": "England", "england": "Grossbritannien", "grossbritannien": "Europa",
        # ... Hier fügst du den Rest deines Dictionaries ein ...
    }

    @staticmethod
    def refine_regions(current_regions: set, keywords: set, description: str, passes: int = 3) -> set:
        """
        Veredelt Regionen rekursiv: Findet Orte im Text und leitet daraus
        höhere Ebenen (Bundesland, Land, Kontinent) ab.
        """
        # 1. Vorbereitung
        kw_string = " ".join([str(k).lower() for k in keywords])
        desc_lower = description.lower() if description else ""
        search_base = kw_string + " " + desc_lower

        # Erster Scan: Direkte Funde im Text
        for term, parent in MetadataService.REGION_HIERARCHY.items():
            if term in search_base:
                current_regions.add(term.capitalize())
                current_regions.add(parent)

        # 2. Rekursive Veredelung (Die "Ahnenforschung" der Regionen)
        for _ in range(passes):
            new_entries = set()
            # Wichtig: Wir prüfen gegen Kleinschreibung im Dictionary
            current_list_lower = [str(r).lower() for r in current_regions]

            for region_name in current_list_lower:
                if region_name in MetadataService.REGION_HIERARCHY:
                    parent = MetadataService.REGION_HIERARCHY[region_name]
                    if parent not in current_regions:
                        new_entries.add(parent)

            if not new_entries:
                break
            current_regions.update(new_entries)

        return current_regions