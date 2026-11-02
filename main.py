# coding: utf-8
import json
from flask import Flask, request
import sys
from musica import *
from collections import OrderedDict
import unicodedata

import sequencias_db

app = Flask(__name__)

def limpa_cifra(raw_cifra):
    cifra = []
    for m in raw_cifra:
        if m.strip() != '':
            # filtra tablaturas
            if '|' in m:
                acorde = m.split('|')[0].split()[0]
                cifra.append(acorde)
            # lida com acordes separados por espaço
            else:
                tokens = [token for token in m.split()]
                cifra += tokens
    return cifra

# colunas do csv
ARTISTA_ID = 0
MUSICA_ID = 1
ARTISTA = 2
MUSICA = 3
GENERO = 4
POPULARIDADE = 5
TOM = 6
SEQ_FAMOSA = 7
CIFRA = 8
TAM_PAGINA = 100

genero_musicas = {}
generos = set()
acordes = set()
# quantas músicas usam cada grafia de acorde (uma vez por música, via
# musica.acordes): serve para ordenar as sugestões de grafia no POST /sequencias
uso_acordes = {}

musicas_dict = {}

f = open('data/top/dataset_final.csv')
f.readline()

for line in f:
    line = line.replace('"', '').replace('NA', '')[:-1]

    musica = line.split(',')
    musica[POPULARIDADE] = int(musica[POPULARIDADE].replace('.', ''))

    if musica[CIFRA] != '':
        musica[CIFRA] = limpa_cifra(musica[CIFRA].split(';'))
    else:
        musica[CIFRA] = []

    musica[SEQ_FAMOSA] = musica[SEQ_FAMOSA].split(";")

    # conjunto único de gêneros
    generos.add(musica[GENERO])

    # inclui música no dict de músicas
    musica_obj = Musica(musica[ARTISTA_ID], musica[ARTISTA],
            musica[MUSICA_ID], musica[MUSICA], musica[GENERO],
            int(musica[POPULARIDADE]), musica[SEQ_FAMOSA],
            musica[TOM], musica[CIFRA])

    musicas_dict[musica_obj.id_unico_musica] = musica_obj

    # conjunto único de acordes
    for acorde in musica_obj.acordes:
        acordes.add(acorde)
        uso_acordes[acorde] = uso_acordes.get(acorde, 0) + 1

    # constrói dict mapeando gênero para músicas
    # deve ser usado para melhorar o desempenho das buscas
    if musica_obj.genero in genero_musicas:
        genero_musicas[musica_obj.genero].append(musica_obj)
    else:
        genero_musicas[musica_obj.genero] = [musica_obj]

# dicionário de músicas cujos valores são ordenados por popularidade
musicas = OrderedDict(sorted(musicas_dict.items(),
    key=lambda x: x[1].popularidade, reverse = True))

# para trabalhar melhor com json
generos = list(generos)

# ordena genero_musicas por popularidade
for k,v in genero_musicas.items():
    genero_musicas[k].sort(key = lambda x : x.popularidade, reverse = True)

f.close()

# índice por vocabulário para a busca por sequência (regra A): frozenset dos
# acordes na caixa exata -> músicas com exatamente esse vocabulário. As listas
# seguem a mesma iteração de apply_filtro (gênero a gênero, cada gênero por
# popularidade) para preservar a ordem de apply_filtro — que é a mesma ordem
# antiga de get_similares_por_sequencia, hoje removida. Caixa exata: A7M
# (sétima maior) e A7m (menor com sétima) são acordes diferentes; o lower()
# antigo apagava isso (revisão de 2026-11-01 na proposta e no ADR 0002).
# apply_filtro só é definida abaixo, então o loop é feito aqui na mesma forma.
cifra_borda = {}
indice_vocabulario = {}
for genero in generos:
    for musica in genero_musicas[genero]:
        cifra_borda[musica.id_unico_musica] = ';' + ';'.join(
                musica.cifra) + ';'
        vocabulario = frozenset(musica.acordes)
        indice_vocabulario.setdefault(vocabulario, []).append(musica)

# catálogo de sequências: cria diretório/schema (conferindo user_version) e
# semeia as 6 originais de forma idempotente (INSERT OR IGNORE)
sequencias_db.init()
sequencias_db.seed()


@app.route('/')
def index():
    return app.send_static_file('index.html')
''' Busca por músicas que possuem no título ou no nome do artista o argumento passado por key.
params: key e generos (opcional). Caso generos não sejam definidos, a busca não irá filtrar por gênero.
exemplo 1: /search?key=no dia em que eu saí de casa
exemplo 2: /search?key=no dia em que eu saí de casa&generos=Rock,Samba '''

@app.route('/<path:path>')
def static_proxy(path):
  # send_static_file will guess the correct MIME type
  return app.send_static_file(path)

@app.route('/search')
def busca():
    generos_tag = request.args.get('generos', [])
    pagina_tag = request.args.get('pagina','1')
    keys = request.args.get('key').lower()
    keys = remover_combinantes(keys).split(' ')

    generos_key = generos
    if generos_tag:
        generos_key = generos_tag.split(',')

    collection = apply_filtro(musicas.values(), generos_key)
    out = []

    for musica in collection:
        text = '%s %s' % (musica.nome_artista.lower(), musica.nome_musica.lower())
        text_list = remover_combinantes(text).split(' ')
        if all(key in text_list for key in keys):
            matches = {
                'id_unico_musica' : musica.id_unico_musica,
                'id_artista' : musica.id_artista,
                'id_musica' : musica.id_musica,
                'nome_artista' : musica.nome_artista,
                'nome_musica' : musica.nome_musica,
                'genero' : musica.genero,
                'url' : musica.url,
            }
            out.append(matches)
    return json.dumps(get_pagina(out, pagina_tag))

# cópia
def remover_combinantes(string):
    string = unicodedata.normalize('NFD', string)
    return u''.join(ch for ch in string if unicodedata.category(ch) != 'Mn')

''' Retorna as músicas armazenadas no sistema (ordenados por popularidade).
    O serviço é paginado. Cada página tem tamanho 100, por default.
    params: pagina. Caso não seja definida a página, o valor default é 1.
    exemplo 1: /musica?pagina=2
    exemplo 2: /musica'''
@app.route('/musicas')
def get_musicas():
    return json.dumps([v.__dict__ for v in musicas.values()])

@app.route('/generos')
def get_generos():
    return json.dumps(generos)

@app.route('/acordes')
def get_acordes():
    return json.dumps(list(acordes))

@app.route('/sequencias')
def get_sequencias():
    out = []
    for linha in sequencias_db.listar():
        out.append({
            'id' : linha['id'],
            'acordes' : linha['acordes'],
            'origem' : linha['origem'],
            'total_musicas' : len(busca_por_sequencia(linha['acordes'])),
        })
    return json.dumps(out)

@app.route('/sequencias', methods=['POST'])
def criar_sequencia():
    dados = request.get_json(silent=True)
    if (not isinstance(dados, dict)
            or not isinstance(dados.get('acordes'), list)):
        return json.dumps({'erro' : 'corpo_invalido'}), 400

    tokens = dados['acordes']
    if any(not isinstance(token, str) for token in tokens):
        return json.dumps({'erro' : 'corpo_invalido'}), 400
    # tolera espaços nas pontas: trim antes de validar e guardar (" Bm " ->
    # "Bm"); a checagem de vazio roda depois, e só separadores também contam
    tokens = [token.strip() for token in tokens]
    if not tokens or any(token.strip(';,') == '' for token in tokens):
        return json.dumps({'erro' : 'sequencia_vazia'}), 400

    desconhecidos = []
    for token in tokens:
        if token in acordes:
            continue
        # sugestoes: todas as grafias do dataset iguais ignorando a caixa,
        # ordenadas por quantas músicas usam cada uma (mais usada primeiro;
        # empate alfabético). Uma lista, e não uma grafia só, porque com caixa
        # exata AM7 e Am7 são acordes diferentes: sugerir sorted()[0] preferia
        # as maiúsculas (am7 -> AM7, 40 músicas, em vez de Am7, 5.729).
        candidatos = sorted(
                (a for a in acordes if a.lower() == token.lower()),
                key=lambda a: (-uso_acordes.get(a, 0), a))
        desconhecidos.append({
            'acorde' : token,
            'sugestoes' : candidatos,
        })
    if desconhecidos:
        return json.dumps({
            'erro' : 'acorde_desconhecido',
            'acordes' : desconhecidos,
        }), 400

    linha, criada = sequencias_db.inserir_ou_obter(tokens)
    corpo = {
        'id' : linha['id'],
        'acordes' : linha['acordes'],
        'existente' : not criada,
        'total_musicas' : len(busca_por_sequencia(linha['acordes'])),
    }
    return json.dumps(corpo), 201 if criada else 200

@app.route('/musica/<m_id>/')
def get_musica(m_id):
    return json.dumps(musicas[m_id].__dict__)

@app.route('/similares')
def get_similares():
    # tratando request
    acordes_tag = request.args.get('acordes')
    id_musica_tag = request.args.get('id_unico_musica')
    sequencia_tag = request.args.get('sequencia')
    pagina_tag = request.args.get('pagina','1')

    # se não existir, filtra por todos.
    generos_tag = request.args.get('generos')
    generos_key = generos
    if generos_tag:
        generos_key = generos_tag.split(',')

    acordes = []
    if acordes_tag:
        acordes = acordes_tag.split(',')
    elif id_musica_tag:
        musica = musicas[id_musica_tag]
        acordes = musica.acordes
    elif sequencia_tag:
        try:
            pagina = int(pagina_tag)
        except ValueError:
            pagina = 0
        if pagina < 1:
            return json.dumps({'erro' : 'pagina_invalida'}), 400

        tokens = [token.strip() for token in sequencia_tag.split(',')]
        tokens = [token for token in tokens if token]
        if not tokens:
            return json.dumps([])

        linha = sequencias_db.buscar_por_chave(';'.join(tokens))
        if linha is None:
            return json.dumps([])

        return json.dumps(get_pagina(
                busca_por_sequencia(linha['acordes'], generos_key), pagina_tag))

    similares = get_similares(acordes, generos_key, id_musica_tag)

    return json.dumps(get_pagina(similares, pagina_tag))

# Busca por sequência de acordes (regra A): vocabulário exato via índice +
# bloco contíguo testado com bordas ';' (sem borda, 'A7;D;A' casaria por
# prefixo em 'A7;D;A7'). A caixa é exata (A7M ≠ A7m), tanto no vocabulário
# quanto no bloco. Devolve os mesmos campos do /similares (dict por
# música), na ordem de apply_filtro. generos_key filtra por gênero, como a
# função antiga fazia. Sequência vazia devolve [] — sem a
# guarda, ';;' casaria as músicas de cifra vazia (§2.8 da pesquisa).
def busca_por_sequencia(tokens, generos_key=None):
    if not tokens:
        return []
    seq_borda = ';' + ';'.join(tokens) + ';'

    similares = []
    for musica in indice_vocabulario.get(frozenset(tokens), []):
        if generos_key is not None and musica.genero not in generos_key:
            continue
        if seq_borda in cifra_borda[musica.id_unico_musica]:
            similar = {
                'id_unico_musica' : musica.id_unico_musica,
                'id_artista' : musica.id_artista,
                'id_musica' : musica.id_musica,
                'nome_artista' : musica.nome_artista,
                'nome_musica' : musica.nome_musica,
                'popularidade' : musica.popularidade,
                'acordes' : musica.acordes,
                'genero' : musica.genero,
                'url' : musica.url,
            }
            similares.append(similar)

    return similares


def get_pagina(colecao, pagina_tag):
    sl = (int(pagina_tag) - 1)*TAM_PAGINA
    return colecao[sl:sl+TAM_PAGINA]

def get_similares(acordes, generos_key, id_musica = None):

    # filtra para melhor desempenho
    collection = apply_filtro(musicas.values(), generos_key)

    similares = []
    for musica in collection:

        if musica.id_unico_musica != id_musica:

            inter = set(acordes).intersection(set(musica.acordes))
            diff = set(musica.acordes) - set(acordes)

            # somente as que tiverem interseção e as que forem
            # dos generos solicitados.
            if len(inter) > 0:
                similar = {
                        'id_unico_musica' : musica.id_unico_musica,
                        'id_artista' : musica.id_artista,
                        'id_musica' : musica.id_musica,
                        'nome_artista' : musica.nome_artista,
                        'nome_musica' : musica.nome_musica,
                        'popularidade' : musica.popularidade,
                        'acordes' : musica.acordes,
                        'genero' : musica.genero,
                        'url' : musica.url,
                        'diferenca' : list(diff),
                        'intersecao' : list(inter)
                }

                similares.append(similar)

    # ordenados por menor diferença, maior interseção e maior popularidade.
    return sorted(similares, key=lambda x: (len(x['diferenca']), -len(x['intersecao'])))

## Filtra a coleção de músicas por gênero.
def apply_filtro(musicas, generos_key):
    # filtra para melhor desempenho
    collection = []
    for genero in generos_key:
        if genero in generos:
            collection += genero_musicas[genero]
    return collection

@app.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

if __name__ == '__main__':
    app.run(debug=True)
