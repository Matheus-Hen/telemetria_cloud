# Leitor de telemetria a partir do vídeo de sim racing na nuvem

Pilotos de sim racing que usam um serviço de cloud gaming jogam num servidor remoto. O jogo para o qual este leitor foi feito é **Le Mans Ultimate**, jogado no GeForce NOW. Na máquina do piloto chega o vídeo transmitido, com o painel (HUD) de Le Mans Ultimate desenhado na imagem. A telemetria nativa do simulador — API, pacote de rede ou arquivo que um jogo instalado localmente escreveria — permanece no servidor do serviço.

Este script existe para esse piloto montar a própria telemetria e analisar o desempenho a partir só desse vídeo. Ele mede as barras de acelerador e de freio pela cor, reconhece a velocidade numérica e acumula a distância. O `cloud` do nome do repositório (`telemetria_cloud`) designa esse cenário: telemetria reconstruída quando Le Mans Ultimate está na nuvem.

O programa não entra na conta do GeForce NOW e não conversa com o processo do jogo. A entrada é um arquivo de vídeo da transmissão, já gravado. O autor confirmou gravações do GeForce NOW em 1080p (1920×1080) a 30 fps; o preset `original` guarda os recortes medidos nelas. Há um segundo preset, `lmu_default_1080p`, para o HUD padrão do jogo, conferido numa captura de 1920×1080 a 60 fps. O passo de tempo é `1/fps` lido do arquivo, com reserva de 30 fps se o vídeo não informar a taxa. O repositório é a parte prática de um TCC. Este README descreve o que o código faz hoje.

## Público-alvo

Pilotos de Le Mans Ultimate que disputam a sessão no GeForce NOW e usam o vídeo transmitido para analisar a própria pilotagem. O jogo roda no servidor da NVIDIA, e a telemetria de Le Mans Ultimate não chega ao computador do piloto. O mesmo tipo de restrição aparece em outros serviços de cloud gaming, como o Xbox Cloud Gaming (xCloud); os recortes deste repositório, porém, foram medidos em gravação do GeForce NOW.

## Objetivo

Oferecer a esse piloto uma telemetria própria de análise de desempenho, extraída do HUD de Le Mans Ultimate no vídeo capturado do stream. Quadro a quadro, o sistema obtém:

- a intensidade da barra verde do acelerador;
- a intensidade da barra rosa do freio;
- a velocidade escrita em dígitos.

A velocidade é acumulada em distância com o período de um quadro (`1/fps`). No fim, o script abre um gráfico do percentual de cada barra contra a distância, ou grava esse gráfico em PNG. A série (tempo, distância, velocidade e percentuais) pode ser gravada em CSV.

A gravação do autor no GeForce NOW é 1920×1080 a 30 fps, e os recortes dessa captura estão no preset `original`. O HUD padrão do Le Mans Ultimate, com o dial no canto inferior direito, está no preset `lmu_default_1080p`, medido numa captura de 1920×1080 a 60 fps. Sem argumentos, o script abre `test_telemetria.mp4` com o preset `original`.

## Como funciona

`leitor.py` lê os argumentos, escolhe os recortes e percorre o vídeo.

1. `--config` escolhe o preset `original` ou `lmu_default_1080p`, ou um arquivo JSON com os três recortes. O padrão é `original`.
2. Cria um leitor EasyOCR para português e inglês (`easyocr.Reader(['pt', 'en'])`). Na primeira vez, a biblioteca baixa os modelos para `~/.EasyOCR/model`.
3. Abre o vídeo de `--video` (padrão: `test_telemetria.mp4`) e lê `CAP_PROP_FPS`. Se a taxa não vier ou for inválida, usa 30. O passo é `dt = 1/fps`.
4. Zera a velocidade (km/h) e a distância (m).
5. Para cada quadro, até `VideoCapture.read()` falhar:
   1. Converte o quadro de BGR para HSV.
   2. Aplica a máscara verde no recorte do acelerador e guarda a quantidade de pixels.
   3. Aplica a máscara rosa no recorte do freio e guarda a contagem do mesmo modo.
   4. Recorta a velocidade, converte de BGR para RGB e chama `readtext`.
   5. Percorre os resultados. Se a confiança é maior que `--confianca` (padrão 0,5) e `text.isdigit()` é verdadeiro, substitui a velocidade por `int(text)`. Se vários resultados do mesmo quadro passam no filtro, fica o último da lista. Se nenhum passa, a velocidade anterior permanece (0 até a primeira leitura aceita).
   6. Soma `(velocidade / 3.6) * dt` metros à distância. `velocidade / 3.6` converte km/h para m/s.
6. Divide cada série de pixels pelo próprio máximo e multiplica por 100. Se o máximo é 0, o percentual fica em 0.
7. Desenha as duas curvas contra a distância, com fundo escuro, preenchimento e grade. Sem `--headless`, abre a janela com `plt.show()`. Com `--headless`, grava o PNG e não abre janela.
8. Se `--csv` foi informado, grava a série já em percentual.

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

**EasyOCR, em lugar do Tesseract.** O HUD entrega um retângulo com um inteiro (30×84 pixels no preset `original`; 60×140 no `lmu_default_1080p`). O EasyOCR recebe a imagem RGB e devolve, para cada trecho, caixa, texto e confiança. O filtro do script (confiança acima de `--confianca`, padrão 0,5, e `text.isdigit()`) usa essa confiança diretamente, e `Reader(['pt', 'en'])` não pede um binário instalado à parte no sistema. O Tesseract, via `pytesseract`, é mais leve e é uma alternativa sólida para texto nítido, mas depende do executável do Tesseract no sistema operacional e, em dígitos pequenos de HUD, em geral pede ampliação, limiar e um modo de segmentação (`--psm`) ajustados ao recorte. Isso aumentaria etapas que este script não tem. PaddleOCR também devolve texto e confiança, com outro conjunto de modelos e uma instalação mais pesada, sem ganho claro para um único número. Casar cada dígito com um molde da fonte do HUD seria mais rápido e mais frágil a antialiasing e à troca de fonte. O EasyOCR é a biblioteca que o código chama; a comparação acima é o argumento sugerido para a Metodologia, e o autor deve confirmá-lo.

**Matplotlib.** Duas curvas, preenchimento, grade e rótulos cabem em `pyplot` e `Axes`. `plt.show()` abre a janela; `--headless` grava o mesmo gráfico em PNG, sem display. Plotly acrescentaria um gráfico interativo e um runtime de front-end que o script não usa. Seaborn organiza gráficos estatísticos em cima do Matplotlib, sem papel nas duas séries brutas. `matplotlib-inline` só altera o backend dentro do IPython e do Jupyter; este arquivo é executado como script.

**Dependências retiradas de `requirements.txt`.** `pandas` e `matplotlib-inline` não são importados. `opencv-contrib-python` não é necessário para as quatro chamadas de OpenCV do arquivo. `opencv-python` foi trocado por `opencv-python-headless==4.13.0.92` pelo conflito com a dependência do EasyOCR, descrito acima. `matplotlib` e `easyocr` foram incluídos porque o script os importa e a lista antiga não os instalava.

## Requisitos

Há dois blocos. O bloco do problema e do público registra o que o autor informou sobre para quem o trabalho existe. O bloco seguinte descreve o comportamento atual de `leitor.py`. A faixa rosa do freio foi alargada com o aval do autor depois de medir matiz por volta de 172 no HUD padrão. O verde e o limiar padrão de confiança (0,5) continuam os valores anteriores do código.

### Problema e público

- **RP01.** O público-alvo são pilotos de Le Mans Ultimate no GeForce NOW. A telemetria nativa do jogo permanece no servidor remoto, como também ocorre em outros serviços de cloud gaming.
- **RP02.** O jogo executa em servidor remoto. A telemetria nativa do simulador não está disponível na máquina do piloto, e o sistema não depende dela.
- **RP03.** A fonte de dados é o vídeo do HUD de Le Mans Ultimate gravado do GeForce NOW em 1080p (1920×1080). Os recortes foram medidos nessa resolução. O sistema extrai acelerador, freio e velocidade desse painel para o piloto compor a própria telemetria e analisar o desempenho ao longo da distância percorrida.
- **RP04.** Nesta versão, a transmissão entra como arquivo de vídeo já gravado. O sistema não autentica no serviço de nuvem, não abre a sessão ao vivo e não se comunica com o processo do jogo.

### Requisitos funcionais

Estes itens são o modo como o script cumpre a extração descrita em RP03.

- **RF01.** O sistema abre o vídeo indicado em `--video`. Sem o argumento, abre `test_telemetria.mp4`.
- **RF02.** Para cada quadro, o sistema estima o acelerador pela quantidade de pixels verdes no recorte do preset ou do JSON, com HSV de `[35, 40, 40]` a `[85, 255, 255]`.
- **RF03.** Para cada quadro, o sistema estima o freio pela quantidade de pixels rosa no recorte correspondente, com HSV de `[140, 80, 80]` a `[179, 255, 255]`.
- **RF04.** O sistema lê a velocidade no recorte escolhido, com OCR em português e inglês, e aceita somente texto formado só por dígitos com confiança maior que `--confianca` (padrão 0,5).
- **RF05.** Quando o quadro não produz leitura aceita, o sistema conserva a última velocidade aceita. Até a primeira leitura aceita, a velocidade usada é 0.
- **RF06.** Se o OCR devolve mais de um texto aceito no mesmo quadro, o sistema fica com o último item dessa lista.
- **RF07.** A cada quadro, o sistema soma à distância `(velocidade_em_km/h / 3,6) * (1/fps)` metros. A taxa vem de `CAP_PROP_FPS`. Se ela falta ou é inválida, o sistema usa 30 fps.
- **RF08.** Ao terminar o vídeo, o sistema converte cada série de pixels em percentual do máximo da própria série. Máximo 0 vira percentual 0.
- **RF09.** O sistema exibe, ou grava em PNG com `--headless`, um gráfico de linha do percentual do acelerador (verde) e do freio (vermelho) em função da distância, com o título `Telemetria`, o eixo horizontal `Distância (m)` e o eixo vertical `% aceleração/freio`.
- **RF10.** Com `--csv`, o sistema grava `tempo_s`, `distancia_m`, `velocidade_kmh`, `acelerador_pct` e `freio_pct`.

### Requisitos não funcionais

- **RNF01.** O processamento dos quadros ocorre na máquina do piloto, em um único processo. Nenhuma credencial do GeForce NOW é necessária, porque a entrada já é o vídeo gravado.
- **RNF02.** As faixas HSV e os idiomas do OCR são constantes no código. Recortes, limiar de confiança, vídeo, PNG e CSV entram pela linha de comando.
- **RNF03.** Sem `--headless`, a saída do gráfico é a janela do Matplotlib. Com `--headless`, o gráfico vai para um PNG. O CSV é opcional.
- **RNF04.** A instalação é a lista fixada em `requirements.txt`. O OCR acrescenta o download dos modelos na primeira execução. Argumentos, CSV e JSON usam a biblioteca padrão.
- **RNF05.** O tempo de cada quadro inclui uma chamada de OCR. O hardware disponível para o PyTorch (CPU ou GPU) determina esse tempo.
- **RNF06.** Cada preset vale para o enquadramento em que foi medido, em 1920×1080. Outra resolução ou outra escala da janela desloca o HUD. A compressão do stream altera cor e nitidez dos dígitos. A distância acompanha a taxa gravada no arquivo.

### Fora do que o código faz hoje

Limites do script: ele não acompanha a barra se o HUD mudar de lugar entre um preset e outro (é preciso trocar `--config`), não trata mais de um vídeo por execução, não calcula tempo de volta e não confronta a leitura com uma telemetria de referência — que, no cenário de RP02, o piloto não recebe do servidor. O arco vermelho de RPM do HUD padrão pode cair na faixa rosa e inflar o freio em alguns quadros.

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

O script não captura a transmissão. Grave a sessão e passe o arquivo em `--video`.

Há dois enquadramentos de 1920×1080 já descritos no código:

- **`original`.** Recortes medidos na gravação do autor no GeForce NOW, a 30 fps. As barras de acelerador e de freio ocupam a mesma coluna.
- **`lmu_default_1080p`.** HUD padrão do Le Mans Ultimate: dial circular no canto inferior direito. O freio (rosa) fica à esquerda do acelerador (verde), no arco esquerdo do dial. A velocidade numérica fica à direita das barras. Este preset foi conferido numa captura de 1920×1080 a 60 fps.

Para repetir a gravação do autor: jogar Le Mans Ultimate no GeForce NOW em 1920×1080 a 30 fps, gravar sem redimensionar e usar `--config original`. Para o HUD padrão na posição do preset novo, a captura também precisa ser 1920×1080, e a taxa pode ser outra: o script lê o FPS do arquivo. Num arquivo de 30 fps, `1/fps` vale cerca de 0,0333 s e substitui a constante antiga `0.033`. Num arquivo de 60 fps, o passo é 1/60 s.

O arquivo de exemplo do autor não está no Git. `.gitignore` ignora `test_telemetria.mp4` e nomes com esse prefixo. Sem `--video`, o script procura `test_telemetria.mp4` no diretório de trabalho.

### Resolução e sistema de coordenadas

Os recortes são fatias absolutas, no formato `[linha_inicial:linha_final, coluna_inicial:coluna_final]`, com origem no canto superior esquerdo e a linha crescendo para baixo. Um quadro menor que o fim do recorte corta a fatia e a contagem cai.

### Preset `original`

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho |
| --- | --- | --- | --- |
| Acelerador | verde | `[585:690, 1053:1095]` | 105×42 px |
| Freio | rosa | `[575:677, 1053:1095]` | 102×42 px |
| Velocidade | dígitos | `[610:640, 1128:1212]` | 30×84 px |

As duas barras compartilham as colunas 1053:1095 e se sobrepõem nas linhas 585:677. A cor separa as séries. Em 1920×1080 esses retângulos ficam um pouco à direita do centro e um pouco abaixo do meio do quadro.

### Preset `lmu_default_1080p`

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho |
| --- | --- | --- | --- |
| Acelerador | verde | `[880:1020, 1590:1615]` | 140×25 px |
| Freio | rosa | `[850:1020, 1565:1592]` | 170×27 px |
| Velocidade | dígitos | `[910:970, 1650:1790]` | 60×140 px |

O freio ocupa as colunas 1565:1592 e o acelerador as colunas 1590:1615: lado a lado, freio à esquerda. Os dois se encostam em duas colunas. A velocidade fica imediatamente à direita.

A faixa verde é HSV `[35, 40, 40]` a `[85, 255, 255]`. A faixa rosa é HSV `[140, 80, 80]` a `[179, 255, 255]`, nos dois presets. O limite antigo de matiz 168 deixava o freio do HUD padrão quase vazio, porque a barra medida fica em torno de 172.

O OCR só aceita texto formado só por dígitos. Um rótulo com unidade (`163 KPH` num único trecho), espaço ou casa decimal é rejeitado por `text.isdigit()`.

### JSON próprio

`--config` também aceita um arquivo. As quatro posições são linha inicial, linha final, coluna inicial e coluna final.

```json
{
  "acelerador": [880, 1020, 1590, 1615],
  "freio": [850, 1020, 1565, 1592],
  "velocidade": [910, 970, 1650, 1790]
}
```

## Como executar

Com o ambiente ativado, a gravação do GeForce NOW no preset original:

```bash
python leitor.py --video test_telemetria.mp4 --config original
```

O mesmo comando sem argumentos procura `test_telemetria.mp4` e usa `original`.

HUD padrão, gráfico em PNG e série em CSV, sem janela:

```bash
python leitor.py \
  --video gravacao.mp4 \
  --config lmu_default_1080p \
  --headless \
  --png telemetria.png \
  --csv telemetria.csv
```

Confiança mínima diferente da padrão:

```bash
python leitor.py --video gravacao.mp4 --config lmu_default_1080p --confianca 0.4 --headless
```

Recortes num arquivo:

```bash
python leitor.py --video gravacao.mp4 --config meus_rois.json --headless --csv telemetria.csv
```

A primeira chamada cria o leitor OCR e pode demorar enquanto os modelos são baixados. Cada quadro passa por `readtext`. Ao terminar, o script imprime a taxa lida, o passo `dt`, a quantidade de quadros e o config usado.

## Saída

Sem `--headless`, uma janela do Matplotlib. Com `--headless`, um PNG no caminho de `--png` (padrão `telemetria.png`):

- fundo escuro;
- curva verde do acelerador e curva vermelha do freio (a máscara do freio é rosa; a linha do gráfico é vermelha);
- área sob cada curva com transparência 0,3;
- grade com transparência 0,2;
- título `Telemetria`, eixo horizontal `Distância (m)`, eixo vertical `% aceleração/freio`.

O CSV, quando pedido, tem o cabeçalho `tempo_s,distancia_m,velocidade_kmh,acelerador_pct,freio_pct`. Tempo e distância usam o `dt` do arquivo. A velocidade é a última leitura aceita naquele quadro. Os percentuais já estão normalizados pelo máximo da gravação.

## Limitações

- A telemetria nativa de Le Mans Ultimate não entra no fluxo. O gráfico mostra o que foi lido do vídeo.
- O script não abre a sessão na nuvem. Sem um arquivo já gravado, não há o que processar.
- Cada preset vale para um enquadramento. `original` e `lmu_default_1080p` não são intercambiáveis: no HUD padrão, os recortes antigos não caem nas barras.
- O arco vermelho de RPM pode invadir a faixa rosa e contar como freio em alguns quadros do HUD padrão.
- Compressão e bitrate do stream mudam a cor das barras e a nitidez dos dígitos.
- Outra resolução ou outra escala da janela desloca o HUD e os recortes leem o lugar errado.
- A distância usa `1/fps` do arquivo. Se o contêiner mente a taxa, a distância sai na mesma proporção. Sem taxa válida, o passo assume 30 fps.
- A velocidade rejeitada não zera o valor: um dígito lido uma vez continua valendo nos quadros seguintes em que o OCR falha.
- `text.isdigit()` descarta leitura com letra, espaço ou unidade no mesmo trecho.
- O percentual 100% é o máximo da própria gravação. Acelerador e freio não compartilham o mesmo máximo.
- Vídeo ausente ou sem quadros encerra o script com uma mensagem. Máximo de pixels igual a 0 vira percentual 0, sem divisão por zero.
- Não há comparação automática com uma telemetria de referência.
- Sem `--headless`, a janela exige um backend interativo do Matplotlib.

## Diagramas

Os quatro diagramas UML pedidos na metodologia do trabalho prático estão em [`docs/diagramas`](docs/diagramas/README.md), cada um em fonte PlantUML (`.puml`) e em PNG. O diagrama de classes é um modelo lógico: o script não declara classes. Cada diagrama tem um parágrafo pronto para o capítulo de Metodologia. Eles descrevem o fluxo com preset, taxa lida do vídeo, máscaras, OCR e a saída em janela, PNG ou CSV.

## O que o autor precisa revisar

- A redação de RP01–RP04, para o tom do TCC. Já estão confirmados o jogo (Le Mans Ultimate), o GeForce NOW em 1920×1080 a 30 fps para o preset `original`, e o HUD padrão em 1920×1080 a 60 fps para o preset `lmu_default_1080p`.
- A seção de justificativa das ferramentas, para que ela descreva a escolha que de fato foi feita.
- A faixa verde e o limiar padrão 0,5. A faixa rosa `[140, 80, 80]`–`[179, 255, 255]` foi a correção aprovada para a matiz medida perto de 172.
- Se o percentual relativo ao máximo da gravação é a grandeza que o gráfico deve mostrar, ou se a escala deveria ser a altura cheia da barra.
- Os parágrafos em `docs/diagramas/README.md` antes de colá-los na Metodologia (numeração de figuras e fonte, no padrão ABNT adotado no trabalho).
