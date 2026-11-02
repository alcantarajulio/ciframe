# coding: utf-8
"""Gera tests/fixtures/gabarito_sequencias.json direto da coluna SEQ_FAMOSA.

Não usa nenhuma função de busca de main.py: o oráculo fica independente do
código testado. Para cada id de sequência famosa (0-5), coleta as músicas cujo
`musica.seqs_famosas` contém o id e grava {chave: [id_unico_musica, ...]} com
os ids em sorted() — a ordem de iteração varia com PYTHONHASHSEED
(01-research.md §2.4), então a comparação entre processos é de conjunto, não de
ordem. As chaves ficam na grafia histórica em minúsculas, como o fixture é
consumido pelos testes.

main.py é importado com SEQUENCIAS_DB apontando para um arquivo temporário,
para não criar dados/ no checkout; só as músicas interessam aqui.

Rode da raiz do repo: python scripts/gerar_gabarito_sequencias.py
"""
import atexit
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# antes do import de main, que abre o catálogo no boot
_tmpdir = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _tmpdir, True)
os.environ['SEQUENCIAS_DB'] = os.path.join(_tmpdir, 'sequencias.db')

import main

# chave histórica do fixture -> id na coluna SEQ_FAMOSA
CHAVES = [
    ('bm;g;d;a', 0),
    ('c;g;am;f', 1),
    ('em;g', 2),
    ('c;a7;dm;g7', 3),
    ('gm;f', 4),
    ('c;c7;f;fm', 5),
]

gabarito = {}
total = 0
for chave, id_seq in CHAVES:
    ids = sorted(musica.id_unico_musica
            for musica in main.musicas.values()
            if str(id_seq) in musica.seqs_famosas)
    gabarito[chave] = ids
    total += len(ids)
    print('%s: %d' % (chave, len(ids)))
print('total: %d' % total)

caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        '..', 'tests', 'fixtures', 'gabarito_sequencias.json')
os.makedirs(os.path.dirname(caminho), exist_ok=True)
with open(caminho, 'w') as f:
    json.dump(gabarito, f, indent=2, sort_keys=True)
    f.write('\n')
print('gravado: %s' % os.path.normpath(caminho))
