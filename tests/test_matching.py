# coding: utf-8
import json
import os
import unittest

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

if __name__ == '__main__':
    unittest.main()
