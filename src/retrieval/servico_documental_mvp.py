"""Consulta ao índice existente. Sem geração de respostas ou reindexação."""
import copy
import json
from pathlib import Path
from threading import Lock
from time import perf_counter


def validar_corpus(chunks, recortes, dados):
    mapa = {c['chunk_id']: c for c in chunks}
    rs = {r['recorte_id']: r for r in recortes}
    if not mapa or len(mapa) != len(chunks) or len(rs) != len(recortes):
        raise ValueError('Corpus vazio ou IDs repetidos.')
    if {c['recorte_id'] for c in chunks} != set(rs):
        raise ValueError('Chunks e recortes não correspondem.')
    ids = dados['ids']
    if len(set(ids)) != len(ids) or set(ids) != set(mapa):
        raise ValueError('IDs do índice divergem dos chunks.')
    if len(dados['documents']) != len(ids) or len(dados['embeddings']) != len(ids):
        raise ValueError('Índice incompleto.')
    for ident, texto in zip(ids, dados['documents']):
        if texto != mapa[ident]['texto']:
            raise ValueError('Texto persistido divergente.')
    for r in recortes:
        if not r['texto_para_busca'].strip() or not r['fontes']:
            raise ValueError('Recorte vazio ou sem fonte.')
        for fonte in r['fontes']:
            if type(fonte['pagina_fisica']) is not int or fonte['pagina_fisica'] < 1:
                raise ValueError('Página física inválida.')
    return rs


def montar_resultado(pergunta, ranking, mapa, assinatura, tempo, quantidade=5):
    if not 1 <= quantidade <= 10:
        raise ValueError('Quantidade inválida.')
    itens = []
    for pos, item in enumerate(ranking[:quantidade], 1):
        r = mapa[item['recorte_id']]
        itens.append({'posicao': pos, 'recorte_id': r['recorte_id'],
                      'texto': r['texto_para_busca'], 'fontes': copy.deepcopy(r['fontes']),
                      'tipo_evidencia': r['tipo_evidencia'],
                      'nota_editorial': r.get('nota_editorial', '')})
    return {'pergunta': pergunta, 'assinatura_indice': assinatura,
            'tempo_busca_s': round(tempo, 3), 'resultados': itens,
            'llm_executado': False, 'relevancia_validada': False}


class ServicoDocumental:
    def __init__(self, base):
        # Imports pesados apenas ao abrir a busca, não ao usar PMMA/SIBAL.
        from src.retrieval.indice_saffire_v2 import preparar, cliente, sha, validar_vetores
        import numpy as np
        nasa, chunks, _, modelo, config, assinatura, pasta = preparar(Path(base))
        manifesto = json.loads((pasta / 'manifesto.json').read_text(encoding='utf-8-sig'))
        if manifesto['assinatura'] != assinatura or manifesto['status'] != 'completo':
            raise ValueError('Índice incompatível ou incompleto. Não foi recriado.')
        if not (pasta / 'chroma').is_dir():
            raise FileNotFoundError('Pasta Chroma ausente. Não foi criado um índice novo.')
        bruto = (nasa / 'processed/recortes_saffire_v1/recortes.json').read_bytes()
        ver = json.loads((nasa / 'processed/chunks_saffire_v2/verificacao.json').read_text(encoding='utf-8-sig'))
        if sha(bruto) != ver['sha256_recortes_json']:
            raise ValueError('Hash dos recortes diverge da origem dos chunks.')
        recortes = json.loads(bruto.decode('utf-8-sig'))['recortes']
        self.db = cliente(pasta)
        col = self.db.get_collection(name='saffire_documental', embedding_function=None)
        if (col.metadata or {}).get('assinatura') != assinatura:
            raise ValueError('Assinatura da coleção divergente.')
        dados = col.get(include=['embeddings', 'documents'])
        self.mapa = validar_corpus(chunks, recortes, dados)
        self.vetores = np.asarray(dados['embeddings'])
        validar_vetores(self.vetores, len(chunks))
        self.ids, self.chunks, self.recortes = dados['ids'], chunks, recortes
        self.modelo, self.limite, self.assinatura = modelo, config['limite_efetivo'], assinatura
        self.lock = Lock()

    def consultar(self, pergunta):
        from src.retrieval.auditoria_recuperacao_v2 import ranking_exato
        from src.retrieval.busca_hibrida import buscar
        from src.retrieval.indice_saffire_v2 import validar_vetores
        if not isinstance(pergunta, str) or not pergunta.strip():
            raise ValueError('Digite uma pergunta / Enter a question.')
        pergunta = pergunta.strip()
        if len(pergunta) > 2000:
            raise ValueError('Pergunta longa demais / Question too long.')
        inicio = perf_counter()
        entrada = 'query: ' + pergunta
        with self.lock:
            n = len(self.modelo.tokenizer(entrada, truncation=False, verbose=False)['input_ids'])
            if n > self.limite:
                raise ValueError('Pergunta excede o limite do modelo; reduza o texto.')
            vetor = self.modelo.encode([entrada], prompt='', normalize_embeddings=True,
                                       convert_to_numpy=True, show_progress_bar=False)
        validar_vetores(vetor, 1)
        denso = ranking_exato(self.ids, self.vetores, vetor[0])
        hibrido = buscar(self.recortes, self.chunks, denso, pergunta)['hibrido']
        return montar_resultado(pergunta, hibrido, self.mapa, self.assinatura,
                                perf_counter() - inicio)
