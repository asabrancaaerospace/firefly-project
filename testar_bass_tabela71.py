import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from src.ingestion.bass_tabela71 import estruturar, executar

BASE=Path(__file__).resolve().parent


class TestTabela71(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nasa=BASE/'data'/'nasa_oficial'
        cls.entrada=cls.nasa/'extracted'/'tabelas_candidatas_bass_v1.json'
        dados=json.loads(cls.entrada.read_text(encoding='utf-8-sig'))
        cls.tabela=next(t for t in dados['tabelas'] if t['tabela']=='7.1')
        cls.registros=estruturar(cls.tabela)
        cls.por_codigo={r['identificador_publicado']:r for r in cls.registros}

    def test_investigacoes(self):
        self.assertEqual(len(self.registros),31)
        self.assertEqual(sum(r['investigacao_id']=='PSI-25' for r in self.registros),27)
        self.assertEqual(sum(r['investigacao_id']=='PSI-26' for r in self.registros),4)

    def test_nota_oxigenio(self):
        self.assertEqual({r['identificador_publicado'] for r in self.registros if r['oxigenio_nota_b']},{'GMT45-T1','GMT45-T2'})
        self.assertEqual(self.por_codigo['GMT45-T1']['oxigenio_vol_pct'],'18.5')

    def test_fluxo_sem_pontos_inventados(self):
        r=self.por_codigo['GMT45-T2']
        self.assertEqual((r['fluxo_inicial_mm_s'],r['fluxo_final_mm_s']),('100','50'))
        self.assertIsNone(r['fluxo_valor_unico_mm_s'])
        self.assertEqual(self.por_codigo['GMT45-T1']['fluxo_valor_unico_mm_s'],'100')

    def test_reutilizacao_desconhecida(self):
        self.assertEqual(sum(r['reutilizacao_relata'] is True for r in self.registros),8)
        self.assertIsNone(self.por_codigo['GMT45-T1']['reutilizacao_relata'])

    def test_comentarios_nao_sao_seguranca(self):
        self.assertEqual(self.por_codigo['GMT45-T1']['observacao_padronizada'],'nao_informada_nesta_coluna')
        self.assertEqual(self.por_codigo['GMT45-T15']['observacao_padronizada'],'ausencia_de_blowoff_relatada')
        self.assertEqual(self.por_codigo['GMT96-T8']['observacao_padronizada'],'nao_informada_nesta_coluna')
        self.assertEqual(self.por_codigo['GMT216-T25']['observacao_padronizada'],'ignicao_relatada')

    def test_nota_alterada_rejeitada(self):
        t=copy.deepcopy(self.tabela);t['linhas'][0]['celulas_originais'][3]='18.5'
        with self.assertRaises(ValueError):estruturar(t)

    def test_pdf_real_e_sobrescrita(self):
        with tempfile.TemporaryDirectory(prefix='teste_bass71_') as pasta:
            base=Path(pasta);destino=base/'data'/'nasa_oficial'
            (destino/'extracted').mkdir(parents=True)
            (destino/'raw'/'PSI-25'/'Report').mkdir(parents=True)
            shutil.copyfile(self.entrada,destino/'extracted'/self.entrada.name)
            nome='BASS-II Summary Report.pdf'
            shutil.copyfile(self.nasa/'raw'/'PSI-25'/'Report'/nome,destino/'raw'/'PSI-25'/'Report'/nome)
            executar(base)
            saida=json.loads((destino/'processed'/'bass_tabela71_v1'/'registros.json').read_text(encoding='utf-8'))
            self.assertEqual(saida,self.registros)
            with self.assertRaises(FileExistsError):executar(base)


if __name__=='__main__':
    unittest.main(verbosity=2)
