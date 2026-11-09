# Leitor de telemetria a partir do vídeo de sim racing na nuvem

Pilotos de sim racing que usam um serviço de cloud gaming jogam num servidor remoto. O jogo para o qual este leitor foi feito é **Le Mans Ultimate**, jogado no GeForce NOW. Na máquina do piloto chega o vídeo transmitido, com o painel (HUD) de Le Mans Ultimate desenhado na imagem. A telemetria nativa do simulador — API, pacote de rede ou arquivo que um jogo instalado localmente escreveria — permanece no servidor do serviço.

Este script existe para esse piloto montar a própria telemetria e analisar o desempenho a partir só desse vídeo. Ele mede as barras de acelerador e de freio pela cor, reconhece a velocidade numérica e acumula a distância. O `cloud` do nome do repositório (`telemetria_cloud`) designa esse cenário: telemetria reconstruída quando Le Mans Ultimate está na nuvem.

O programa não entra na conta do GeForce NOW e não conversa com o processo do jogo. A entrada é um arquivo de vídeo da transmissão, já gravado. O autor confirmou que esses vídeos são gravados do GeForce NOW em 1080p (1920×1080) e que os recortes do HUD foram medidos nessa resolução. O repositório é a parte prática de um TCC. Este README descreve o que o código faz hoje, com detalhe suficiente para outra pessoa repetir o processamento. Faixas de cor, limiar do OCR e o passo de tempo continuam lidos do código e seguem marcados para revisão.

## Público-alvo

Pilotos de Le Mans Ultimate que disputam a sessão no GeForce NOW e usam o vídeo transmitido para analisar a própria pilotagem. O jogo roda no servidor da NVIDIA, e a telemetria de Le Mans Ultimate não chega ao computador do piloto. O mesmo tipo de restrição aparece em outros serviços de cloud gaming, como o Xbox Cloud Gaming (xCloud); os recortes deste repositório, porém, foram medidos em gravação do GeForce NOW.

## Objetivo

Oferecer a esse piloto uma telemetria própria de análise de desempenho, extraída do HUD de Le Mans Ultimate no vídeo capturado do stream. Quadro a quadro, o sistema obtém:

- a intensidade da barra verde do acelerador;
- a intensidade da barra rosa do freio;
- a velocidade escrita em dígitos.

A velocidade é acumulada em distância. No fim, o script abre um gráfico com o percentual de cada barra no eixo vertical e a distância, em metros, no eixo horizontal. Essa figura é o artefato de análise que o código produz hoje. A série numérica não é gravada em arquivo.

A entrada esperada é um vídeo do HUD de Le Mans Ultimate gravado do GeForce NOW em 1080p (1920×1080). O autor confirmou essa origem e confirmou que os recortes foram medidos em quadros dessa resolução. O nome do jogo e o do serviço não aparecem em `leitor.py`: o script só abre `test_telemetria.mp4`.

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

- **RP01.** O público-alvo são pilotos de Le Mans Ultimate no GeForce NOW. A telemetria nativa do jogo permanece no servidor remoto, como também ocorre em outros serviços de cloud gaming.
- **RP02.** O jogo executa em servidor remoto. A telemetria nativa do simulador não está disponível na máquina do piloto, e o sistema não depende dela.
- **RP03.** A fonte de dados é o vídeo do HUD de Le Mans Ultimate gravado do GeForce NOW em 1080p (1920×1080). Os recortes foram medidos nessa resolução. O sistema extrai acelerador, freio e velocidade desse painel para o piloto compor a própria telemetria e analisar o desempenho ao longo da distância percorrida.
- **RP04.** Nesta versão, a transmissão entra como arquivo de vídeo já gravado. O sistema não autentica no serviço de nuvem, não abre a sessão ao vivo e não se comunica com o processo do jogo.

### Requisitos funcionais

Estes itens são o modo como o script cumpre a extração descrita em RP03.

- **RF01.** O sistema abre, no diretório de trabalho, o arquivo `test_telemetria.mp4` com a gravação do HUD de Le Mans Ultimate feita no GeForce NOW em 1920×1080.
- **RF02.** Para cada quadro lido, o sistema estima a intensidade do acelerador pela quantidade de pixels verdes no recorte fixo linhas 585:690 e colunas 1053:1095, com HSV de `[35, 40, 40]` a `[85, 255, 255]`.
- **RF03.** Para cada quadro lido, o sistema estima a intensidade do freio pela quantidade de pixels rosa no recorte fixo linhas 575:677 e colunas 1053:1095, com HSV de `[140, 100, 100]` a `[168, 255, 255]`.
- **RF04.** O sistema lê a velocidade no recorte linhas 610:640 e colunas 1128:1212 com OCR em português e inglês, e aceita somente texto formado só por dígitos com confiança maior que 0,5.
- **RF05.** Quando o quadro não produz leitura aceita, o sistema conserva a última velocidade aceita. Até a primeira leitura aceita, a velocidade usada é 0.
- **RF06.** Se o OCR devolve mais de um texto aceito no mesmo quadro, o sistema fica com o último item dessa lista.
- **RF07.** A cada quadro, o sistema soma à distância `(velocidade_em_km/h / 3,6) * 0,033` metros.
- **RF08.** Ao terminar o vídeo, o sistema converte cada série de pixels em percentual do máximo da própria série.
- **RF09.** O sistema exibe um gráfico de linha do percentual do acelerador (verde) e do freio (vermelho) em função da distância, com o título `Telemetria`, o eixo horizontal `Distância (m)` e o eixo vertical `% aceleração/freio`.

### Requisitos não funcionais

- **RNF01.** O processamento dos quadros ocorre na máquina do piloto, em um único processo, sem parâmetros de linha de comando e sem arquivo de configuração. Nenhuma credencial do GeForce NOW é necessária, porque a entrada já é o vídeo gravado.
- **RNF02.** Recortes, faixas HSV, idiomas do OCR, limiar de confiança e passo de tempo são constantes no código-fonte.
- **RNF03.** A única saída é a janela do Matplotlib. O script não grava PNG, CSV nem outro arquivo de resultado. A série usada na análise existe só enquanto a janela está aberta.
- **RNF04.** A instalação é a lista fixada em `requirements.txt`. O OCR acrescenta o download dos modelos na primeira execução.
- **RNF05.** O tempo de cada quadro inclui uma chamada de OCR. O hardware disponível para o PyTorch (CPU ou GPU) determina esse tempo.
- **RNF06.** O resultado numérico foi definido para gravação do GeForce NOW em 1920×1080, com os recortes medidos nessa resolução, e para uma duração de quadro compatível com 0,033 s. Outra resolução, outra escala da janela ou outro cliente desloca o HUD. A compressão do stream altera cor e nitidez dos dígitos.

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

A entrada esperada é um vídeo do HUD de Le Mans Ultimate gravado do GeForce NOW em 1080p (1920×1080). O autor confirmou essa resolução e confirmou que os recortes foram medidos nela. O script não captura a transmissão sozinho. Um caminho reproduzível é: jogar Le Mans Ultimate no GeForce NOW com a sessão em 1920×1080, gravar essa imagem e exportar o trecho em que o HUD de acelerador, freio e velocidade está visível, sem redimensionar o quadro.

O arquivo de entrada não está no Git. `.gitignore` ignora `test_telemetria.mp4` e nomes com esse prefixo. Coloque a gravação no diretório de onde o script será executado, com este nome exato:

```text
test_telemetria.mp4
```

O caminho no código é relativo. Executar o script de outro diretório faz o `VideoCapture` não abrir o arquivo.

### Resolução e sistema de coordenadas

Os recortes são fatias NumPy absolutas, no formato `[linha_inicial:linha_final, coluna_inicial:coluna_final]`, com origem no canto superior esquerdo do quadro e a linha crescendo para baixo. Foram medidos em quadros de 1920×1080 gravados do GeForce NOW. Nessa resolução, as barras ficam um pouco à direita do centro e um pouco abaixo do meio do quadro: as colunas 1053 a 1212 ocupam cerca de 55% a 63% da largura, e as linhas 575 a 690 ocupam cerca de 53% a 64% da altura. Os dígitos da velocidade ficam imediatamente à direita das barras.

Um quadro menor que 1212×690 deixa alguma fatia vazia ou cortada e a contagem cai. Outra resolução, outra escala da janela do GeForce NOW ou outro jogo desloca o HUD e faz os mesmos números lerem o lugar errado. O arquivo de exemplo não está no repositório.

### Layout que os recortes assumem

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho | Critério |
| --- | --- | --- | --- | --- |
| Acelerador | verde | `[585:690, 1053:1095]` | 105×42 px | HSV `[35, 40, 40]` a `[85, 255, 255]` |
| Freio | rosa | `[575:677, 1053:1095]` | 102×42 px | HSV `[140, 100, 100]` a `[168, 255, 255]` |
| Velocidade | dígitos | `[610:640, 1128:1212]` | 30×84 px | OCR; confiança > 0,5 e só dígitos |

As duas barras ocupam a mesma faixa de colunas (1053:1095). As linhas se sobrepõem de 585 a 677. A separação entre acelerador e freio é a cor da máscara, não uma região disjunta. Esses retângulos são os que o autor mediu no HUD de Le Mans Ultimate em 1920×1080.

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
- Compressão e bitrate do GeForce NOW mudam a cor das barras e a nitidez dos dígitos. Os limiares HSV e o OCR foram ajustados ao HUD de Le Mans Ultimate nessa gravação de 1920×1080.
- Os recortes e as cores são constantes, medidos em 1080p. Outra resolução ou outra escala da janela do GeForce NOW invalida a leitura sem um erro explicativo.
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

- A redação de RP01–RP04, para o tom do TCC. O conteúdo desse bloco segue o que o autor descreveu. Já estão confirmados o jogo (Le Mans Ultimate), o cliente (GeForce NOW) e a resolução em que os recortes foram medidos (1920×1080).
- A seção de justificativa das ferramentas, para que ela descreva a escolha que de fato foi feita.
- As faixas HSV e o limiar de confiança do OCR. Esses números estão no código e ainda não foram confirmados como escolha de projeto.
- Se a análise de desempenho precisa da série gravada em arquivo. Hoje o resultado é só a janela do gráfico.
- Se 0,033 s é o período real dos quadros dessa gravação.
- Se o percentual relativo ao máximo da gravação é a grandeza que o gráfico deve mostrar, ou se a escala deveria ser a altura cheia da barra.
- Os parágrafos em `docs/diagramas/README.md` antes de colá-los na Metodologia (numeração de figuras e fonte, no padrão ABNT adotado no trabalho).
