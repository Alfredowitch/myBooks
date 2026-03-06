"""
Bridge\audio_manager
Sie soll verstehen, in welcher "Welt" (Ebene) wir uns befinden, während der Scanner wandert.
"""
import os

class AudioManager:
    @staticmethod
    def identify_context(current_path, context):
        new_ctx = context.copy()
        parts = current_path.split(os.sep)

        # 1. Anker finden (Wo steht "Hörbuch-")
        anchor_idx = -1
        for i, p in enumerate(parts):
            if "Hörbuch-" in p:
                anchor_idx = i
                new_ctx["language"] = p.split("-")[-1]
                break

        if anchor_idx == -1:
            return new_ctx  # Kein Anker gefunden, Abbruch

        # 2. Relative Teile nach dem Anker (z.B. ["Alexander Hartung", "Jan Tommen"])
        rel_parts = parts[anchor_idx + 1:]
        depth = len(rel_parts)
        new_ctx["depth"] = depth

        # 3. Struktur-Logik anwenden
        if depth >= 1:
            # Ebene 1 ist immer der Autor (Standard)
            # Spezialprüfung für Unterstriche (_byRegion) folgt später
            new_ctx["author"] = rel_parts[0]

        if depth >= 2:
            # Ebene 2 ist die Serie
            new_ctx["series"] = rel_parts[1]

        return new_ctx