"""Testes com PDFs artificiais de diagnóstico, criados somente em pasta temporária."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from extrair_documentos_saffire import executar, sha256


class TestExtracao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='teste_documental_')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.nasa = self.base / 'data' / 'nasa_oficial'
        self.raw = self.nasa / 'raw'
        self.raw.mkdir(parents=True)
        (self.nasa / 'metadata').mkdir()
        self.pdf = self.raw / 'diagnostico.pdf'
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((72, 72), 'ARTIFICIAL: teste de ordem e rastreabilidade.')
            pdf.new_page()
            pdf.save(self.pdf)
        self.hash_original = sha256(self.pdf)
        self.manifesto = {'documentos': [{
            'documento_id': 'DIAGNOSTICO_ARTIFICIAL',
            'nome_referencia': self.pdf.name,
            'sha256': self.hash_original,
            'paginas_esperadas': 2,
            'deslocamento_pagina_impressa': None,
            'faixas_de_paginas': [{'inicio': 1, 'fim': 2, 'rotulo': 'diagnostico_artificial'}],
        }]}
        self.salvar_manifesto()

    def salvar_manifesto(self):
        (self.nasa / 'metadata' / 'selecao_documental_saffire_v1.json').write_text(
            json.dumps(self.manifesto), encoding='utf-8')

    def rodar(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return executar(self.base)

    def test_preserva_paginas_texto_blocos_e_original(self):
        relatorio = self.rodar()
        arquivo = self.nasa / 'extracted' / 'saffire_documental_v1' / 'paginas.json'
        dados = json.loads(arquivo.read_text(encoding='utf-8'))
        paginas = dados['documentos'][0]['paginas']
        self.assertEqual([p['pagina_fisica'] for p in paginas], [1, 2])
        self.assertIn('ARTIFICIAL', paginas[0]['texto_ordem_nativa'])
        self.assertTrue(paginas[0]['blocos_texto'])
        self.assertEqual(relatorio['paginas_sem_texto'], 1)
        self.assertEqual(sha256(self.pdf), self.hash_original)
        self.assertEqual(sha256(arquivo), relatorio['sha256_paginas_json'])

    def test_deduplica_por_conteudo_preserva_caminhos(self):
        shutil.copyfile(self.pdf, self.raw / 'copia.pdf')
        r = self.rodar()
        self.assertEqual(r['documentos_unicos'], 1)
        self.assertEqual(r['ocorrencias_fisicas_selecionadas'], 2)
        self.assertEqual(r['paginas_preservadas'], 2)

    def test_nome_diferente_hash_igual(self):
        self.pdf.rename(self.raw / 'outro_nome.PDF')
        self.assertEqual(self.rodar()['documentos_unicos'], 1)

    def test_hash_divergente_impede_saida(self):
        self.manifesto['documentos'][0]['sha256'] = '0' * 64
        self.salvar_manifesto()
        with self.assertRaises(FileNotFoundError):
            self.rodar()
        self.assertFalse((self.nasa / 'extracted' / 'saffire_documental_v1').exists())

    def test_contagem_divergente_impede_saida(self):
        self.manifesto['documentos'][0]['paginas_esperadas'] = 3
        self.salvar_manifesto()
        with self.assertRaises(ValueError):
            self.rodar()

    def test_impede_sobrescrita(self):
        self.rodar()
        arquivo = self.nasa / 'extracted' / 'saffire_documental_v1' / 'paginas.json'
        antes = sha256(arquivo)
        with self.assertRaises(FileExistsError):
            self.rodar()
        self.assertEqual(sha256(arquivo), antes)

    def test_pagina_sem_classificacao_rejeitada(self):
        self.manifesto['documentos'][0]['faixas_de_paginas'][0]['fim'] = 1
        self.salvar_manifesto()
        with self.assertRaises(ValueError):
            self.rodar()


if __name__ == '__main__':
    unittest.main(verbosity=2)
