# Avaliação da leitura do HUD (TCC)

Material da avaliação descrita no TCC "Telemetria a partir do vídeo: extração de dados via HUD de simuladores de corrida em jogos em nuvem". O vídeo da sessão (Le Mans Ultimate no GeForce NOW, Fuji Speedway, 1280×720 a 30 fps, 34.701 quadros) não é público; os arquivos abaixo permitem recalcular todas as métricas sem ele.

```bash
python avaliacao/avaliar.py                    # só biblioteca padrão; grava avaliacao/resultados_avaliacao.json
python avaliacao/teste_detector_voltas.py      # detector de voltas, a partir das leituras gravadas do cronômetro
```

## Voltas avaliadas

O `leitor.py` revisado foi executado no vídeo inteiro com a separação automática de voltas (`--saida-voltas`). Das 10 voltas detectadas, 5 foram válidas (3, 4, 5, 6 e 9); a avaliação usa as duas mais rápidas, a 9 (1:50,075) e a 6 (1:52,917). O resumo está em `saidas_ferramenta/voltas.csv`.

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `saidas_ferramenta/voltas.csv` | Resumo das 10 voltas: quadros de início e fim, tempo no HUD, duração no vídeo, válida ou não e motivo, distância, maior ausência do cronômetro. |
| `saidas_ferramenta/volta_06.csv`, `volta_09.csv` | Saída do `leitor.py` revisado para cada volta (preset `lmu_gfn_720p`, normalização p99 na própria volta); `quadro` é o quadro do vídeo. |
| `dados/serie_volta_06_roi_original.csv`, `..._09_...` | Pixels rosa no recorte do freio da primeira versão (`[548:672, 1064:1078]`) nos mesmos quadros, gerados por `gerar_roi_original.py` a partir do vídeo. |
| `dados/amostra_2voltas.csv` | Sorteio estratificado: Nº, volta, índice e quadro do vídeo, tempo na volta e estrato (não foi mostrado ao anotador). |
| `dados/anotacao_autor_2voltas.xlsx` / `.csv` | Anotação cega feita pelo autor nos 80 quadros: estado do acelerador e do freio (ausente, parcial, pleno) e velocidade exibida. O CSV é a mesma planilha convertida, sem alterações. |
| `dados/anotacao_autor_2voltas_corrigida.xlsx` / `.csv` | A mesma anotação com uma única célula alterada: o freio do Nº 52 (quadro 32.782, volta 9), anotado como ausente, foi corrigido para pleno pelo autor ao revisar o único desacordo de presença (a barra está cheia na prancha). É a anotação usada por padrão no `avaliar.py`. |
| `dados/inicio_frenagem.csv` | Primeiro quadro com preenchimento rosa visível em cada uma das 13 zonas de frenagem (5 na volta 6 e 8 na volta 9), por inspeção quadro a quadro. |
| `dados/leituras_cronometro_gfn.csv` | Leituras do cronômetro a cada 5 quadros no vídeo inteiro, usadas no teste do detector de voltas. |
| `busca/` | Registro da busca bibliográfica de 16/11/2026. |
| `avaliar.py` | Matriz de confusão, acurácia, precisão, revocação e F1 da presença das barras; erro em quadros plenos; acerto da velocidade; IC 95% de Wilson e de Clopper–Pearson; desacordos de três estados; contaminação do recorte original; normalização; distância; início das frenagens; indicadores do traçado. |

## Protocolo

- **Amostra.** 40 quadros por volta, sorteados com semente fixa (20261118) e embaralhados. Estratos pela saída revisada, só para o sorteio: acelerador desligado (4), parcial (7) e pleno (6); freio parcial (7), pleno (7) e em transição (9; de 2 quadros antes a 3 depois de uma mudança de estado). Na volta 6 não há freio parcial fora das transições, e as 7 vagas passaram para as transições (16).
- **Anotação.** Feita pelo autor sobre pranchas com o HUD ampliado e guias de 25/50/75/100%, sem ver a saída da ferramenta nem os estratos. Estados: ausente, parcial (abaixo de ~90%) e pleno (~90% ou mais). O preenchimento percentual era opcional e não foi preenchido; por isso o erro de intensidade só é calculado nos quadros plenos (referência 100%). Um único anotador.
- **Presença na ferramenta.** Percentual ≥ 5%.
- **Início de frenagem.** Borda de subida do freio (≥ 5%) mais próxima do quadro observado, numa janela de 15 quadros antes a 10 depois; o erro em metros usa a velocidade do quadro observado e 1/30 s por quadro.

## Limitações

Uma sessão, um piloto, um carro, um circuito, uma resolução e um serviço (GeForce NOW). O recorte revisado do freio foi definido com dados desta mesma sessão (inclusive das voltas 6 e 9), então a avaliação da versão revisada não é um teste independente. Os estratos vêm da saída revisada, de modo que a amostra não representa os quadros em que só a primeira versão via freio; esses quadros são contados na volta inteira.
