"""Extrai telemetria do HUD de um vídeo de sim racing.

O script mede as barras de acelerador e de freio pela cor, lê a velocidade
numérica com OCR e acumula a distância. Os recortes do HUD ficam em presets
ou num JSON. O passo de tempo sai da taxa de quadros do arquivo.

Revisão de nov. 2026 (avaliação do TCC):
- o recorte do freio do preset lmu_gfn_720p foi estreitado para não pegar a
  zebra vermelha da pista, visível acima do dial;
- o preset padrão passou a ser lmu_gfn_720p, e o script avisa quando um
  recorte não tem nenhum pixel da cor esperada no vídeo inteiro;
- a normalização padrão passou a ser o percentil 99 da série (opções: p99,
  max e fixa, esta pela área da barra plena informada no preset ou no JSON);
- o OCR ganhou checagem de faixa plausível e de salto máximo entre quadros,
  e o motivo de cada rejeição vai para o CSV.

Separação de voltas (nov. 2026):
- quando o preset tem o recorte "cronometro" (tempo da volta atual, no canto
  superior direito do HUD), o script lê esse tempo por OCR a cada N quadros;
- ao cruzar a linha, o tempo congela no tempo oficial da volta; o script
  confirma o congelamento, refina quadro a quadro o instante em que o tempo
  atingiu esse valor, fecha a volta e grava saida/volta_NN.csv (e o PNG, se
  pedido), recomeçando a distância do zero;
- se o cronômetro some por mais que --invalida-apos segundos durante a volta,
  ou se o tempo para enquanto o vídeo continua (pausa do jogo), a volta é
  marcada como inválida e não é gravada; a volta de saída (antes do primeiro
  reinício) e a volta final incompleta também não são gravadas;
- voltas.csv resume todas as voltas detectadas.
"""

import argparse
import csv
import re
import sys
import json
from collections import Counter, deque
from pathlib import Path

import cv2 as cv
import matplotlib
import numpy as np
import easyocr

# Faixas HSV no padrão do OpenCV (matiz de 0 a 179).
VERDE_INFERIOR = np.array([35, 40, 40])
VERDE_SUPERIOR = np.array([85, 255, 255])
# O freio do HUD padrão fica em torno da matiz 172, acima do limite antigo 168.
# O arco vermelho de RPM pode entrar nessa faixa e contaminar o freio em alguns quadros.
ROSA_INFERIOR = np.array([140, 80, 80])
ROSA_SUPERIOR = np.array([179, 255, 255])

# Cada recorte é (linha_inicial, linha_final, coluna_inicial, coluna_final).
PRESETS = {
    # Coordenadas da primeira versão do script. As duas barras compartilham a coluna.
    "original": {
        "acelerador": (585, 690, 1053, 1095),
        "freio": (575, 677, 1053, 1095),
        "velocidade": (610, 640, 1128, 1212),
    },
    # Captura real do autor: GeForce NOW, OBS, Le Mans Ultimate, Fuji Speedway,
    # 1280×720, 30 fps. A barra de freio fica à esquerda do acelerador, no arco
    # interno esquerdo do dial. O recorte da velocidade são os dígitos de KPH.
    # A barra rosa de combustível (y >= 675, x >= 1090) fica de fora do freio.
    # O widget verde dos pneus (x < 1050) fica de fora do acelerador.
    # O recorte do freio começa em y = 582: acima disso ele alcançava a pista,
    # e a zebra vermelha e branca caía na faixa rosa (falsos acionamentos).
    # Embaixo ele vai até y = 681 e x = 1082 para incluir o fim do arco.
    # area_* é a quantidade de pixels da barra plena (pegada da barra na ROI),
    # usada só com --normalizacao fixa.
    "lmu_gfn_720p": {
        "acelerador": (585, 678, 1070, 1088),
        "freio": (582, 681, 1063, 1082),
        "velocidade": (608, 655, 1140, 1235),
        "area_acelerador": 380,
        "area_freio": 369,
        # Tempo da volta atual ("Atual", canto superior direito) e número da
        # volta ("Volta"), usados na separação automática de voltas.
        "cronometro": (96, 117, 1200, 1268),
        "numero_volta": (22, 42, 1236, 1268),
    },
    # HUD padrão do Le Mans Ultimate em 1920×1080: dial no canto inferior direito.
    # Freio à esquerda, acelerador à direita, no arco esquerdo do dial.
    "lmu_default_1080p": {
        "acelerador": (880, 1020, 1590, 1615),
        "freio": (850, 1020, 1565, 1592),
        "velocidade": (910, 970, 1650, 1790),
    },
}

CHAVES_ROI = ("acelerador", "freio", "velocidade")
CHAVES_AREA = ("area_acelerador", "area_freio")
CHAVES_OPCIONAIS = ("cronometro", "numero_volta")

# Limites do filtro do OCR. A maior variação observada nas três voltas do TCC
# foi de 6 km/h entre quadros consecutivos (30 fps); 15 km/h por quadro deixa
# folga sem aceitar trocas de dígito grosseiras.
VELOCIDADE_MAXIMA_PADRAO = 400
SALTO_MAXIMO_PADRAO = 15.0
# Depois de tantas rejeições seguidas por salto, a próxima leitura dentro da
# faixa é aceita, para o filtro não travar num valor errado.
REJEICOES_PARA_REINICIAR = 15

# Separação de voltas. No vídeo do TCC, o "Atual" some por até ~5 s em voltas
# válidas (o HUD mostra "-" enquanto exibe o delta de setor); 8 s deixa folga.
PASSO_CRONOMETRO_PADRAO = 5
INVALIDA_APOS_PADRAO = 8.0
TOLERANCIA_INICIO_S = 0.2   # concordância entre leituras do mesmo cronômetro
DESVIO_PAUSA_S = 0.5        # atraso do cronômetro em relação ao vídeo = pausa
REINICIO_MINIMO_S = 20.0    # um reinício real atrasa o cronômetro em quase uma volta inteira


def interpretar_recorte(valor):
    if len(valor) != 4:
        raise SystemExit(
            "Cada recorte precisa de quatro números: "
            "linha_inicial, linha_final, coluna_inicial, coluna_final."
        )
    return tuple(int(numero) for numero in valor)


def carregar_rois(config):
    caminho = Path(config)
    if caminho.is_file():
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        faltando = [chave for chave in CHAVES_ROI if chave not in dados]
        if faltando:
            raise SystemExit(f"O JSON não tem as chaves: {', '.join(faltando)}.")
        rois = {chave: interpretar_recorte(dados[chave]) for chave in CHAVES_ROI}
        for chave in CHAVES_AREA:
            if chave in dados:
                rois[chave] = float(dados[chave])
        for chave in CHAVES_OPCIONAIS:
            if chave in dados:
                rois[chave] = interpretar_recorte(dados[chave])
        return rois
    if config not in PRESETS:
        nomes = ", ".join(PRESETS)
        raise SystemExit(
            f"Configuração desconhecida: {config}. Presets: {nomes}. "
            "Ou informe o caminho de um arquivo JSON."
        )
    return PRESETS[config]


def fps_do_video(cap):
    fps = cap.get(cv.CAP_PROP_FPS)
    if fps is None or fps != fps or fps <= 0:
        return 30.0
    return float(fps)


def percentual(serie, metodo="p99", area=None):
    """Converte a contagem de pixels em percentual.

    max: divide pelo maior valor da série (comportamento antigo; um único
         quadro atípico comprime todos os outros).
    p99: divide pelo percentil 99 da série, mais robusto a picos isolados.
    fixa: divide pela área da barra plena (pixels), informada no preset/JSON.
    O resultado é limitado a 100.
    """
    valores = np.asarray(serie, dtype=float)
    if valores.size == 0:
        return valores
    if metodo == "fixa":
        if not area:
            raise SystemExit(
                "--normalizacao fixa exige area_acelerador e area_freio no preset ou no JSON."
            )
        referencia = float(area)
    elif metodo == "max":
        referencia = float(valores.max())
    else:
        referencia = float(np.percentile(valores, 99))
    if referencia <= 0:
        return np.zeros_like(valores)
    return np.minimum(valores / referencia * 100, 100.0)


def filtrar_leitura(texto, confianca, limiar, anterior, quadros_desde, rejeicoes,
                    vel_max, salto_max):
    """Decide se uma leitura do OCR é aceita. Devolve (aceita, motivo)."""
    if confianca <= limiar:
        return False, "confianca"
    if not str(texto).isdigit():
        return False, "nao_numerico"
    valor = int(texto)
    if not 0 <= valor <= vel_max:
        return False, "faixa"
    if anterior is not None and rejeicoes < REJEICOES_PARA_REINICIAR:
        if abs(valor - anterior) > salto_max * max(1, quadros_desde):
            return False, "salto"
    return True, "aceito"


def ler_tempo(texto):
    """Converte a leitura do cronômetro (M:SS.mmm) em segundos.

    O OCR costuma perder os separadores ("023.359"), então só os dígitos
    contam: 6 dígitos = M SS mmm. Outros formatos são descartados.
    """
    digitos = re.sub(r"\D", "", str(texto))
    if len(digitos) != 6:
        return None
    minutos, segundos, milesimos = int(digitos[0]), int(digitos[1:3]), int(digitos[3:])
    if segundos >= 60:
        return None
    return minutos * 60 + segundos + milesimos / 1000


def ocr_cronometro(reader, recorte_bgr):
    resultado = reader.readtext(
        cv.cvtColor(recorte_bgr, cv.COLOR_BGR2RGB), allowlist="0123456789:."
    )
    return ler_tempo("".join(texto for _b, texto, _c in resultado))


def ocr_numero_volta(reader, recorte_bgr):
    ampliado = cv.resize(recorte_bgr, None, fx=2, fy=2, interpolation=cv.INTER_CUBIC)
    resultado = reader.readtext(cv.cvtColor(ampliado, cv.COLOR_BGR2RGB), allowlist="0123456789")
    texto = "".join(t for _b, t, c in resultado if c > 0.5)
    return int(texto) if texto.isdigit() and 0 < int(texto) < 1000 else None


class DetectorVoltas:
    """Acompanha o cronômetro do HUD e decide onde cada volta começa e termina.

    Cada leitura válida v no quadro q implica um início de volta em q/fps - v.
    Dentro de uma volta esse início é constante; ele muda quando a volta
    reinicia (o tempo cai) ou quando o jogo pausa (o tempo para e o vídeo não).
    Ao cruzar a linha, o HUD congela o tempo oficial por alguns segundos:
    três leituras iguais seguidas confirmam o fim da volta.
    """

    def __init__(self, fps, passo):
        self.fps = fps
        self.passo = passo
        self.inicio = None          # quadro de início da volta atual (None = volta de saída)
        self.inicios = []           # inícios implícitos (s) das leituras vivas da volta
        self.ultima = None          # (quadro, valor) da última leitura viva
        self.recentes = deque(maxlen=5)  # últimas leituras válidas, para achar o congelamento
        self.congelado = False      # exibindo o tempo oficial da volta que acabou
        self.limite_s = None        # início (s) da volta que começou no último congelamento
        self.pendente = None        # mudança aguardando confirmação
        self.ultimo_visivel = None
        self.reiniciar_estatisticas()

    def reiniciar_estatisticas(self):
        self.maior_ausencia = 0.0
        self.pausa = 0.0
        self.numeros = Counter()

    def _referencia(self):
        return float(np.median(self.inicios)) if self.inicios else None

    def amostra(self, quadro, valor):
        """Processa uma leitura amostrada. Devolve um evento ou None.

        Eventos: ("fim", quadro_aprox, tempo_hud, refinar) quando uma volta termina;
        ("inicio", quadro) quando o cronômetro aparece zerando sem volta anterior.
        Depois de um "fim", quem chama deve chamar fechar(quadro_final).
        """
        if valor is None:
            if self.ultimo_visivel is not None:
                ausencia = (quadro - self.ultimo_visivel) / self.fps
                self.maior_ausencia = max(self.maior_ausencia, ausencia)
            return None
        ausencia = 0.0 if self.ultimo_visivel is None else (quadro - self.ultimo_visivel) / self.fps
        self.ultimo_visivel = quadro
        inicio_novo = quadro / self.fps - valor

        if self.congelado:
            # Ignora o tempo congelado (e erros de leitura dele) até o
            # cronômetro voltar a correr a partir do início da nova volta.
            if self.limite_s is not None and abs(inicio_novo - self.limite_s) < 1.0:
                self.congelado = False
                self.inicios = [inicio_novo]
                self.ultima = (quadro, valor)
                self.recentes.clear()
            return None

        self.recentes.append((quadro, valor))
        iguais = [q for q, v in self.recentes if v == valor]
        referencia = self._referencia()
        if len(iguais) >= 3 and valor > 30:
            primeiro = iguais[0]
            coerente = referencia is None or abs(primeiro / self.fps - valor - referencia) < DESVIO_PAUSA_S
            if coerente:
                self.congelado = True
                self.pendente = None
                self.recentes.clear()
                return ("fim", primeiro, valor, True)

        if self.pendente is not None:
            tipo, s_cand = self.pendente
            self.pendente = None
            if abs(inicio_novo - s_cand) < TOLERANCIA_INICIO_S:
                self.ultima = (quadro, valor)
                if tipo == "pausa":
                    self.pausa += s_cand - referencia
                    self.inicios = [inicio_novo]
                    return None
                limite = int(round(s_cand * self.fps))
                self.inicios = [inicio_novo]
                if tipo == "primeira" or self.inicio is None:
                    self.inicio = limite
                    self.reiniciar_estatisticas()
                    return ("inicio", limite)
                return ("fim", limite, None, False)

        if referencia is None:
            if self.inicio is None and self.ultima is None:
                self.pendente = ("primeira", inicio_novo)
            else:
                self.inicios.append(inicio_novo)
                self.ultima = (quadro, valor)
            return None
        desvio = inicio_novo - referencia
        if desvio > DESVIO_PAUSA_S:
            if desvio >= REINICIO_MINIMO_S:
                # O tempo caiu quase uma volta: a volta reiniciou sem exibir o
                # tempo congelado (acontece quando a volta foi invalidada).
                self.pendente = ("reinicio", inicio_novo)
            elif ausencia >= 0.8 * desvio - 0.3:
                # O cronômetro sumiu e voltou atrasado: o jogo ficou pausado.
                self.pendente = ("pausa", inicio_novo)
            # Caso contrário, é erro de leitura (ex.: 7 lido como 1); descartado.
            return None
        if desvio < -DESVIO_PAUSA_S:
            return None  # leitura incoerente (troca de dígito); descartada
        self.inicios.append(inicio_novo)
        self.inicios = self.inicios[-30:]
        self.ultima = (quadro, valor)
        return None

    def fechar(self, limite):
        """Registra o novo início e devolve as estatísticas da volta que terminou."""
        estatisticas = {
            "maior_ausencia_s": round(self.maior_ausencia, 2),
            "pausa_s": round(self.pausa, 2),
            "numero_hud": self.numeros.most_common(1)[0][0] if self.numeros else None,
        }
        self.inicio = limite
        self.limite_s = limite / self.fps
        if not self.congelado:
            self.inicios = [self.limite_s]
        self.reiniciar_estatisticas()
        return estatisticas


def refinar_limite(reader, buffer, tempo_hud, quadro_aprox, passo):
    """Primeiro quadro do buffer cujo cronômetro já atingiu o tempo oficial."""
    for quadro, recorte in buffer:
        if quadro < quadro_aprox - 2 * passo:
            continue
        valor = ocr_cronometro(reader, recorte)
        if valor is not None and tempo_hud - 0.0005 <= valor <= tempo_hud + 0.1:
            return quadro
    return quadro_aprox


def gravar_volta(caminho, quadros, dt, velocidades, px_acel, px_freio, status_ocr,
                 normalizacao, rois):
    """Grava uma volta com distância recomeçando do zero e percentuais da própria volta."""
    distancia = np.cumsum(np.asarray(velocidades, dtype=float) / 3.6 * dt)
    acel = percentual(px_acel, normalizacao, rois.get("area_acelerador"))
    freio = percentual(px_freio, normalizacao, rois.get("area_freio"))
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["quadro", "tempo_s", "distancia_m", "velocidade_kmh", "acelerador_pct",
             "freio_pct", "px_acelerador", "px_freio", "ocr_status"]
        )
        for i, quadro in enumerate(quadros):
            escritor.writerow([quadro, round((i + 1) * dt, 4), round(float(distancia[i]), 3),
                               velocidades[i], round(float(acel[i]), 3), round(float(freio[i]), 3),
                               px_acel[i], px_freio[i], status_ocr[i]])
    return distancia, acel, freio


def gravar_csv(caminho, tempo, distancia, velocidade, acelerador, freio,
               px_acel, px_freio, status_ocr):
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["tempo_s", "distancia_m", "velocidade_kmh", "acelerador_pct", "freio_pct",
             "px_acelerador", "px_freio", "ocr_status"]
        )
        for linha in zip(tempo, distancia, velocidade, acelerador, freio,
                         px_acel, px_freio, status_ocr):
            escritor.writerow(linha)


def desenhar(distancia, acelerador, freio, headless, png):
    if headless:
        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(20, 6))
    ax.plot(distancia, acelerador, "-", color="green")
    ax.plot(distancia, freio, "-", color="red")
    ax.fill_between(distancia, acelerador, alpha=0.3, color="green")
    ax.fill_between(distancia, freio, alpha=0.3, color="red")
    ax.grid(alpha=0.2)
    ax.set(title="Telemetria", xlabel="Distância (m)", ylabel="% aceleração/freio")
    if headless:
        fig.savefig(png, dpi=120, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai acelerador, freio e velocidade do HUD de um vídeo."
    )
    parser.add_argument(
        "--video",
        default="test_telemetria.mp4",
        help="Arquivo de vídeo (padrão: test_telemetria.mp4).",
    )
    parser.add_argument(
        "--config",
        default="lmu_gfn_720p",
        help=(
            "Preset lmu_gfn_720p (padrão), lmu_default_1080p ou original, ou caminho "
            "de um JSON com os recortes acelerador, freio e velocidade."
        ),
    )
    parser.add_argument(
        "--normalizacao",
        choices=("p99", "max", "fixa"),
        default="p99",
        help="Referência do percentual: p99 (padrão), max ou fixa (área da barra plena).",
    )
    parser.add_argument(
        "--vel-max",
        type=float,
        default=VELOCIDADE_MAXIMA_PADRAO,
        help="Maior velocidade plausível em km/h; leituras acima são rejeitadas (padrão: 400).",
    )
    parser.add_argument(
        "--salto-max",
        type=float,
        default=SALTO_MAXIMO_PADRAO,
        help="Maior variação aceita, em km/h por quadro, desde a última leitura aceita (padrão: 15).",
    )
    parser.add_argument(
        "--confianca",
        type=float,
        default=0.5,
        help="Confiança mínima do OCR, exclusiva (padrão: 0.5).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Grava o gráfico em PNG e não abre janela.",
    )
    parser.add_argument(
        "--png",
        default="telemetria.png",
        help="Caminho do PNG usado com --headless (padrão: telemetria.png).",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Se informado, grava tempo, distância, velocidade e percentuais neste CSV.",
    )
    parser.add_argument(
        "--sem-voltas",
        action="store_true",
        help="Não separa voltas, mesmo que o preset tenha o recorte do cronômetro.",
    )
    parser.add_argument(
        "--saida-voltas",
        default="saida",
        help="Pasta dos arquivos volta_NN.csv e voltas.csv (padrão: saida).",
    )
    parser.add_argument(
        "--passo-cronometro",
        type=int,
        default=PASSO_CRONOMETRO_PADRAO,
        help="Lê o cronômetro a cada N quadros; o limite da volta é refinado quadro a quadro (padrão: 5).",
    )
    parser.add_argument(
        "--invalida-apos",
        type=float,
        default=INVALIDA_APOS_PADRAO,
        help="Segundos seguidos sem cronômetro visível para invalidar a volta (padrão: 8).",
    )
    parser.add_argument(
        "--png-voltas",
        action="store_true",
        help="Grava também o gráfico de cada volta válida (volta_NN.png).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    rois = carregar_rois(args.config)
    ya1, ya2, xa1, xa2 = rois["acelerador"]
    yf1, yf2, xf1, xf2 = rois["freio"]
    yo1, yo2, xo1, xo2 = rois["velocidade"]

    reader = easyocr.Reader(["pt", "en"])
    cap = cv.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Não foi possível abrir o vídeo: {args.video}")

    fps = fps_do_video(cap)
    dt = 1.0 / fps
    pixels_acel = []
    pixels_freio = []
    velocidades = []
    distancias = []
    tempos = []
    distancia = 0.0
    velocidade = 0
    ultima_aceita = None
    quadros_desde = 0
    rejeicoes_seguidas = 0
    status_ocr = []
    contagem_status = {}

    cronometro = None if args.sem_voltas else rois.get("cronometro")
    if cronometro is not None:
        # O modelo só em inglês lê os dígitos do cronômetro melhor que o de pt+en.
        leitor_cronometro = easyocr.Reader(["en"], verbose=False)
        yc1, yc2, xc1, xc2 = cronometro
        numero_roi = rois.get("numero_volta")
        passo = max(1, args.passo_cronometro)
        detector = DetectorVoltas(fps, passo)
        buffer_cronometro = deque(maxlen=6 * passo + 2)
        pasta_voltas = Path(args.saida_voltas)
        pasta_voltas.mkdir(parents=True, exist_ok=True)
        voltas = []
        inicio_atual = None

    def registrar_volta(inicio, fim, tempo_hud, estatisticas, motivo_extra=None):
        indices = range(inicio, fim)
        vel = [velocidades[i] for i in indices]
        distancia_volta = float(np.sum(np.asarray(vel, dtype=float) / 3.6 * dt)) if vel else 0.0
        motivos = []
        if motivo_extra:
            motivos.append(motivo_extra)
        if estatisticas and estatisticas["maior_ausencia_s"] >= args.invalida_apos:
            motivos.append(f"cronômetro ausente por {estatisticas['maior_ausencia_s']:.1f} s")
        if estatisticas and estatisticas["pausa_s"] > 0:
            motivos.append(f"pausa de {estatisticas['pausa_s']:.1f} s")
        numero = (estatisticas or {}).get("numero_hud")
        if numero is None:
            numero = len(voltas) + 1
        registro = {
            "volta": numero,
            "quadro_inicio": inicio,
            "quadro_fim": fim,
            "tempo_hud_s": "" if tempo_hud is None else f"{tempo_hud:.3f}",
            "tempo_video_s": f"{(fim - inicio) * dt:.3f}",
            "valida": "nao" if motivos else "sim",
            "motivo": "; ".join(motivos),
            "distancia_m": f"{distancia_volta:.2f}",
            "maior_ausencia_cronometro_s": (estatisticas or {}).get("maior_ausencia_s", ""),
            "arquivo": "",
        }
        if not motivos:
            nome = pasta_voltas / f"volta_{numero:02d}.csv"
            dist, acel, frei = gravar_volta(
                nome, list(indices), dt, vel, [pixels_acel[i] for i in indices],
                [pixels_freio[i] for i in indices], [status_ocr[i] for i in indices],
                args.normalizacao, rois,
            )
            registro["arquivo"] = str(nome)
            if args.png_voltas:
                desenhar(dist, acel, frei, True, str(nome.with_suffix(".png")))
        voltas.append(registro)
        estado = "válida" if not motivos else f"inválida ({registro['motivo']})"
        print(f"volta {numero}: quadros {inicio}-{fim}, tempo HUD {registro['tempo_hud_s'] or '-'} s, "
              f"{estado}{', gravada em ' + registro['arquivo'] if registro['arquivo'] else ''}", flush=True)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)
        mask_acel = cv.inRange(
            frame_hsv[ya1:ya2, xa1:xa2], VERDE_INFERIOR, VERDE_SUPERIOR
        )
        mask_freio = cv.inRange(
            frame_hsv[yf1:yf2, xf1:xf2], ROSA_INFERIOR, ROSA_SUPERIOR
        )
        pixels_acel.append(cv.countNonZero(mask_acel))
        pixels_freio.append(cv.countNonZero(mask_freio))

        recorte = cv.cvtColor(frame[yo1:yo2, xo1:xo2], cv.COLOR_BGR2RGB)
        quadros_desde += 1
        status = "sem_leitura"
        for (_bbox, text, confidence) in reader.readtext(recorte):
            aceita, motivo = filtrar_leitura(
                text, confidence, args.confianca, ultima_aceita, quadros_desde,
                rejeicoes_seguidas, args.vel_max, args.salto_max,
            )
            if aceita:
                velocidade = int(text)
                status = "aceito"
            elif status != "aceito" and (
                motivo in ("faixa", "salto") or status == "sem_leitura"
            ):
                status = f"rejeitado_{motivo}"
        if status == "aceito":
            ultima_aceita = velocidade
            quadros_desde = 0
            rejeicoes_seguidas = 0
        elif status == "rejeitado_salto":
            rejeicoes_seguidas += 1
        status_ocr.append(status)
        contagem_status[status] = contagem_status.get(status, 0) + 1
        distancia += (velocidade / 3.6) * dt
        distancias.append(distancia)
        velocidades.append(velocidade)
        tempos.append(len(distancias) * dt)

        if cronometro is not None:
            quadro = len(distancias) - 1
            buffer_cronometro.append((quadro, frame[yc1:yc2, xc1:xc2].copy()))
            if quadro % passo == 0:
                if numero_roi is not None and detector.inicio is not None and quadro % (6 * passo) == 0:
                    y1, y2, x1, x2 = numero_roi
                    numero = ocr_numero_volta(leitor_cronometro, frame[y1:y2, x1:x2])
                    if numero is not None:
                        detector.numeros[numero] += 1
                evento = detector.amostra(quadro, ocr_cronometro(leitor_cronometro, frame[yc1:yc2, xc1:xc2]))
                if evento is not None and evento[0] == "inicio":
                    limite = evento[1]
                    if limite <= 0:
                        inicio_atual = None  # a volta começou antes do vídeo: incompleta
                    else:
                        registrar_volta(0, limite, None, None, "volta de saída (antes do primeiro reinício)")
                        inicio_atual = limite
                elif evento is not None and evento[0] == "fim":
                    _tipo, limite, tempo_hud, refinar = evento
                    if refinar:
                        limite = refinar_limite(leitor_cronometro, buffer_cronometro, tempo_hud, limite, passo)
                    estatisticas = detector.fechar(limite)
                    if inicio_atual is None:
                        registrar_volta(0, limite, tempo_hud, None, "volta de saída (antes do primeiro reinício)")
                    else:
                        registrar_volta(inicio_atual, limite, tempo_hud, estatisticas)
                    inicio_atual = limite

    cap.release()
    if cronometro is not None and distancias:
        if inicio_atual is None:
            registrar_volta(0, len(distancias), None, None, "sem reinício do cronômetro no vídeo")
        else:
            registrar_volta(inicio_atual, len(distancias), None, detector.fechar(len(distancias)),
                            "incompleta (o vídeo terminou)")
        resumo_voltas = pasta_voltas / "voltas.csv"
        with open(resumo_voltas, "w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(voltas[0]))
            escritor.writeheader()
            escritor.writerows(voltas)
        validas = sum(v["valida"] == "sim" for v in voltas)
        print(f"voltas: {len(voltas)} detectadas, {validas} válidas; resumo em {resumo_voltas}", flush=True)
    if not distancias:
        raise SystemExit(f"O vídeo não tem quadros: {args.video}")

    for nome, serie in (("acelerador", pixels_acel), ("freio", pixels_freio)):
        if max(serie) == 0:
            print(
                f"AVISO: o recorte do {nome} não teve nenhum pixel da cor esperada em "
                "nenhum quadro. Confira se o preset (--config) corresponde à resolução "
                "e ao leiaute do HUD do vídeo.",
                file=sys.stderr,
                flush=True,
            )
    acelerador = percentual(pixels_acel, args.normalizacao, rois.get("area_acelerador"))
    freio = percentual(pixels_freio, args.normalizacao, rois.get("area_freio"))
    print(
        f"fps={fps:.3f} dt={dt:.6f}s quadros={len(distancias)} config={args.config} "
        f"normalizacao={args.normalizacao}",
        flush=True,
    )
    resumo = " ".join(f"{k}={v}" for k, v in sorted(contagem_status.items()))
    print(f"ocr: {resumo}", flush=True)
    if args.csv:
        gravar_csv(args.csv, tempos, distancias, velocidades, acelerador, freio,
                   pixels_acel, pixels_freio, status_ocr)
    desenhar(distancias, acelerador, freio, args.headless, args.png)


if __name__ == "__main__":
    main()
