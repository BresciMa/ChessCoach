"""Textos visíveis, na redação da especificação de produto."""

from __future__ import annotations

from chesscoach.types import Level

TRAINING_TEXT = (
    "Chess Coach é uma ferramenta de treino e estudo. Ele usa um motor de xadrez "
    "e um assistente de texto para comentar posições.\n"
    "\n"
    "Partidas valendo rating, torneios e outros jogos em que ajuda externa é proibida "
    "podem vetar este tipo de auxílio. A responsabilidade de não usar o Chess Coach "
    "nesses jogos é integralmente sua.\n"
    "\n"
    "Este programa não se esconde de anti-cheat e não deve ser usado para obter "
    "vantagem em partida competitiva."
)

TRAINING_ACCEPT = "Entendi e aceito"
TRAINING_DECLINE = "Sair"
TRAINING_BADGE = "Modo treino"

MSG_UNREADABLE = (
    "Não consegui ler o tabuleiro. Confira o retângulo das 64 casas."
)
MSG_UNSTABLE = "O tabuleiro não estabilizou. Pause animações ou marque só as 64 casas."
MSG_BOARD_LOST = "Perda do tabuleiro."
MSG_BOARD_BACK = "Tabuleiro conectado."
MSG_AMBIGUOUS = "Vi mais de um lance possível. Jogue de novo ou escreva o lance."
MSG_NO_ENGINE = "O motor não está configurado. Indique o caminho do Stockfish."
MSG_ENGINE_SILENT = "O motor não respondeu nesta posição."
MSG_NO_KEY = "Falta a chave GEMINI_API_KEY. O coach não consegue escrever."
MSG_SSL = (
    "Não consegui falar com o Gemini. A rede apresentou um certificado que o Python não reconhece. "
    "Feche o app e abra de novo. Se continuar, grave o certificado da empresa num arquivo .pem "
    "e aponte a variável SSL_CERT_FILE para esse arquivo."
)
MSG_LLM_FAILED = "Não consegui falar com o Gemini. Verifique a chave e a conexão."
MSG_NEED_ROI = "Marque o retângulo das 64 casas."
MSG_PROMOTION = "Peão promovido. Escolha dama, torre, bispo ou cavalo."
MSG_FOLLOWING = "Acompanhando desde a posição inicial."
MSG_WE_WON = "Vencemos"
CALIBRATION_HELP = "Arraste um retângulo só sobre as 64 casas, sem o relógio e sem as letras."
KEY_HELP = (
    "A chave é a variável GEMINI_API_KEY, não um campo neste formulário. "
    "Numa rede corporativa, SSL_CERT_FILE pode apontar para o certificado .pem da empresa."
)

LEVEL_LABELS: dict[Level, str] = {
    Level.BEGINNER: "Iniciante total",
    Level.LEVEL_1: "Nível 1",
    Level.LEVEL_2: "Nível 2",
    Level.LEVEL_3: "Nível 3",
    Level.MASTER: "Master",
}

LEVEL_BLURBS: dict[Level, str] = {
    Level.BEGINNER: "como as peças andam.",
    Level.LEVEL_1: "sugere o próximo lance.",
    Level.LEVEL_2: "alerta perigos, sem dizer o lance.",
    Level.LEVEL_3: "fala de plano e estratégia.",
    Level.MASTER: "comenta só depois do lance.",
}

PIECE_NAMES = {
    "P": "peão branco",
    "N": "cavalo branco",
    "B": "bispo branco",
    "R": "torre branca",
    "Q": "dama branca",
    "K": "rei branco",
    "p": "peão preto",
    "n": "cavalo preto",
    "b": "bispo preto",
    "r": "torre preta",
    "q": "dama preta",
    "k": "rei preto",
}

PIECE_RULES = {
    "P": "O peão anda uma casa para frente e captura na diagonal. No primeiro lance, pode andar duas casas.",
    "N": "O cavalo anda em L: duas casas numa direção e uma para o lado. Ele pula peças.",
    "B": "O bispo anda na diagonal, quantas casas quiser, sem pular peças.",
    "R": "A torre anda na linha ou na coluna, quantas casas quiser, sem pular peças.",
    "Q": "A dama anda na linha, na coluna ou na diagonal, sem pular peças.",
    "K": "O rei anda uma casa em qualquer direção. O roque é o lance em que o rei anda duas casas na direção da torre.",
}
