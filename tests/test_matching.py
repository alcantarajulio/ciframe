# coding: utf-8
import atexit
import json
import os
import shutil
import tempfile
import unittest

# o import de main roda o boot do catálogo (passo 4); isola o banco em
# arquivo temporário para não criar dados/ no checkout durante os testes
_tmpdir = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _tmpdir, True)
os.environ['SEQUENCIAS_DB'] = os.path.join(_tmpdir, 'sequencias.db')

import main

GABARITO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'fixtures', 'gabarito_sequencias.json')

class TestMatching(unittest.TestCase):

    def test_regressao_das_seis_sequencias(self):
        with open(GABARITO) as f:
            gabarito = json.load(f)
        self.assertEqual(len(gabarito), 6)
        for chave in gabarito:
            ids = sorted(m['id_unico_musica']
                    for m in main.busca_por_sequencia(chave.split(';')))
            self.assertEqual(ids, gabarito[chave], chave)

    def test_borda_impede_match_por_prefixo(self):
        # sem as bordas ';', 'a7;d;a' casa por prefixo em cifras como
        # 'A7;D;A7' e devolve 17 músicas; com bordas, exatamente 1
        # (02-proposal.md, "Bordas, e não in puro")
        similares = main.busca_por_sequencia(['A7', 'D', 'A'])
        self.assertEqual(len(similares), 1)

    def test_sequencia_vazia_nao_chega_na_busca(self):
        # sem a guarda, ';;' casaria as 8.141 músicas de cifra vazia (§2.8)
        self.assertEqual(main.busca_por_sequencia([]), [])

    def test_filtro_por_genero(self):
        tokens = ['bm', 'g', 'd', 'a']
        todos = main.busca_por_sequencia(tokens)
        filtrado = main.busca_por_sequencia(tokens, ['Rock'])
        self.assertTrue(filtrado)
        self.assertTrue(all(m['genero'] == 'Rock' for m in filtrado))
        # mesmo subconjunto do resultado sem filtro, na mesma ordem relativa
        esperado = [m['id_unico_musica'] for m in todos
                if m['genero'] == 'Rock']
        self.assertEqual([m['id_unico_musica'] for m in filtrado], esperado)

if __name__ == '__main__':
    unittest.main()
