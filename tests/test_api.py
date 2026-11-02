# coding: utf-8
import atexit
import json
import os
import shutil
import tempfile
import unittest

# isola o banco do catálogo antes de importar main (o boot roda no import)
_tmpdir = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _tmpdir, True)
CAMINHO_DB = os.path.join(_tmpdir, 'sequencias.db')
os.environ['SEQUENCIAS_DB'] = CAMINHO_DB

import main
import sequencias_db

GABARITO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'fixtures', 'gabarito_sequencias.json')

def resetar_banco():
    for sufixo in ('', '-wal', '-shm'):
        caminho = CAMINHO_DB + sufixo
        if os.path.exists(caminho):
            os.remove(caminho)
    sequencias_db.init()
    sequencias_db.seed()

class TestSequenciasApi(unittest.TestCase):

    def setUp(self):
        os.environ['SEQUENCIAS_DB'] = CAMINHO_DB
        resetar_banco()
        self.client = main.app.test_client()

    def corpo(self, resposta):
        return json.loads(resposta.get_data(as_text=True))

    def test_get_sequencias_lista_as_seis_sementes(self):
        resposta = self.client.get('/sequencias')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('text/html', resposta.content_type)
        sequencias = self.corpo(resposta)
        self.assertEqual(len(sequencias), 6)
        self.assertTrue(all(s['origem'] == 'seed' for s in sequencias))
        for sequencia in sequencias:
            self.assertIn('id', sequencia)
            self.assertIn('acordes', sequencia)
            self.assertIn('total_musicas', sequencia)

    def test_total_musicas_bate_com_o_gabarito(self):
        with open(GABARITO) as f:
            gabarito = json.load(f)
        sequencias = self.corpo(self.client.get('/sequencias'))
        totais = {';'.join(a.lower() for a in s['acordes']): s['total_musicas']
                for s in sequencias}
        self.assertEqual(totais['bm;g;d;a'], len(gabarito['bm;g;d;a']))

    def test_post_cria_sequencia_nova(self):
        resposta = self.client.post('/sequencias',
                json={'acordes': ['D', 'A', 'Bm', 'G']})
        self.assertEqual(resposta.status_code, 201)
        corpo = self.corpo(resposta)
        self.assertEqual(corpo['acordes'], ['D', 'A', 'Bm', 'G'])
        self.assertFalse(corpo['existente'])
        self.assertIsInstance(corpo['id'], int)
        self.assertGreater(corpo['total_musicas'], 0)
        lista = self.corpo(self.client.get('/sequencias'))
        self.assertEqual(len(lista), 7)

    def test_post_repetido_e_idempotente(self):
        resposta_primeiro = self.client.post('/sequencias',
                json={'acordes': ['D', 'A', 'Bm', 'G']})
        self.assertEqual(resposta_primeiro.status_code, 201)
        primeiro = self.corpo(resposta_primeiro)
        resposta = self.client.post('/sequencias',
                json={'acordes': ['D', 'A', 'Bm', 'G']})
        self.assertEqual(resposta.status_code, 200)
        segundo = self.corpo(resposta)
        self.assertTrue(segundo['existente'])
        self.assertEqual(segundo['id'], primeiro['id'])
        lista = self.corpo(self.client.get('/sequencias'))
        self.assertEqual(len(lista), 7)

    def test_post_idempotente_entre_grafias_que_so_diferem_na_caixa(self):
        # Am7 e AM7 são grafias do mesmo acorde no dataset (as duas passam na
        # validação exata) e caem na mesma chave am7;d: o segundo POST devolve
        # a existente, com o mesmo id e os acordes como foram digitados antes
        primeira = self.client.post('/sequencias',
                json={'acordes': ['Am7', 'D']})
        self.assertEqual(primeira.status_code, 201)
        corpo_primeiro = self.corpo(primeira)

        segunda = self.client.post('/sequencias',
                json={'acordes': ['AM7', 'D']})
        self.assertEqual(segunda.status_code, 200)
        corpo_segundo = self.corpo(segunda)
        self.assertTrue(corpo_segundo['existente'])
        self.assertEqual(corpo_segundo['id'], corpo_primeiro['id'])
        self.assertEqual(corpo_segundo['acordes'], ['Am7', 'D'])

        # espaços nas pontas são trimados antes da validação: mesma chave
        com_espacos = self.client.post('/sequencias',
                json={'acordes': [' AM7 ', ' D ']})
        self.assertEqual(com_espacos.status_code, 200)
        self.assertEqual(self.corpo(com_espacos)['id'], corpo_primeiro['id'])

        # A7M é sétima maior, acorde diferente de Am7 (menor com sétima):
        # a chave a7m;d não colapsa com am7;d, então cria outra sequência
        terceira = self.client.post('/sequencias',
                json={'acordes': ['A7M', 'D']})
        self.assertEqual(terceira.status_code, 201)
        self.assertNotEqual(self.corpo(terceira)['id'], corpo_primeiro['id'])

        lista = self.corpo(self.client.get('/sequencias'))
        self.assertEqual(len(lista), 8)

    def test_post_tolera_espacos_nas_pontas_dos_tokens(self):
        # " Bm " e " G " passam na validação e são guardados sem os espaços
        resposta = self.client.post('/sequencias',
                json={'acordes': [' Bm ', ' G ']})
        self.assertEqual(resposta.status_code, 201)
        corpo = self.corpo(resposta)
        self.assertFalse(corpo['existente'])
        self.assertEqual(corpo['acordes'], ['Bm', 'G'])

    def test_post_corpo_invalido(self):
        for kwargs in (
                {'data': 'isto nao e json', 'content_type': 'text/plain'},
                {'json': {}},
                {'json': {'outra': ['Bm']}},
                {'json': {'acordes': 'Bm G D A'}},
                {'json': {'acordes': [1, 2]}},
        ):
            resposta = self.client.post('/sequencias', **kwargs)
            self.assertEqual(resposta.status_code, 400, kwargs)
            self.assertEqual(self.corpo(resposta), {'erro': 'corpo_invalido'})

    def test_post_sequencia_vazia(self):
        for acordes in ([], [''], ['   '], [',', ';'], ['', 'C']):
            resposta = self.client.post('/sequencias',
                    json={'acordes': acordes})
            self.assertEqual(resposta.status_code, 400, acordes)
            self.assertEqual(self.corpo(resposta),
                    {'erro': 'sequencia_vazia'})

    def test_post_acorde_desconhecido_com_sugestao(self):
        resposta = self.client.post('/sequencias',
                json={'acordes': ['bm', 'G', 'D', 'A']})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('text/html', resposta.content_type)
        self.assertEqual(self.corpo(resposta), {
            'erro': 'acorde_desconhecido',
            'acordes': [{'acorde': 'bm', 'sugestao': 'Bm'}],
        })
        # nada foi criado
        self.assertEqual(len(self.corpo(self.client.get('/sequencias'))), 6)

    def test_post_acorde_desconhecido_sem_sugestao(self):
        resposta = self.client.post('/sequencias',
                json={'acordes': ['Cb', 'G']})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.corpo(resposta), {
            'erro': 'acorde_desconhecido',
            'acordes': [{'acorde': 'Cb', 'sugestao': None}],
        })

    def _todas_as_musicas(self, sequencia):
        ids = []
        pagina = 1
        while True:
            resposta = self.client.get('/similares', query_string={
                    'sequencia': sequencia, 'pagina': pagina})
            self.assertEqual(resposta.status_code, 200)
            itens = self.corpo(resposta)
            ids.extend(m['id_unico_musica'] for m in itens)
            if len(itens) < main.TAM_PAGINA:
                return ids
            pagina += 1

    def test_regressao_das_seis_pelo_endpoint(self):
        with open(GABARITO) as f:
            gabarito = json.load(f)
        for chave, ids_esperados in gabarito.items():
            ids = self._todas_as_musicas(chave.replace(';', ','))
            self.assertEqual(sorted(ids), ids_esperados, chave)

    def test_pagina_1_igual_a_busca_por_sequencia(self):
        tokens = ['bm', 'g', 'd', 'a']
        esperado = main.get_pagina(main.busca_por_sequencia(tokens), '1')
        obtido = self.corpo(self.client.get('/similares',
                query_string={'sequencia': 'Bm,G,D,A'}))
        self.assertEqual([m['id_unico_musica'] for m in obtido],
                [m['id_unico_musica'] for m in esperado])

    def test_similares_com_espacos(self):
        obtido = self.corpo(self.client.get('/similares',
                query_string={'sequencia': 'Bm, G, D, A'}))
        self.assertGreater(len(obtido), 0)

    def test_similares_com_genero(self):
        tokens = ['bm', 'g', 'd', 'a']
        esperado = main.get_pagina(
                main.busca_por_sequencia(tokens, ['Rock']), '1')
        obtido = self.corpo(self.client.get('/similares',
                query_string={'sequencia': 'Bm,G,D,A', 'generos': 'Rock'}))
        self.assertEqual([m['id_unico_musica'] for m in obtido],
                [m['id_unico_musica'] for m in esperado])
        self.assertTrue(all(m['genero'] == 'Rock' for m in obtido))

    def test_sequencia_inexistente_200_vazio(self):
        resposta = self.client.get('/similares',
                query_string={'sequencia': 'Am,F,C,G'})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.corpo(resposta), [])

    def test_pagina_invalida_400(self):
        resposta = self.client.get('/similares', query_string={
                'sequencia': 'Bm,G,D,A', 'pagina': 'abc'})
        self.assertEqual(resposta.status_code, 400)

    def test_acordes_e_search_intactos(self):
        acordes = self.corpo(self.client.get('/similares',
                query_string={'acordes': 'Bm,G'}))
        self.assertEqual(len(acordes), 100)
        busca = self.corpo(self.client.get('/search',
                query_string={'key': 'legiao'}))
        self.assertGreater(len(busca), 0)

if __name__ == '__main__':
    unittest.main()
