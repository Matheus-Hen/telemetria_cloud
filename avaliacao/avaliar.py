#!/usr/bin/env python3
"""Recalcula, sem o vídeo, todas as métricas da avaliação do TCC (voltas 6 e 9).

Uso: python avaliacao/avaliar.py [anotacao.csv|.xlsx]   (padrão: dados/anotacao_autor_2voltas_corrigida.csv)
Grava avaliacao/resultados_avaliacao.json. Só biblioteca padrão (XLSX exige openpyxl).

Entradas:
  saidas_ferramenta/voltas.csv, volta_06.csv, volta_09.csv  saída do leitor.py revisado no vídeo inteiro
  dados/serie_volta_NN_roi_original.csv  pixels rosa no recorte do freio da primeira versão ([548:672, 1064:1078])
  dados/amostra_2voltas.csv              sorteio estratificado (Nº, volta, quadro do vídeo, estrato)
  dados/anotacao_autor_2voltas.csv       anotação cega do autor (estado das barras e velocidade), como entregue
  dados/anotacao_autor_2voltas_corrigida.csv  a mesma, com o freio do Nº 52 (quadro 32.782) corrigido para pleno pelo autor
  dados/inicio_frenagem.csv              primeiro quadro com rosa visível em cada zona de frenagem
Primeira versão = recorte original do freio + normalização pelo máximo; versão revisada = recorte
[582:681, 1063:1082] + percentil 99 (percentuais da própria saída da ferramenta).
"""
import csv, json, math, statistics, sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
DADOS = PASTA / "dados"
SAIDAS = PASTA / "saidas_ferramenta"
LIMIAR_PRESENCA = 5.0
AREA_REF = {"acelerador": 380, "freio": 369}
ESTADOS = {"ausente": "ausente", "parcial": "parcial", "pleno": "pleno", "plena": "pleno", "cheio": "pleno"}
CONFIGURACOES = {
    "acelerador": {"max": ("px_acelerador", "max"), "p99 (versão revisada)": ("px_acelerador", "p99"),
                   "área fixa": ("px_acelerador", "fixa")},
    "freio": {"recorte original + max (primeira versão)": ("px_freio_roi_original", "max"),
              "recorte original + p99": ("px_freio_roi_original", "p99"),
              "recorte revisado + max": ("px_freio", "max"),
              "recorte revisado + p99 (versão revisada)": ("px_freio", "p99"),
              "recorte revisado + área fixa": ("px_freio", "fixa")},
}

def wilson(k, n, z=1.959964):
    if n == 0: return (math.nan, math.nan)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))

def _cdf(k, n, p): return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))

def _bissecao(f):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) > 0 else (lo, m)
    return (lo + hi) / 2

def clopper_pearson(k, n, a=0.05):
    if n == 0: return (math.nan, math.nan)
    inf = 0.0 if k == 0 else _bissecao(lambda p: a / 2 - (1 - _cdf(k - 1, n, p)))
    sup = 1.0 if k == n else _bissecao(lambda p: _cdf(k, n, p) - a / 2)
    return (inf, sup)

def ic(k, n): return {"wilson": [round(x, 4) for x in wilson(k, n)],
                      "clopper_pearson": [round(x, 4) for x in clopper_pearson(k, n)]}

def ler_csv(p):
    with open(p, newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))

CABECALHOS = {"nº": "n", "n": "n", "volta": "volta", "quadro (vídeo)": "quadro_video", "quadro_video": "quadro_video",
              "tempo na volta (s)": "tempo_volta_s", "tempo_volta_s": "tempo_volta_s", "acelerador": "acelerador",
              "acelerador % (opcional)": "acelerador_pct", "acelerador_pct": "acelerador_pct", "freio": "freio",
              "freio % (opcional)": "freio_pct", "freio_pct": "freio_pct", "velocidade (km/h)": "velocidade_kmh",
              "velocidade_kmh": "velocidade_kmh", "observação": "observacao", "observacao": "observacao"}


def ler_anotacao(p):
    """Lê a planilha pelos nomes das colunas (colunas opcionais podem ter sido apagadas)."""
    p = Path(p)
    if p.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        ws = load_workbook(p, data_only=True).active
        linhas = list(ws.iter_rows(values_only=True))
        chaves = [CABECALHOS.get(str(c).strip().lower(), str(c)) for c in linhas[0]]
        brutas = [dict(zip(chaves, ["" if v is None else v for v in l])) for l in linhas[1:] if l and l[0] is not None]
    else:
        brutas = [{CABECALHOS.get(k.strip().lower(), k): v for k, v in r.items()} for r in ler_csv(p)]
    for r in brutas:
        for k in ("acelerador_pct", "freio_pct", "observacao"):
            r.setdefault(k, "")
    return brutas

def num(v):
    v = str(v).strip().replace(",", ".").replace("%", "")
    return float(v) if v not in ("", "None") else None

def percentil(v, q):
    s = sorted(v); i = (len(s) - 1) * q / 100; lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)

def normalizar(px, met, canal):
    ref = max(px) if met == "max" else percentil(px, 99) if met == "p99" else AREA_REF[canal]
    return [min(100.0, 100 * x / ref) if ref > 0 else 0.0 for x in px]

def resumo(e):
    if not e: return None
    a = [abs(x) for x in e]
    return {"n": len(e), "erro_medio": round(statistics.mean(e), 2), "erro_abs_medio": round(statistics.mean(a), 2),
            "erro_abs_mediano": round(statistics.median(a), 2), "erro_abs_max": round(max(a), 2)}

def carregar_series(voltas):
    series = {}
    for v in voltas:
        linhas = ler_csv(SAIDAS / f"volta_{v:02d}.csv")
        por_quadro = {int(r["quadro"]): r for r in linhas}
        orig = DADOS / f"serie_volta_{v:02d}_roi_original.csv"
        if orig.exists():
            for r in ler_csv(orig):
                q = int(r["quadro_video"])
                if q in por_quadro:
                    por_quadro[q]["px_freio_roi_original"] = r["px_freio_roi_original"]
        series[v] = (linhas, por_quadro)
    return series


def avaliar(anot, series):
    res = {"n": len(anot), "estratos": {}, "presenca_e_intensidade": {}, "ocr": {}}
    for a in anot: res["estratos"][a["estrato"]] = res["estratos"].get(a["estrato"], 0) + 1
    for canal, cfgs in CONFIGURACOES.items():
        res["presenca_e_intensidade"][canal] = {}
        for nome, (col, met) in cfgs.items():
            pct = {}
            ok = True
            for v, (linhas, por_quadro) in series.items():
                if any(col not in r for r in linhas):
                    ok = False; break
                valores = normalizar([float(r[col]) for r in linhas], met, canal)
                pct[v] = {int(r["quadro"]): p for r, p in zip(linhas, valores)}
            if not ok:
                continue
            vp = fp = fn = vn = 0; parc, plen = [], []
            for a in anot:
                t = pct[a["volta"]][a["quadro"]]; est = a[canal]; ref = a[f"{canal}_pct"]
                pres, det = est != "ausente", t >= LIMIAR_PRESENCA
                vp += pres and det; fp += (not pres) and det; fn += pres and not det; vn += (not pres) and not det
                if est == "parcial" and ref is not None: parc.append(t - ref)
                if est == "pleno": plen.append(t - (ref if ref is not None else 100.0))
            n = vp + fp + fn + vn
            prec = vp / (vp + fp) if vp + fp else math.nan; rev = vp / (vp + fn) if vp + fn else math.nan
            f1 = 2 * prec * rev / (prec + rev) if (vp + fp) and (vp + fn) and prec + rev else math.nan
            res["presenca_e_intensidade"][canal][nome] = {
                "matriz": {"VP": vp, "FP": fp, "FN": fn, "VN": vn},
                "acuracia": round((vp + vn) / n, 4) if n else None, "acuracia_ic95": ic(vp + vn, n),
                "precisao": round(prec, 4), "precisao_ic95": ic(vp, vp + fp),
                "revocacao": round(rev, 4), "revocacao_ic95": ic(vp, vp + fn), "f1": round(f1, 4),
                "intensidade_parcial_pp": resumo(parc), "intensidade_plena_pp": resumo(plen)}
    com_vel = [a for a in anot if a["vel"] is not None]
    serie_vel = lambda a: int(series[a["volta"]][1][a["quadro"]]["velocidade_kmh"])
    certos = sum(serie_vel(a) == int(a["vel"]) for a in com_vel)
    res["ocr"] = {"corretos": certos, "n": len(com_vel), "ic95": ic(certos, len(com_vel)),
                  "divergencias": [{"n": a["n"], "volta": a["volta"], "anotado": int(a["vel"]), "serie": serie_vel(a)}
                                   for a in com_vel if serie_vel(a) != int(a["vel"])]}
    return res


def imprimir(titulo, res):
    print(f"== {titulo}: {res['n']} quadros; estratos {res['estratos']}")
    for canal, cfgs in res["presenca_e_intensidade"].items():
        for nome, m in cfgs.items():
            w = m["precisao_ic95"]["wilson"]; wr = m["revocacao_ic95"]["wilson"]
            ip, il = m["intensidade_parcial_pp"], m["intensidade_plena_pp"]
            print(f"{canal:10s} {nome:42s} {m['matriz']} prec={m['precisao']:.3f} [{w[0]:.3f};{w[1]:.3f}] "
                  f"rev={m['revocacao']:.3f} [{wr[0]:.3f};{wr[1]:.3f}] F1={m['f1']:.3f} "
                  f"EAM parcial={ip['erro_abs_medio'] if ip else '-'} plena={il['erro_abs_medio'] if il else '-'}")
    o = res["ocr"]; print(f"velocidade {o['corretos']}/{o['n']} IC95 Wilson {o['ic95']['wilson']}")




COMPRIMENTO_OFICIAL_M = 4563.0
FPS = 30.0


def estado(p):
    return "ausente" if p < LIMIAR_PRESENCA else "pleno" if p >= 90 else "parcial"


def extras(voltas, series, anot):
    """Desacordos de três estados, contaminação, normalização, distância, início das frenagens e traçado."""
    resumo_voltas = {int(r["volta"]): r for r in ler_csv(SAIDAS / "voltas.csv")}
    inicios = {}
    for r in ler_csv(DADOS / "inicio_frenagem.csv"):
        inicios.setdefault(int(r["volta"]), []).append(int(r["quadro_video_inicio_observado"]))
    res = {"desacordos_tres_estados": [], "por_volta": {}}
    for v in voltas:
        linhas, por_quadro = series[v]
        quadros = [int(r["quadro"]) for r in linhas]
        orig = normalizar([float(r["px_freio_roi_original"]) for r in linhas], "max", "freio")
        acel1 = normalizar([float(r["px_acelerador"]) for r in linhas], "max", "acelerador")
        fr = [float(r["freio_pct"]) for r in linhas]; ac = [float(r["acelerador_pct"]) for r in linhas]
        px_rev = [int(r["px_freio"]) for r in linhas]
        vel = [int(r["velocidade_kmh"]) for r in linhas]; dist = [float(r["distancia_m"]) for r in linhas]
        idx = {q: i for i, q in enumerate(quadros)}
        for a in anot:
            if a["volta"] != v: continue
            i = idx[a["quadro"]]
            for canal, lido_rev, lido_1 in (("acelerador", ac[i], acel1[i]), ("freio", fr[i], orig[i])):
                if estado(lido_rev) != a[canal] or estado(lido_1) != a[canal]:
                    res["desacordos_tres_estados"].append({"n": a["n"], "volta": v, "quadro_video": a["quadro"], "canal": canal,
                        "anotado": a[canal], "revisada": [estado(lido_rev), round(lido_rev, 1)], "primeira": [estado(lido_1), round(lido_1, 1)]})
        plenos = [i for i, x in enumerate(fr) if x >= 90]
        n = len(linhas); s = resumo_voltas[v]
        t_hud = float(s["tempo_hud_s"]); t_video = n / FPS
        dist_aj = dist[-1] - (t_video - t_hud) * vel[-1] / 3.6
        zonas = []
        lig1 = [x >= LIMIAR_PRESENCA for x in orig]; lig2 = [x >= LIMIAR_PRESENCA for x in fr]
        for q in inicios.get(v, []):
            m = idx[q]; mpq = vel[m] / 3.6 / FPS; z = {"quadro_video": q, "distancia_m": round(dist[m], 1), "vel_kmh": vel[m]}
            for nome, lig in (("primeira", lig1), ("revisada", lig2)):
                bordas = [k for k in range(m - 15, m + 11) if lig[k] and not lig[k - 1]]
                k = min(bordas, key=lambda b: abs(b - m)) if bordas else None
                z[nome] = None if k is None else {"erro_quadros": k - m, "erro_m": round((k - m) * mpq, 2)}
            # quadros com freio na primeira versão sem nenhum pixel rosa no recorte revisado, nos 15 quadros anteriores
            z["pulso_espurio_antes_primeira"] = sum(1 for j in range(max(0, m - 15), m) if lig1[j] and px_rev[j] == 0)
            zonas.append(z)
        ultimo_parcial = max(i for i, x in enumerate(ac) if x < 90)
        res["por_volta"][v] = {
            "quadros": n,
            "ocr": {st: sum(r["ocr_status"] == st for r in linhas) for st in sorted({r["ocr_status"] for r in linhas})},
            "freio_ligado_primeira": sum(lig1), "freio_ligado_revisada": sum(lig2),
            "freio_espurio_primeira": sum(1 for i in range(n) if lig1[i] and px_rev[i] == 0),
            "freio_perdido_primeira": sum(1 for i in range(n) if lig2[i] and not lig1[i]),
            "px_max_freio": {"primeira": max(int(float(r["px_freio_roi_original"])) for r in linhas), "revisada": max(px_rev)},
            "mediana_barra_plena_pct": {"primeira": round(statistics.median([orig[i] for i in plenos]), 1),
                                        "revisada": round(statistics.median([fr[i] for i in plenos]), 1)},
            "distancia": {"estimada_m": round(dist[-1], 2), "erro_pct": round(100 * (dist[-1] - COMPRIMENTO_OFICIAL_M) / COMPRIMENTO_OFICIAL_M, 3),
                          "tempo_hud_s": t_hud, "duracao_video_s": round(t_video, 3), "dif_quadros": round((t_video - t_hud) * FPS, 1),
                          "ajustada_m": round(dist_aj, 2), "erro_ajustado_pct": round(100 * (dist_aj - COMPRIMENTO_OFICIAL_M) / COMPRIMENTO_OFICIAL_M, 3)},
            "inicio_frenagem": zonas,
            "tracado": {"acelerador_90_pct_quadros": round(100 * sum(x >= 90 for x in ac) / n, 1),
                        "sobreposicao_10_pct_revisada": round(100 * sum(a > 10 and f > 10 for a, f in zip(ac, fr)) / n, 2),
                        "sobreposicao_10_pct_primeira": round(100 * sum(a > 10 and f > 10 for a, f in zip(acel1, orig)) / n, 2),
                        "vel_max_kmh": max(vel), "vel_media_kmh": round(statistics.mean(vel), 1),
                        "reta_inicial_m": round(dist[next(i for i, x in enumerate(fr) if x >= LIMIAR_PRESENCA)]),
                        "reta_final_m": round(dist[-1] - dist[ultimo_parcial])},
        }
    return res


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else DADOS / "anotacao_autor_2voltas_corrigida.csv"
    amostra = {int(r["n"]): r for r in ler_csv(DADOS / "amostra_2voltas.csv")}
    voltas = sorted({int(r["volta"]) for r in amostra.values()})
    series = carregar_series(voltas)
    anot, problemas = [], []
    for r in ler_anotacao(caminho):
        n = int(float(r["n"])); ref = amostra[n]; q = int(ref["quadro_video"]); v = int(ref["volta"])
        if int(float(r["quadro_video"])) != q or int(float(r["volta"])) != v:
            problemas.append(f"Nº {n}: volta/quadro diferem da amostra ({v}/{q})")
        ea = ESTADOS.get(str(r["acelerador"]).strip().lower()); ef = ESTADOS.get(str(r["freio"]).strip().lower())
        if ea is None or ef is None: problemas.append(f"Nº {n}: estado em branco ou inválido"); continue
        anot.append(dict(n=n, volta=v, quadro=q, estrato=ref["estrato"], acelerador=ea, freio=ef,
                         acelerador_pct=num(r["acelerador_pct"]), freio_pct=num(r["freio_pct"]), vel=num(r["velocidade_kmh"])))
    if len(anot) != len(amostra): problemas.append(f"{len(amostra) - len(anot)} quadros da amostra sem anotação válida")
    for p in problemas: print("AVISO:", p)
    res = {"n_amostra": len(amostra), "problemas": problemas, "total": avaliar(anot, series)}
    imprimir("total", res["total"])
    for v in voltas:
        res[f"volta_{v}"] = avaliar([a for a in anot if a["volta"] == v], series)
        imprimir(f"volta {v}", res[f"volta_{v}"])
    res["extras"] = extras(voltas, series, anot)
    for d in res["extras"]["desacordos_tres_estados"]: print("desacordo:", d)
    for v, e in res["extras"]["por_volta"].items():
        print(f"volta {v}:", {k: e[k] for k in e if k != "inicio_frenagem"})
        for z in e["inicio_frenagem"]: print("   início", z)
    with open(PASTA / "resultados_avaliacao.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("resultado completo em", PASTA / "resultados_avaliacao.json")


if __name__ == "__main__":
    main()
