import unittest
from src.retrieval.busca_hibrida import termos, ranking_bm25, fundir, buscar, pergunta_metodologica


class TestBusca(unittest.TestCase):
    def test_intencao_metodologica_bilingue(self):
        self.assertTrue(pergunta_metodologica('How was the quantity measured in another experiment?'))
        self.assertTrue(pergunta_metodologica('Como foi medida a grandeza em outro experimento?'))

    def test_pergunta_numerica_nao_aciona_prior(self):
        self.assertFalse(pergunta_metodologica('What temperature was measured?'))
        self.assertFalse(pergunta_metodologica('Qual temperatura foi medida?'))

    def test_romanos_sem_confundir_missoes(self):
        self.assertEqual(termos('Saffire-I Saffire-II Saffire-III'), ['saffire1','saffire2','saffire3'])

    def test_equivalencia_lexical_limitada(self):
        self.assertEqual(termos('medição oxigênio propagação'),termos('measurement oxygen spread'))

    def test_consulta_sem_termos_correspondentes(self):
        self.assertEqual(ranking_bm25({'a':'cotton flame'},'galaxies'),[])

    def test_bm25_prioriza_correspondencia(self):
        r = ranking_bm25({'a':'measurement method','b':'office invoice'},'método de medição')
        self.assertEqual(r[0]['recorte_id'],'a')

    def test_fusao_recompensa_ambos_canais(self):
        d=[{'recorte_id':'a'},{'recorte_id':'b'}]
        l=[{'recorte_id':'b'}]
        self.assertEqual(fundir(d,l)[0]['recorte_id'],'b')

    def test_agrupa_chunks_do_mesmo_recorte(self):
        rs=[{'recorte_id':'r','fontes':[{}],'tipo_evidencia':'metodo_medicao','texto_para_busca':'measurement'}]
        cs=[{'chunk_id':'1','recorte_id':'r'},{'chunk_id':'2','recorte_id':'r'}]
        rankings=[{'chunk_id':'1','distancia_cosseno':0.3},{'chunk_id':'2','distancia_cosseno':0.1}]
        r=buscar(rs,cs,rankings,'measurement')
        self.assertEqual(len(r['hibrido']),1)
        self.assertEqual(r['denso'][0]['chunk_id'],'2')


if __name__=='__main__':
    unittest.main(verbosity=2)
