"""Extrai telemetria do HUD de um vídeo de sim racing.

O script mede as barras de acelerador e de freio pela cor, lê a velocidade
numérica com OCR e acumula a distância. Os recortes do HUD ficam em presets
ou num JSON. O passo de tempo sai da taxa de quadros do arquivo.
"""

import argparse
import csv
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
    # Coordenadas originais do script, medidas na gravação do GeForce NOW.
    # As duas barras compartilham a mesma coluna.
    "original": {
        "acelerador": (585, 690, 1053, 1095),
        "freio": (575, 677, 1053, 1095),
        "velocidade": (610, 640, 1128, 1212),
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
        return {chave: interpretar_recorte(dados[chave]) for chave in CHAVES_ROI}
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


def percentual(serie):
    valores = np.asarray(serie, dtype=float)
    if valores.size == 0:
        return valores
    maximo = float(valores.max())
    if maximo <= 0:
        return np.zeros_like(valores)
    return (valores / maximo) * 100


def gravar_csv(caminho, tempo, distancia, velocidade, acelerador, freio):
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["tempo_s", "distancia_m", "velocidade_kmh", "acelerador_pct", "freio_pct"]
        )
        for linha in zip(tempo, distancia, velocidade, acelerador, freio):
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
        default="original",
        help=(
            "Preset original ou lmu_default_1080p, ou caminho de um JSON "
            "com os recortes acelerador, freio e velocidade."
        ),
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
        for (_bbox, text, confidence) in reader.readtext(recorte):
            if confidence > args.confianca and str(text).isdigit():
                velocidade = int(text)
        distancia += (velocidade / 3.6) * dt
        distancias.append(distancia)
        velocidades.append(velocidade)
        tempos.append(len(distancias) * dt)

    cap.release()
    if not distancias:
        raise SystemExit(f"O vídeo não tem quadros: {args.video}")

    acelerador = percentual(pixels_acel)
    freio = percentual(pixels_freio)
    print(
        f"fps={fps:.3f} dt={dt:.6f}s quadros={len(distancias)} config={args.config}",
        flush=True,
    )
    if args.csv:
        gravar_csv(args.csv, tempos, distancias, velocidades, acelerador, freio)
    desenhar(distancias, acelerador, freio, args.headless, args.png)


if __name__ == "__main__":
    main()
