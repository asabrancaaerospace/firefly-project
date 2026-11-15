"""Testes de apresentação com dados artificiais identificados; não validam o acervo."""
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest
from src.ui.firefly_v3 import dashboard as ui
from src.ui.firefly_v3.charts import pmma, sibal

P=[dict(condicao_id='ARTIFICIAL_1',teste_id='T1',teste='M1',faces=1,espessura_mm='1',largura_mm='22.0',escoamento_mm_s=90,propagacao_mm_s=0.071,o2_inicial='22.2',o2_final='21.9',status='valor_publicado',fonte={'linha_dados':1}),
   dict(condicao_id='ARTIFICIAL_2',teste_id='T2',teste='M2',faces=2,espessura_mm='1',largura_mm='22.0',escoamento_mm_s=100,propagacao_mm_s=None,o2_inicial='22',o2_final='21',status='nao_rastreada',fonte={'linha_dados':2})]
T={r['teste_id']:{'celulas_originais':['ARTIFICIAL']*9,'fonte':r['fonte']} for r in P}
S=[dict(registro_id='ARTIFICIAL_S1',identificador_publicado='TESTE',investigacao_id='PSI-25',largura_mm='22.0',oxigenio_vol_pct='18.5',tipo_fluxo='inicio_e_fim_publicados',fluxo_valor_unico_mm_s=None,fluxo_inicial_mm_s='100',fluxo_final_mm_s='50',fluxo_original_cm_s='10 to 5',comentario_original='ARTIFICIAL',oxigenio_nota_b=True,reutilizacao_relata=None,observacao_padronizada='nao_informada_nesta_coluna',fonte={'linha_dados':1},celulas_originais=['ARTIFICIAL']*5)]

class TestFirefly(unittest.TestCase):
    def setUp(self):
        for patcher in [patch.object(ui,'carregar_pmma',return_value=(P,T)),patch.object(ui,'carregar_sibal',return_value=S),patch.object(ui,'cobertura',return_value=([],{}))]:
            patcher.start();self.addCleanup(patcher.stop)
    def app(self):
        return AppTest.from_file(str(Path(__file__).parent/'app_firefly_v3.py'),default_timeout=30).run()
    def test_initial_overview_english(self):
        a=self.app();self.assertEqual(len(a.exception),0)
        self.assertEqual(a.title[0].value,'Combustion evidence, in view')
        self.assertEqual(a.selectbox(key='firefly_language').value,'en')
    def test_portuguese_switch(self):
        a=self.app();a.selectbox(key='firefly_language').set_value('pt-BR').run()
        self.assertEqual(a.title[0].value,'Evidências de combustão em perspectiva')
        self.assertEqual(len(a.exception),0)
    def test_pmma_empty_filter(self):
        a=self.app();a.radio(key='firefly_page').set_value('pmma').run()
        self.assertEqual(len(a.exception),0)
        a.multiselect(key='pmma_width').set_value([]).run()
        self.assertTrue(any('No records match' in x.value for x in a.info))
    def test_sibal_navigation(self):
        a=self.app();a.radio(key='firefly_page').set_value('sibal').run()
        self.assertEqual(len(a.exception),0)
        self.assertTrue(any('note b' in x.value for x in a.warning))
    def test_search_empty_does_not_load_model(self):
        with patch.object(ui,'servico') as serv:
            a=self.app();a.radio(key='firefly_page').set_value('search').run()
            a.button[0].click().run()
            self.assertEqual(len(a.exception),0);serv.assert_not_called()
    def test_pmma_missing_not_zero(self):
        f=pmma(P);self.assertEqual(sum(len(x.x) for x in f.data),1)
        self.assertEqual(list(f.data[0].y),[0.071])
        self.assertEqual(f.layout.xaxis.title.text,'Airflow (mm/s)')
    def test_sibal_endpoints_not_interpolated(self):
        f=sibal(S);self.assertEqual(sorted(float(y) for tr in f.data for y in tr.y),[50,100])
        self.assertTrue(all(tr.mode=='markers' for tr in f.data))
    def test_search_display_and_stale_result_cleared(self):
        result={'pergunta':'Artificial question','tempo_busca_s':0.1,'resultados':[{
            'posicao':1,'recorte_id':'ARTIFICIAL','texto':'Artificial source text.',
            'tipo_evidencia':'metodo_medicao','fontes':[{'documento_id':'DOC_TEST',
            'titulo_documento':'Artificial document','pagina_fisica':1}]}],
            'llm_executado':False,'relevancia_validada':False}
        with patch.object(ui,'servico',return_value=SimpleNamespace(consultar=lambda _:result)):
            a=self.app();a.radio(key='firefly_page').set_value('search').run()
            a.text_area(key='ff_question').set_value('Artificial question')
            a.button[0].click().run()
            self.assertEqual(len(a.exception),0)
            self.assertEqual(a.session_state['ff_result']['pergunta'],'Artificial question')
            a.text_area(key='ff_question').set_value('')
            a.button[0].click().run()
            self.assertNotIn('ff_result',a.session_state)
    def test_cross_material_comparison_warning(self):
        a=self.app();a.radio(key='firefly_page').set_value('scenarios').run()
        a.selectbox(key='compare_b').set_value('ARTIFICIAL_S1').run()
        self.assertEqual(len(a.exception),0)
        self.assertTrue(any('Different materials' in x.value for x in a.warning))
    def test_export_preserves_sources_without_mutating_input(self):
        from src.ui.firefly_v3.additions import pacote_exportacao
        r=pacote_exportacao(P,'PMMA','en')
        self.assertEqual(r['record_count'],2)
        self.assertIsNone(r['records'][1]['propagacao_mm_s'])
        r['records'][0]['fonte']['linha_dados']=999
        self.assertEqual(P[0]['fonte']['linha_dados'],1)
        self.assertFalse(r['safety_certification'])
    def test_coverage_distinguishes_missing_from_zero(self):
        from src.ui.firefly_v3.additions import cobertura_tabelas
        r=cobertura_tabelas(P,S)
        self.assertEqual(r[0]['spread'],1)
        self.assertIsNone(r[1]['spread'])
        self.assertEqual(r[1]['reuse'],0)
        self.assertIsNone(r[0]['pressure'])
    def test_coverage_page(self):
        a=self.app();a.radio(key='firefly_page').set_value('coverage').run()
        self.assertEqual(len(a.exception),0)
        self.assertEqual(a.title[0].value,'Evidence coverage')
    def test_brand_extracts_blue_orange_and_ignores_transparency(self):
        from src.ui.firefly_v3.brand import palette_from_pixels
        p=palette_from_pixels([(0,16,180,255)]*5+[(220,100,0,255)]*5+[(0,0,255,0)]*10)
        self.assertEqual(p['blue'],'#0010B4');self.assertEqual(p['orange'],'#DC6400')
        self.assertEqual(p['origin'],'logo')
    def test_brand_fallback(self):
        from src.ui.firefly_v3.brand import palette_from_pixels
        self.assertEqual(palette_from_pixels([(255,255,255,255)])['origin'],'fallback')
    def test_brand_contrast(self):
        from src.ui.firefly_v3.brand import contrast_text
        self.assertEqual(contrast_text('#000000'),'#FFFFFF')
        self.assertEqual(contrast_text('#FFFFFF'),'#000000')
    def test_investigation_profile(self):
        a=self.app();a.radio(key='firefly_page').set_value('investigations').run()
        self.assertEqual(len(a.exception),0)
        self.assertEqual(a.title[0].value,'Investigations')
        self.assertTrue(any('Untracked spread' in x.value for x in a.markdown))
    def test_missing_saffire_excerpt_not_claimed(self):
        a=self.app();a.radio(key='firefly_page').set_value('investigations').run()
        a.selectbox(key='ff_investigation').set_value('Saffire').run()
        self.assertEqual(len(a.exception),0)
        self.assertTrue(any('Required source excerpt unavailable' in x.value for x in a.warning))
    def test_calculator(self):
        from src.ui.firefly_v3.scenarios import partial_pressure
        self.assertAlmostEqual(partial_pressure(21,101.325),21.27825)
        self.assertEqual(partial_pressure(0,100),0)
        for o,p in [(101,100),(21,-1),(float('nan'),100),(21,float('inf'))]:
            with self.assertRaises(ValueError):partial_pressure(o,p)
    def test_scenarios_page(self):
        a=self.app();a.radio(key='firefly_page').set_value('scenarios').run()
        self.assertEqual(len(a.exception),0)
        self.assertTrue(any('21.278' in x.value for x in a.metric))
    def test_portuguese_plot_labels(self):
        self.assertEqual(sibal(S,False).layout.xaxis.title.text,'Oxigênio (vol%)')
        self.assertEqual(pmma(P,False).layout.yaxis.title.text,'Propagação (mm/s)')

if __name__=='__main__':unittest.main(verbosity=2)
