# Especificação de produto

Chess Coach é um app desktop de treino. A pessoa joga noutro programa ou site. Este app lê o tabuleiro na tela e conversa numa janela flutuante. O nível de ajuda muda o que o coach diz sozinho e o que ele desenha no tabuleiro.

Público: adolescente e adulto. Frases curtas, em português, sem gíria obrigatória. Informação importante não depende só de cor.

## Modo treino

O app é só para estudo e treino. Usar em partida valendo rating, torneio ou qualquer jogo em que ajuda externa é proibida é responsabilidade integral de quem usa.

Não existe modo invisível, janela sem título, disfarce de outro programa, nem recurso para contornar anti-cheat. A janela do coach fica identificável o tempo todo. A camada das setas deixa o clique passar até o tabuleiro. A janela do coach não deixa.

### Primeiro uso

Antes de análise, dica, seta ou chat funcionarem, um diálogo bloqueia a janela. A pessoa escolhe "Entendi e aceito" ou "Sair". O aceite fica em `training_accepted`. Fechar o diálogo sem aceitar é o mesmo que "Sair" para essas funções: a janela pode existir, o coach não opera.

Texto do diálogo, nesta redação:

> Chess Coach é uma ferramenta de treino e estudo. Ele usa um motor de xadrez e um assistente de texto para comentar posições.
>
> Partidas valendo rating, torneios e outros jogos em que ajuda externa é proibida podem vetar este tipo de auxílio. A responsabilidade de não usar o Chess Coach nesses jogos é integralmente sua.
>
> Este programa não se esconde de anti-cheat e não deve ser usado para obter vantagem em partida competitiva.

Botões: "Entendi e aceito" e "Sair".

### Rótulo permanente

Na barra da janela, o texto "Modo treino" fica visível em toda sessão, também depois do aceite. Não há opção para ocultar.

## Níveis

A pessoa troca o nível por um popup da barra. A troca vale na próxima fala.

A fala espontânea segue o nível. O botão Dica, ou um pedido explícito no chat, libera um lance em qualquer nível. A lista de pedidos e o recorte dos dados estão em [arquitetura.md](arquitetura.md).

- **Iniciante total.** A pessoa está aprendendo o movimento das peças. Depois de um lance, o coach diz qual peça andou e como ela anda. Pode indicar um lance simples. Casas legais só aparecem se a pessoa pedir.
- **Nível 1.** A pessoa já sabe o básico. O coach sugere o próximo lance. Com Setas ligado, desenha essa sugestão.
- **Nível 2.** O coach alerta xeque, peça solta, peça ameaçada e rei no centro. Não nomeia o lance até a pessoa pedir no chat ou em Dica. A seta de melhor lance fica apagada até esse pedido.
- **Nível 3.** O coach fala de plano, desenvolvimento e segurança do rei. Não lista a linha do motor até a pessoa pedir.
- **Master.** O coach só comenta o lance que acabou de acontecer: se melhorou ou piorou a posição, em linguagem de faixa, sem sugerir o próximo. Pergunta no chat sobre o passado da posição pode ser respondida. O próximo lance só sai com pedido explícito.

Pausar congela captura, fala espontânea e setas. Dica e chat continuam disponíveis sobre a última posição estável, se o treino foi aceito.

## Janela

Referência visual: a janela escura de [Interface de Xadrez com Coach IA.png](Interface%20de%20Xadrez%20com%20Coach%20IA.png). O site desenhado atrás dela não faz parte do produto.

- Sem borda de sistema, arrastável pela barra superior, sempre no topo.
- Foto do coach com cerca de 28 px, circular. Pode ser um avatar empacotado. Ao lado: "Chess Coach", o nome do nível e "Modo treino".
- Minimizar e fechar. Fechar encerra o app. Minimizar recolhe para a barra de tarefas.
- Área de chat com bolhas de texto. Campo: "Pergunte ao coach..." e botão enviar.
- Corpo do texto com cerca de 15 px. Contraste alto no tema escuro. O acento claro da imagem é cor de destaque, não o único meio de mostrar estado.
- Alvos da barra com pelo menos 40 px de lado.

### Barra direita

Largura entre 48 e 56 px. Ícone mais tooltip. De cima para baixo:

- Pausar. Tooltip "Pausar". Quando ativo, o tooltip passa a "Retomar".
- Dica. Tooltip "Pedir um lance".
- Setas. Tooltip "Mostrar setas no tabuleiro". Liga e desliga. Padrão desligado.
- Calibrar. Tooltip "Marcar o tabuleiro".
- Últimas. Tooltip "Últimas jogadas". Abre popup.
- Nível. Tooltip "Nível de ajuda". Abre popup.
- Configurações. Tooltip "Configurações".

### Popup de últimas jogadas

Abre ancorado à barra, não empurra o chat. Lista os lances em SAN, em pares quando couber. Avaliação numérica não aparece nos níveis 2, 3 e Master. No Iniciante total e no Nível 1, a faixa em palavras pode aparecer no último lance. Fechar pelo X do popup.

### Popup de nível

Cinco opções, com o nome e uma linha:

- Iniciante total — como as peças andam.
- Nível 1 — sugere o próximo lance.
- Nível 2 — alerta perigos, sem dizer o lance.
- Nível 3 — fala de plano e estratégia.
- Master — comenta só depois do lance.

### Configurações

Campos: monitor, tema das peças (`lichess_2d`, `chesscom_2d`), caminho do Stockfish, id do modelo Gemini (só leitura do valor configurado, edição num único campo). Texto de ajuda: a chave é a variável `GEMINI_API_KEY`, não um campo neste formulário. Link ou texto do aviso de treino, para reler.

### Setas

Segunda janela, transparente, sempre no topo, do tamanho do retângulo calibrado. O clique atravessa. Desenha no máximo uma seta, a do campo `arrow` da política, e casas de ameaça quando a política mandar. Com Setas desligado, ou sem calibração, a janela fica oculta. A seta some quando um novo lance é confirmado, até a política publicar outra.

## Calibração

O botão Calibrar explica: "Arraste um retângulo só sobre as 64 casas, sem o relógio e sem as letras."

A pessoa escolhe o monitor se houver mais de um, a orientação ("Eu jogo de Brancas embaixo" ou "Eu jogo de Pretas embaixo") e o tema.

Dois modos:

- "Acompanhar do início". Vale quando a partida na tela está na posição inicial. O app não tenta reconhecer peça; segue as casas que mudam.
- "Ler posição agora". Uma leitura do tema escolhido. Se falhar, a mensagem é a de tabuleiro ilegível e a partida anterior, se havia, permanece.

Tema 3D, tabuleiro em perspectiva e conjunto de peças fora dos dois temas não são suportados. A mensagem de falha pede para voltar ao tema 2D padrão ou acompanhar do início.

## Fora da v1

Menu lateral, Comunidade, curso, puzzles, gráfico de avaliação, detecção automática do tabuleiro, acompanhar partida sem o retângulo marcado, modo invisível.

## Aceite

- Sem o aceite do aviso, Dica, chat, setas e análise não disparam, e o diálogo explica o motivo.
- Com o aceite, "Modo treino" continua na barra.
- Não há controle de ocultar o rótulo nem de tornar a janela anônima.
- No nível 2, depois de um lance, o texto espontâneo não contém um lance sugerido. Apertar Dica produz um lance.
- No Master, não há fala entre lances. Depois do lance, o comentário não traz o próximo lance.
- Últimas jogadas abre em popup e fecha sem mudar o tamanho do chat.
- A barra direita cabe em 56 px.
- Calibrar recusa um acompanhamento se a pessoa não marcou o retângulo.
- "Ler posição agora" com confiança baixa não altera a FEN.
- Durante a animação da peça, nenhuma mensagem nova de coach é enviada.
