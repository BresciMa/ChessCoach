# Validação da proposta

Este arquivo é o veredito sobre o [documento de intenção](documento%20de%20intenção.md) e sobre a imagem [Interface de Xadrez com Coach IA.png](Interface%20de%20Xadrez%20com%20Coach%20IA.png). A especificação que os agentes implementam está em [arquitetura.md](arquitetura.md), [especificacao-produto.md](especificacao-produto.md) e [backlog-agentes.md](backlog-agentes.md).

O documento de intenção responde a uma pergunta técnica: dá para construir um coach desktop que lê pixels de qualquer app ou site de xadrez. Ele não descreve o produto pedido: níveis de ajuda, chat, Gemini atrás de uma interface, e a janela flutuante. A imagem é referência visual da janela do coach, não a lista de funcionalidades.

## O que fica

- App desktop sempre por cima, lendo pixels. Não usa a API do Chess.com, do Lichess nem de outro cliente.
- Pipeline em camadas. A visão produz estado de tabuleiro. Quem fala com a pessoa é o coach.
- Na v1 a pessoa marca o retângulo das 64 casas. O app não procura o tabuleiro sozinho.
- Depois da primeira posição, a partida é acompanhada pela diferença entre quadros estáveis. Lance ilegal não entra no histórico.
- Stockfish, via UCI, calcula. O modelo de linguagem só redige.
- O app é ferramenta de treino. A janela permanece identificável. Não há modo invisível nem recurso para contornar anti-cheat.

## O que muda

### Linguagem

A v1 é Python 3.12 com PySide6. C e C++ ficam fora desta versão.

O tempo do programa está na captura, no Stockfish e na rede do Gemini. O código do app é a cola: ler o tabuleiro, aplicar o nível de ajuda e falar com a pessoa. Python já traz OpenCV, `python-chess`, PySide6 e o SDK do Gemini. C++ passaria a compensar se, numa versão futura, a captura ou um classificador próprio medirem gargalo. Os contratos em [arquitetura.md](arquitetura.md) existem para trocar um módulo sem reescrever o produto. C puro não entra: janela, HTTP e regras de xadrez deixariam de ter biblioteca à altura do problema.

### Captura

Cinco a quinze capturas da tela inteira por segundo ficam de fora. Depois da calibração, a captura é só o retângulo do tabuleiro:

- Em repouso, um quadro a cada 250 ms.
- Quando a diferença nas 64 casas passa do limiar, o intervalo cai para 100 ms.
- A posição só é lida quando dois quadros seguidos ficam parecidos.
- Stockfish e Gemini não rodam durante a animação.
- Se a imagem não estabilizar em cerca de 1 s, o ritmo volta a 250 ms e a interface avisa que o tabuleiro está instável.

Relógio, cursor e compressão não disparam leitura. O limiar olha as casas, não a janela inteira.

### Visão

Um classificador neural universal (ONNX, 13 classes, qualquer conjunto de peças, inclusive 3D) não entra na v1. Não há dataset para isso.

A v1 lê a posição de dois jeitos:

- Acompanhar desde a posição inicial, só com casas que mudaram e com as regras.
- Ler agora, por comparação com as peças de um tema suportado: Lichess 2D padrão e Chess.com 2D padrão, tabuleiro alinhado aos eixos.

Se a confiança for baixa, o app diz que não leu e não inventa FEN. Tema 3D, tabuleiro torto e skins raras ficam de fora.

### Coach

Os níveis de ajuda não estavam no documento de intenção. São regra de produto. O Stockfish não fala com o Gemini. O `PositionAnalyzer` monta `CoachFacts`. A `HelpPolicy` apaga o que o nível não pode ver. O Gemini redige o que sobrou.

Gemini é o provedor padrão, atrás de `LlmProvider`. O identificador do modelo fica num único lugar da configuração. A chave vem de `GEMINI_API_KEY`.

### Interface

A imagem mistura um site de xadrez (Jogar, Problemas, Aprender, Análises, Comunidade, Configurações) com o coach. O produto é a janela flutuante. Comunidade, curso, puzzles, menu lateral e gráfico de avaliação ficam de fora da v1.

Da imagem, ficam: janela escura arrastável, foto pequena do coach, chat, barra estreita à direita e popup de últimas jogadas.

## Fora da v1

- Detecção automática do quadrilátero do tabuleiro.
- C++ / Qt / DXGI como implementação.
- ONNX Runtime e treinamento de classificador.
- Modo invisível, disfarce de outro programa, ou qualquer recurso pensado para furar anti-cheat.
- Cliente completo de xadrez, conta de usuário, comunidade e lições.
