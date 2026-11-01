#!/usr/bin/env python3
# coding: utf-8
"""Pesquisa read-only: como as 6 sequencias de main.py sao marcadas no CSV.

Compara a tag pre-computada SEQ_FAMOSA (coluna 8 do CSV) com regras de matching
calculadas em tempo real a partir da coluna CIFRA (coluna 9), para as 6
sequencias hardcoded em main.py:40-45.

O parsing do CSV replica main.py:49-98 (incluindo o `line.replace('NA','')` e o
`[:-1]`). Nada e escrito no CSV. Tambem mede sequencias populares (secao 11),
duplicatas (12), a coluna TOM (13), rotacoes (14), vocabulario de acordes e
entradas de borda (15) e o que mudaria no matching por campo harmonico (16).

Uso:
    python3 scripts/research_seq_famosas_match.py
    python3 scripts/research_seq_famosas_match.py --app   # cross-check com main.py
    python3 scripts/research_seq_famosas_match.py --exemplos 5
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, OrderedDict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_REL = os.path.join('data', 'top', 'dataset_final.csv')
CSV_NOTAS_REL = os.path.join('data', 'dataset_seq_notas.csv')

# main.py:26-34
ARTISTA_ID, MUSICA_ID, ARTISTA, MUSICA, GENERO, POPULARIDADE, TOM, SEQ_FAMOSA, CIFRA = range(9)

# main.py:40-45 (chave usada pelo endpoint -> indice no CSV)
SEQUENCIAS = [
    (0, 'BmGDA', ('Bm', 'G', 'D', 'A')),
    (1, 'CGAmF', ('C', 'G', 'Am', 'F')),
    (2, 'EmG', ('Em', 'G')),
    (3, 'CA7DmG7', ('C', 'A7', 'Dm', 'G7')),
    (4, 'GmF', ('Gm', 'F')),
    (5, 'CC7FFm', ('C', 'C7', 'F', 'Fm')),
]

# data/mapeamento_sequencias_famosas.txt
NOMES = {
    0: 'Sequencia de Bm',
    1: 'Sequencia de C',
    2: 'Sequencia Em',
    3: 'Sequencia de C (Samba)',
    4: 'Sequencia de Gm',
    5: 'Sequencia de C (Samba cont.)',
}

# Progressoes populares (fora do CSV) para medir o que cada regra encontraria
POPULARES = [
    ('G D Em C', ('G', 'D', 'Em', 'C')),
    ('D A Bm G', ('D', 'A', 'Bm', 'G')),
    ('Am F C G', ('Am', 'F', 'C', 'G')),
    ('Em C G D', ('Em', 'C', 'G', 'D')),
    ('C Am F G', ('C', 'Am', 'F', 'G')),
    ('G Em C D', ('G', 'Em', 'C', 'D')),
    ('Am G F E', ('Am', 'G', 'F', 'E')),
    ('C G F G', ('C', 'G', 'F', 'G')),
    ('Em Am D G', ('Em', 'Am', 'D', 'G')),
    ('G C D', ('G', 'C', 'D')),
]


# ---------------------------------------------------------------- parsing ---

def limpa_cifra(raw_cifra):
    """Copia literal de main.py:11-23."""
    cifra = []
    for m in raw_cifra:
        if m.strip() != '':
            if '|' in m:
                acorde = m.split('|')[0].split()[0]
                cifra.append(acorde)
            else:
                tokens = [token for token in m.split()]
                cifra += tokens
    return cifra


def carrega(caminho):
    """Replica main.py:49-98. Devolve lista de dicts, um por linha de dados."""
    musicas = []
    n_linha = 1  # linha 1 do arquivo e o cabecalho
    with open(caminho, 'r') as f:
        f.readline()  # main.py:50
        for line in f:
            n_linha += 1
            bruta = line.rstrip('\n')
            limpa = line.replace('"', '').replace('NA', '')[:-1]  # main.py:53
            campos = limpa.split(',')                             # main.py:55
            cifra_tokens = limpa_cifra(campos[CIFRA].split(';')) if campos[CIFRA] != '' else []
            seqs = campos[SEQ_FAMOSA].split(';')                   # main.py:63
            musicas.append({
                'linha': n_linha,
                'id_artista': campos[ARTISTA_ID],
                'id_musica': campos[MUSICA_ID],
                'artista': campos[ARTISTA],
                'nome': campos[MUSICA],
                'genero': campos[GENERO],
                'popularidade': int(campos[POPULARIDADE].replace('.', '')),
                'tom': campos[TOM],
                'seqs_famosas': seqs,
                'cifra': cifra_tokens,
                'cifra_sem_limpeza': [t for t in campos[CIFRA].split(';') if t.strip()],
                'linha_bruta': bruta,
            })
    return musicas


# -------------------------------------------------------------- algoritmos ---

def alg_gerador(seq, m):
    """Regra que gerou a tag (scripts/generate_data_set.py:7-24).

    Duas condicoes simultaneas:
      1. `s in acorde`: a sequencia, unida por ';' e em minusculas, e substring
         contigua da cifra tambem unida por ';';
      2. para todo acorde da musica, ele pertence ao conjunto de acordes da
         sequencia (loop interno de get_famosas, linhas 16-20).
    Juntas, 1+2 significam: a sequencia aparece como bloco contiguo E o
    vocabulario de acordes da musica e exatamente o vocabulario da sequencia.
    """
    s = ';'.join(seq).lower()
    cifra = ';'.join(m['cifra']).lower()
    if s not in cifra:
        return False
    tokens = set(s.split(';'))
    return all(t in tokens for t in cifra.split(';'))


def alg_bloco_contiguo(seq, m):
    """So o teste 1 do gerador: bloco contiguo, sem exigir vocabulario exato."""
    return ';'.join(seq).lower() in ';'.join(m['cifra']).lower()


def alg_tokens_contiguos(seq, m):
    """Bloco contiguo comparando token a token (evita casar 'F' com 'F#'/'Fm')."""
    cifra = [t.lower() for t in m['cifra']]
    alvo = [t.lower() for t in seq]
    n = len(alvo)
    for i in range(len(cifra) - n + 1):
        if cifra[i:i + n] == alvo:
            return True
    return False


def alg_vocabulario_exato(seq, m):
    """So o teste 2 do gerador: mesmo conjunto de acordes, ordem ignorada."""
    return set(m['cifra']) == set(seq)


def alg_todos_acordes(seq, m):
    """Todos os acordes da sequencia aparecem na musica (ordem ignorada)."""
    return set(seq) <= set(m['cifra'])


def alg_subsequencia(seq, m):
    """Ordem preservada, buracos permitidos (acordes no meio nao invalidam)."""
    alvo = [t.lower() for t in seq]
    j = 0
    for t in (x.lower() for x in m['cifra']):
        if j < len(alvo) and t == alvo[j]:
            j += 1
    return j == len(alvo)


def alg_prefixo(seq, m):
    """Sequencia e o bloco inicial da cifra."""
    n = len(seq)
    return [t.lower() for t in m['cifra'][:n]] == [t.lower() for t in seq]


ALGORITMOS = OrderedDict([
    ('gerador', alg_gerador),
    ('bloco_contiguo', alg_bloco_contiguo),
    ('tokens_contiguos', alg_tokens_contiguos),
    ('vocabulario_exato', alg_vocabulario_exato),
    ('todos_acordes', alg_todos_acordes),
    ('subsequencia', alg_subsequencia),
    ('prefixo', alg_prefixo),
])

ROTULOS = {
    'gerador': 'A. regra do gerador (bloco contiguo + vocabulario exato)',
    'bloco_contiguo': 'B. bloco contiguo (substring), sem vocabulario exato',
    'tokens_contiguos': 'C. tokens contiguos, sem vocabulario exato',
    'vocabulario_exato': 'D. vocabulario exato, ordem ignorada',
    'todos_acordes': 'E. todos os acordes da sequencia presentes, ordem ignorada',
    'subsequencia': 'F. subsequencia (ordem, com buracos)',
    'prefixo': 'G. sequencia abre a cifra (prefixo)',
}


# ------------------------------------------------------------------ helpers ---

def chave(m):
    return '%s_%s' % (m['id_artista'], m['id_musica'])


def tag_marca(m, idx):
    """Semantica do runtime: main.py:209 `str(id_seq) in musica.seqs_famosas`."""
    return str(idx) in m['seqs_famosas']


def rotacoes(seq):
    """Rotacoes ciclicas distintas de uma sequencia (a propria inclusa)."""
    out = []
    for i in range(len(seq)):
        r = seq[i:] + seq[:i]
        if r not in out:
            out.append(r)
    return out


PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def divide_acorde(token):
    """Separa a classe de altura da raiz e o sufixo (qualidade/inversao).

    Ex.: 'C#m7/G#' -> (1, 'm7/G#'), 'Bb' -> (10, ''). Devolve None para token
    que nao comeca por nota (ex.: '2x', '13)'), que existem na cauda do CSV.
    """
    m = re.match(r'^([A-G])([#b]*)(.*)$', token)
    if not m:
        return None
    pc = PC[m.group(1)]
    for ch in m.group(2):
        pc = (pc + 1) % 12 if ch == '#' else (pc - 1) % 12
    return pc, m.group(3)


def tonal(seq, shift=0):
    """Acorde -> (classe de altura transposta, sufixo); None se nao ha nota.

    A classe de altura ignora a grafia (bemol/sustenido); o sufixo mantem
    qualidade e inversao, para a comparacao nao virar so a triade.
    """
    out = []
    for token in seq:
        d = divide_acorde(token)
        if d is None:
            return None
        out.append(((d[0] + shift) % 12, d[1]))
    return tuple(out)


def assinatura_tonal(tokens):
    """String delimitada por ';' para busca de bloco sem casar prefixo de token."""
    return ';' + ';'.join('%d|%s' % x for x in tokens) + ';'


_CIFRAS_TONAIS = None


def cifras_tonais():
    """(chave, assinatura, vocabulario) de cada musica, calculado uma vez."""
    global _CIFRAS_TONAIS
    if _CIFRAS_TONAIS is None:
        _CIFRAS_TONAIS = []
        for m in MUSICAS:
            t = tonal(m['cifra'])
            if t is None:
                continue
            _CIFRAS_TONAIS.append((chave(m), assinatura_tonal(t), frozenset(t)))
    return _CIFRAS_TONAIS


def ids_tonal(seq):
    """Uniao das 12 transposicoes: a mesma forma em qualquer tom."""
    alvos = [tonal(seq, shift) for shift in range(12)]
    if any(a is None for a in alvos):
        return set()
    ids = set()
    for alvo in alvos:
        assinatura = assinatura_tonal(alvo)
        vocabulario = frozenset(alvo)
        for k, cifra, voc in cifras_tonais():
            if voc <= vocabulario and assinatura in cifra:
                ids.add(k)
    return ids


def carrega_graus(caminho):
    """Le ARTISTA/MUSICA/TOM/CIFRA/NCIFRA de dataset_seq_notas.csv e alinha.

    Devolve (linhas, alinhadas). `linhas` tem uma entrada por linha do arquivo;
    `alinhadas` so as que tem CIFRA e NCIFRA com o mesmo numero de tokens (12
    linhas tem ';' sobrando na CIFRA e 23 nao tem NCIFRA). Cada entrada e um
    dict com 'chave', 'tom', 'cifra' e 'graus'.
    """
    linhas = []
    with open(caminho, newline='') as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor)
        i_art = cabecalho.index('ARTISTA')
        i_mus = cabecalho.index('MUSICA')
        i_tom = cabecalho.index('TOM')
        i_cif = cabecalho.index('CIFRA')
        i_nci = cabecalho.index('NCIFRA')
        for row in leitor:
            cifra = row[i_cif].split(';') if row[i_cif] else []
            graus = row[i_nci].split(';') if row[i_nci] else []
            if cifra and cifra[-1] == '' and len(cifra) != len(graus):
                cifra = cifra[:-1]  # strsplit do R descarta o vazio final
            linhas.append({
                'chave': '%s_%s' % (row[i_art], row[i_mus]),
                'tom': row[i_tom],
                'cifra': cifra,
                'graus': graus,
            })
    alinhadas = [x for x in linhas if x['cifra'] and len(x['cifra']) == len(x['graus'])]
    return linhas, alinhadas


def alg_graus(pat, linha):
    """Regra A em graus: bloco contiguo de graus + vocabulario exato de graus.

    Compara token a token: os graus tem 1 a 3 letras, entao busca por substring
    casaria 'I;V' dentro de 'VI;V' e inflaria a contagem.
    """
    graus = linha['graus']
    n = len(pat)
    achou = any(graus[i:i + n] == list(pat)
                for i in range(len(graus) - n + 1))
    return achou and set(graus) <= set(pat)


def ids_graus(pat, alinhadas):
    return {x['chave'] for x in alinhadas if alg_graus(pat, x)}


def rotulo_musica(m):
    return '%s - %s' % (m['artista'] or '?', m['nome'] or '?')


def trecho(m, seq, janela=3):
    """Trecho da cifra em volta da primeira ocorrencia dos acordes da sequencia."""
    alvo = [t.lower() for t in seq]
    cifra = [t.lower() for t in m['cifra']]
    n = len(alvo)
    for i in range(len(cifra) - n + 1):
        if cifra[i:i + n] == alvo:
            ini = max(0, i - janela)
            fim = min(len(cifra), i + n + janela)
            return '... ' + ' '.join(m['cifra'][ini:fim]) + ' ...'
    return ' '.join(m['cifra'][:8]) + (' ...' if len(m['cifra']) > 8 else '')


def compara(fn, idx, seq):
    set_tag = {chave(m) for m in MUSICAS if tag_marca(m, idx)}
    set_alg = {chave(m) for m in MUSICAS if fn(seq, m)}
    ambos = len(set_tag & set_alg)
    so_algo = len(set_alg - set_tag)
    so_tag = len(set_tag - set_alg)
    uniao = len(set_tag | set_alg)
    return {
        'tag': len(set_tag), 'algo': len(set_alg), 'ambos': ambos,
        'so_algo': so_algo, 'so_tag': so_tag,
        'jaccard': (ambos / uniao) if uniao else 1.0,
    }


# --------------------------------------------------------------------- main ---

MUSICAS = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app', action='store_true',
                    help='cross-check dos numeros contra o modulo main.py carregado')
    ap.add_argument('--exemplos', type=int, default=2,
                    help='quantos exemplos por bloco (default 2)')
    ap.add_argument('--ordem-generos', action='store_true',
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    os.chdir(RAIZ)

    if args.ordem_generos:
        # usado pelos subprocessos com PYTHONHASHSEED diferentes
        generos = set()
        with open(CSV_REL) as f:
            f.readline()
            for line in f:
                generos.add(line.replace('"', '').replace('NA', '')[:-1].split(',')[GENERO])
        print(list(generos)[:6])
        return

    MUSICAS.extend(carrega(CSV_REL))
    k = args.exemplos

    print('=' * 78)
    print('1. DATASET')
    print('=' * 78)
    print('linhas de dados lidas       : %d' % len(MUSICAS))
    print('musicas com cifra vazia     : %d' % sum(1 for m in MUSICAS if not m['cifra']))
    print('id_unico_musica distintos   : %d' % len({chave(m) for m in MUSICAS}))
    print('musicas com tag             : %d' % sum(
        1 for m in MUSICAS if any(s != '' for s in m['seqs_famosas'])))

    dist = Counter(';'.join(m['seqs_famosas']) for m in MUSICAS)
    print('\nvalores distintos da coluna SEQ_FAMOSA (ja splitada em ";" como main.py:63):')
    for valor, qtd in dist.most_common():
        print('  %-6r %6d' % (valor, qtd))

    multi = [m for m in MUSICAS if len([s for s in m['seqs_famosas'] if s != '']) > 1]
    print('musicas com mais de uma tag : %d' % len(multi))
    for m in multi[:5]:
        print('   %s  tags=%s' % (rotulo_musica(m), m['seqs_famosas']))

    # efeito colateral de main.py:53 (replace('NA','') na linha inteira)
    com_na = [m for m in MUSICAS if 'NA' in m['linha_bruta']]
    print('linhas com "NA" na linha crua: %d' % len(com_na))
    nomes_mudados = []
    for m in com_na:
        brutos = m['linha_bruta'].replace('"', '').split(',')
        if len(brutos) > ARTISTA and (brutos[ARTISTA] != m['artista'] or brutos[MUSICA] != m['nome']):
            nomes_mudados.append((brutos[ARTISTA], brutos[MUSICA], m['artista'], m['nome']))
    print('  dessas, nome de artista/musica alterado pelo replace: %d' % len(nomes_mudados))
    for b in nomes_mudados[:5]:
        print('    %r/%r -> %r/%r' % b)

    print()
    print('=' * 78)
    print('2. TAG POR SEQUENCIA (main.py:40-45)')
    print('=' * 78)
    print('%-3s %-9s %-28s %8s' % ('idx', 'chave', 'nome (mapeamento)', 'tag_marca'))
    for idx, chave_seq, seq in SEQUENCIAS:
        n = sum(1 for m in MUSICAS if tag_marca(m, idx))
        print('%-3d %-9s %-28s %8d' % (idx, chave_seq, NOMES[idx], n))
    print('total marcado por ao menos 1 tag: %d' % sum(
        1 for m in MUSICAS if any(tag_marca(m, i) for i, _, _ in SEQUENCIAS)))

    print()
    print('=' * 78)
    print('3. A REGRA DO GERADOR REPRODUZ A TAG?')
    print('=' * 78)
    print('%-3s %-9s %6s %6s %6s %7s %7s' % ('idx', 'chave', 'tag', 'algo', 'ambos', 'so_algo', 'so_tag'))
    for idx, chave_seq, seq in SEQUENCIAS:
        r = compara(alg_gerador, idx, seq)
        print('%-3d %-9s %6d %6d %6d %7d %7d' % (
            idx, chave_seq, r['tag'], r['algo'], r['ambos'], r['so_algo'], r['so_tag']))
    tot = {f: sum(compara(alg_gerador, i, s)[f] for i, _, s in SEQUENCIAS)
           for f in ('tag', 'algo', 'ambos', 'so_algo', 'so_tag')}
    print('%-3s %-9s %6d %6d %6d %7d %7d' % (
        'tot', '', tot['tag'], tot['algo'], tot['ambos'], tot['so_algo'], tot['so_tag']))

    print()
    print('=' * 78)
    print('4. CANDIDATOS x TAG (por sequencia)')
    print('=' * 78)
    print('tag=musicas marcadas no CSV | algo=regra em tempo real | so_algo=regra diz sim e')
    print('tag diz nao | so_tag=tag diz sim e regra diz nao')
    for nome_alg, fn in ALGORITMOS.items():
        print('\n' + '-' * 78)
        print(ROTULOS[nome_alg])
        print('-' * 78)
        print('%-3s %-9s %6s %6s %6s %7s %7s %8s' % (
            'idx', 'chave', 'tag', 'algo', 'ambos', 'so_algo', 'so_tag', 'jaccard'))
        for idx, chave_seq, seq in SEQUENCIAS:
            r = compara(fn, idx, seq)
            print('%-3d %-9s %6d %6d %6d %7d %7d %8.3f' % (
                idx, chave_seq, r['tag'], r['algo'], r['ambos'], r['so_algo'],
                r['so_tag'], r['jaccard']))
        tot = {f: sum(compara(fn, i, s)[f] for i, _, s in SEQUENCIAS)
               for f in ('tag', 'algo', 'ambos', 'so_algo', 'so_tag')}
        print('%-3s %-9s %6d %6d %6d %7d %7d' % (
            'tot', '', tot['tag'], tot['algo'], tot['ambos'], tot['so_algo'], tot['so_tag']))

    print()
    print('=' * 78)
    print('5. ORDEM E REPETICAO')
    print('=' * 78)
    print('%-3s %-9s %5s %8s %10s %12s %14s' % (
        'idx', 'chave', 'tag', 'vocab_eq', 'vocab_sem_bloco', 'bloco_com_extra', 'subseq_sem_bloco'))
    for idx, chave_seq, seq in SEQUENCIAS:
        vocab = [m for m in MUSICAS if alg_vocabulario_exato(seq, m)]
        sem_bloco = [m for m in vocab if not alg_tokens_contiguos(seq, m)]
        bloco_extra = [m for m in MUSICAS
                       if alg_tokens_contiguos(seq, m) and not alg_vocabulario_exato(seq, m)]
        subseq = [m for m in MUSICAS if alg_subsequencia(seq, m) and not alg_bloco_contiguo(seq, m)]
        print('%-3d %-9s %5d %8d %10d %12d %14d' % (
            idx, chave_seq, sum(1 for m in MUSICAS if tag_marca(m, idx)),
            len(vocab), len(sem_bloco), len(bloco_extra), len(subseq)))

    print()
    print('=' * 78)
    print('6. EXEMPLOS')
    print('=' * 78)
    for idx, chave_seq, seq in SEQUENCIAS:
        alvo = ' '.join(seq)
        marcadas = [m for m in MUSICAS if tag_marca(m, idx)]
        so_algo_b = [m for m in MUSICAS if alg_bloco_contiguo(seq, m) and not tag_marca(m, idx)]
        vocab_sem_bloco = [m for m in MUSICAS
                           if alg_vocabulario_exato(seq, m) and not alg_tokens_contiguos(seq, m)]
        so_tag_prefixo = [m for m in marcadas if not alg_prefixo(seq, m)]
        print('\n### seq %d %s  [%s]  tag=%d' % (idx, NOMES[idx], alvo, len(marcadas)))
        print('  (i) marcadas pela tag:')
        for m in marcadas[:k]:
            print('    %s:%d  %s' % (CSV_REL, m['linha'], rotulo_musica(m)))
            print('      cifra: %s' % trecho(m, seq))
        print('  (ii) bloco contiguo presente mas SEM tag (extra): %d' % len(so_algo_b))
        for m in so_algo_b[:k]:
            print('    %s:%d  %s' % (CSV_REL, m['linha'], rotulo_musica(m)))
            print('      cifra: %s' % trecho(m, seq))
        print('  (iii) vocab exato mas sem bloco contiguo (so ordem): %d' % len(vocab_sem_bloco))
        for m in vocab_sem_bloco[:k]:
            print('    %s:%d  %s' % (CSV_REL, m['linha'], rotulo_musica(m)))
            print('      cifra: %s' % ' '.join(m['cifra'][:10]))
        print('  (iv) tag diz sim mas prefixo diz nao: %d' % len(so_tag_prefixo))
        for m in so_tag_prefixo[:k]:
            print('    %s:%d  %s' % (CSV_REL, m['linha'], rotulo_musica(m)))
            print('      cifra: %s' % trecho(m, seq))

    print()
    print('=' * 78)
    print('7. NORMALIZACAO / TOKENS')
    print('=' * 78)
    todos = Counter()
    for m in MUSICAS:
        todos.update(m['cifra'])
    print('tokens de acorde distintos (CIFRA limpa) : %d' % len(todos))
    print('total de tokens (com repeticao)          : %d' % sum(todos.values()))
    print('tokens contendo "|"                      : %d' % sum(1 for t in todos if '|' in t))
    print('tokens com espaco/vazio                  : %d' % sum(
        1 for t in todos if ' ' in t or t.strip() == ''))

    def normaliza(a):
        return a[0].upper() + a[1:].lower() if a else a
    grupos = {}
    for t in todos:
        grupos.setdefault(normaliza(t), set()).add(t)
    colisoes = {k2: v for k2, v in grupos.items() if len(v) > 1}
    print('grupos que colidem se normalizar a caixa : %d' % len(colisoes))
    for c in sorted(colisoes)[:12]:
        print('  %-10s <- %s' % (c, sorted(colisoes[c])))

    print('\nocorrencia de cada acorde das 6 sequencias:')
    for idx, chave_seq, seq in SEQUENCIAS:
        partes = ['%s=%d' % (c, sum(1 for m in MUSICAS if c in m['cifra'])) for c in seq]
        print('  seq %d %-9s %s' % (idx, chave_seq, ', '.join(partes)))

    print('\nenarmonia (o runtime nao normaliza; grafias contam como acordes distintos):')
    for a, b in [('A#', 'Bb'), ('D#', 'Eb'), ('C#', 'Db'), ('G#', 'Ab'), ('F#', 'Gb')]:
        na = sum(1 for m in MUSICAS if a in m['cifra'])
        nb = sum(1 for m in MUSICAS if b in m['cifra'])
        nab = sum(1 for m in MUSICAS if a in m['cifra'] and b in m['cifra'])
        print('  %-3s em %5d musicas | %-3s em %5d | as duas %3d' % (a, na, b, nb, nab))

    print()
    print('=' * 78)
    print('8. PAGINACAO (TAM_PAGINA=100, main.py:35) E ORDEM DOS GENEROS')
    print('=' * 78)
    print('%-3s %-9s %6s %6s %8s' % ('idx', 'chave', 'tag', 'bloco', 'paginas(bloco)'))
    for idx, chave_seq, seq in SEQUENCIAS:
        n_tag = sum(1 for m in MUSICAS if tag_marca(m, idx))
        n_bloco = sum(1 for m in MUSICAS if alg_bloco_contiguo(seq, m))
        print('%-3d %-9s %6d %6d %8d' % (idx, chave_seq, n_tag, n_bloco, (n_bloco + 99) // 100))

    print('\nlist(generos) (main.py:92) vem de um set; o Dockerfile nao fixa')
    print('PYTHONHASHSEED, entao a ordem muda entre processos:')
    if not args.ordem_generos:
        import subprocess
        for seed in ('0', '1'):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            saida = subprocess.run(
                [sys.executable, os.path.abspath(__file__), '--ordem-generos'],
                env=env, capture_output=True, text=True).stdout.strip()
            print('  PYTHONHASHSEED=%s -> %s' % (seed, saida))

    print()
    print('=' * 78)
    print('9. FRONTEND x BACKEND, E A OUTRA BASE DE CIFRAS')
    print('=' * 78)
    app_js = os.path.join('static', 'assets', 'js', 'app.js')
    if os.path.exists(app_js):
        import re
        with open(app_js) as f:
            js = f.read()
        lista_js = re.findall(r'"([^"]+)"', js.split('GENEROS')[1])
        lista_back = sorted({m['genero'] for m in MUSICAS})
        print('GENEROS no frontend (app.js:6-58): %d' % len(lista_js))
        print('generos no backend (coluna 4)    : %d' % len(lista_back))
        print('  so no backend : %s' % sorted(set(lista_back) - set(lista_js)))
        print('  so no frontend: %s' % sorted(set(lista_js) - set(lista_back)))

    notas_rel = os.path.join('data', 'dataset_seq_notas.csv')
    if os.path.exists(notas_rel):
        import csv
        notas = {}
        with open(notas_rel, newline='') as f:
            leitor = csv.reader(f)
            next(leitor)
            for row in leitor:
                notas[(row[1], row[2])] = row[6]
        por_id = {(m['id_artista'], m['id_musica']): m for m in MUSICAS}
        comuns = set(por_id) & set(notas)
        cruas = sum(1 for c in comuns
                    if [t for t in notas[c].split(';') if t.strip()] == por_id[c]['cifra_sem_limpeza'])
        limpas = sum(1 for c in comuns
                     if [t for t in notas[c].split(';') if t.strip()] == por_id[c]['cifra'])
        print('\nids em comum com %s: %d' % (notas_rel, len(comuns)))
        print('  cifras identicas na coluna CIFRA crua : %d' % cruas)
        print('  cifras identicas depois de limpa_cifra: %d' % limpas)

    print()
    print('=' * 78)
    print('10. CUSTO (uma passada pelas 67.585 musicas x 6 sequencias)')
    print('=' * 78)
    import time
    for nome_alg, fn in ALGORITMOS.items():
        t0 = time.perf_counter()
        total = 0
        for idx, chave_seq, seq in SEQUENCIAS:
            total += sum(1 for m in MUSICAS if fn(seq, m))
        dt = time.perf_counter() - t0
        print('%-20s %6.0f ms  (%d matches)' % (nome_alg, dt * 1000, total))

    print()
    print('=' * 78)
    print('11. SEQUENCIAS POPULARES SOB CADA REGRA')
    print('=' * 78)
    print('A=gerador B=substring C=tokens D=vocab E=todos F=subseq G=prefixo')
    print('%-18s %7s %7s %7s %7s %7s %7s %7s' % (
        'sequencia', 'A', 'B', 'C', 'D', 'E', 'F', 'G'))
    for nome, seq in POPULARES:
        nums = [sum(1 for m in MUSICAS if fn(seq, m)) for fn in ALGORITMOS.values()]
        print('%-18s %7d %7d %7d %7d %7d %7d %7d' % ((nome,) + tuple(nums)))
    print('\nmesma tabela para as 6 de main.py:40-45 (referencia):')
    for idx, chave_seq, seq in SEQUENCIAS:
        nums = [sum(1 for m in MUSICAS if fn(seq, m)) for fn in ALGORITMOS.values()]
        print('%-18s %7d %7d %7d %7d %7d %7d %7d' % ((' '.join(seq),) + tuple(nums)))

    print()
    print('=' * 78)
    print('12. DUPLICATAS E IDENTIDADE DE MUSICA')
    print('=' * 78)
    ids = [chave(m) for m in MUSICAS]
    print('linhas de dados                   : %d' % len(ids))
    print('id_unico_musica distintos         : %d' % len(set(ids)))
    print('linhas repetindo um id            : %d' % (len(ids) - len(set(ids))))
    grupos = {}
    for m in MUSICAS:
        k = (m['artista'].strip().lower(), m['nome'].strip().lower())
        grupos.setdefault(k, set()).add(chave(m))
    dup = {k: v for k, v in grupos.items() if len(v) > 1}
    print('pares (artista, nome) em >1 id    : %d' % len(dup))
    print('musicas envolvidas nesses pares   : %d' % sum(len(v) for v in dup.values()))
    for k, v in list(dup.items())[:5]:
        print('  %s / %s -> %d ids' % (k[0], k[1], len(v)))

    print()
    print('=' * 78)
    print('13. COLUNA TOM (campo harmonico): o que existe no CSV')
    print('=' * 78)
    toms = Counter(m['tom'] for m in MUSICAS)
    com_tom = [m for m in MUSICAS if m['tom'] != '']
    tom_na_cifra = sum(1 for m in com_tom if m['tom'] in m['cifra'])
    enarm = {'A#': 'Bb', 'D#': 'Eb', 'C#': 'Db', 'G#': 'Ab', 'F#': 'Gb'}
    enarm_inv = {v: k for k, v in enarm.items()}
    def equivalente(t):
        return enarm.get(t) or enarm_inv.get(t)
    tom_enh = sum(1 for m in com_tom
                  if m['tom'] not in m['cifra']
                  and equivalente(m['tom']) in m['cifra'])
    tom_primeiro = sum(1 for m in com_tom if m['cifra'] and m['cifra'][0] == m['tom'])
    print('valores distintos de TOM  : %d' % len(toms))
    print('musicas com TOM vazio     : %d' % sum(1 for m in MUSICAS if m['tom'] == ''))
    print('musicas com TOM preenchido: %d' % len(com_tom))
    print('  TOM como token exato na cifra        : %d' % tom_na_cifra)
    print('  TOM ausente, mas enarmonico presente : %d' % tom_enh)
    print('  TOM e o primeiro acorde da cifra     : %d' % tom_primeiro)
    for t, q in toms.most_common(12):
        print('  %-6r %6d' % (t, q))

    print()
    print('=' * 78)
    print('14. ROTACAO: "G D Em C" E "D Em C G" SAO A MESMA SEQUENCIA?')
    print('=' * 78)
    base = POPULARES + [(' '.join(seq), seq) for _, _, seq in SEQUENCIAS]

    def marcadas(seq, fn=alg_gerador):
        return {chave(m) for m in MUSICAS if fn(seq, m)}

    grupos = OrderedDict()
    for nome, seq in base:
        grupos.setdefault(min(rotacoes(seq)), []).append(nome)
    print('forma canonica (menor rotacao) compartilhada por mais de uma sequencia:')
    for canon, nomes in grupos.items():
        if len(nomes) > 1:
            print('  %-16s <- %s' % (' '.join(canon), ' | '.join(nomes)))

    print()
    print('%-16s %5s %5s %5s %5s %5s %5s' % (
        'sequencia', 'A', 'rots', 'ident', 'jmin', 'jmax', 'uniao'))
    for nome, seq in base:
        ids = marcadas(seq)
        rots = rotacoes(seq)[1:]
        uniao = set(ids)
        ident = 0
        jac = []
        for r in rots:
            outros = marcadas(r)
            uniao |= outros
            if outros == ids:
                ident += 1
            jac.append(len(ids & outros) / len(ids | outros))
        print('%-16s %5d %5d %5d %5.2f %5.2f %5d' % (
            nome, len(ids), len(rots), ident, min(jac), max(jac), len(uniao)))

    print()
    print('uniao das rotacoes sob A x regra D (mesmo vocabulario, ordem ignorada):')
    for nome, seq in base:
        uniao = set()
        for r in rotacoes(seq):
            uniao |= marcadas(r)
        vocab = marcadas(seq, alg_vocabulario_exato)
        print('  %-16s uniao=%4d  D=%4d  D fora da uniao=%4d' % (
            nome, len(uniao), len(vocab), len(vocab - uniao)))

    print()
    print('=' * 78)
    print('15. ACORDE INEXISTENTE, SEQUENCIA VAZIA E SEQUENCIA INEXISTENTE')
    print('=' * 78)
    por_musica = Counter()
    for m in MUSICAS:
        for t in set(m['cifra']):
            por_musica[t] += 1
    print('tokens de acorde distintos: %d (em %d musicas)' % (len(por_musica), len(MUSICAS)))
    for n in (1, 5, 10, 100):
        print('  tokens presentes em <=%3d musicas: %5d' % (
            n, sum(1 for c in por_musica.values() if c <= n)))
    print('  10 mais frequentes: %s' % ', '.join(
        '%s(%d)' % (t, c) for t, c in por_musica.most_common(10)))
    fora = [t for t in por_musica if not re.match(r'^[A-G]', t)]
    print('  tokens que nao comecam por nota maiuscula: %d  (ex.: %s)' % (
        len(fora), ', '.join(sorted(fora)[:6])))

    borda = [
        ('vazia', ('',)),
        ('C', ('C',)),
        ('Am', ('Am',)),
        ('G G', ('G', 'G')),
        ('G D Em C G D Em C', ('G', 'D', 'Em', 'C', 'G', 'D', 'Em', 'C')),
        ('Cb (inexistente)', ('Cb',)),
        ('X7 (inexistente)', ('X7',)),
        ('C H (H inexistente)', ('C', 'H')),
    ]
    print()
    print('regras A-G para entradas de borda (uma sequencia por request):')
    print('%-22s %s' % ('entrada', 'A/B/C/D/E/F/G'))
    for nome, seq in borda:
        nums = [sum(1 for m in MUSICAS if fn(seq, m)) for fn in ALGORITMOS.values()]
        print('%-22s %s' % (nome, nums))
    print('obs.: a sequencia vazia casa %d musicas na regra A (as de cifra vazia)'
          % sum(1 for m in MUSICAS if alg_gerador(('',), m)))
    print('      e %d na regra B (todas); precisa de guarda antes de qualquer regra.'
          % sum(1 for m in MUSICAS if alg_bloco_contiguo(('',), m)))

    print()
    print('=' * 78)
    print('16. CAMPO HARMONICO: O QUE MUDARIA NO MATCHING')
    print('=' * 78)
    universo = {chave(m) for m in MUSICAS}
    linhas, alinhadas = carrega_graus(CSV_NOTAS_REL)
    fora = [x for x in alinhadas if x['chave'] not in universo]
    alinhadas = [x for x in alinhadas if x['chave'] in universo]
    tokens_grau = [g for x in alinhadas for g in x['graus']]
    vazios = sum(1 for g in tokens_grau if g == '')
    na = sum(1 for g in tokens_grau if g == 'NA')
    print('(a) a base NCIFRA (data/dataset_seq_notas.csv)')
    print('  linhas no arquivo                  : %d' % len(linhas))
    print('  musicas no runtime                 : %d' % len(MUSICAS))
    print('  pares (artista, musica) distintos  : %d'
          % len({(m['artista'], m['nome']) for m in MUSICAS}))
    print('  linhas com CIFRA vazia             : %d'
          % sum(1 for x in linhas if not x['cifra']))
    print('  linhas alinhadas CIFRA x NCIFRA    : %d'
          % sum(1 for x in linhas if x['cifra'] and len(x['cifra']) == len(x['graus'])))
    print('    dessas, com chave no runtime     : %d (%d fora do runtime)'
          % (len(alinhadas), len(fora)))
    print('    TOM vazio                        : %d'
          % sum(1 for x in alinhadas if x['tom'] == ''))
    print('    com >=1 grau vazio               : %d' % sum(
        1 for x in alinhadas if any(g == '' for g in x['graus'])))
    print('    com >=1 ``NA``                   : %d' % sum(
        1 for x in alinhadas if any(g == 'NA' for g in x['graus'])))
    print('  tokens de grau nas linhas alinhadas: %d, %d distintos' % (
        len(tokens_grau), len(set(tokens_grau))))
    print('    vazios                           : %d (%.2f%%)'
          % (vazios, 100.0 * vazios / len(tokens_grau)))
    print('    ``NA``                           : %d (%.2f%%)'
          % (na, 100.0 * na / len(tokens_grau)))
    print('    mais frequentes                  : %s' % ', '.join(
        '%s(%d)' % (g or 'vazio', c) for g, c in Counter(tokens_grau).most_common(9)))

    print()
    print('(b) sem TOM: comparar a consulta transposta nas 12 classes de altura')
    print('  %-14s %10s %9s %7s' % ('consulta', 'literal A', 'uniao 12', 'ganho'))
    grupos = [
        ('populares', [
            ('C G Am F', ('C', 'G', 'Am', 'F')),
            ('G D Em C', ('G', 'D', 'Em', 'C')),
            ('G C D', ('G', 'C', 'D')),
            ('Bm G D A', ('Bm', 'G', 'D', 'A')),
        ]),
        ('as 6 do catalogo', [(chave_seq, seq) for _, chave_seq, seq in SEQUENCIAS]),
    ]
    for titulo, itens in grupos:
        print('  %s:' % titulo)
        for nome, seq in itens:
            a = {chave(m) for m in MUSICAS if alg_gerador(seq, m)}
            t = ids_tonal(seq)
            razao = (len(t) / float(len(a))) if a else 0.0
            print('    %-12s %10d %9d %6.1fx' % (nome, len(a), len(t), razao))
    print('  musicas fora do matching tonal (algum token sem nota): %d'
          % sum(1 for m in MUSICAS if tonal(m['cifra']) is None))

    print()
    print('(c) por graus (NCIFRA): bloco contiguo + vocabulario exato de graus')
    print('  %-12s %5s %-12s %9s %11s' % (
        'progressao', 'tom', 'graus', 'so bloco', 'bloco+vocab'))
    for nome, tom, pat in [
        ('C G Am F', 'C', ('I', 'V', 'VI', 'IV')),
        ('G D Em C', 'G', ('I', 'V', 'VI', 'IV')),
        ('G C D', 'G', ('I', 'IV', 'V')),
        ('Bm G D A', 'D', ('VI', 'IV', 'I', 'V')),
    ]:
        bloco = sum(
            1 for x in alinhadas
            if any(x['graus'][i:i + len(pat)] == list(pat)
                   for i in range(len(x['graus']) - len(pat) + 1)))
        exato = len(ids_graus(pat, alinhadas))
        print('  %-12s %5s %-12s %9d %11d' % (
            nome, tom, ' '.join(pat), bloco, exato))
    print('  obs.: o NCIFRA descarta o modo, entao "C G Am F" em C e')
    print('        "G D Em C" em G caem no mesmo padrao I V VI IV.')
    print('        comparacao token a token: por substring, "I;V" casaria')
    print('        dentro de "VI;V" e inflaria o bloco de 6.527 para 7.605.')

    por_bloco = {}
    for x in alinhadas:
        graus = x['graus']
        voc = set(graus)
        if '' in voc:
            continue
        for i in range(len(graus) - 3):
            bloco = tuple(graus[i:i + 4])
            if set(bloco) == voc:
                por_bloco.setdefault(bloco, set()).add(x['chave'])
    top = sorted(por_bloco.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:6]
    print()
    print('  blocos de 4 graus com pelo menos 1 musica: %d' % len(por_bloco))
    print('  mais frequentes (musicas distintas):')
    for bloco, ids in top:
        print('    %-22s %5d' % (' '.join(bloco), len(ids)))

    print()
    print('(d) sobreposicao para C G Am F (296 musicas na regra A)')
    seq = ('C', 'G', 'Am', 'F')
    pat = ('I', 'V', 'VI', 'IV')
    lit = {chave(m) for m in MUSICAS if alg_gerador(seq, m)}
    tom = ids_tonal(seq)
    grau = ids_graus(pat, alinhadas)
    print('  literal (A)     : %4d' % len(lit))
    print('  uniao 12 tons   : %4d' % len(tom))
    print('  graus I V VI IV : %4d' % len(grau))
    print('  graus & tons    : %4d' % len(grau & tom))
    print('  so graus        : %4d  (qualidade, modo ou inversao diferente)'
          % len(grau - tom))
    print('  so tons         : %4d  (TOM divergente, ou grau vazio/ausente)'
          % len(tom - grau))
    print('  musicas do runtime com NCIFRA alinhado: %d de %d (%.1f%%)' % (
        len(alinhadas), len(MUSICAS), 100.0 * len(alinhadas) / len(MUSICAS)))
    por_chave_graus = {x['chave']: x for x in alinhadas}
    fora_grau = lit - grau
    sem_linha = {k for k in fora_grau if k not in por_chave_graus}
    print('  dos %d literais, %d tambem estao nos graus; %d fora: %d sem linha na base, %d com TOM divergente'
          % (len(lit), len(lit & grau), len(fora_grau), len(sem_linha),
             len(fora_grau - sem_linha)))
    for k in sorted(grau - tom)[:2]:
        x = por_chave_graus.get(k)
        if not x:
            continue
        for i in range(len(x['graus']) - 3):
            if tuple(x['graus'][i:i + 4]) == pat:
                print('  ex. so graus: %s -> %s' % (k, ' '.join(x['cifra'][i:i + 4])))
                break

    if args.app:
        print()
        print('=' * 78)
        print('17. CROSS-CHECK COM O MODULO main.py CARREGADO')
        print('=' * 78)
        if RAIZ not in sys.path:
            sys.path.insert(0, RAIZ)
        import main as app_main
        print('main.musicas  : %d' % len(app_main.musicas))
        print('main.generos  : %d  (primeiros: %s)' % (len(app_main.generos), app_main.generos[:4]))
        print('main.acordes  : %d' % len(app_main.acordes))
        for idx, chave_seq, seq in SEQUENCIAS:
            via_app = app_main.get_similares_por_sequencia(idx, app_main.generos)
            ids_app = {r['id_unico_musica'] for r in via_app}
            ids_tag = {chave(m) for m in MUSICAS if tag_marca(m, idx)}
            pagina1 = app_main.get_pagina(via_app, '1')
            print('  seq %d %-9s app=%4d tag=%4d iguais=%s pagina1=%d' % (
                idx, chave_seq, len(ids_app), len(ids_tag), ids_app == ids_tag, len(pagina1)))
        print('\nchaves aceitas por GET /similares?sequencia= (main.py:190-197):')
        for idx, chave_seq, seq in SEQUENCIAS:
            print('  "%s" (idx %d) <- frontend envia "%s"' % (chave_seq, idx, ','.join(seq)))

        print('\nrequisicoes via Flask test client:')
        import json
        cliente = app_main.app.test_client()
        for url in ['/musicas', '/generos', '/acordes',
                    '/similares?sequencia=BmGDA',
                    '/similares?sequencia=BmGDA&pagina=2',
                    '/similares?sequencia=Bm,G,D,A',
                    '/similares?sequencia=EmG',
                    '/similares?sequencia=CG',
                    '/similares?sequencia=xyz',
                    '/similares?sequencia=AmF',
                    '/similares?acordes=Bm,G']:
            resp = cliente.get(url)
            corpo = resp.get_data(as_text=True)
            try:
                itens = len(json.loads(corpo))
            except ValueError:
                itens = 'n/a'
            print('  %-45s status=%s ct=%-24s itens=%s' % (
                url, resp.status_code, resp.headers.get('Content-Type'), itens))

        print('\nentradas de borda em /similares?sequencia= (hoje, main.py:190-197):')
        app_main.app.logger.disabled = True
        for qs in ['sequencia=', 'sequencia=,', 'sequencia=,,,',
                   'sequencia=%20', 'sequencia=%20,%20', 'sequencia=xyz',
                   'sequencia=G', 'sequencia=bm,g,d,a', 'sequencia=Bm,G,D,A,',
                   'sequencia=Bm,%20G', 'sequencia=Bm,G,D,A,C,C,C']:
            resp = cliente.get('/similares?' + qs)
            try:
                itens = len(json.loads(resp.get_data(as_text=True)))
            except ValueError:
                itens = 'n/a'
            print('  %-32s status=%s itens=%s' % (qs, resp.status_code, itens))
        for p in ['abc', '0', '-1']:
            resp = cliente.get('/similares?sequencia=BmGDA&pagina=' + p)
            print('  %-32s status=%s' % ('pagina=' + p, resp.status_code))


if __name__ == '__main__':
    main()
