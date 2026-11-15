"""Consulta de registros SIBAL; extremos publicados não são novas medições temporais."""
import json
from pathlib import Path
from src.ingestion.bass_tabela51 import sha256, HASH_RELATORIO
from src.ingestion.bass_tabela71 import estruturar

ROTULOS={
 'extincao_quenching_relatada':'Extinção relatada (quenched)',
 'ausencia_de_blowoff_relatada':'Ausência de blowoff relatada',
 'ausencia_de_ignicao_relatada':'Ausência de ignição relatada',
 'extincao_blowoff_relatada':'Extinção relatada (blowoff)',
 'chama_em_uma_face_relatada':'Chama em uma face relatada',
 'ignicao_relatada':'Ignição relatada',
 'nao_informada_nesta_coluna':'Não informada na coluna de comentários',
}


def carregar(base: Path):
    nasa=base/'data'/'nasa_oficial'
    pasta=nasa/'processed'/'bass_tabela71_v1'
    registros=json.loads((pasta/'registros.json').read_text(encoding='utf-8-sig'))
    verificacao=json.loads((pasta/'verificacao.json').read_text(encoding='utf-8-sig'))
    candidato=nasa/'extracted'/'tabelas_candidatas_bass_v1.json'
    pdf=nasa/'raw'/'PSI-25'/'Report'/'BASS-II Summary Report.pdf'
    if sha256(pdf)!=HASH_RELATORIO or verificacao['pdf_sha256']!=HASH_RELATORIO:
        raise ValueError('Hash do relatório divergente.')
    if sha256(candidato)!=verificacao['json_entrada_sha256']:
        raise ValueError('O candidato mudou após o processamento.')
    if verificacao.get('conferencia_celulas_com_pdf') is not True:
        raise ValueError('Conferência das células não registrada.')
    dados=json.loads(candidato.read_text(encoding='utf-8-sig'))
    tabelas=[t for t in dados['tabelas'] if t['tabela']=='7.1']
    if len(tabelas)!=1 or registros!=estruturar(tabelas[0]):
        raise ValueError('Registros divergentes da transformação verificada.')
    return registros


def filtrar(registros,investigacoes,larguras,observacoes,qualidade,reutilizacao):
    return [r for r in registros if r['investigacao_id'] in investigacoes
            and r['largura_mm'] in larguras
            and r['observacao_padronizada'] in observacoes
            and ('com_ressalva' if r['oxigenio_nota_b'] else 'sem_ressalva_explicita') in qualidade
            and ('relatada' if r['reutilizacao_relata'] is True else 'nao_informada') in reutilizacao]


def resumir(registros):
    return {'registros':len(registros),
            'bass_ii':sum(r['investigacao_id']=='PSI-25' for r in registros),
            'bass':sum(r['investigacao_id']=='PSI-26' for r in registros),
            'o2_com_ressalva':sum(r['oxigenio_nota_b'] for r in registros),
            'reutilizacao_relatada':sum(r['reutilizacao_relata'] is True for r in registros)}


def marcadores(registros):
    saida=[]
    for r in registros:
        if r['tipo_fluxo']=='valor_unico_publicado':
            valores=[('Valor único',r['fluxo_valor_unico_mm_s'])]
        elif r['tipo_fluxo']=='inicio_e_fim_publicados':
            valores=[('Início',r['fluxo_inicial_mm_s']),('Fim',r['fluxo_final_mm_s'])]
        else:
            raise ValueError('Tipo de fluxo desconhecido.')
        for etapa,valor in valores:
            saida.append({'registro_id':r['registro_id'],'etapa':etapa,
                          'fluxo_mm_s':float(valor),'oxigenio_vol_pct':float(r['oxigenio_vol_pct']),
                          'registro':r})
    return saida


def criar_figura(registros):
    import plotly.graph_objects as go
    pontos=marcadores(registros)
    cores=dict(zip(ROTULOS,['#0072B2','#E69F00','#009E73','#D55E00','#CC79A7','#56B4E9','#666666']))
    simbolos={'Valor único':'circle','Início':'square-open','Fim':'diamond-open'}
    fig=go.Figure()
    for observacao in ROTULOS:
        ps=[p for p in pontos if p['registro']['observacao_padronizada']==observacao]
        if not ps:continue
        detalhes=[]
        for p in ps:
            r=p['registro']
            detalhes.append([r['identificador_publicado'],r['investigacao_id'],p['etapa'],
                             r['largura_mm'],r['comentario_original'],
                             'Leitura possivelmente inexata (nota b)' if r['oxigenio_nota_b'] else 'Sem ressalva explícita nesta tabela',
                             'Relatada' if r['reutilizacao_relata'] is True else 'Não informada',
                             r['fonte']['linha_dados'],r['registro_id'],r['fluxo_original_cm_s']])
        fig.add_trace(go.Scatter(
            x=[p['oxigenio_vol_pct'] for p in ps],y=[p['fluxo_mm_s'] for p in ps],
            mode='markers',name=ROTULOS[observacao],customdata=detalhes,
            marker={'color':cores[observacao],'size':11,'symbol':[simbolos[p['etapa']] for p in ps]},
            hovertemplate=('Registro: %{customdata[0]} · %{customdata[1]}<br>'
                           'Fluxo representado: %{customdata[2]} · %{y} mm/s<br>'
                           'Fluxo original: %{customdata[9]} cm/s<br>'
                           'O₂ publicado: %{x} vol%<br>Largura: %{customdata[3]} mm<br>'
                           'Comentário: %{customdata[4]}<br>O₂: %{customdata[5]}<br>'
                           'Reutilização: %{customdata[6]}<br>'
                           'Tabela 7.1 · página física 104 · linha %{customdata[7]}<br>'
                           'ID: %{customdata[8]}<extra></extra>'),
        ))
    fig.update_layout(title='SIBAL — condições de fluxo e oxigênio publicadas',template='plotly_white',
                      xaxis_title='Oxigênio publicado (vol%)',yaxis_title='Velocidade de escoamento (mm/s)',
                      height=650,margin={'t':70,'b':70},legend={'title':{'text':'Observação publicada'}})
    fig.update_yaxes(rangemode='tozero')
    return fig
