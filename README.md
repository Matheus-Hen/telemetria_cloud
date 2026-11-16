# Leitor de telemetria a partir do vídeo de sim racing na nuvem

Pilotos de sim racing que usam um serviço de cloud gaming jogam num servidor remoto. O jogo para o qual este leitor foi feito é **Le Mans Ultimate**, jogado no GeForce NOW. Na máquina do piloto chega o vídeo transmitido, com o painel (HUD) de Le Mans Ultimate desenhado na imagem. A telemetria nativa do simulador — API, pacote de rede ou arquivo que um jogo instalado localmente escreveria — permanece no servidor do serviço.

Este script existe para esse piloto montar a própria telemetria e analisar o desempenho a partir só desse vídeo. Ele mede as barras de acelerador e de freio pela cor, reconhece a velocidade numérica e acumula a distância. O `cloud` do nome do repositório (`telemetria_cloud`) designa esse cenário: telemetria reconstruída quando Le Mans Ultimate está na nuvem.

O programa não entra na conta do GeForce NOW e não conversa com o processo do jogo. A entrada é um arquivo de vídeo da transmissão, já gravado. O autor confirmou a captura real no GeForce NOW, gravada no OBS em Le Mans Ultimate (Fuji Speedway), em 1280×720 a 30 fps; o preset `lmu_gfn_720p` guarda esses recortes. O preset `lmu_default_1080p` é outro enquadramento, o HUD padrão conferido numa captura de 1920×1080 a 60 fps. O passo de tempo é `1/fps` lido do arquivo, com reserva de 30 fps se o vídeo não informar a taxa. O repositório é a parte prática de um TCC. Este README descreve o que o código faz hoje.

## Público-alvo

Pilotos de Le Mans Ultimate que disputam a sessão no GeForce NOW e usam o vídeo transmitido para analisar a própria pilotagem. O jogo roda no servidor da NVIDIA, e a telemetria de Le Mans Ultimate não chega ao computador do piloto. O mesmo tipo de restrição aparece em outros serviços de cloud gaming, como o Xbox Cloud Gaming (xCloud). Os recortes da captura do autor foram medidos no GeForce NOW em 1280×720.

## Objetivo

Oferecer a esse piloto uma telemetria própria de análise de desempenho, extraída do HUD de Le Mans Ultimate no vídeo capturado do stream. Quadro a quadro, o sistema obtém:

- a intensidade da barra verde do acelerador;
- a intensidade da barra rosa do freio;
- a velocidade escrita em dígitos.

A velocidade é acumulada em distância com o período de um quadro (`1/fps`). No fim, o script abre um gráfico do percentual de cada barra contra a distância, ou grava esse gráfico em PNG. A série (tempo, distância, velocidade e percentuais) pode ser gravada em CSV.

A gravação do autor no GeForce NOW é 1280×720 a 30 fps, e os recortes dessa captura estão no preset `lmu_gfn_720p`. O HUD padrão do Le Mans Ultimate, com o dial no canto inferior direito, está no preset `lmu_default_1080p`, medido numa captura de 1920×1080 a 60 fps. O preset `original` conserva as coordenadas da primeira versão do script. Sem argumentos, o script abre `test_telemetria.mp4` com o preset `lmu_gfn_720p` (padrão desde a revisão pós-banca; antes era `original`).

## Como funciona

`leitor.py` lê os argumentos, escolhe os recortes e percorre o vídeo.

1. `--config` escolhe o preset `original`, `lmu_gfn_720p` ou `lmu_default_1080p`, ou um arquivo JSON com os três recortes (e, opcionalmente, `area_acelerador` e `area_freio`). O padrão é `lmu_gfn_720p`. Se um recorte não tiver nenhum pixel da cor esperada em todo o vídeo, o script avisa no stderr que o preset provavelmente não corresponde à gravação.
2. Cria um leitor EasyOCR para português e inglês (`easyocr.Reader(['pt', 'en'])`). Na primeira vez, a biblioteca baixa os modelos para `~/.EasyOCR/model`.
3. Abre o vídeo de `--video` (padrão: `test_telemetria.mp4`) e lê `CAP_PROP_FPS`. Se a taxa não vier ou for inválida, usa 30. O passo é `dt = 1/fps`.
4. Zera a velocidade (km/h) e a distância (m).
5. Para cada quadro, até `VideoCapture.read()` falhar:
   1. Converte o quadro de BGR para HSV.
   2. Aplica a máscara verde no recorte do acelerador e guarda a quantidade de pixels.
   3. Aplica a máscara rosa no recorte do freio e guarda a contagem do mesmo modo.
   4. Recorta a velocidade, converte de BGR para RGB e chama `readtext`.
   5. Percorre os resultados. Se a confiança é maior que `--confianca` (padrão 0,5), `text.isdigit()` é verdadeiro, o valor está entre 0 e `--vel-max` (padrão 400 km/h) e não difere da última leitura aceita em mais de `--salto-max` (padrão 15 km/h) por quadro decorrido desde ela, substitui a velocidade por `int(text)`. Depois de 15 rejeições seguidas por salto, a próxima leitura dentro da faixa é aceita, para o filtro não ficar preso a um valor errado. Cada quadro recebe um status no CSV (`aceito`, `sem_leitura`, `rejeitado_confianca`, `rejeitado_nao_numerico`, `rejeitado_faixa` ou `rejeitado_salto`), e a contagem de cada status é impressa no fim da execução. Se vários resultados do mesmo quadro passam no filtro, fica o último da lista. Se nenhum passa, a velocidade anterior permanece (0 até a primeira leitura aceita).
   6. Soma `(velocidade / 3.6) * dt` metros à distância. `velocidade / 3.6` converte km/h para m/s.
6. Converte cada série de pixels em percentual com `--normalizacao`: `p99` (padrão) divide pelo percentil 99 da própria série e limita a 100; `max` divide pelo máximo (comportamento da primeira versão); `fixa` divide por `area_acelerador`/`area_freio` do preset. Se a referência é 0, o percentual fica em 0.
7. Desenha as duas curvas contra a distância, com fundo escuro, preenchimento e grade. Sem `--headless`, abre a janela com `plt.show()`. Com `--headless`, grava o PNG e não abre janela.
8. Se `--csv` foi informado, grava a série já em percentual.

O percentual de cada barra é relativo ao percentil 99 daquela série, naquela gravação: pressupõe que a gravação tenha acionamentos plenos. Com `max`, um único quadro atípico (por exemplo, pixels da pista dentro do recorte) comprime todas as outras leituras; foi o que ocorreu com o recorte original do freio em `lmu_gfn_720p`, que alcançava a zebra vermelha e branca da pista acima do dial.

## Tecnologias e justificativa

O texto desta seção é uma justificativa reconstruída a partir do que o script importa e do que cada biblioteca entrega nesse uso. Está escrito para o autor conferir, ajustar e, se for o caso, assumir no capítulo de Metodologia. Não é um registro de uma decisão que esteja documentada em outro lugar do repositório.

| Ferramenta | Versão fixada | Papel neste script |
| --- | --- | --- |
| Python | 3.13 (avaliação do TCC) | Executa o processamento de ponta a ponta |
| OpenCV (`opencv-python-headless`) | 4.13.0.92 | Abre o vídeo, converte cor, recorta e conta pixels da máscara |
| NumPy | 2.5.0 | Guarda as séries e fornece os limites HSV |
| EasyOCR | 1.7.2 | Lê os dígitos da velocidade e devolve a confiança |
| Matplotlib | 3.10.7 | Desenha e exibe o gráfico |
| PyTorch e torchvision | transitivas do EasyOCR | Rede do OCR; não são chamadas direto pelo script |

**Python.** O processamento é um laço sobre quadros, com pouca interface. Python concentra OpenCV, OCR e gráfico no mesmo arquivo, que é o formato deste repositório. C++ com OpenCV reduziria o tempo por quadro e aumentaria o código de ligação com o OCR. MATLAB lê vídeo e plota com poucas linhas, com licença e um ambiente menos direto de reproduzir fora da instituição. Para um script único de extração e figura, Python é a opção que o código já adota.

**OpenCV.** `VideoCapture`, `cvtColor`, `inRange` e `countNonZero` cobrem a leitura do arquivo e a segmentação por cor no espaço HSV, que separa a tinta da barra do brilho do quadro. Scikit-image trata imagem estática e não abre o vídeo. Pillow não oferece captura de vídeo. Chamar o FFmpeg à parte e operar só com NumPy repetiria o que o OpenCV já faz no recorte e na máscara. O pacote instalado é o `opencv-python-headless`, na mesma versão 4.13.0.92 que o repositório já fixava: a API usada é a do módulo principal, a janela do resultado é do Matplotlib, e o EasyOCR depende do pacote headless. Manter `opencv-python` ou `opencv-contrib-python` junto com o headless instala dois módulos `cv2` no mesmo ambiente e a importação deixa de ser confiável. Nenhum algoritmo exclusivo do contrib (rastreadores, ArUco, e outros) aparece em `leitor.py`.

**NumPy.** As três séries crescem com `np.append`, e os limites de cor são arrays de três valores. Listas Python bastariam para centenas de quadros e evitariam o custo de realocar o array a cada `append`; o script, porém, já entrega esses dados ao Matplotlib como array. Pandas criaria um `DataFrame` que o gráfico não usa. A versão 2.5.0 foi mantida porque já estava fixada e é compatível com as outras versões desta lista.

**EasyOCR, em lugar do Tesseract.** O HUD entrega um retângulo com um inteiro (47×95 pixels no preset `lmu_gfn_720p`; 30×84 no `original`; 60×140 no `lmu_default_1080p`). O EasyOCR recebe a imagem RGB e devolve, para cada trecho, caixa, texto e confiança. O filtro do script (confiança acima de `--confianca`, padrão 0,5, e `text.isdigit()`) usa essa confiança diretamente, e `Reader(['pt', 'en'])` não pede um binário instalado à parte no sistema. O Tesseract, via `pytesseract`, é mais leve e é uma alternativa sólida para texto nítido, mas depende do executável do Tesseract no sistema operacional e, em dígitos pequenos de HUD, em geral pede ampliação, limiar e um modo de segmentação (`--psm`) ajustados ao recorte. Isso aumentaria etapas que este script não tem. PaddleOCR também devolve texto e confiança, com outro conjunto de modelos e uma instalação mais pesada, sem ganho claro para um único número. Casar cada dígito com um molde da fonte do HUD seria mais rápido e mais frágil a antialiasing e à troca de fonte. O EasyOCR é a biblioteca que o código chama; a comparação acima é o argumento sugerido para a Metodologia, e o autor deve confirmá-lo.

**Matplotlib.** Duas curvas, preenchimento, grade e rótulos cabem em `pyplot` e `Axes`. `plt.show()` abre a janela; `--headless` grava o mesmo gráfico em PNG, sem display. Plotly acrescentaria um gráfico interativo e um runtime de front-end que o script não usa. Seaborn organiza gráficos estatísticos em cima do Matplotlib, sem papel nas duas séries brutas. `matplotlib-inline` só altera o backend dentro do IPython e do Jupyter; este arquivo é executado como script.

**Dependências retiradas de `requirements.txt`.** `pandas` e `matplotlib-inline` não são importados. `opencv-contrib-python` não é necessário para as quatro chamadas de OpenCV do arquivo. `opencv-python` foi trocado por `opencv-python-headless==4.13.0.92` pelo conflito com a dependência do EasyOCR, descrito acima. `matplotlib` e `easyocr` foram incluídos porque o script os importa e a lista antiga não os instalava.

## Requisitos

Há dois blocos. O bloco do problema e do público registra o que o autor informou sobre para quem o trabalho existe. O bloco seguinte descreve o comportamento atual de `leitor.py`. A faixa rosa do freio foi alargada com o aval do autor depois de medir matiz por volta de 172 no HUD padrão. O verde e o limiar padrão de confiança (0,5) continuam os valores anteriores do código.

### Problema e público

- **RP01.** O público-alvo são pilotos de Le Mans Ultimate no GeForce NOW. A telemetria nativa do jogo permanece no servidor remoto, como também ocorre em outros serviços de cloud gaming.
- **RP02.** O jogo executa em servidor remoto. A telemetria nativa do simulador não está disponível na máquina do piloto, e o sistema não depende dela.
- **RP03.** A fonte de dados é o vídeo do HUD de Le Mans Ultimate gravado do GeForce NOW em 1280×720 a 30 fps. Os recortes dessa captura estão no preset `lmu_gfn_720p`. O sistema extrai acelerador, freio e velocidade desse painel para o piloto compor a própria telemetria e analisar o desempenho ao longo da distância percorrida.
- **RP04.** Nesta versão, a transmissão entra como arquivo de vídeo já gravado. O sistema não autentica no serviço de nuvem, não abre a sessão ao vivo e não se comunica com o processo do jogo.

### Requisitos funcionais

A numeração segue o capítulo de metodologia do TCC.

- **RF01.** O sistema abre o arquivo de vídeo com a gravação do HUD do Le Mans Ultimate capturada da transmissão. Sem `--video`, abre `test_telemetria.mp4`.
- **RF02.** Para cada quadro, o sistema estima a intensidade do acelerador pela quantidade de pixels verdes em uma região fixa do HUD (HSV `[35, 40, 40]` a `[85, 255, 255]`).
- **RF03.** Para cada quadro, o sistema estima a intensidade do freio pela quantidade de pixels rosa em uma região fixa do HUD (HSV `[140, 80, 80]` a `[179, 255, 255]`), delimitada de modo a não incluir a imagem da pista. No preset `lmu_gfn_720p` o recorte é `[582:681, 1063:1082]`.
- **RF04.** O sistema lê a velocidade por OCR em uma região fixa, aceitando apenas texto composto exclusivamente por dígitos, com confiança superior a 0,5, com valor na faixa plausível de 0 a 400 km/h e com variação de no máximo 15 km/h por quadro decorrido desde a última leitura aceita. O motivo de cada rejeição é registrado.
- **RF05.** Quando um quadro não produz leitura aceita, o sistema conserva a última velocidade aceita e adota 0 até a primeira leitura válida.
- **RF06.** Quando o OCR devolve mais de um texto aceito no mesmo quadro, o sistema adota o último da lista.
- **RF07.** A cada quadro, o sistema acumula a distância percorrida a partir da velocidade: `(velocidade_em_km/h / 3,6) * (1/fps)` metros. A taxa vem de `CAP_PROP_FPS`; se falta ou é inválida, usa 30 fps.
- **RF08.** Ao término do vídeo, o sistema converte cada série de pixels em percentual de uma referência: por padrão, o percentil 99 da própria série; opcionalmente, o máximo da série ou uma área fixa da barra plena informada na configuração. O percentual é limitado a 100%. Referência 0 vira percentual 0.
- **RF09.** O sistema exibe um gráfico com os percentuais de acelerador (verde) e de freio (vermelho) em função da distância, em metros. Com `--headless`, o mesmo gráfico é gravado em PNG.
- **RF10.** O sistema separa as voltas pelo cronômetro da volta atual exibido no HUD, gravando cada volta válida em um arquivo próprio, com a distância reiniciada em zero, e um resumo de todas as voltas. Não grava a volta em que o cronômetro desaparece por tempo prolongado, a volta em que o jogo é pausado, a volta de saída nem a volta final incompleta.

### Requisitos não funcionais

- **RNF01.** O processamento ocorre na máquina do piloto, em um único processo, sem exigir credenciais de serviços de nuvem.
- **RNF02.** Faixas HSV, idiomas do OCR e o limiar de confiança padrão (0,5) estão no código. As regiões de interesse são selecionáveis por presets nomeados. O passo de tempo é a taxa de quadros lida do vídeo.
- **RNF03.** A saída inclui a janela gráfica do Matplotlib e, quando configurado (`--csv`, e os arquivos de volta), a exportação das séries em CSV. Com `--headless`, o gráfico do vídeo inteiro vai para PNG em vez da janela.
- **RNF04.** A instalação é reproduzível a partir da lista de dependências com versões fixadas em `requirements.txt`.
- **RNF05.** O tempo de processamento de cada quadro inclui uma chamada de OCR e depende do hardware disponível ao PyTorch (CPU ou GPU).
- **RNF06.** O resultado numérico só é reprodutível em gravações cujo leiaute de HUD corresponda ao preset selecionado. A taxa de quadros é lida do arquivo. Alterar a resolução ou a escala da janela do cliente exige novo mapeamento. A captura do autor no GeForce NOW é 1280×720; o HUD padrão conferido à parte é 1920×1080.
- **RNF07.** O sistema emite aviso quando uma região de interesse não contém nenhum pixel da cor esperada em todo o vídeo, situação típica de preset incompatível com a gravação.

### Fora do que o código faz hoje

Limites do script: ele não acompanha a barra se o HUD mudar de lugar entre um preset e outro (é preciso trocar `--config`), não trata mais de um vídeo por execução, não calcula tempo de volta e não confronta a leitura com uma telemetria de referência — que, no cenário de RP02, o piloto não recebe do servidor. Na captura `lmu_gfn_720p`, o recorte original do freio (linhas 548–672) alcançava a zebra da pista acima do dial e gerava acionamentos espúrios; o recorte revisado (linhas 582–681, colunas 1063–1082) cobre só o arco da barra. No HUD padrão, o arco vermelho de RPM pode cair na faixa rosa e inflar o freio em alguns quadros.

## Instalação

Requisitos de sistema: Python 3.13 (versão usada na avaliação do TCC), `pip` e espaço em disco para o PyTorch que o EasyOCR instala (vários GB). No índice padrão do PyPI o pacote binário do PyTorch inclui bibliotecas CUDA e também carrega em máquina só com CPU. Na primeira execução é preciso rede para baixar os modelos do EasyOCR.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

No Debian/Ubuntu, se `python3 -m venv` avisar que o `ensurepip` não está disponível, instale o pacote `python3-venv` da mesma versão do interpretador e crie o ambiente de novo.

## Vídeo de entrada

O script não captura a transmissão. Grave a sessão e passe o arquivo em `--video`.

Há três conjuntos de recortes no código:

- **`lmu_gfn_720p`.** Captura real do autor: Le Mans Ultimate no GeForce NOW, gravada no OBS em Fuji Speedway, 1280×720 a 30 fps. O freio fica à esquerda do acelerador, no arco interno esquerdo do dial. A velocidade são os dígitos de KPH. O recorte do freio deixa de fora a barra rosa de combustível (`y >= 675` e `x >= 1090`). O recorte do acelerador deixa de fora o widget verde dos pneus (`x < 1050`). O mesmo conteúdo está em `configs/config_gfn_720p.json`.
- **`lmu_default_1080p`.** HUD padrão do Le Mans Ultimate: dial circular no canto inferior direito, em 1920×1080. O freio (rosa) fica à esquerda do acelerador (verde), no arco esquerdo do dial. A velocidade numérica fica à direita das barras. Este preset foi conferido numa captura de 1920×1080 a 60 fps, não na gravação do GeForce NOW.
- **`original`.** Coordenadas da primeira versão do script. As barras de acelerador e de freio ocupam a mesma coluna. Não é a calibração da captura de 1280×720.

Para repetir a gravação do autor: jogar Le Mans Ultimate no GeForce NOW em 1280×720 a 30 fps, gravar no OBS sem redimensionar e usar `--config lmu_gfn_720p`. Para o HUD padrão, a captura precisa ser 1920×1080 e o config é `lmu_default_1080p`. A taxa pode ser outra: o script lê o FPS do arquivo. Num arquivo de 30 fps, `1/fps` vale cerca de 0,0333 s e substitui a constante antiga `0.033`. Num arquivo de 60 fps, o passo é 1/60 s.

O arquivo de exemplo do autor não está no Git. `.gitignore` ignora `test_telemetria.mp4` e nomes com esse prefixo. Sem `--video`, o script procura `test_telemetria.mp4` no diretório de trabalho.

### Resolução e sistema de coordenadas

Os recortes são fatias absolutas, no formato `[linha_inicial:linha_final, coluna_inicial:coluna_final]`, com origem no canto superior esquerdo e a linha crescendo para baixo. Um quadro menor que o fim do recorte corta a fatia e a contagem cai.

### Preset `original`

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho |
| --- | --- | --- | --- |
| Acelerador | verde | `[585:690, 1053:1095]` | 105×42 px |
| Freio | rosa | `[575:677, 1053:1095]` | 102×42 px |
| Velocidade | dígitos | `[610:640, 1128:1212]` | 30×84 px |

As duas barras compartilham as colunas 1053:1095 e se sobrepõem nas linhas 585:677. A cor separa as séries. Estes números são os da primeira versão do script, não os da captura de 1280×720.

### Preset `lmu_default_1080p`

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho |
| --- | --- | --- | --- |
| Acelerador | verde | `[880:1020, 1590:1615]` | 140×25 px |
| Freio | rosa | `[850:1020, 1565:1592]` | 170×27 px |
| Velocidade | dígitos | `[910:970, 1650:1790]` | 60×140 px |

O freio ocupa as colunas 1565:1592 e o acelerador as colunas 1590:1615: lado a lado, freio à esquerda. Os dois se encostam em duas colunas. A velocidade fica imediatamente à direita.

### Preset `lmu_gfn_720p`

| Sinal | Cor no HUD | Recorte (linhas, colunas) | Tamanho |
| --- | --- | --- | --- |
| Acelerador | verde | `[585:678, 1070:1088]` | 93×18 px |
| Freio | rosa | `[582:681, 1063:1082]` | 99×19 px |
| Velocidade | dígitos KPH | `[608:655, 1140:1235]` | 47×95 px |

O freio ocupa as colunas 1063:1082 e o acelerador as colunas 1070:1088: lado a lado, freio à esquerda, no arco interno esquerdo do dial. O recorte do freio começa na linha 582, abaixo da borda do dial: o recorte antigo (`[548:672, 1064:1078]`) incluía a imagem da pista nas linhas 548–571 e contava a zebra como freio. O preset também guarda `area_acelerador` (380 px) e `area_freio` (369 px), pegada das barras usada por `--normalizacao fixa`. O arquivo `configs/config_gfn_720p.json` repete estes valores para `--config`.

A faixa verde é HSV `[35, 40, 40]` a `[85, 255, 255]`. A faixa rosa é HSV `[140, 80, 80]` a `[179, 255, 255]`, em todos os presets. O limite antigo de matiz 168 deixava o freio do HUD padrão quase vazio, porque a barra medida fica em torno de 172.

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

Captura do autor no GeForce NOW (1280×720, 30 fps), gráfico em PNG e série em CSV, sem janela:

```bash
python leitor.py --video video.mp4 --config lmu_gfn_720p --headless --png telemetria.png --csv telemetria.csv
```

O mesmo recorte lido do JSON:

```bash
python leitor.py --video video.mp4 --config configs/config_gfn_720p.json --headless --png telemetria.png --csv telemetria.csv
```

Sem argumentos, o script procura `test_telemetria.mp4` e usa o preset `lmu_gfn_720p`. Para a primeira versão das coordenadas:

```bash
python leitor.py --video test_telemetria.mp4 --config original --normalizacao max
```

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

O CSV, quando pedido, tem o cabeçalho `tempo_s,distancia_m,velocidade_kmh,acelerador_pct,freio_pct,px_acelerador,px_freio,ocr_status`. Tempo e distância usam o `dt` do arquivo. A velocidade é a última leitura aceita naquele quadro. Os percentuais seguem `--normalizacao`; as contagens brutas de pixels permitem renormalizar fora do script.

## Limitações

- A telemetria nativa de Le Mans Ultimate não entra no fluxo. O gráfico mostra o que foi lido do vídeo.
- O script não abre a sessão na nuvem. Sem um arquivo já gravado, não há o que processar.
- Cada preset vale para um enquadramento. `lmu_gfn_720p` é a captura de 1280×720; `lmu_default_1080p` é o HUD padrão em 1920×1080. Trocar o preset no vídeo errado faz os recortes caírem fora das barras.
- No preset `lmu_gfn_720p`, o recorte antigo do freio (`[548:672, 1064:1078]`) alcançava a zebra da pista acima do dial e contava essa zebra como freio. O recorte revisado (`[582:681, 1063:1082]`) começa abaixo dessa borda. Um recorte que ainda alcance a pista continua contando zebras; o aviso de recorte vazio não detecta esse caso.
- No preset `lmu_default_1080p`, o arco vermelho de RPM pode invadir a faixa rosa e contar como freio em alguns quadros. Esse arco não é a causa da contaminação medida na captura de 1280×720.
- Compressão e bitrate do stream mudam a cor das barras e a nitidez dos dígitos.
- Outra resolução ou outra escala da janela desloca o HUD e os recortes leem o lugar errado.
- A distância usa `1/fps` do arquivo. Se o contêiner mente a taxa, a distância sai na mesma proporção. Sem taxa válida, o passo assume 30 fps.
- A velocidade rejeitada não zera o valor: um dígito lido uma vez continua valendo nos quadros seguintes em que o OCR falha.
- `text.isdigit()` descarta leitura com letra, espaço ou unidade no mesmo trecho.
- O percentual 100% é o percentil 99 da própria gravação (ou o máximo, com `--normalizacao max`). Acelerador e freio não compartilham a mesma referência. O percentual é o preenchimento da barra no HUD, não a posição física do pedal.
- Vídeo ausente ou sem quadros encerra o script com uma mensagem. Recorte sem nenhum pixel da cor gera aviso, e referência 0 vira percentual 0, sem divisão por zero.
- Não há comparação automática com uma telemetria de referência.
- Sem `--headless`, a janela exige um backend interativo do Matplotlib.

## Separação automática de voltas

Com o preset `lmu_gfn_720p` (ou um JSON com a chave `cronometro`), o script também lê o tempo da volta atual ("Atual", canto superior direito do HUD, recorte `[96:117, 1200:1268]`) e o número da volta ("Volta", `[22:42, 1236:1268]`).

- **Leitura.** O cronômetro passa pelo EasyOCR a cada `--passo-cronometro` quadros (padrão 5). Cada leitura `v` no quadro `q` implica um início de volta em `q/fps − v`; dentro de uma volta esse valor é constante, o que permite descartar erros de leitura.
- **Fim da volta.** Ao cruzar a linha, o Le Mans Ultimate congela o tempo oficial da volta no "Atual" por cerca de 10 s. Três leituras iguais entre as cinco últimas confirmam o fim; o script então lê quadro a quadro o trecho anterior e marca como limite o primeiro quadro em que o cronômetro atingiu o tempo oficial. A volta é fechada e gravada, e a distância e as séries recomeçam do zero. O arquivo é `saida/volta_seqNN_hudMM.csv`: NN é a ordem da volta na sessão (válida ou não) e MM é o número lido no HUD. Se o OCR do número falha, o nome fica `volta_seqNN_hudsem.csv`. Se esse caminho já existe, o script acrescenta `_2`, `_3` e assim por diante. O PNG de `--png-voltas` usa o mesmo radical. Se o tempo cai sem congelar (volta invalidada), o limite vem do início implícito das leituras novas.
- **Voltas inválidas (não são gravadas).** O cronômetro some por `--invalida-apos` segundos seguidos ou mais (padrão 8; no vídeo do TCC o HUD mostra "-" por até ~5 s em voltas válidas, ao exibir o delta de setor), ou o tempo para enquanto o vídeo continua (pausa do jogo: o menu esconde o HUD e o cronômetro volta atrasado). A volta de saída (antes do primeiro reinício) e a volta final incompleta também não são gravadas.
- **Resumo.** `saida/voltas.csv` traz `seq, volta, quadro_inicio, quadro_fim, tempo_hud_s, tempo_video_s, valida, motivo, distancia_m, maior_ausencia_cronometro_s, arquivo`. A coluna `volta` é o número do HUD e fica vazia quando o OCR não o leu. `arquivo` só é preenchido nas voltas válidas.
- **Percentuais por volta.** Em `volta_seqNN_hudMM.csv`, acelerador e freio são normalizados com a série da própria volta (`--normalizacao`), e a coluna `quadro` é o índice do quadro no vídeo inteiro.

```bash
python leitor.py --video sessao.mp4 --headless --saida-voltas saida --png-voltas
python leitor.py --video volta.mp4 --sem-voltas --headless --csv volta.csv   # comportamento anterior
```

Teste de regressão do detector (sem OCR, reproduz as leituras gravadas do vídeo do TCC): `python avaliacao/teste_detector_voltas.py`.

O vídeo inteiro continua gerando o gráfico e o `--csv` de antes. Sem `--headless`, use `--png-voltas` com cuidado: o gráfico por volta força o backend sem janela.

## Avaliação (TCC)

A pasta [`avaliacao/`](avaliacao/README.md) traz a saída da ferramenta nas duas voltas válidas mais rápidas da sessão do autor (detectadas automaticamente), a anotação cega de 80 quadros feita pelo autor, os inícios de frenagem observados e o script `avaliar.py`, que recalcula presença, precisão, revocação, F1, erro nos quadros plenos, acerto do OCR, intervalos de confiança de 95% (Wilson e Clopper–Pearson), distância e início das frenagens sem o vídeo e só com a biblioteca padrão do Python:

```bash
python avaliacao/avaliar.py
```

## Diagramas

Os quatro diagramas UML pedidos na metodologia do trabalho prático estão em [`docs/diagramas`](docs/diagramas/README.md), cada um em fonte PlantUML (`.puml`) e em PNG. O diagrama de classes é um modelo lógico: o script não declara classes. Cada diagrama tem um parágrafo pronto para o capítulo de Metodologia. Eles descrevem o fluxo com preset, taxa lida do vídeo, máscaras, OCR e a saída em janela, PNG ou CSV.

## O que o autor precisa revisar

- A redação de RP01–RP04, para o tom do TCC. Já estão confirmados o jogo (Le Mans Ultimate), a captura do autor no GeForce NOW em 1280×720 a 30 fps (preset `lmu_gfn_720p`, OBS, Fuji Speedway) e o HUD padrão em 1920×1080 a 60 fps para o preset `lmu_default_1080p`.
- A seção de justificativa das ferramentas, para que ela descreva a escolha que de fato foi feita.
- A faixa verde e o limiar padrão 0,5. A faixa rosa `[140, 80, 80]`–`[179, 255, 255]` foi a correção aprovada para a matiz medida perto de 172.
- Se o percentil 99 deve continuar como padrão, ou se `fixa` deve virar padrão depois de calibrar a área a partir de quadros de barra plena (na avaliação do TCC, a área medida pela frequência de pixels leu a barra plena como 88–94%).
- Os parágrafos em `docs/diagramas/README.md` antes de colá-los na Metodologia (numeração de figuras e fonte, no padrão ABNT adotado no trabalho).
