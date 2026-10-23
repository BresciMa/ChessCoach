# Backlog para agentes

Implementar nesta ordem. Cada fatia só começa quando a anterior passa nos testes dela. Não ampliar o escopo da fatia. A regra de produto está em [especificacao-produto.md](especificacao-produto.md). Contratos e formatos estão em [arquitetura.md](arquitetura.md).

Em todas as fatias, não fazer: C++ ou Qt nativo, ONNX, detecção automática do tabuleiro, menu lateral, comunidade, modo invisível, empacotar o binário do Stockfish, gravar `GEMINI_API_KEY` em arquivo.

## 1. Esqueleto e contratos

Criar `src/chesscoach/` com os módulos vazios do layout, os tipos `CoachFacts`, `PolicyDecision`, `Level`, `Reason` e os protocolos. Configuração carrega e grava `%APPDATA%/ChessCoach/config.json` sem campo de chave de API. `training_accepted` padrão falso.

Pronto quando: os tipos importam, um teste instancia `CoachFacts`, e a config de ida e volta preserva o nível e o aceite.

Não fazer: janela, captura, chamada de rede.

## 2. Captura e calibração

`ScreenCapture` de uma região de um monitor. Calibração guarda monitor, retângulo, orientação e tema. Agendador com relógio injetável: 250 ms em `idle`, 100 ms em `moving`, dois quadros parecidos confirmam, 1 s sem estabilidade emite `BoardUnstable` e volta a `idle`.

Pronto quando: testes com frames falsos cobrem repouso, animação curta e timeout. Nenhum teste precisa de monitor real.

Não fazer: classificar peça, chamar Stockfish, abrir a janela do coach.

## 3. Tracker e FEN

Partida em `python-chess`. Modo acompanhar do início, na posição inicial. Casas que mudaram viram no máximo um lance legal, cobrindo captura, roque, en passant e promoção. Zero matches não alteram a partida. Dois matches emitem `Ambiguous`. Promoção sem peça emite `PromotionNeeded`.

`PieceClassifier` por template, com uma imagem fixture de cada tema. Uma casa abaixo da confiança rejeita o tabuleiro inteiro. "Ler posição agora" só substitui a FEN quando `ok` é verdadeiro.

Pronto quando: os testes de visão e de regras descritos na arquitetura passam sem tela ao vivo.

Não fazer: rede neural, achar o tabuleiro sem retângulo, tema 3D.

## 4. Stockfish

`ChessEngine` sobe o processo do caminho configurado, envia `position fen` e `go movetime`, lê a avaliação e até três lances. Processo ausente ou timeout devolve `None`.

Pronto quando: um teste com binário local, se o caminho existir, lê uma posição conhecida; um teste sem binário recebe `None` e não levanta exceção para o chamador.

Não fazer: distribuir o executável, deixar o motor analisar durante `moving`.

## 5. Analisador e CoachFacts

`PositionAnalyzer` preenche o objeto com as definições da arquitetura. Motor `None` zera só os campos de motor.

Pronto quando: testes de peça solta, xeque, desenvolvimento, rei e motor ausente passam sem Gemini.

Não fazer: texto livre de avaliação no analisador, campo `king_safety` com adjetivo.

## 6. Política e Gemini

`HelpPolicy` implementa a tabela de níveis e os três motivos. `GeminiProvider` implementa `LlmProvider`. O orquestrador chama o modelo uma vez por lance confirmado, por Dica e por mensagem, com o pacote já recortado. Sem chave, não há request; a interface recebe o erro previsto.

Pronto quando: os testes de política da arquitetura passam sem rede. Um teste do provedor usa um fake de `LlmProvider`, não a API.

Não fazer: mandar o JSON cru do Stockfish ao modelo, segunda chamada para classificar a intenção da frase.

## 7. Janela, aviso e últimas jogadas

Janela PySide6 conforme a especificação de produto: arrastar, sempre no topo, avatar de 28 px, rótulo "Modo treino", chat, barra de 48 a 56 px, popup de últimas, popup de nível, configurações.

O diálogo de primeiro uso usa o texto exato da spec. Sem aceite, Dica, chat, setas e análise ficam desligados. O rótulo não tem como sumir.

Pronto quando: um teste de UI ou um script de abertura mostra o diálogo antes do chat operar, e o popup de últimas abre e fecha sem redimensionar o chat.

Não fazer: gráfico de avaliação, menu lateral, modo invisível.

## 8. Overlay de setas

Janela transparente alinhada ao retângulo, clique atravessa, desenha só `arrow` e `threat_squares` da política, e só com Setas ligado. Some ao confirmar outro lance.

Pronto quando: com nível 2 e fala espontânea, nenhuma seta de lance aparece; depois de Dica, a seta daquele lance aparece se o botão estiver ligado.

Não fazer: várias setas da linha principal, desenhar por cima com a janela do coach bloqueando o tabuleiro.

## 9. Encaixe e critérios de aceite

Ligar o tracker ao analisador, à política, ao orquestrador e às duas janelas. Percorrer a lista de aceite da especificação de produto. Corrigir o que falhar sem abrir funcionalidade nova.

Pronto quando: cada item de aceite da spec de produto tem um teste automático ou um passo manual escrito ao lado do resultado. Os testes automáticos das fatias 1 a 6 continuam passando.
