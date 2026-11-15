"""Índice local E5/Chroma; não executa LLM nem inclui gabaritos no corpus."""
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

MODELO = 'intfloat/multilingual-e5-small'
POLITICA = 'e5_cpu_normalizado_cosine_chunks_v2'


def sha(dados):
    return hashlib.sha256(dados).hexdigest().upper()


def ler_chunks(nasa):
    pasta = nasa / 'processed/chunks_saffire_v2'
    dados = (pasta / 'chunks.json').read_bytes()
    relatorio = json.loads((pasta / 'verificacao.json').read_text(encoding='utf-8-sig'))
    if sha(dados) != relatorio['sha256_chunks_json']:
        raise ValueError('Hash dos chunks diverge do relatório. Não edite o hash.')
    chunks = json.loads(dados.decode('utf-8-sig'))['chunks']
    ids = [c['chunk_id'] for c in chunks]
    if not ids or len(set(ids)) != len(ids) or len(ids) != relatorio['chunks']:
        raise ValueError('Contagem ou IDs inválidos.')
    for c in chunks:
        if not c['texto'].strip() or c['prefixo_embedding'] != 'passage: ' or not c['fontes_do_recorte']:
            raise ValueError('Chunk vazio, sem fonte ou com prefixo inesperado.')
    return chunks, relatorio


def fingerprint_modelo(modelo):
    """Hash dos pesos efetivamente carregados, sem salvar cópia dos pesos."""
    import torch
    h = hashlib.sha256()
    for nome, tensor in sorted(modelo.state_dict().items()):
        h.update(json.dumps([nome, str(tensor.dtype), list(tensor.shape)]).encode())
        array = tensor.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy()
        h.update(memoryview(array).cast('B'))
    return h.hexdigest().upper()


def validar_vetores(vetores, quantidade):
    import numpy as np
    if vetores.shape != (quantidade, 384) or not np.isfinite(vetores).all():
        raise ValueError('Formato ou valores inválidos nos embeddings.')
    if not np.allclose(np.linalg.norm(vetores, axis=1), 1, atol=1e-4):
        raise ValueError('Embeddings não normalizados.')


def preparar(base):
    from sentence_transformers import SentenceTransformer
    nasa = Path(base).resolve() / 'data/nasa_oficial'
    chunks, relatorio = ler_chunks(nasa)
    modelo = SentenceTransformer(MODELO, device='cpu', local_files_only=True,
                                trust_remote_code=False)
    limite = min(512, int(modelo.max_seq_length), int(modelo.tokenizer.model_max_length))
    entradas = ['passage: ' + c['texto'] for c in chunks]
    for c, texto in zip(chunks, entradas):
        n = len(modelo.tokenizer(texto, add_special_tokens=True, truncation=False,
                                verbose=False)['input_ids'])
        if n != c['tokens_com_prefixo_e_especiais'] or n > min(320, limite):
            raise ValueError(f'Tokenização mudou ou excedeu o limite: {c["chunk_id"]}. Revisar antes de indexar.')
    # Ignora apenas configurações transitórias de padding/truncation do backend.
    backend = json.loads(modelo.tokenizer.backend_tokenizer.to_str())
    backend.pop('padding', None)
    backend.pop('truncation', None)
    assinatura = {'politica': POLITICA, 'modelo': MODELO,
        'sha256_chunks_json': relatorio['sha256_chunks_json'],
        'sha256_pesos': fingerprint_modelo(modelo),
        'sha256_tokenizer': sha(json.dumps(backend, sort_keys=True).encode()),
        'modulos': {nome: {'classe': type(m).__name__, 'config': m.get_config_dict()}
                    for nome, m in modelo._modules.items()},
        'limite_efetivo': limite,
        'versoes': {p: version(p) for p in ['torch','sentence-transformers','transformers','tokenizers','chromadb']}}
    identidade = sha(json.dumps(assinatura, sort_keys=True, default=str).encode())
    pasta = nasa / 'indexes' / ('saffire_v2_' + identidade[:16].lower())
    return nasa, chunks, entradas, modelo, assinatura, identidade, pasta


def cliente(pasta):
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=str(pasta / 'chroma'),
                                     settings=Settings(anonymized_telemetry=False))


def indexar(base):
    nasa, chunks, entradas, modelo, assinatura, identidade, pasta = preparar(base)
    vetores = modelo.encode(entradas, batch_size=4, prompt='',
                           normalize_embeddings=True, convert_to_numpy=True,
                           show_progress_bar=True)
    validar_vetores(vetores, len(chunks))
    db = cliente(pasta)
    colecao = db.get_or_create_collection(name='saffire_documental',
        embedding_function=None, metadata={'assinatura': identidade},
        configuration={'hnsw': {'space': 'cosine'}})
    if colecao.metadata.get('assinatura') != identidade:
        raise ValueError('Coleção incompatível.')
    ids = [c['chunk_id'] for c in chunks]
    if set(colecao.get(include=[])['ids']) - set(ids):
        raise ValueError('Coleção contém IDs inesperados; nenhuma exclusão automática será feita.')
    metadados = []
    for c in chunks:
        fonte = c['fontes_do_recorte'][0]
        metadados.append({'recorte_id': c['recorte_id'], 'tipo_evidencia': c['tipo_evidencia'],
                         'documento_id': fonte['documento_id'], 'pagina_fisica': fonte['pagina_fisica']})
    # IDs estáveis tornam uma nova execução uma atualização, sem duplicar registros.
    for i in range(0, len(chunks), 32):
        colecao.upsert(ids=ids[i:i+32], embeddings=vetores[i:i+32].tolist(),
                       documents=[c['texto'] for c in chunks[i:i+32]],
                       metadatas=metadados[i:i+32])
    if set(colecao.get(include=[])['ids']) != set(ids):
        raise ValueError('Persistência incompleta. A mesma execução pode ser retomada.')
    manifesto = {**assinatura, 'assinatura': identidade, 'chunks': len(chunks),
                 'dimensao': 384, 'distancia': 'cosine', 'status': 'completo'}
    temporario = pasta / 'manifesto.tmp'
    temporario.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporario.replace(pasta / 'manifesto.json')
    print(f'Embeddings: {vetores.shape}; dispositivo: {modelo.device}')
    print(f'Registros persistidos: {colecao.count()}')
    print(f'Índice: {pasta}')
    print('Indexação concluída. Nenhum LLM foi executado.')


PERGUNTAS = [
    ('Q1_EN', 'What airflow speed and quasi-steady flame spread rate were reported for Saffire-III?'),
    ('Q1_PT', 'Qual velocidade de escoamento e taxa de propagação quase estacionária foram relatadas para Saffire-III?'),
    ('Q2_EN', 'How was flame spread measured in Saffire-I?'),
    ('Q2_PT', 'Como foi medida a propagação da chama em Saffire-I?'),
]


def consultar(base):
    nasa, chunks, entradas, modelo, assinatura, identidade, pasta = preparar(base)
    caminho = pasta / 'manifesto.json'
    if not caminho.is_file():
        raise FileNotFoundError('Não existe índice completo compatível. Execute indexar; se mudou dependências, confira a configuração.')
    manifesto = json.loads(caminho.read_text(encoding='utf-8'))
    if manifesto['assinatura'] != identidade or manifesto['status'] != 'completo':
        raise ValueError('Manifesto incompatível ou índice incompleto.')
    db = cliente(pasta)
    colecao = db.get_collection(name='saffire_documental', embedding_function=None)
    mapa = {c['chunk_id']: c for c in chunks}
    if colecao.metadata.get('assinatura') != identidade or set(colecao.get(include=[])['ids']) != set(mapa):
        raise ValueError('Índice não corresponde ao corpus.')
    saidas = []
    for ident, pergunta in PERGUNTAS:
        entrada = 'query: ' + pergunta
        if len(modelo.tokenizer(entrada, truncation=False)['input_ids']) > assinatura['limite_efetivo']:
            raise ValueError('Pergunta excede o limite do modelo.')
        v = modelo.encode([entrada], prompt='', normalize_embeddings=True,
                          convert_to_numpy=True, show_progress_bar=False)
        validar_vetores(v, 1)
        resposta = colecao.query(query_embeddings=v.tolist(), n_results=min(5,len(chunks)),
                                include=['distances','documents','metadatas'])
        resultados = []
        print(f'\n{ident}: {pergunta}')
        for pos, (chunk_id, distancia, texto) in enumerate(zip(
            resposta['ids'][0], resposta['distances'][0], resposta['documents'][0]), 1):
            c = mapa[chunk_id]
            if texto != c['texto']:
                raise ValueError('Texto persistido diverge do chunk de origem.')
            resultados.append({'posicao': pos, 'chunk_id': chunk_id, 'distancia_cosseno': distancia,
                               'texto': texto, 'tipo_evidencia': c['tipo_evidencia'],
                               'nota_editorial': c['nota_editorial'], 'fontes_do_recorte': c['fontes_do_recorte']})
            fonte = c['fontes_do_recorte'][0]
            print(f'{pos}. {fonte["apelido_documento"]}, p. {fonte["pagina_fisica"]}; distância {distancia:.4f}; {c["tipo_evidencia"]}')
            if pos <= 3:
                print(texto)
        saidas.append({'pergunta_id': ident, 'pergunta': pergunta, 'resultados': resultados})
    reports = nasa / 'reports'
    reports.mkdir(exist_ok=True)
    arquivo = reports / ('recuperacao_saffire_v2_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    arquivo.write_text(json.dumps({'assinatura_indice': identidade,
        'avaliacao_automatica_de_relevancia': False, 'consultas': saidas}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nRelatório completo: {arquivo}')
    print('Conferir relevância nas fontes. Distância não comprova suporte à resposta.')
