#!/usr/bin/env python3
"""Conta os pixels rosa no recorte ORIGINAL do freio (primeira versão do preset lmu_gfn_720p,
linhas 548-672, colunas 1064-1078, que alcançava a pista) nos
quadros das voltas amostradas, direto do vídeo completo, para comparar com a 1ª versão.

Uso: python avaliacao/gerar_roi_original.py VIDEO leitor.py
Gera dados/serie_volta_NN_roi_original.csv (quadro_video, px_freio_roi_original) para cada
volta de amostra_2voltas.csv, cobrindo os quadros de saidas_ferramenta/volta_NN.csv.
"""
import csv, importlib.util, sys
from pathlib import Path
import cv2 as cv

PASTA = Path(__file__).resolve().parent
video, caminho_leitor = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("leitor", caminho_leitor)
leitor = importlib.util.module_from_spec(spec); spec.loader.exec_module(leitor)
y1, y2, x1, x2 = 548, 672, 1064, 1078  # recorte do freio da primeira versão (commit e1a1a53)
voltas = sorted({int(r["volta"]) for r in csv.DictReader(open(PASTA / "dados" / "amostra_2voltas.csv"))})
cap = cv.VideoCapture(video)
for v in voltas:
    quadros = [int(r["quadro"]) for r in csv.DictReader(open(PASTA / "saidas_ferramenta" / f"volta_{v:02d}.csv"))]
    cap.set(cv.CAP_PROP_POS_FRAMES, quadros[0])
    with open(PASTA / "dados" / f"serie_volta_{v:02d}_roi_original.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["quadro_video", "px_freio_roi_original"])
        for q in quadros:
            ok, quadro = cap.read()
            if not ok: break
            hsv = cv.cvtColor(quadro[y1:y2, x1:x2], cv.COLOR_BGR2HSV)
            w.writerow([q, cv.countNonZero(cv.inRange(hsv, leitor.ROSA_INFERIOR, leitor.ROSA_SUPERIOR))])
    print("volta", v, len(quadros), "quadros")
