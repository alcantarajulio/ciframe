# coding: utf-8
"""Gera tests/fixtures/gabarito_sequencias.json com o código atual de main.py.

Chama get_similares_por_sequencia(id_seq, generos) para id_seq 0-5 e grava
{chave: [id_unico_musica, ...]}. Os ids vão em sorted() porque a ordem de
iteração varia com PYTHONHASHSEED (01-research.md §2.4): comparação entre
processos é de conjunto, não de ordem.

Rode da raiz do repo: python scripts/gerar_gabarito_sequencias.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import main

CHAVES = ['bm;g;d;a', 'c;g;am;f', 'em;g', 'c;a7;dm;g7', 'gm;f', 'c;c7;f;fm']

gabarito = {}
total = 0
for id_seq, chave in enumerate(CHAVES):
    similares = main.get_similares_por_sequencia(id_seq, main.generos)
    gabarito[chave] = sorted(m['id_unico_musica'] for m in similares)
    total += len(gabarito[chave])
    print('%s: %d' % (chave, len(gabarito[chave])))
print('total: %d' % total)

caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        '..', 'tests', 'fixtures', 'gabarito_sequencias.json')
os.makedirs(os.path.dirname(caminho), exist_ok=True)
with open(caminho, 'w') as f:
    json.dump(gabarito, f, indent=2, sort_keys=True)
    f.write('\n')
print('gravado: %s' % os.path.normpath(caminho))
