# Leitor de telemetria a partir do vídeo de sim racing na nuvem

Pilotos de sim racing que usam um serviço de cloud gaming jogam num servidor remoto. O jogo para o qual este leitor foi feito é **Le Mans Ultimate**. É o caso de quem o joga, por exemplo, pela NVIDIA GeForce NOW ou pelo Xbox Cloud Gaming (xCloud). Na máquina do piloto chega o vídeo transmitido, com o painel (HUD) de Le Mans Ultimate desenhado na imagem. A telemetria nativa do simulador — API, pacote de rede ou arquivo que um jogo instalado localmente escreveria — permanece no servidor do serviço.

Este script existe para esse piloto montar a própria telemetria e analisar o desempenho a partir só desse vídeo. Ele mede as barras de acelerador e de freio pela cor, reconhece a velocidade numérica e acumula a distância. O `cloud` do nome do repositório (`telemetria_cloud`) designa esse cenário: telemetria reconstruída quando Le Mans Ultimate está na nuvem.

O programa não entra na conta do GeForce NOW, do xCloud nem de outro serviço, e não conversa com o processo do jogo. A entrada é um arquivo de vídeo da transmissão, já gravado. O repositório é a parte prática de um TCC. Este README descreve o que o código faz hoje, com detalhe suficiente para outra pessoa repetir o processamento. O público e o problema desta seção foram informados pelo autor. Números de recorte, faixas de cor e o passo de tempo continuam lidos do código e seguem marcados para revisão.

## Público-alvo

Pilotos de Le Mans Ultimate que disputam a sessão por um serviço de jogo na nuvem e usam o vídeo transmitido para analisar a própria pilotagem. Os serviços citados pelo autor são a NVIDIA GeForce NOW e o Xbox Cloud Gaming (xCloud). O mesmo enquadramento vale para um serviço equivalente em que o jogo roda no servidor e a telemetria de Le Mans Ultimate não é entregue ao computador do piloto.

## Objetivo

Oferecer a esse piloto uma telemetria própria de análise de desempenho, extraída do HUD de Le Mans Ultimate no vídeo capturado do stream. Quadro a quadro, o sistema obtém:

- a intensidade da barra verde do acelerador;
- a intensidade da barra rosa do freio;
- a velocidade escrita em dígitos.

A velocidade é acumulada em distância. No fim, o script abre um gráfico com o percentual de cada barra no eixo vertical e a distância, em metros, no eixo horizontal. Essa figura é o artefato de análise que o código produz hoje. A série numérica não é gravada em arquivo.

A entrada esperada é um vídeo do HUD de Le Mans Ultimate capturado da transmissão do cloud gaming. O nome do jogo não aparece em `leitor.py`: o script só abre `test_telemetria.mp4`, e os recortes foram medidos para esse painel. O autor ainda precisa confirmar qual cliente de nuvem e qual resolução foram usados nessa medição.

## Como funciona

`leitor.py` é um script procedural, sem funções nem classes. A execução segue esta ordem.

1. Cria um leitor EasyOCR para português e inglês (`easyocr.Reader(['pt', 'en'])`). Na primeira vez, a biblioteca baixa os modelos para `~/.EasyOCR/model`.
2. Zera a velocidade (km/h) e a distância (m) e cria três séries NumPy vazias: `acelerador`, `freio` e `distancia_total`. A variável `frame_count` é criada com valor 0 e não volta a ser usada.
3. Abre o arquivo `test_telemetria.mp4` no diretório de trabalho, com caminho relativo.
4. Para cada quadro, até `VideoCapture.read()` falhar:
   1. Converte o quadro de BGR para HSV.
   2. Aplica uma máscara verde no recorte do acelerador e guarda `countNonZero` (quantidade de pixels dentro da faixa).
   3. Aplica uma máscara rosa no recorte do freio e guarda a contagem do mesmo modo.
   4. Recorta a região da velocidade, converte esse recorte de BGR para RGB e chama `readtext`.
   5. Percorre os resultados do OCR. Se a confiança é maior que 0,5 e `text.isdigit()` é verdadeiro, substitui a velocidade por `int(text)`. Se vários resultados do mesmo quadro passam no filtro, fica o último da lista. Se nenhum passa, a velocidade anterior permanece (0 até a primeira leitura aceita).
   6. Atualiza a distância e anexa o valor à série:

      ```text
      distancia = distancia + (velocidade / 3.6) * 0.033
      ```

      `velocidade / 3.6` converte km/h para m/s. `0.033` é um passo de tempo fixo, em segundos, aplicado a todo quadro. O script não lê a taxa de quadros do arquivo (`CAP_PROP_FPS`).
5. Depois do último quadro, divide a série do acelerador pelo máximo dela e multiplica por 100. Desenha essa curva em verde contra `distancia_total`.
6. Repete a normalização para o freio e desenha a curva em vermelho.
7. Aplica o estilo `dark_background`, preenche a área sob as curvas (alfa 0,3), liga a grade (alfa 0,2) e define título e eixos.
8. Chama `plt.show()`, que bloqueia até a janela ser fechada, e só então executa `cap.release()`.

O percentual de cada barra é relativo ao maior valor observado naquela série, naquela gravação. O pico de uma curva que teve ao menos um pixel colorido fica em 100%, mesmo que a barra do HUD nunca tenha enchido o recorte.

## Tecnologias e justificativa

O texto desta seção é uma justificativa reconstruída a partir do que o script importa e do que cada biblioteca entrega nesse uso. Está escrito para o autor conferir, ajustar e, se for o caso, assumir no capítulo de Metodologia. Não é um registro de uma decisão que esteja documentada em outro lugar do repositório.

| Ferramenta | Versão fixada | Papel neste script |
| --- | --- | --- |
| Python | 3.12 na verificação desta documentação | Executa o processamento de ponta a ponta |
| OpenCV (`opencv-python-headless`) | 4.13.0.92 | Abre o vídeo, converte cor, recorta e conta pixels da máscara |
| NumPy | 2.5.0 | Guarda as séries e fornece os limites HSV |
| EasyOCR | 1.7.2 | Lê os dígitos da velocidade e devolve a confiança |
| Matplotlib | 3.10.7 | Desenha e exibe o gráfico |
| PyTorch e torchvision | transitivas do EasyOCR | Rede do OCR; não são chamadas direto pelo script |

**Python.** O processamento é um laço sobre quadros, com pouca interface. Python concentra OpenCV, OCR e gráfico no mesmo arquivo, que é o formato deste repositório. C++ com OpenCV reduziria o tempo por quadro e aumentaria o código de ligação com o OCR. MATLAB lê vídeo e plota com poucas linhas, com licença e um ambiente menos direto de reproduzir fora da instituição. Para um script único de extração e figura, Python é a opção que o código já adota.

**OpenCV.** `VideoCapture`, `cvtColor`, `inRange` e `countNonZero` cobrem a leitura do arquivo e a segmentação por cor no espaço HSV, que separa a tinta da barra do brilho do quadro. Scikit-image trata imagem estática e não abre o vídeo. Pillow não oferece captura de vídeo. Chamar o FFmpeg à parte e operar só com NumPy repetiria o que o OpenCV já faz no recorte e na máscara. O pacote instalado é o `opencv-python-headless`, na mesma versão 4.13.0.92 que o repositório já fixava: a API usada é a do módulo principal, a janela do resultado é do Matplotlib, e o EasyOCR depende do pacote headless. Manter `opencv-python` ou `opencv-contrib-python` junto com o headless instala dois módulos `cv2` no mesmo ambiente e a importação deixa de ser confiável. Nenhum algoritmo exclusivo do contrib (rastreadores, ArUco, e outros) aparece em `leitor.py`.

**NumPy.** As três séries crescem com `np.append`, e os limites de cor são arrays de três valores. Listas Python bastariam para centenas de quadros e evitariam o custo de realocar o array a cada `append`; o script, porém, já entrega esses dados ao Matplotlib como array. Pandas criaria um `DataFrame` que o gráfico não usa. A versão 2.5.0 foi mantida porque já estava fixada e é compatível com as outras versões desta lista.

**EasyOCR, em lugar do Tesseract.** O HUD entrega um retângulo pequeno (30×84 pixels) com um inteiro. O EasyOCR recebe a imagem RGB e devolve, para cada trecho, caixa, texto e confiança. O filtro do script (`confidence > 0.5` e `text.isdigit()`) usa essa confiança diretamente, e `Reader(['pt', 'en'])` não pede um binário instalado à parte no sistema. O Tesseract, via `pytesseract`, é mais leve e é uma alternativa sólida para texto nítido, mas depende do executável do Tesseract no sistema operacional e, em dígitos pequenos de HUD, em geral pede ampliação, limiar e um modo de segmentação (`--psm`) ajustados ao recorte. Isso aumentaria etapas que este script não tem. PaddleOCR também devolve texto e confiança, com outro conjunto de modelos e uma instalação mais pesada, sem ganho claro para um único número. Casar cada dígito com um molde da fonte do HUD seria mais rápido e mais frágil a antialiasing e à troca de fonte. O EasyOCR é a biblioteca que o código chama; a comparação acima é o argumento sugerido para a Metodologia, e o autor deve confirmá-lo.

**Matplotlib.** Duas curvas, preenchimento, grade e rótulos cabem em `pyplot` e `Axes`, e `plt.show()` é a única saída do programa. Plotly acrescentaria um gráfico interativo e um runtime de front-end que o script não usa. Seaborn organiza gráficos estatísticos em cima do Matplotlib, sem papel nas duas séries brutas. `matplotlib-inline` só altera o backend dentro do IPython e do Jupyter; este arquivo é executado como script.

**Dependências retiradas de `requirements.txt`.** `pandas` e `matplotlib-inline` não são importados. `opencv-contrib-python` não é necessário para as quatro chamadas de OpenCV do arquivo. `opencv-python` foi trocado por `opencv-python-headless==4.13.0.92` pelo conflito com a dependência do EasyOCR, descrito acima. `matplotlib` e `easyocr` foram incluídos porque o script os importa e a lista antiga não os instalava.

## Requisitos

Há dois blocos. O bloco do problema e do público registra o que o autor informou sobre para quem o trabalho existe. O bloco seguinte descreve o comportamento atual de `leitor.py`. Os valores de recorte, HSV, confiança e passo de tempo foram lidos do código e devem ser revisados antes de entrarem no TCC como especificação fechada.

### Problema e público

- **RP01.** O público-alvo são pilotos de sim racing que jogam por serviço de cloud gaming, como a NVIDIA GeForce NOW e o Xbox Cloud Gaming (xCloud), ou por um serviço equivalente com a mesma restrição.
- **RP02.** O jogo executa em servidor remoto. A telemetria nativa do simulador não está disponível na máquina do piloto, e o sistema não depende dela.
- **RP03.** A fonte de dados é o vídeo do HUD de Le Mans Ultimate capturado da transmissão do cloud gaming. O sistema extrai acelerador, freio e velocidade desse painel para o piloto compor a própria telemetria e analisar o desempenho ao longo da distância percorrida.
- **RP04.** Nesta versão, a transmissão entra como arquivo de vídeo já gravado. O sistema não autentica no serviço de nuvem, não abre a sessão ao vivo e não se comunica com o processo do jogo.

### Requisitos funcionais

Estes itens são o modo como o script cumpre a extração descrita em RP03.

- **RF01.** O sistema abre, no diretório de trabalho, o arquivo `test_telemetria.mp4` com a gravação do HUD de Le Mans Ultimate capturada do stream de cloud gaming.
- **RF02.** Para cada quadro lido, o sistema estima a intensidade do acelerador pela quantidade de pixels verdes no recorte fixo linhas 585:690 e colunas 1053:1095, com HSV de `[35, 40, 40]` a `[85, 255, 255]`.
- **RF03.** Para cada quadro lido, o sistema estima a intensidade do freio pela quantidade de pixels rosa no recorte fixo linhas 575:677 e colunas 1053:1095, com HSV de `[140, 100, 100]` a `[168, 255, 255]`.
- **RF04.** O sistema lê a velocidade no recorte linhas 610:640 e colunas 1128:1212 com OCR em português e inglês, e aceita somente texto formado só por dígitos com confiança maior que 0,5.
- **RF05.** Quando o quadro não produz leitura aceita, o sistema conserva a última velocidade aceita. Até a primeira leitura aceita, a velocidade usada é 0.
- **RF06.** Se o OCR devolve mais de um texto aceito no mesmo quadro, o sistema fica com o último item dessa lista.
- **RF07.** A cada quadro, o sistema soma à distância `(velocidade_em_km/h / 3,6) * 0,033` metros.
- **RF08.** Ao terminar o vídeo, o sistema converte cada série de pixels em percentual do máximo da própria série.
- **RF09.** O sistema exibe um gráfico de linha do percentual do acelerador (verde) e do freio (vermelho) em função da distância, com o título `Telemetria`, o eixo horizontal `Distância (m)` e o eixo vertical `% aceleração/freio`.

### Requisitos não funcionais

- **RNF01.** O processamento dos quadros ocorre na máquina do piloto, em um único processo, sem parâmetros de linha de comando e sem arquivo de configuração. Nenhuma credencial de GeForce NOW, xCloud ou outro serviço é necessária, porque a entrada já é o vídeo.
- **RNF02.** Recortes, faixas HSV, idiomas do OCR, limiar de confiança e passo de tempo são constantes no código-fonte.
- **RNF03.** A única saída é a janela do Matplotlib. O script não grava PNG, CSV nem outro arquivo de resultado. A série usada na análise existe só enquanto a janela está aberta.
- **RNF04.** A instalação é a lista fixada em `requirements.txt`. O OCR acrescenta o download dos modelos na primeira execução.
- **RNF05.** O tempo de cada quadro inclui uma chamada de OCR. O hardware disponível para o PyTorch (CPU ou GPU) determina esse tempo.
- **RNF06.** O resultado numérico só se reproduz numa gravação do mesmo cliente de nuvem, com o HUD nos mesmos pixels e com duração de quadro compatível com 0,033 s. Resolução, escala da janela e compressão do stream alteram cor e nitidez dos dígitos.

### Fora do que o código faz hoje

Limites observados no script, para o autor confirmar o escopo do TCC: ele não acompanha a barra se o cliente de nuvem mudar o tamanho ou a posição do HUD, não calibra cor com amostra do piloto, não trata mais de um vídeo por execução, não exporta a série para reuso posterior, não calcula tempo de volta e não confronta a leitura com uma telemetria de referência — que, no cenário de RP02, o piloto não recebe do servidor.

## Instalação

Requisitos de sistema: Python 3.12, `pip` e espaço em disco para o PyTorch que o EasyOCR instala (vários GB). No índice padrão do PyPI o pacote binário do PyTorch inclui bibliotecas CUDA e também carrega em máquina só com CPU. Na primeira execução é preciso rede para baixar os modelos do EasyOCR.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

No Debian/Ubuntu, se `python3 -m venv` avisar que o `ensurepip` não está disponível, instale o pacote `python3-venv` da mesma versão do interpretador e crie o ambiente de novo.

## Vídeo de entrada

A entrada esperada é um vídeo do HUD de Le Mans Ultimate capturado da transmissão do cloud gaming e salvo em arquivo. O script não captura essa transmissão sozinho. Um caminho reproduzível é: jogar Le Mans Ultimate no cliente (GeForce NOW, xCloud ou equivalente), gravar a janela ou usar a gravação que o próprio cliente oferecer, e exportar o trecho em que o HUD de acelerador, freio e velocidade está visível, no mesmo enquadramento em que os recortes foram medidos.

O arquivo de entrada não está no Git. `.gitignore` ignora `test_telemetria.mp4` e nomes com esse prefixo. Coloque a gravação no diretório de onde o script será executado, com este nome exato:

```text
test_telemetria.mp4
```

O caminho no código é relativo. Executar o script de outro diretório faz o `VideoCapture` não abrir o arquivo.

### Resolução e sistema de coordenadas

Os recortes são fatias NumPy absolutas, no formato `[linha_inicial:linha_final, coluna_inicial:coluna_final]`, com origem no canto superior esquerdo do quadro e a linha crescendo para baixo. Para os três recortes existirem por inteiro, o quadro precisa ter pelo menos 1212 colunas e 690 linhas. Abaixo disso, a fatia volta vazia ou cortada e a contagem cai.

O repositório não contém o vídeo de Le Mans Ultimate usado para escolher esses números, então a resolução real dessa captura precisa ser confirmada pelo autor. Em um quadro de 1280×720, os recortes ficam no canto inferior direito: as barras por volta de 82% da largura e de 80% a 96% da altura, e os dígitos imediatamente à direita das barras. Outro tamanho de janela, outra escala do cliente de nuvem ou outro jogo deslocam o HUD e fazem os retângulos lerem o lugar errado.

### Layout que os recortes assumem

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho | Critério |
| --- | --- | --- | --- | --- |
| Acelerador | verde | `[585:690, 1053:1095]` | 105×42 px | HSV `[35, 40, 40]` a `[85, 255, 255]` |
| Freio | rosa | `[575:677, 1053:1095]` | 102×42 px | HSV `[140, 100, 100]` a `[168, 255, 255]` |
| Velocidade | dígitos | `[610:640, 1128:1212]` | 30×84 px | OCR; confiança > 0,5 e só dígitos |

As duas barras ocupam a mesma faixa de colunas (1053:1095). As linhas se sobrepõem de 585 a 677. A separação entre acelerador e freio é a cor da máscara, não uma região disjunta. Isso descreve o HUD de Le Mans Ultimate na gravação de referência. O autor deve conferir se as barras desse jogo ficam mesmo assim na captura do stream (duas barras na mesma coluna, ou uma barra que troca de cor, com caixas ligeiramente diferentes).

O número da velocidade precisa caber nesse retângulo de 30×84 pixels, em dígitos que o EasyOCR leia como texto numérico inteiro. Um rótulo com unidade (`120 km/h`), espaço ou casa decimal é rejeitado por `text.isdigit()`.

## Como executar

Com o ambiente ativado e o vídeo no diretório atual:

```bash
python leitor.py
```

Não há argumentos. A primeira chamada cria o leitor OCR e pode demorar enquanto os modelos são baixados e a rede sobe. Cada quadro seguinte passa pelo `readtext` desse recorte.

## Saída

Uma janela do Matplotlib, aberta por `plt.show()`:

- fundo escuro (`dark_background`, aplicado depois das duas chamadas a `ax.plot`);
- curva verde do acelerador e curva vermelha do freio (a máscara do freio é rosa; a linha do gráfico é vermelha);
- área sob cada curva com transparência 0,3;
- grade com transparência 0,2;
- título `Telemetria`, eixo horizontal `Distância (m)`, eixo vertical `% aceleração/freio`.

O arquivo de vídeo só é liberado depois que essa janela fecha. Nada é gravado em disco. Para guardar a figura é preciso salvá-la pela interface do Matplotlib, ou alterar o script — o que esta documentação não faz.

## Limitações

- A telemetria nativa de Le Mans Ultimate não entra no fluxo. Tudo o que o gráfico mostra foi lido do vídeo do stream.
- O script não abre a sessão na nuvem. Sem um arquivo já gravado, não há o que processar.
- Compressão, bitrate e escala do cliente de cloud gaming mudam a cor das barras e a nitidez dos dígitos. Os limiares HSV e o OCR foram ajustados a um HUD fixo, não a qualquer qualidade de transmissão.
- Os recortes e as cores são constantes. Qualquer mudança de resolução, escala da janela ou posição do HUD invalida a leitura sem um erro explicativo.
- O passo de 0,033 s aproxima o período de 30 quadros por segundo (1/30 ≈ 0,0333). Em um vídeo de 60 fps a distância fica cerca do dobro da distância real, porque o código não consulta a taxa do arquivo.
- A velocidade rejeitada não zera o valor: um dígito lido uma vez continua valendo nos quadros seguintes em que o OCR falha.
- `text.isdigit()` descarta leituras com erro típico de OCR que mistura letra e número.
- O percentual 100% é o máximo da própria gravação. Duas gravações com o mesmo pedal físico podem produzir curvas diferentes se o pico de pixels não for o mesmo. Acelerador e freio também não compartilham o mesmo máximo: cada um é normalizado pela própria série, e as caixas têm alturas diferentes (105 e 102 pixels).
- Série vazia (vídeo ausente, caminho errado ou arquivo sem quadro) chega a `np.max` de um array vazio e o script termina com erro. Máximo 0, quando a cor não aparece, produz divisão por zero na normalização.
- Não há comparação com uma telemetria de referência, então esta documentação não afirma acurácia de OCR nem de cor.
- `np.append` dentro do laço realoca as séries a cada quadro.
- A janela gráfica exige um backend interativo do Matplotlib. Em máquina sem display, `plt.show()` não apresenta o resultado.

## Diagramas

Os quatro diagramas UML pedidos na metodologia do trabalho prático estão em [`docs/diagramas`](docs/diagramas/README.md), cada um em fonte PlantUML (`.puml`) e em PNG. O diagrama de classes é um modelo lógico: o script não declara classes. Cada diagrama tem um parágrafo pronto para o capítulo de Metodologia.

## O que o autor precisa revisar

- Qual cliente de nuvem (GeForce NOW, xCloud ou outro) produziu o `test_telemetria.mp4` usado para medir os recortes. O jogo dessa captura, confirmado pelo autor, é Le Mans Ultimate; o nome não está no código.
- A redação de RP01–RP04, para o tom do TCC. O conteúdo desse bloco segue o que o autor descreveu sobre público e problema.
- A seção de justificativa das ferramentas, para que ela descreva a escolha que de fato foi feita.
- RF01–RF09 e RNF02–RNF06 nos pontos em que o número veio só do código (recortes, HSV, confiança, 0,033 s, percentual pelo máximo).
- Se a análise de desempenho precisa da série gravada em arquivo. Hoje o resultado é só a janela do gráfico.
- A resolução do `test_telemetria.mp4` e se as barras verde e rosa ocupam mesmo os retângulos da tabela, inclusive a sobreposição.
- Se 0,033 s é o período real dos quadros dessa gravação.
- Se o percentual relativo ao máximo da gravação é a grandeza que o gráfico deve mostrar, ou se a escala deveria ser a altura cheia da barra.
- Os parágrafos em `docs/diagramas/README.md` antes de colá-los na Metodologia (numeração de figuras e fonte, no padrão ABNT adotado no trabalho).
