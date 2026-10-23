"""Nomes em português para prefixos de lances. O modelo não inventa o nome."""

from __future__ import annotations

# O prefixo mais longo que bater com a partida é o nome usado.
_OPENINGS: tuple[tuple[str, str], ...] = (
    ("e4 e5 Nf3 Nc6 d4", "Abertura Escocesa"),
    ("e4 e5 Nf3 Nc6 Bb5", "Abertura Espanhola"),
    ("e4 e5 Nf3 Nc6 Bc4 Bc5", "Abertura Italiana"),
    ("e4 e5 Nf3 Nc6 Bc4 Nf6", "Defesa dos Dois Cavalos"),
    ("e4 e5 Nf3 Nc6 Bc4", "Abertura Italiana"),
    ("e4 e5 Nf3 Nf6", "Defesa Russa"),
    ("e4 e5 Nf3 d6", "Defesa Philidor"),
    ("e4 e5 f4", "Gambito do Rei"),
    ("e4 e5", "Abertura do Peão do Rei"),
    ("e4", "Abertura do Peão do Rei"),
    ("e4 c5", "Defesa Siciliana"),
    ("e4 e6", "Defesa Francesa"),
    ("e4 c6", "Defesa Caro-Kann"),
    ("e4 d5", "Defesa Escandinava"),
    ("e4 Nf6", "Defesa Alekhine"),
    ("e4 d6", "Defesa Pirc"),
    ("e4 g6", "Defesa Moderna"),
    ("d4 d5 c4 c6", "Defesa Eslava"),
    ("d4 d5 c4", "Gambito da Dama"),
    ("d4 Nf6 c4 g6", "Defesa Índia do Rei"),
    ("d4 Nf6 c4 e6 Nc3 Bb4", "Defesa Nimzoíndia"),
    ("d4 Nf6 c4 e6", "Defesa Índia da Dama"),
    ("d4 Nf6", "Defesa Índia"),
    ("d4 f5", "Defesa Holandesa"),
    ("d4 d5", "Abertura do Peão da Dama"),
    ("c4", "Abertura Inglesa"),
    ("Nf3", "Abertura Réti"),
)


def opening_name(sans: list[str]) -> str | None:
    if not sans:
        return None
    text = " ".join(sans)
    found: str | None = None
    length = -1
    for prefix, name in _OPENINGS:
        if text == prefix or text.startswith(prefix + " "):
            if len(prefix) > length:
                found = name
                length = len(prefix)
    return found
