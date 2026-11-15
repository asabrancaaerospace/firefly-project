"""Diagnóstico: ranking exato versus Chroma, sem mudar o corpus ou treinar modelo."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def ranking_exato(ids, vetores, consulta):
    if len(ids) != len(vetores) or len(set(ids)) != len(ids):
        raise ValueError('IDs ou quantidade de vetores inválidos.')
    q = [float(x) for x in consulta]
    if not q or not all(math.isfinite(x) for x in q):
        raise ValueError('Consulta inválida.')
    nq = math.sqrt(sum(x*x for x in q))
    if nq == 0:
        raise ValueError('Vetor de consulta nulo.')
    resultado = []
    for ident, vetor in zip(ids, vetores):
        v = [float(x) for x in vetor]
        if len(v) != len(q) or not all(math.isfinite(x) for x in v):
            raise ValueError('Vetor documental inválido.')
        nv = math.sqrt(sum(x*x for x in v))
        if nv == 0:
            raise ValueError('Vetor documental nulo.')
        distancia = 1 - sum(a*b for a,b in zip(v,q)) / (nv*nq)
        resultado.append({'chunk_id': ident, 'distancia_cosseno': distancia})
    return sorted(resultado, key=lambda r: (r['distancia_cosseno'], r['chunk_id']))


def executar(base):
    from src.retrieval.indice_saffire_v2 import preparar, cliente, PERGUNTAS, validar_vetores
    nasa, chunks, entradas, modelo, assinatura, identidade, pasta = preparar(base)
    manifesto = json.loads((pasta/'manifesto.json').read_text(encoding='utf-8'))
    if manifesto['assinatura'] != identidade or manifesto['status'] != 'completo':
        raise ValueError('Índice não corresponde à configuração atual.')
    db = cliente(pasta)
    colecao = db.get_collection(name='saffire_documental', embedding_function=None)
    mapa = {c['chunk_id']: c for c in chunks}
    armazenado = colecao.get(include=['embeddings','documents'])
    if set(armazenado['ids']) != set(mapa) or colecao.metadata.get('assinatura') != identidade:
        raise ValueError('Índice incompatível com os chunks.')
    for ident, texto in zip(armazenado['ids'], armazenado['documents']):
        if texto != mapa[ident]['texto']:
            raise ValueError('Texto armazenado divergente.')
    # Alvos apenas para diagnóstico; nunca modificam a ordem da busca.
    alvos_metodo = {c['chunk_id'] for c in chunks if c['tipo_evidencia']=='metodo_medicao'
                    and any(f['apelido_documento']=='SAFFIRE_ARTIGO' and f['pagina_fisica']==8
                            for f in c['fontes_do_recorte'])}
    consultas = []
    for nome, pergunta in PERGUNTAS:
        vetor = modelo.encode(['query: '+pergunta], prompt='', normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=False)
        validar_vetores(vetor, 1)
        ordem = ranking_exato(armazenado['ids'], armazenado['embeddings'], vetor[0])
        hnsw = colecao.query(query_embeddings=vetor.tolist(), n_results=min(5,len(chunks)), include=['distances'])
        top5 = [r['chunk_id'] for r in ordem[:5]]
        alvos = [dict(r, posicao=i) for i,r in enumerate(ordem,1) if r['chunk_id'] in alvos_metodo]
        principais = []
        for i, r in enumerate(ordem[:20],1):
            c = mapa[r['chunk_id']]
            principais.append({**r, 'posicao':i, 'recorte_id':c['recorte_id'],
                'tipo_evidencia':c['tipo_evidencia'], 'texto':c['texto'],
                'fontes_resumidas':[{'documento':f['apelido_documento'], 'pagina':f['pagina_fisica']}
                                   for f in c['fontes_do_recorte']]})
        comuns = len(set(top5) & set(hnsw['ids'][0]))
        consultas.append({'pergunta_id':nome, 'pergunta':pergunta,
                          'top5_chroma':hnsw['ids'][0], 'top5_exato':top5,
                          'ids_em_comum_top5':comuns, 'top20_exato':principais,
                          'posicoes_trechos_metodo_p8':alvos})
        print(f'{nome}: coincidência dos conjuntos top 5 = {comuns}/5')
        print('Posições exatas dos chunks de método da página 8:', [r['posicao'] for r in alvos])

    # Localiza cortes dentro de palavras e continuação de palavras hifenizadas.
    import re
    fonte = json.loads((nasa/'processed/recortes_saffire_v1/recortes.json').read_text(encoding='utf-8-sig'))
    recortes = {r['recorte_id']:r['texto_para_busca'] for r in fonte['recortes']}
    bordas = []
    for c in chunks:
        t = recortes[c['recorte_id']]
        a,b = c['inicio_char_normalizado'], c['fim_char_normalizado_exclusivo']
        if t[a:b] != c['texto']:
            raise ValueError('Recorte atual diverge do chunk; diagnóstico interrompido.')
        motivos = []
        if a > 0 and t[a-1].isalnum() and t[a].isalnum():
            motivos.append('inicio_no_meio_de_palavra')
        if b < len(t) and t[b-1].isalnum() and t[b].isalnum():
            motivos.append('fim_no_meio_de_palavra')
        if a > 0 and re.search(r'\w+-\s+$',t[max(0,a-50):a]):
            motivos.append('inicio_apos_hifen_de_quebra')
        if motivos:
            bordas.append({'chunk_id':c['chunk_id'], 'motivos':motivos,
                           'inicio_com_contexto':t[max(0,a-30):a+70],
                           'fim_com_contexto':t[max(a,b-50):min(len(t),b+30)]})
    saida = nasa/'reports'
    saida.mkdir(exist_ok=True)
    arquivo = saida/('auditoria_recuperacao_v2_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    arquivo.write_text(json.dumps({'assinatura_indice':identidade,'chunks':len(chunks),
        'alvos_metodo_p8_presentes':len(alvos_metodo), 'consultas':consultas,
        'bordas_candidatas_a_revisao':bordas,
        'observacao':'Busca exata é referência vetorial, não gabarito de relevância científica. Nenhum ranking foi favorecido pelos alvos de diagnóstico.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Chunks com bordas candidatas a revisão: {len(bordas)}')
    print(f'Relatório: {arquivo}')
