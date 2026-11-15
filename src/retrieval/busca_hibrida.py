"""Recuperação experimental por recorte: embeddings + BM25 + fusão RRF."""
import math
import re
import unicodedata
from collections import Counter

VERSAO = 'recorte_dense_bm25_intencao_metodo_rrf60_v1'
ROTULOS = {
    'metodo_medicao': 'measurement method procedure',
    'metodos_e_condicoes': 'experimental setup conditions apparatus',
    'resultado_experimental_publicado': 'experimental results',
    'resultado_experimental_e_interpretacao': 'experimental results interpretation',
    'resultados_computacionais': 'numerical simulation computational results',
    'modelagem': 'numerical model simulation',
    'comparacao_entre_estudos': 'comparison between studies',
    'ressalva_metodologica': 'methodological limitations caveats',
    'contexto_secundario_historico': 'historical secondary context',
    'organizacao_e_configuracao_descrita': 'data organization described configuration',
}
GRUPOS = [
    ('measurement','measure','measured','measurements','medicao','medida','medidas','medido','medidos','medir'),
    ('method','methods','metodo','metodos','procedure','procedimento'),
    ('spread','propagation','propagacao'), ('flame','flames','chama','chamas'),
    ('airflow','escoamento'), ('speed','speeds','velocity','velocities','velocidade','velocidades'),
    ('oxygen','oxigenio'), ('pressure','pressures','pressao','pressoes'),
    ('sample','samples','amostra','amostras'), ('fabric','fabrics','tecido','tecidos'),
    ('temperature','temperatures','temperatura','temperaturas'),
    ('simulation','simulations','simulacao','simulacoes','simulated','simulado'),
    ('model','models','modelo','modelos'), ('limit','limits','limite','limites'),
    ('composition','composicao'), ('cotton','algodao'), ('fiberglass','vidro'),
    ('dimensions','dimension','dimensoes','dimensao'), ('width','largura'),
    ('length','comprimento'), ('thickness','espessura'),
    ('quasisteady','quasi-steady','quase-estacionaria','quase-estacionario'),
    ('safety','seguranca'), ('ventilation','ventilacao'), ('historical','historico','historicos'),
]
SINONIMOS = {termo: grupo[0] for grupo in GRUPOS for termo in grupo}
IGNORAR = set('a an the of in on at to and or for was were is are do does did how what which with by from as be been it its this that these those o os as um uma de da das do dos em no na nos nas para por e ou foi foram e sao como qual quais que com se ao aos uma um'.split())


def termos(texto):
    s = unicodedata.normalize('NFKD',texto.casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    # Normalização lexical apenas; o texto científico original não é alterado.
    s = re.sub(r'\bsaffire[\s-]*(iii|ii|i|[123])\b',
               lambda m: 'saffire'+{'i':'1','ii':'2','iii':'3'}.get(m[1],m[1]),s)
    tokens = re.findall(r'[a-z]+(?:-[a-z]+)*\d*|\d+(?:[.,]\d+)?',s)
    return [SINONIMOS.get(t,t) for t in tokens if t not in IGNORAR]


def ranking_bm25(textos, pergunta):
    docs = {ident:Counter(termos(texto)) for ident,texto in textos.items()}
    if not docs:
        return []
    comprimentos = {ident:sum(c.values()) for ident,c in docs.items()}
    media = sum(comprimentos.values())/len(docs) or 1
    query = set(termos(pergunta))
    resultados = []
    for ident, contagem in docs.items():
        score = 0.0
        for termo in query:
            tf = contagem.get(termo,0)
            if not tf:
                continue
            df = sum(termo in c for c in docs.values())
            idf = math.log(1+(len(docs)-df+0.5)/(df+0.5))
            score += idf*(tf*2.2)/(tf+1.2*(0.25+0.75*comprimentos[ident]/media))
        if score>0:
            resultados.append({'recorte_id':ident,'score_bm25':score})
    return sorted(resultados,key=lambda x:(-x['score_bm25'],x['recorte_id']))


def fundir(denso, lexical, k=60, metodologico=None):
    if k<=0:
        raise ValueError('k deve ser positivo.')
    posd = {x['recorte_id']:i for i,x in enumerate(denso,1)}
    posl = {x['recorte_id']:i for i,x in enumerate(lexical,1)}
    posm = {x['recorte_id']:i for i,x in enumerate(metodologico or [],1)}
    resultados = []
    for ident in set(posd)|set(posl)|set(posm):
        score = (1/(k+posd[ident]) if ident in posd else 0)+(1/(k+posl[ident]) if ident in posl else 0)
        score += 1/(k+posm[ident]) if ident in posm else 0
        resultados.append({'recorte_id':ident,'score_rrf':score,
                           'posicao_densa':posd.get(ident),'posicao_lexical':posl.get(ident),
                           'posicao_prior_metodologico':posm.get(ident)})
    return sorted(resultados,key=lambda x:(-x['score_rrf'],x['recorte_id']))


def pergunta_metodologica(pergunta):
    s=''.join(c for c in unicodedata.normalize('NFKD',pergunta.casefold()) if not unicodedata.combining(c))
    ts=set(termos(pergunta))
    return 'method' in ts or (bool(re.search(r'\b(how|como)\b',s)) and 'measurement' in ts)


def buscar(recortes, chunks, ranking_chunks, pergunta):
    mapa = {c['chunk_id']:c for c in chunks}
    por_recorte = {}
    for item in ranking_chunks:
        c = mapa[item['chunk_id']]
        ident = c['recorte_id']
        if ident not in por_recorte or item['distancia_cosseno'] < por_recorte[ident]['distancia_cosseno']:
            por_recorte[ident] = {**item,'recorte_id':ident}
    denso = sorted(por_recorte.values(),key=lambda x:(x['distancia_cosseno'],x['recorte_id']))
    textos = {}
    for r in recortes:
        # Só metadados editoriais existentes; sem resposta esperada, páginas-alvo ou gabarito.
        titulo = r['fontes'][0].get('titulo_documento','')
        textos[r['recorte_id']] = titulo+' '+ROTULOS.get(r['tipo_evidencia'],'')+' '+r['texto_para_busca']
    if set(textos)!=set(por_recorte):
        raise ValueError('Recortes e chunks não correspondem.')
    lexical = ranking_bm25(textos,pergunta)
    metodos=[]
    if pergunta_metodologica(pergunta):
        tipos={r['recorte_id']:r['tipo_evidencia'] for r in recortes}
        prioridade={'metodo_medicao':0,'metodos_e_condicoes':1,'ressalva_metodologica':2}
        metodos=sorted([r for r in denso if tipos[r['recorte_id']] in prioridade],
                       key=lambda r:(prioridade[tipos[r['recorte_id']]],r['distancia_cosseno'],r['recorte_id']))
    return {'denso':denso,'lexical':lexical,'prior_metodologico':metodos,
            'intencao_metodologica':pergunta_metodologica(pergunta),
            'hibrido_sem_intencao':fundir(denso,lexical),
            'hibrido':fundir(denso,lexical,metodologico=metodos),
            'termos_lexicais_consulta':sorted(set(termos(pergunta)))}
