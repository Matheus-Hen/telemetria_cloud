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
"""

import argparse
import csv
import sys
import json
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

# Limites do filtro do OCR. A maior variação observada nas três voltas do TCC
# foi de 6 km/h entre quadros consecutivos (30 fps); 15 km/h por quadro deixa
# folga sem aceitar trocas de dígito grosseiras.
VELOCIDADE_MAXIMA_PADRAO = 400
SALTO_MAXIMO_PADRAO = 15.0
# Depois de tantas rejeições seguidas por salto, a próxima leitura dentro da
# faixa é aceita, para o filtro não travar num valor errado.
REJEICOES_PARA_REINICIAR = 15


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

    cap.release()
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
