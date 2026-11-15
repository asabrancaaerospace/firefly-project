"""Aplica uma seleção editorial auditável; não consulta LLM nem banco vetorial."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

POLITICA = 'ligaturas_espacos_hifens_lista_v1'
LIGATURAS = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st'}
# Só reconstruímos palavras explicitamente autorizadas; hífens semânticos ficam intactos.
PALAVRAS = {'experimental', 'experiments', 'experiment', 'microgravity',
            'pyrolysis', 'combustion', 'temperature', 'radiation', 'velocity',
            'concurrent', 'propagation', 'boundary', 'numerical', 'conditions',
            'oxygen', 'different', 'measurement', 'measurements'}


def digest(conteudo):
    return hashlib.sha256(conteudo).hexdigest().upper()


def normalizar(texto):
    alteracoes = []
    for antigo, novo in LIGATURAS.items():
        n = texto.count(antigo)
        if n:
            alteracoes.append({'regra': 'ligatura', 'de': antigo, 'para': novo, 'ocorrencias': n})
            texto = texto.replace(antigo, novo)

    def unir(match):
        palavra = match[1] + match[2]
        if palavra.lower() in PALAVRAS:
            alteracoes.append({'regra': 'hifen_de_quebra_autorizado',
                               'de': match[0], 'para': palavra})
            return palavra
        return match[0]

    texto = re.sub(r'([A-Za-z]+)-[ \t]*\r?\n[ \t]*([A-Za-z]+)', unir, texto)
    # Apenas controles sem conteúdo textual; não altera números, sinais ou expoentes.
    texto, n = re.subn(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', texto)
    if n:
        alteracoes.append({'regra': 'controle_para_espaco', 'ocorrencias': n})
    novo = re.sub(r'\s+', ' ', texto).strip()
    if novo != texto:
        alteracoes.append({'regra': 'espacos_e_quebras_uniformizados'})
    return novo, alteracoes


def construir(paginas_bytes, plano):
    if digest(paginas_bytes) != plano['sha256_paginas_json'].upper():
        raise ValueError('O JSON de páginas não corresponde à versão revisada. Não edite o hash para contornar a conferência.')
    base = json.loads(paginas_bytes.decode('utf-8-sig'))
    docs = {d['documento_id']: d for d in base['documentos']}
    vistos = set()
    resultado = []
    for item in plano['recortes']:
        ident = item['recorte_id']
        if ident in vistos:
            raise ValueError(f'ID repetido: {ident}')
        vistos.add(ident)
        if not item['fontes']:
            raise ValueError(f'Recorte sem fonte: {ident}')
        partes = []
        referencias = []
        for fonte in item['fontes']:
            doc = docs[fonte['documento_id']]
            if doc['sha256_pdf'] != fonte['sha256_pdf']:
                raise ValueError(f'Hash do PDF divergente: {ident}')
            numero = fonte['pagina_fisica']
            if not isinstance(numero, int) or not 1 <= numero <= len(doc['paginas']):
                raise ValueError('Página inválida.')
            pagina = doc['paginas'][numero - 1]
            texto = pagina[plano['campo_texto']]
            inicio, fim = fonte['inicio_char'], fonte['fim_char_exclusivo']
            if not 0 <= inicio < fim <= len(texto):
                raise ValueError(f'Intervalo inválido: {ident}')
            literal = texto[inicio:fim]
            if literal != fonte['trecho_literal']:
                raise ValueError(f'Trecho divergente: {ident}')
            partes.append(literal)
            referencias.append({**fonte, 'pagina_impressa': pagina['pagina_impressa'],
                                'apelido_documento': doc['ficha_selecao']['apelido'],
                                'titulo_documento': doc['ficha_selecao']['titulo'],
                                'campo_texto': plano['campo_texto']})
        original = '\n'.join(partes)
        normalizado, alteracoes = normalizar(original)
        if not normalizado:
            raise ValueError(f'Recorte vazio: {ident}')
        resultado.append({
            'recorte_id': ident, 'tipo_evidencia': item['tipo_evidencia'],
            'nota_editorial': item['nota_editorial'],
            'texto_original_selecionado': original, 'texto_para_busca': normalizado,
            'fontes': referencias, 'exclusoes_internas': item['exclusoes_internas'],
            'politica_normalizacao': POLITICA, 'transformacoes': alteracoes,
            'sha256_texto_para_busca': digest(normalizado.encode('utf-8')),
            'status': 'recorte_editorial_aguardando_chunking_e_avaliacao',
        })
    # Relações documentais; não significam que todo vizinho deva entrar no contexto do LLM.
    for i, recorte in enumerate(resultado):
        doc_id = recorte['fontes'][0]['documento_id']
        recorte['vizinhos_na_selecao'] = [resultado[j]['recorte_id'] for j in (i-1, i+1)
            if 0 <= j < len(resultado) and resultado[j]['fontes'][0]['documento_id'] == doc_id]
    return resultado


def executar(base):
    nasa = Path(base).resolve() / 'data' / 'nasa_oficial'
    entrada = nasa / 'extracted' / 'saffire_documental_v1' / 'paginas.json'
    caminho_plano = nasa / 'metadata' / 'plano_recortes_saffire_v1.json'
    destino = nasa / 'processed' / 'recortes_saffire_v1'
    if destino.exists():
        raise FileExistsError(f'Saída já existe; não será sobrescrita: {destino}')
    paginas_bytes = entrada.read_bytes()
    plano_bytes = caminho_plano.read_bytes()
    plano = json.loads(plano_bytes.decode('utf-8-sig'))
    recortes = construir(paginas_bytes, plano)
    contagens = {}
    for r in recortes:
        chave = r['fontes'][0]['documento_id']
        contagens[chave] = contagens.get(chave, 0) + 1
    relatorio = {'recortes': len(recortes), 'por_documento': contagens,
                 'sha256_paginas_json': digest(paginas_bytes),
                 'sha256_plano': digest(plano_bytes), 'politica_normalizacao': POLITICA,
                 'indexado_no_chroma': False, 'embeddings_gerados': False,
                 'limite_tokens_verificado': False,
                 'conteudo_fora_do_piloto': plano['conteudo_fora_do_piloto']}
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = Path(tempfile.mkdtemp(prefix='.recortes_', dir=destino.parent))
    try:
        arquivo = temporario / 'recortes.json'
        arquivo.write_text(json.dumps({'versao': 1, 'recortes': recortes}, ensure_ascii=False, indent=2), encoding='utf-8')
        relatorio['sha256_recortes_json'] = digest(arquivo.read_bytes())
        (temporario / 'verificacao.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')
        if destino.exists():
            raise FileExistsError(f'Saída já existe: {destino}')
        temporario.rename(destino)
    finally:
        if temporario.exists():
            shutil.rmtree(temporario)
    print(f'Recortes preparados: {len(recortes)}')
    for doc, quantidade in contagens.items():
        print(f'{doc}: {quantidade}')
    print(f'Saída: {destino}')
    print('Originais preservados. Embeddings e indexação ainda não executados.')
    return relatorio
