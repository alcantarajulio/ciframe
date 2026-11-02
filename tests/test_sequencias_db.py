# coding: utf-8
import os
import sqlite3
import tempfile
import unittest

import sequencias_db

class TestSequenciasDb(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ['SEQUENCIAS_DB'] = os.path.join(
                self.tmp.name, 'sequencias.db')
        self.addCleanup(os.environ.pop, 'SEQUENCIAS_DB', None)
        sequencias_db.init()

    def test_schema_criado_e_user_version(self):
        con = sqlite3.connect(os.environ['SEQUENCIAS_DB'])
        try:
            tabela = con.execute(
                "SELECT name FROM sqlite_master"
                " WHERE type='table' AND name='sequencias'").fetchone()
            self.assertIsNotNone(tabela)
            versao = con.execute('PRAGMA user_version').fetchone()[0]
            self.assertEqual(versao, 1)
        finally:
            con.close()

    def test_seed_insere_as_seis_na_ordem(self):
        sequencias_db.seed()
        sequencias = sequencias_db.listar()
        self.assertEqual([s['chave'] for s in sequencias],
                ['Bm;G;D;A', 'C;G;Am;F', 'Em;G',
                 'C;A7;Dm;G7', 'Gm;F', 'C;C7;F;Fm'])
        self.assertTrue(all(s['origem'] == 'seed' for s in sequencias))
        self.assertEqual(sequencias[0]['acordes'], ['Bm', 'G', 'D', 'A'])

    def test_seed_repetido_nao_duplica(self):
        sequencias_db.seed()
        sequencias_db.seed()
        self.assertEqual(len(sequencias_db.listar()), 6)

    def test_inserir_ou_obter_cria_e_depois_devolve_existente(self):
        sequencias_db.seed()
        linha, criada = sequencias_db.inserir_ou_obter(['D', 'A', 'Bm', 'G'])
        self.assertTrue(criada)
        self.assertEqual(linha['chave'], 'D;A;Bm;G')
        self.assertEqual(linha['origem'], 'usuario')
        self.assertEqual(linha['acordes'], ['D', 'A', 'Bm', 'G'])

        # mesmos tokens devolvem a existente, sem criar
        de_novo, criada_de_novo = sequencias_db.inserir_ou_obter(
                ['D', 'A', 'Bm', 'G'])
        self.assertFalse(criada_de_novo)
        self.assertEqual(de_novo['id'], linha['id'])
        self.assertEqual(de_novo['acordes'], ['D', 'A', 'Bm', 'G'])
        self.assertEqual(len(sequencias_db.listar()), 7)

    def test_chave_distingue_caixa(self):
        sequencias_db.seed()
        linha, criada = sequencias_db.inserir_ou_obter(['A7M', 'D'])
        self.assertTrue(criada)
        self.assertEqual(linha['chave'], 'A7M;D')

        # A7M é sétima maior, A7m é menor com sétima: caixa exata, linha nova
        outra, criada_outra = sequencias_db.inserir_ou_obter(['A7m', 'D'])
        self.assertTrue(criada_outra)
        self.assertEqual(outra['chave'], 'A7m;D')
        self.assertNotEqual(outra['id'], linha['id'])
        self.assertEqual(len(sequencias_db.listar()), 8)

    def test_buscar_por_chave(self):
        sequencias_db.seed()
        self.assertEqual(sequencias_db.buscar_por_chave('Em;G')['acordes'],
                ['Em', 'G'])
        # a chave antiga em minúsculas não existe mais
        self.assertIsNone(sequencias_db.buscar_por_chave('em;g'))
        self.assertIsNone(sequencias_db.buscar_por_chave('nao;existe'))

if __name__ == '__main__':
    unittest.main()
