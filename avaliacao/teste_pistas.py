#!/usr/bin/env python3
"""Teste do catálogo de pistas e do ajuste da distância ao comprimento (sem OCR, sem vídeo).

Uso: python avaliacao/teste_pistas.py
"""
import csv, sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import leitor  # noqa: E402


def main():
    pistas = leitor.carregar_pistas()
    for chave, pista in pistas.items():
        assert pista["comprimento_m"] > 0 and pista["fonte"].startswith("https://"), chave
    # Fuji: o mesmo comprimento usado na avaliação do TCC.
    assert leitor.resolver_pista("fuji", None) == ("Fuji Speedway (4563 m)", 4563.0)
    # --comprimento-pista tem precedência; sem nenhum dos dois, ou com chave desconhecida, para.
    assert leitor.resolver_pista("fuji", 4526)[1] == 4526.0
    assert leitor.resolver_pista(None, 3000)[1] == 3000.0
    for argumentos in ((None, None), ("nao-existe", None), (None, 0)):
        try:
            leitor.resolver_pista(*argumentos)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"deveria interromper: {argumentos}")
    print("OK: catálogo com", len(pistas), "pistas; --pista/--comprimento-pista conferidos")

    # Volta 9 gravada: a distância integrada termina em 4.550,55 m (-0,273%);
    # reescalada, termina exatamente no comprimento e fica dentro de [0, 4563].
    linhas = list(csv.DictReader(open(RAIZ / "avaliacao/saidas_ferramenta/volta_09.csv", encoding="utf-8")))
    distancia = np.array([float(r["distancia_m"]) for r in linhas])
    na_pista, erro = leitor.distancia_na_pista(distancia, 4563.0)
    assert abs(erro - (-0.273)) < 0.001, erro
    assert na_pista[-1] == 4563.0 and na_pista.min() >= 0 and na_pista.max() <= 4563.0
    assert np.all(np.diff(na_pista) >= 0)
    erro_aviso = leitor.avisar_distancia("teste", 4800.0, 4563.0, 5.0)  # +5,2%: deve avisar no stderr
    assert erro_aviso > 5
    print(f"OK: volta 9 com {distancia[-1]:.2f} m ({erro:+.3f}%) reescalada para [0, 4563] m")


if __name__ == "__main__":
    main()
