"""Sem argumento: testes de lógica. --real: acrescenta testes com E5 local e acervo."""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from src.retrieval.chunking_documental_v2 import (
    PREFIXO, carregar_tokenizer, dividir, executar, quantidade, sha, validar_cobertura, validar_bordas,
)


class TokenizerDiagnostico:
    """Um token por caractere; não representa E5 nem produz embeddings."""
    is_fast = True
    model_max_length = 512

    def __call__(self, texto, add_special_tokens=False, truncation=False,
                 return_offsets_mapping=False, verbose=False):
        if truncation:
            raise AssertionError('Truncamento não deve ser solicitado.')
        ids = list(range(len(texto)))
        if add_special_tokens:
            ids = [-1] + ids + [-2]
        resultado = {'input_ids': ids}
        if return_offsets_mapping:
            resultado['offset_mapping'] = [(i, i+1) for i in range(len(texto))]
        return resultado


class TestLogica(unittest.TestCase):
    def setUp(self):
        self.t = TokenizerDiagnostico()

    def test_curto_inclui_prefixo_e_especiais(self):
        r = dividir('Dado artificial.', self.t)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['tokens_com_prefixo_e_especiais'], len(PREFIXO+'Dado artificial.')+2)

    def test_longo_cobertura_e_sobreposicao(self):
        texto = 'Texto artificial para diagnóstico. ' * 90
        r = dividir(texto, self.t)
        validar_cobertura(texto, r, self.t)
        self.assertGreater(len(r), 1)
        self.assertLess(r[1]['inicio_char_normalizado'], r[0]['fim_char_normalizado_exclusivo'])
        self.assertTrue(all(x['tokens_com_prefixo_e_especiais'] <= 320 for x in r))

    def test_preserva_numeros_simbolos_e_espacos(self):
        texto = ' 1.75 mm/s; O₂; 25 cm/s. Não é medição nova. ' * 50
        r = dividir(texto, self.t)
        validar_cobertura(texto, r, self.t)
        for parte in r:
            self.assertEqual(parte['texto'], texto[parte['inicio_char_normalizado']:parte['fim_char_normalizado_exclusivo']])

    def test_resultado_deterministico(self):
        texto = 'Diagnóstico artificial. ' * 60
        self.assertEqual(dividir(texto, self.t), dividir(texto, self.t))

    def test_texto_vazio_rejeitado(self):
        with self.assertRaises(ValueError):
            dividir('  ', self.t)

    def test_configuracao_invalida_rejeitada(self):
        with self.assertRaises(ValueError):
            dividir('texto', self.t, limite=513)
        with self.assertRaises(ValueError):
            dividir('texto', self.t, sobreposicao=320)

    def test_lacuna_rejeitada(self):
        texto = 'x ' * 900
        r = dividir(texto, self.t)
        r[1]['inicio_char_normalizado'] = r[0]['fim_char_normalizado_exclusivo'] + 1
        with self.assertRaises(ValueError):
            validar_cobertura(texto, r, self.t)

    def test_texto_alterado_rejeitado(self):
        r = dividir('diagnostico', self.t)
        r[0]['texto'] = 'alterado'
        with self.assertRaises(ValueError):
            validar_cobertura('diagnostico', r, self.t)

    def test_nao_separa_convection(self):
        texto = ('Conditions affect convection and propagation. ' * 70)
        partes = dividir(texto, self.t)
        validar_bordas(texto, partes)
        for p in partes:
            self.assertFalse(p['texto'].startswith('vection'))

    def test_nao_separa_palavra_hifenizada(self):
        texto = ('Test of fab- ric samples with low-speed airflow. ' * 70)
        partes = dividir(texto, self.t)
        validar_bordas(texto, partes)
        self.assertTrue(all(not p['texto'].startswith('ric ') for p in partes))

    def test_unidade_longa_demais_rejeitada(self):
        with self.assertRaises(ValueError):
            dividir('x'*900, self.t)


class TestE5Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = carregar_tokenizer()

    def test_e5_limites_e_cobertura(self):
        texto = ('Diagnostic text, not experimental data: 1.75 mm/s; O₂; 25 cm/s. '
                 'This text tests token boundaries and preservation. ') * 80
        r = dividir(texto, self.tokenizer)
        validar_cobertura(texto, r, self.tokenizer)
        self.assertGreater(len(r), 1)
        validar_bordas(texto,r)
        self.assertTrue(all(quantidade(self.tokenizer, p['texto']) <= 320 for p in r))

    def test_acervo_real_e_sobrescrita(self):
        origem = Path(__file__).resolve().parent / 'data/nasa_oficial/processed/recortes_saffire_v1'
        antes = {nome: sha((origem/nome).read_bytes()) for nome in ['recortes.json','verificacao.json']}
        with tempfile.TemporaryDirectory(prefix='teste_chunks_e5_') as pasta:
            base = Path(pasta)
            destino = base / 'data/nasa_oficial/processed/recortes_saffire_v1'
            destino.mkdir(parents=True)
            for nome in antes:
                shutil.copyfile(origem/nome, destino/nome)
            with contextlib.redirect_stdout(io.StringIO()):
                r = executar(base, self.tokenizer)
            self.assertEqual(r['recortes'], 50)
            self.assertGreaterEqual(r['chunks'], 50)
            self.assertLessEqual(r['maior_tamanho_tokens'], 320)
            saida = base / 'data/nasa_oficial/processed/chunks_saffire_v2/chunks.json'
            chunks = json.loads(saida.read_text(encoding='utf-8'))['chunks']
            self.assertEqual(len({c['chunk_id'] for c in chunks}), len(chunks))
            self.assertTrue(any(c['tipo_evidencia']=='ressalva_metodologica' for c in chunks))
            with self.assertRaises(FileExistsError):
                executar(base, self.tokenizer)
            # Mesmo conteúdo e tokenizer devem gerar IDs estáveis numa segunda execução isolada.
            outros = base / 'segunda_execucao'
            outra_origem = outros / 'data/nasa_oficial/processed/recortes_saffire_v1'
            shutil.copytree(destino, outra_origem)
            with contextlib.redirect_stdout(io.StringIO()):
                executar(outros, self.tokenizer)
            outros_chunks = json.loads((outros / 'data/nasa_oficial/processed/chunks_saffire_v2/chunks.json').read_text(encoding='utf-8'))['chunks']
            self.assertEqual([c['chunk_id'] for c in chunks], [c['chunk_id'] for c in outros_chunks])
        self.assertEqual(antes, {nome: sha((origem/nome).read_bytes()) for nome in antes})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestLogica)
    if '--real' in sys.argv:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestE5Real))
    else:
        print('Somente lógica: o tokenizer de diagnóstico NÃO substitui o teste E5 --real.')
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if resultado.wasSuccessful() else 1)
