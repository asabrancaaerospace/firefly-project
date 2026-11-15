"""Visualização exploratória específica da Tabela 5.1 do BASS-II."""
import json
from pathlib import Path
from decimal import Decimal
from src.ingestion.bass_tabela51 import estruturar, sha256, HASH_RELATORIO


def carregar_dados(base: Path):
    nasa = base / 'data' / 'nasa_oficial'
    pasta = nasa / 'processed' / 'bass_tabela51_v1'
    testes = json.loads((pasta/'testes.json').read_text(encoding='utf-8-sig'))
    condicoes = json.loads((pasta/'condicoes.json').read_text(encoding='utf-8-sig'))
    verificacao = json.loads((pasta/'verificacao.json').read_text(encoding='utf-8-sig'))
    candidato = nasa/'extracted'/'tabelas_candidatas_bass_v1.json'
    pdf = nasa/'raw'/'PSI-25'/'Report'/'BASS-II Summary Report.pdf'
    if sha256(pdf) != HASH_RELATORIO or verificacao['pdf_sha256'] != HASH_RELATORIO:
        raise ValueError('O PDF ou a referência do relatório foi alterado.')
    if sha256(candidato) != verificacao['json_entrada_sha256']:
        raise ValueError('O JSON candidato mudou após o processamento.')
    if verificacao.get('conferencia_celulas_com_pdf') is not True:
        raise ValueError('A conferência das células com o PDF não foi registrada.')
    dados = json.loads(candidato.read_text(encoding='utf-8-sig'))
    tabelas = [t for t in dados['tabelas'] if t['tabela']=='5.1']
    if len(tabelas)!=1:
        raise ValueError('Tabela 5.1 ausente ou repetida.')
    testes_esperados, condicoes_esperadas = estruturar(tabelas[0])
    if testes != testes_esperados or condicoes != condicoes_esperadas:
        raise ValueError('Dados processados divergem da transformação do candidato verificado.')
    return preparar_pontos(testes, condicoes)


def preparar_pontos(testes, condicoes):
    por_id = {t['teste_id']: t for t in testes}
    if len(por_id)!=len(testes):
        raise ValueError('Identificadores de teste repetidos.')
    vistos = set()
    pontos, ausentes = [], []
    for c in condicoes:
        if c['condicao_id'] in vistos:
            raise ValueError('Identificador de condição repetido.')
        vistos.add(c['condicao_id'])
        if c['teste_id'] not in por_id:
            raise ValueError('Condição sem teste correspondente.')
        t = por_id[c['teste_id']]
        if c['propagacao_mm_s'] is None:
            if c['status_propagacao']!='nao_rastreada':
                raise ValueError('Ausência de propagação sem status esperado.')
            ausentes.append({'condicao_id':c['condicao_id'], 'teste':t['identificador_publicado'],
                            'escoamento_mm_s':c['escoamento_mm_s'], 'motivo':'Not tracked'})
            continue
        if c['status_propagacao']!='valor_publicado':
            raise ValueError('Status inesperado para uma medida numérica.')
        x,y=Decimal(c['escoamento_mm_s']),Decimal(c['propagacao_mm_s'])
        if not x.is_finite() or not y.is_finite() or x<0 or y<0:
            raise ValueError('Velocidade inválida para este conjunto.')
        pontos.append({
            'condicao_id':c['condicao_id'], 'teste_id':c['teste_id'],
            'teste':t['identificador_publicado'],
            'escoamento_mm_s':float(x), 'propagacao_mm_s':float(y),
            'espessura_mm':t['espessura_mm'], 'largura_mm':t['largura_mm'],
            'faces':t['faces_em_queima'], 'o2_inicial':t['oxigenio_inicial_vol_pct'],
            'o2_final':t['oxigenio_final_vol_pct'], 'fonte':c['fonte'],
        })
    if (len(testes),len(condicoes),len(pontos),len(ausentes))!=(20,43,39,4):
        raise ValueError('Contagens inesperadas para a Tabela 5.1.')
    return pontos, ausentes


def criar_figura(pontos, incluir_notas=True):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    figura=make_subplots(rows=1,cols=2,shared_yaxes=True,
        subplot_titles=('Queima em uma face','Queima em duas faces'))
    cores={'1':'#0072B2','2':'#E69F00','3':'#009E73','4':'#CC79A7','5':'#D55E00'}
    simbolos={Decimal('12'):'circle',Decimal('22'):'diamond'}
    grupos=sorted({(p['espessura_mm'],p['largura_mm']) for p in pontos},
                  key=lambda g:(Decimal(g[0]),Decimal(g[1])))
    for espessura,largura in grupos:
        legenda_exibida=False
        for faces in (1,2):
            grupo=[p for p in pontos if (p['espessura_mm'],p['largura_mm'],p['faces'])==(espessura,largura,faces)]
            if not grupo:
                continue
            dados=[[p['condicao_id'],p['teste'],p['o2_inicial'],p['o2_final'],
                    p['fonte']['pagina_fisica'],p['fonte']['linha_dados']] for p in grupo]
            figura.add_trace(go.Scatter(
                x=[p['escoamento_mm_s'] for p in grupo],y=[p['propagacao_mm_s'] for p in grupo],
                mode='markers',name=f'{espessura} mm / {largura} mm',
                legendgroup=f'{espessura}_{largura}',showlegend=not legenda_exibida,
                marker={'color':cores[espessura],'symbol':simbolos[Decimal(largura)],'size':10,
                        'line':{'width':1,'color':'white'}},customdata=dados,
                hovertemplate=(
                    'Teste: %{customdata[1]}<br>Condição: %{customdata[0]}<br>'
                    'Escoamento: %{x} mm/s<br>Propagação: %{y} mm/s<br>'
                    f'Espessura: {espessura} mm<br>Largura: {largura} mm<br>'
                    'O₂ inicial do TESTE: %{customdata[2]} vol%<br>'
                    'O₂ final do TESTE: %{customdata[3]} vol%<br>'
                    'Tabela 5.1 · página física %{customdata[4]} · linha de dados %{customdata[5]}'
                    '<extra></extra>'),
            ),row=1,col=faces)
            legenda_exibida=True
    figura.update_xaxes(title_text='Escoamento (mm/s)',matches='x',rangemode='tozero')
    figura.update_yaxes(rangemode='tozero')
    figura.update_yaxes(title_text='Velocidade de propagação (mm/s)',row=1,col=1)
    figura.update_layout(
        title={'text':'BASS-II — propagação em placas de PMMA<br><sup>Tabela 5.1 · microgravidade · escoamento oposto · exploração dos dados publicados</sup>'},
        template='plotly_white',height=820 if incluir_notas else 620,
        margin={'t':110,'b':250 if incluir_notas else 70,'r':30,'l':70},
        legend={'title':{'text':'Espessura / largura'}},
        annotations=list(figura.layout.annotations)+[{
            'text':('Fonte: NASA/TM-20210011385, tabela 5.1, página física 65 / impressa 57.'
                    f'<br>{len(pontos)} condições numéricas de {len({p["teste_id"] for p in pontos})} testes no gráfico.'
                    '<br>Condições de um mesmo teste não são réplicas independentes. O₂ varia entre e durante testes.'
                    '<br>Sem ajuste de curvas ou barras de erro; a tabela não fornece incertezas individuais.'),
            'xref':'paper','yref':'paper','x':0,'y':-0.30,'showarrow':False,'align':'left','xanchor':'left',
        }],
    )
    if not incluir_notas:
        figura.layout.annotations = tuple(figura.layout.annotations[:2])
    return figura


def executar(base: Path):
    pontos,ausentes=carregar_dados(base)
    figura=criar_figura(pontos)
    pasta=base/'data'/'nasa_oficial'/'reports'/'bass_tabela51_grafico_v1'
    if pasta.exists():
        raise FileExistsError(f'Saída já existe; nada será sobrescrito: {pasta}')
    # HTML autossuficiente: os dados e o JavaScript ficam no próprio arquivo.
    html=figura.to_html(full_html=True,include_plotlyjs=True,config={'displaylogo':False})
    pasta.mkdir(parents=True,exist_ok=False)
    with (pasta/'grafico.html').open('x',encoding='utf-8') as f:
        f.write(html)
    with (pasta/'condicoes_nao_plotadas.json').open('x',encoding='utf-8') as f:
        json.dump(ausentes,f,ensure_ascii=False,indent=2)
        f.write('\n')
    print('Entradas numéricas no gráfico:',len(pontos))
    print('Condições sem rastreamento, não plotadas:',len(ausentes))
    for c in ausentes:
        print(c['condicao_id'], '—', c['motivo'])
    print('Gráfico:',pasta/'grafico.html')
