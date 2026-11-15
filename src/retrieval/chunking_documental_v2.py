"""Chunking por offsets do tokenizer; nunca executa inferência nem trunca texto."""
import hashlib
import json
import re
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

MODELO = 'intfloat/multilingual-e5-small'
PREFIXO = 'passage: '
LIMITE = 320
SOBREPOSICAO = 40
POLITICA = 'e5_limites_palavras_320_overlap40_v2'


def sha(conteudo):
    return hashlib.sha256(conteudo).hexdigest().upper()


def tokenizar(tokenizer, texto, especiais=False, offsets=False):
    return tokenizer(texto, add_special_tokens=especiais, truncation=False,
                     return_offsets_mapping=offsets, verbose=False)


def quantidade(tokenizer, texto):
    return len(tokenizar(tokenizer, PREFIXO + texto, especiais=True)['input_ids'])


def unidades_lexicais(texto):
    """Intervalos sem espaços; mantém 'fab- ric' em uma unidade protegida."""
    unidades = []
    for m in re.finditer(r'\S+', texto):
        if unidades:
            a, b = unidades[-1]
            anterior = texto[a:b]
            if len(anterior) >= 2 and anterior[-1] == '-' and anterior[-2].isalpha() and m[0][0].isalpha():
                unidades[-1] = (a, m.end())
                continue
        unidades.append((m.start(), m.end()))
    return unidades


def validar_bordas(texto, partes):
    inicios = {a for a, b in unidades_lexicais(texto)} | {0}
    finais = inicios | {len(texto)}
    for p in partes:
        if p['inicio_char_normalizado'] not in inicios or p['fim_char_normalizado_exclusivo'] not in finais:
            raise ValueError('Chunk cortou uma unidade lexical protegida.')


def dividir(texto, tokenizer, limite=LIMITE, sobreposicao=SOBREPOSICAO):
    if not texto.strip():
        raise ValueError('Texto vazio.')
    if not tokenizer.is_fast:
        raise ValueError('É necessário um tokenizer rápido.')
    reserva = quantidade(tokenizer, '')
    if not reserva < limite <= min(int(tokenizer.model_max_length), 512) or not 0 <= sobreposicao < limite-reserva:
        raise ValueError('Limite ou sobreposição inválidos.')
    unidades = unidades_lexicais(texto)
    fronteiras = sorted({a for a,b in unidades} | {0,len(texto)})
    partes = []
    inicio = 0
    while inicio < len(texto):
        restante = texto[inicio:]
        offsets = [tuple(p) for p in tokenizar(tokenizer, restante, offsets=True)['offset_mapping'] if p[1]>p[0]]
        if not offsets:
            raise ValueError('Offsets indisponíveis.')
        janela = min(limite-reserva, len(offsets))
        alvo = len(texto) if janela == len(offsets) else inicio+offsets[janela-1][1]
        finais = [x for x in fronteiras if inicio < x <= alvo]
        # Se o token termina antes de espaços, pode caber a fronteira seguinte.
        seguinte = next((x for x in fronteiras if x > alvo), None)
        if seguinte is not None and quantidade(tokenizer,texto[inicio:seguinte]) <= limite:
            finais.append(seguinte)
        fim = None
        for candidato in reversed(finais):
            if quantidade(tokenizer,texto[inicio:candidato]) <= limite:
                fim = candidato
                break
        if fim is None:
            raise ValueError('Unidade lexical não cabe no orçamento; revisar o recorte, sem cortar a palavra.')
        if fim < len(texto):
            candidatos = []
            for m in re.finditer(r'[.!?]\s+(?=[A-ZÀ-ÖØ-Þ])', texto[inicio:fim]):
                ponto = inicio+m.end()
                if ponto in fronteiras and ponto >= inicio+int((fim-inicio)*0.65):
                    candidatos.append(ponto)
            for candidato in reversed(candidatos):
                if quantidade(tokenizer,texto[inicio:candidato]) <= limite:
                    fim = candidato
                    break
        trecho = texto[inicio:fim]
        partes.append({'inicio_char_normalizado':inicio, 'fim_char_normalizado_exclusivo':fim,
                       'texto':trecho, 'tokens_com_prefixo_e_especiais':quantidade(tokenizer,trecho)})
        if fim == len(texto):
            break
        pos = [tuple(p) for p in tokenizar(tokenizer,trecho,offsets=True)['offset_mapping'] if p[1]>p[0]]
        proximo = fim
        if sobreposicao and len(pos)>sobreposicao:
            alvo_inicio = inicio+pos[-sobreposicao][0]
            anteriores = [x for x in fronteiras if inicio < x <= alvo_inicio and x < fim]
            if anteriores:
                proximo = anteriores[-1]
        inicio = proximo
    validar_cobertura(texto,partes,tokenizer,limite)
    validar_bordas(texto,partes)
    return partes


def validar_cobertura(texto, partes, tokenizer, limite=LIMITE):
    if not partes:
        raise ValueError('Nenhum chunk.')
    coberto = 0
    anterior = -1
    for p in partes:
        a, b = p['inicio_char_normalizado'], p['fim_char_normalizado_exclusivo']
        if not (0 <= a < b <= len(texto)) or a > coberto or a <= anterior:
            raise ValueError('Intervalos com lacuna, ordem incorreta ou sem avanço.')
        if texto[a:b] != p['texto']:
            raise ValueError('Texto do chunk diverge da origem.')
        contagem = quantidade(tokenizer, p['texto'])
        if contagem > limite or contagem != p['tokens_com_prefixo_e_especiais']:
            raise ValueError('Contagem de tokens inválida.')
        coberto = max(coberto, b)
        anterior = a
    if coberto != len(texto):
        raise ValueError('Final do recorte não foi preservado.')


def carregar_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(MODELO, local_files_only=True,
                                         trust_remote_code=False, use_fast=True)


def executar(base, tokenizer=None):
    nasa = Path(base).resolve() / 'data' / 'nasa_oficial'
    origem = nasa / 'processed' / 'recortes_saffire_v1'
    saida = nasa / 'processed' / 'chunks_saffire_v2'
    if saida.exists():
        raise FileExistsError(f'Saída já existe: {saida}')
    conteudo = (origem / 'recortes.json').read_bytes()
    verificacao = json.loads((origem / 'verificacao.json').read_text(encoding='utf-8-sig'))
    if sha(conteudo) != verificacao['sha256_recortes_json']:
        raise ValueError('Hash dos recortes divergente do relatório de preparação.')
    recortes = json.loads(conteudo.decode('utf-8-sig'))['recortes']
    if not recortes or len({r['recorte_id'] for r in recortes}) != len(recortes):
        raise ValueError('Recortes vazios ou IDs duplicados.')
    tokenizer = tokenizer if tokenizer is not None else carregar_tokenizer()
    assinatura = sha(tokenizer.backend_tokenizer.to_str().encode('utf-8'))
    chunks = []
    contagens = {}
    for r in recortes:
        texto = r['texto_para_busca']
        if sha(texto.encode('utf-8')) != r['sha256_texto_para_busca']:
            raise ValueError(f'Texto alterado: {r["recorte_id"]}')
        partes = dividir(texto, tokenizer)
        contagens[r['recorte_id']] = len(partes)
        for numero, parte in enumerate(partes, 1):
            identidade = [POLITICA, assinatura, r['recorte_id'], sha(texto.encode('utf-8')),
                          parte['inicio_char_normalizado'], parte['fim_char_normalizado_exclusivo']]
            chunks.append({**parte,
                'chunk_id': sha(json.dumps(identidade, ensure_ascii=False).encode('utf-8')).lower(),
                'recorte_id': r['recorte_id'], 'ordem_no_recorte': numero,
                'tipo_evidencia': r['tipo_evidencia'], 'nota_editorial': r['nota_editorial'],
                'fontes_do_recorte': r['fontes'],
                'vizinhos_do_recorte': r['vizinhos_na_selecao'],
                'prefixo_embedding': PREFIXO,
                'escopo_offsets': 'Caracteres de texto_para_busca do recorte; não são coordenadas no PDF.',
            })
    if len({c['chunk_id'] for c in chunks}) != len(chunks):
        raise ValueError('IDs de chunks duplicados.')
    relatorio = {'politica': POLITICA, 'modelo': MODELO, 'prefixo': PREFIXO,
        'limite_tokens': LIMITE, 'sobreposicao_alvo_tokens_sem_especiais': SOBREPOSICAO,
        'limite_declarado_tokenizer': int(tokenizer.model_max_length),
        'sha256_backend_tokenizer': assinatura, 'transformers': version('transformers'),
        'tokenizers': version('tokenizers'), 'sha256_recortes_json': sha(conteudo),
        'recortes': len(recortes), 'chunks': len(chunks), 'chunks_por_recorte': contagens,
        'maior_tamanho_tokens': max(c['tokens_com_prefixo_e_especiais'] for c in chunks),
        'cobertura_integral_dos_recortes': True, 'ids_unicos': True,
        'bordas_lexicais_validadas': True,
        'embeddings_gerados': False, 'indexado_no_chroma': False}
    saida.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.chunks_', dir=saida.parent))
    try:
        caminho = temp / 'chunks.json'
        caminho.write_text(json.dumps({'versao': 2, 'chunks': chunks}, ensure_ascii=False, indent=2), encoding='utf-8')
        relatorio['sha256_chunks_json'] = sha(caminho.read_bytes())
        (temp / 'verificacao.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')
        if saida.exists():
            raise FileExistsError(f'Saída já existe: {saida}')
        temp.rename(saida)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    print(f'Recortes processados: {len(recortes)}')
    print(f'Chunks gerados: {len(chunks)}')
    print(f'Maior tamanho com prefixo e especiais: {relatorio["maior_tamanho_tokens"]}')
    print('Cobertura integral do texto selecionado: OK')
    print('IDs únicos: OK')
    print('Bordas lexicais e palavras hifenizadas protegidas: OK')
    print(f'Saída: {saida}')
    print('Embeddings e indexação ainda não executados.')
    return relatorio
