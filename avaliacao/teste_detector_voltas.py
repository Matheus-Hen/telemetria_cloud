#!/usr/bin/env python3
"""Teste de regressão do detector de voltas (sem OCR, sem vídeo).

Reproduz as leituras do cronômetro gravadas a cada 5 quadros no vídeo de
referência (dados/leituras_cronometro_gfn.csv, OCR EasyOCR "en") e confere se o
DetectorVoltas encontra os mesmos fins de volta, tempos do HUD e pausas
conferidos quadro a quadro no vídeo. Uso: python avaliacao/teste_detector_voltas.py
"""
import csv, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import leitor  # noqa: E402

# (fim aproximado, tempo HUD) conferidos no vídeo; None = volta zerada sem tempo (inválida)
ESPERADO = [(8765, None), (12290, 117.386), (15845, 118.510), (19295, 114.992),
            (22685, 112.917), (26240, 114.164), (30095, 114.324), (33400, 110.075)]
TOLERANCIA_QUADROS = 10


def main():
    linhas = list(csv.DictReader(open(RAIZ / "avaliacao/dados/leituras_cronometro_gfn.csv", encoding="utf-8")))
    det = leitor.DetectorVoltas(30.0, 5)
    inicio, fins = None, []
    for r in linhas:
        ev = det.amostra(int(r["quadro"]), leitor.ler_tempo(r["texto"]))
        if ev and ev[0] == "inicio":
            inicio = ev[1]
        elif ev and ev[0] == "fim":
            fins.append((ev[1], ev[2], det.fechar(ev[1])))
    assert inicio is not None and abs(inicio - 4298) <= TOLERANCIA_QUADROS, inicio
    assert len(fins) == len(ESPERADO), [f[:2] for f in fins]
    for (q, t, est), (qe, te) in zip(fins, ESPERADO):
        assert abs(q - qe) <= TOLERANCIA_QUADROS, (q, qe)
        assert (t is None and te is None) or abs(t - te) < 1e-6, (t, te)
        print(f"fim {q:6d} (esperado {qe}) tempo HUD {t}  ausência máx {est['maior_ausencia_s']} s  pausa {est['pausa_s']} s")
    print("OK: detector reproduz as", len(ESPERADO), "trocas de volta")


if __name__ == "__main__":
    main()
