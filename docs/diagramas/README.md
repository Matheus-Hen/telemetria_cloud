# Diagramas UML do leitor de telemetria

As quatro figuras desta pasta foram desenhadas a partir de `leitor.py`. Cada seção traz a imagem e, em seguida, um parágrafo que pode ser copiado para o capítulo de Metodologia. A numeração (Figura X) fica a cargo do texto do TCC. Sugestão de crédito sob a figura, porque o desenho é de autoria do trabalho: **Elaborada pelo autor.**

O script é procedural. O diagrama de classes não descreve classes declaradas no código; ele organiza os dados e as responsabilidades que o script exerce. Essa ressalva está no parágrafo correspondente e também na própria figura.

## Casos de uso

![Diagrama de casos de uso do leitor de telemetria](diagrama-casos-de-uso.png)

O diagrama de casos de uso delimita o sistema leitor de telemetria e os dois atores externos que participam de toda execução: o piloto de Le Mans Ultimate, que dispara o script sobre a gravação do stream porque a telemetria do jogo ficou no servidor do serviço de nuvem, e o arquivo de vídeo, que fornece os quadros do HUD. O caso de uso principal inclui a segmentação da barra verde, a segmentação da barra rosa, o reconhecimento da velocidade quando o texto só tem dígitos e a confiança supera o limiar informado, a integração dessa velocidade em distância com passo `1/fps` lido do vídeo, a normalização de cada barra pelo máximo da gravação e a exibição do gráfico. Gravar o PNG e exportar o CSV são extensões opcionais, acionadas por `--headless` e `--csv`.

## Classes

![Diagrama de classes lógico do leitor de telemetria](diagrama-classes.png)

O diagrama de classes é um modelo lógico. O arquivo `leitor.py` não declara classes de domínio: as funções e os presets organizam o procedimento, e as ligações da figura indicam uso. A captura abre o vídeo pedido, lê a taxa de quadros e libera o arquivo. Dois detectores aplicam uma faixa HSV ao recorte do preset. No preset `original` as barras compartilham a coluna; no `lmu_default_1080p` o freio fica à esquerda do acelerador. A faixa rosa vai até a matiz 179. O leitor de velocidade usa EasyOCR em português e inglês e só troca o inteiro quando a confiança passa do limiar. O integrador acumula `(velocidade / 3,6) × (1/fps)` metros por quadro e conserva a última velocidade aceita. A série reescreve as contagens como percentual do máximo. O gráfico traça as curvas e ou abre a janela ou grava o PNG.

## Sequência

![Diagrama de sequência do processamento de um vídeo](diagrama-sequencia.png)

O diagrama de sequência mostra uma execução completa, na ordem das chamadas do script. O piloto informa vídeo, preset e limiar. O script cria o leitor EasyOCR, abre o arquivo e obtém `CAP_PROP_FPS` para calcular `dt = 1/fps`, com reserva de 30 fps. Em cada quadro, o OpenCV converte a imagem para HSV, mascara o verde e o rosa nos recortes escolhidos, conta os pixels e entrega o recorte da velocidade em RGB. O EasyOCR devolve texto e confiança; a velocidade só muda quando a confiança supera o limiar e o texto só tem dígitos. A distância usa esse `dt`. O arquivo é liberado ao fim da leitura. Depois, as contagens viram percentual do máximo e o Matplotlib desenha as curvas. Com `--headless` o gráfico vai para um PNG; sem a opção, abre a janela. Com `--csv`, a série é gravada.

## Atividades

![Diagrama de atividades de leitor.py](diagrama-atividades.png)

O diagrama de atividades descreve o mesmo fluxo como um procedimento único. A execução escolhe o preset, prepara o leitor OCR, abre o vídeo, lê a taxa e zera velocidade e distância. Enquanto há quadro, o script mascara e conta o verde e o rosa, reconhece a velocidade e decide se atualiza o inteiro ou se o conserva. A distância daquele quadro usa `1/fps`. Ao fim das leituras o arquivo é liberado, cada série vira percentual do próprio máximo e as curvas são traçadas. A execução headless grava o PNG; caso contrário a janela permanece aberta até ser fechada. Se o CSV foi pedido, a série é gravada em seguida. A figura registra que o percentual é o pico da gravação e que o arco vermelho de RPM pode contaminar a máscara do freio.
