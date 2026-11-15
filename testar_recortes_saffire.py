"""Testes de transformação e integração; grava somente em pasta temporária."""
import copy
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from src.ingestion.recortes_documentais import construir, digest, executar, normalizar


class TestRecortes(unittest.TestCase):
    def setUp(self):
        texto = 'Texto artificial: 1.75 mm/s; experimen-\ntal.'
        self.dados = json.dumps({'documentos': [{
            'documento_id': 'DIAGNOSTICO', 'sha256_pdf': 'A'*64,
            'ficha_selecao': {'apelido': 'TESTE', 'titulo': 'Diagnóstico artificial'},
            'paginas': [{'pagina_fisica': 1, 'pagina_impressa': None,
                         'texto_ordem_nativa': texto}]}]}).encode()
        self.plano = {'sha256_paginas_json': digest(self.dados),
                      'campo_texto': 'texto_ordem_nativa', 'recortes': [{
            'recorte_id': 'TESTE', 'tipo_evidencia': 'artificial', 'nota_editorial': '',
            'exclusoes_internas': [], 'fontes': [{'documento_id': 'DIAGNOSTICO',
            'sha256_pdf': 'A'*64, 'pagina_fisica': 1, 'inicio_char': 0,
            'fim_char_exclusivo': len(texto), 'trecho_literal': texto}]}]}

    def test_normaliza_ligatura_e_hifen_autorizado(self):
        t, log = normalizar('Saﬃre experimen-\ntal')
        self.assertEqual(t, 'Saffire experimental')
        self.assertTrue(log)

    def test_nao_corrige_numeros_nem_hifens_semanticos(self):
        t, _ = normalizar('30 0–40 0 °C; 1.75 mm/s; cm²; low-speed; 1-cm')
        self.assertEqual(t, '30 0–40 0 °C; 1.75 mm/s; cm²; low-speed; 1-cm')

    def test_preserva_original_e_rastreabilidade(self):
        antes = copy.deepcopy(self.plano)
        r = construir(self.dados, self.plano)[0]
        self.assertEqual(r['fontes'][0]['trecho_literal'], antes['recortes'][0]['fontes'][0]['trecho_literal'])
        self.assertEqual(self.plano, antes)
        self.assertIn('experimental', r['texto_para_busca'])

    def test_hash_divergente_rejeitado(self):
        with self.assertRaises(ValueError):
            construir(self.dados + b' ', self.plano)

    def test_trecho_divergente_rejeitado(self):
        self.plano['recortes'][0]['fontes'][0]['trecho_literal'] = 'inventado'
        with self.assertRaises(ValueError):
            construir(self.dados, self.plano)

    def test_id_duplicado_rejeitado(self):
        self.plano['recortes'].append(copy.deepcopy(self.plano['recortes'][0]))
        with self.assertRaises(ValueError):
            construir(self.dados, self.plano)

    def test_intervalo_invalido_rejeitado(self):
        self.plano['recortes'][0]['fontes'][0]['inicio_char'] = -1
        with self.assertRaises(ValueError):
            construir(self.dados, self.plano)

    def test_integracao_real_e_protecao_sobrescrita(self):
        origem = Path(__file__).resolve().parent / 'data' / 'nasa_oficial'
        caminhos = ['extracted/saffire_documental_v1/paginas.json',
                    'metadata/plano_recortes_saffire_v1.json']
        hashes = {p: digest((origem / p).read_bytes()) for p in caminhos}
        with tempfile.TemporaryDirectory(prefix='teste_recortes_') as pasta:
            base = Path(pasta)
            nasa = base / 'data' / 'nasa_oficial'
            for relativo in caminhos:
                destino = nasa / relativo
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origem / relativo, destino)
            with contextlib.redirect_stdout(io.StringIO()):
                relatorio = executar(base)
            self.assertEqual(relatorio['recortes'], 50)
            arquivo = nasa / 'processed/recortes_saffire_v1/recortes.json'
            recortes = json.loads(arquivo.read_text(encoding='utf-8'))['recortes']
            self.assertEqual(len({r['recorte_id'] for r in recortes}), 50)
            texto = '\n'.join(r['texto_para_busca'] for r in recortes)
            for numero in ['1.75 mm/s', '2.32 mm/s', '2.03 mm/s']:
                self.assertIn(numero, texto)
            self.assertNotIn('30 0–40 0', texto)
            self.assertNotIn('[6] G.D. Grayson', texto)
            notas = [r for r in recortes if r['tipo_evidencia']=='ressalva_metodologica']
            self.assertEqual(len(notas), 1)
            self.assertIn('boundary layer', notas[0]['texto_para_busca'])
            with self.assertRaises(FileExistsError):
                executar(base)
        self.assertEqual(hashes, {p: digest((origem / p).read_bytes()) for p in caminhos})


if __name__ == '__main__':
    unittest.main(verbosity=2)
