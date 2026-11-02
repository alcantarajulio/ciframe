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

    def test_post_e_busca_da_mesma_sequencia_com_sustenido(self):
        # fluxo completo da UI: cadastra e busca a mesma chave. O '#' precisa
        # sobreviver ao encode da URL; sem ele a busca virava "sequencia=C" e
        # devolvia outro conjunto (ou vazio).
        tokens = ['C#m', 'A', 'E']
        criada = self.client.post('/sequencias', json={'acordes': tokens})
        self.assertEqual(criada.status_code, 201)
        corpo = self.corpo(criada)
        self.assertEqual(corpo['acordes'], tokens)

        busca = self.client.get('/similares', query_string={
                'sequencia': ','.join(tokens)})
        self.assertEqual(busca.status_code, 200)
        ids = [m['id_unico_musica'] for m in self.corpo(busca)]
        self.assertGreater(len(ids), 0)
        self.assertEqual(ids, [m['id_unico_musica']
                for m in main.busca_por_sequencia(tokens)])
        self.assertEqual(len(ids), corpo['total_musicas'])

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

    def test_post_caixa_distingue_acordes(self):
        # AM7 e Am7 são acordes diferentes (lá maior com sétima x lá menor
        # com sétima, apesar das mesmas letras): chaves e linhas distintas
        am7 = self.client.post('/sequencias',
                json={'acordes': ['Am7', 'D']})
        self.assertEqual(am7.status_code, 201)
        corpo_am7 = self.corpo(am7)

        am7_maiusculo = self.client.post('/sequencias',
                json={'acordes': ['AM7', 'D']})
        self.assertEqual(am7_maiusculo.status_code, 201)
        corpo_am7_maiusculo = self.corpo(am7_maiusculo)
        self.assertFalse(corpo_am7_maiusculo['existente'])
        self.assertNotEqual(corpo_am7_maiusculo['id'], corpo_am7['id'])
        self.assertEqual(corpo_am7_maiusculo['acordes'], ['AM7', 'D'])

        # A7M x A7m é o par que só difere na caixa (mesmas letras)
        a7m = self.client.post('/sequencias',
                json={'acordes': ['A7M', 'D']})
        self.assertEqual(a7m.status_code, 201)
        a7m_minusculo = self.client.post('/sequencias',
                json={'acordes': ['A7m', 'D']})
        self.assertEqual(a7m_minusculo.status_code, 201)
        self.assertNotEqual(self.corpo(a7m_minusculo)['id'],
                self.corpo(a7m)['id'])

        # repetição exata continua idempotente
        repetida = self.client.post('/sequencias',
                json={'acordes': ['Am7', 'D']})
        self.assertEqual(repetida.status_code, 200)
        self.assertTrue(self.corpo(repetida)['existente'])
        self.assertEqual(self.corpo(repetida)['id'], corpo_am7['id'])

        # espaços nas pontas não mudam a identidade (trim; a caixa é mantida)
        com_espacos = self.client.post('/sequencias',
                json={'acordes': [' AM7 ', ' D ']})
        self.assertEqual(com_espacos.status_code, 200)
        self.assertEqual(self.corpo(com_espacos)['id'],
                corpo_am7_maiusculo['id'])

        lista = self.corpo(self.client.get('/sequencias'))
        self.assertEqual(len(lista), 10)

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

    def test_post_acorde_desconhecido_com_sugestoes(self):
        resposta = self.client.post('/sequencias',
                json={'acordes': ['bm', 'G', 'D', 'A']})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('text/html', resposta.content_type)
        self.assertEqual(self.corpo(resposta), {
            'erro': 'acorde_desconhecido',
            'acordes': [{'acorde': 'bm', 'sugestoes': ['Bm']}],
        })
        # nada foi criado
        self.assertEqual(len(self.corpo(self.client.get('/sequencias'))), 6)

    def test_post_sugestoes_ordenadas_por_uso(self):
        # am7 bate ignorando caixa com Am7 (5.729 músicas) e AM7 (40). A lista
        # tem de trazer a grafia mais usada primeiro; sorted() puro preferia
        # AM7 (maiúscula antes de minúscula), que com caixa exata é outro
        # acorde — o erro que esta revisão corrige.
        resposta = self.client.post('/sequencias',
                json={'acordes': ['am7', 'D']})
        self.assertEqual(resposta.status_code, 400)
        corpo = self.corpo(resposta)
        self.assertEqual(corpo['acordes'][0]['sugestoes'],
                ['Am7', 'AM7'])

        sustenido = self.client.post('/sequencias',
                json={'acordes': ['f#m', 'D']})
        self.assertEqual(sustenido.status_code, 400)
        self.assertEqual(self.corpo(sustenido)['acordes'][0]['sugestoes'],
                ['F#m', 'F#M'])

    def test_post_acorde_desconhecido_sem_sugestoes(self):
        resposta = self.client.post('/sequencias',
                json={'acordes': ['Cb', 'G']})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.corpo(resposta), {
            'erro': 'acorde_desconhecido',
            'acordes': [{'acorde': 'Cb', 'sugestoes': []}],
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
        self.assertEqual(len(sequencias_db.SEMENTES), 6)
        # as chaves do fixture são históricas, em minúsculas; a busca é na
        # caixa exata, então usamos as 6 na grafia do seed
        for tokens in sequencias_db.SEMENTES:
            chave = ';'.join(token.lower() for token in tokens)
            ids = self._todas_as_musicas(','.join(tokens))
            self.assertEqual(sorted(ids), gabarito[chave], chave)

    def test_pagina_1_igual_a_busca_por_sequencia(self):
        tokens = ['Bm', 'G', 'D', 'A']
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
        tokens = ['Bm', 'G', 'D', 'A']
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

        # a caixa faz parte da chave: a versão minúscula de uma sequência
        # existente não é encontrada (antes o lower() encontrava)
        minuscula = self.client.get('/similares',
                query_string={'sequencia': 'bm,g,d,a'})
        self.assertEqual(minuscula.status_code, 200)
        self.assertEqual(self.corpo(minuscula), [])

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
