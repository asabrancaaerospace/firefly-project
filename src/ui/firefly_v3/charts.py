"""Figuras de apresentação; não alteram dados nem ajustam modelos."""
from .brand import COLORS
NAVY = COLORS['blue']
ORANGE = COLORS['orange']


def estilo(fig, altura=430):
    fig.update_layout(template='plotly_white', height=altura,
                      font=dict(family='Segoe UI, Arial, sans-serif', color=COLORS['text'], size=13),
                      paper_bgcolor='white', plot_bgcolor='white',
                      margin=dict(t=35,b=65,l=65,r=20),
                      legend=dict(orientation='h',y=-0.23,x=0), hoverlabel=dict(bgcolor='white'))
    fig.update_xaxes(gridcolor='#E7EBF0',zeroline=False)
    fig.update_yaxes(gridcolor='#E7EBF0',zeroline=False)
    return fig


def pmma(registros, en=True):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1,cols=2, shared_yaxes=True,
                        subplot_titles=['One burning face','Two burning faces'] if en else ['Queima em uma face','Queima em duas faces'])
    geometrias=sorted({(r['espessura_mm'],r['largura_mm']) for r in registros if r['propagacao_mm_s'] is not None},key=lambda p:(float(p[0]),float(p[1])))
    symbols=['circle','square','diamond','triangle-up','triangle-down','cross','x','star','hexagon','pentagon']
    for i,(esp,larg) in enumerate(geometrias):
        for face in [1,2]:
            rs=[r for r in registros if int(r['faces'])==face and (r['espessura_mm'],r['largura_mm'])==(esp,larg) and r['propagacao_mm_s'] is not None]
            if not rs:continue
            fig.add_trace(go.Scatter(x=[float(r['escoamento_mm_s']) for r in rs],y=[float(r['propagacao_mm_s']) for r in rs],mode='markers',
                name=f'{esp} / {larg} mm',legendgroup=str(i),showlegend=(face==1 or not any(int(r['faces'])==1 and (r['espessura_mm'],r['largura_mm'])==(esp,larg) and r['propagacao_mm_s'] is not None for r in registros)),
                marker=dict(color=NAVY if i%2==0 else ORANGE,symbol=symbols[i%len(symbols)],size=10),
                customdata=[[r['condicao_id'],r['teste'],str(r['o2_inicial']),str(r['o2_final'])] for r in rs],
                hovertemplate=('ID: %{customdata[0]}<br>'+('Test' if en else 'Teste')+': %{customdata[1]}<br>'+('Airflow' if en else 'Escoamento')+': %{x} mm/s<br>'+('Spread' if en else 'Propagação')+': %{y} mm/s<br>O₂ '+('initial / final (whole test)' if en else 'inicial / final (teste inteiro)')+': %{customdata[2]} / %{customdata[3]} vol%<extra></extra>')),row=1,col=face)
    fig.update_xaxes(title_text='Airflow (mm/s)' if en else 'Escoamento (mm/s)')
    fig.update_yaxes(title_text='Flame spread (mm/s)' if en else 'Propagação (mm/s)',row=1,col=1)
    estilo(fig,520)
    fig.update_layout(legend_title_text='Thickness / width' if en else 'Espessura / largura')
    return fig


def sibal(registros,en=True):
    import plotly.graph_objects as go
    fig=go.Figure()
    for inv in ['PSI-25','PSI-26']:
        for etapa, campo, symbol in [('single','fluxo_valor_unico_mm_s','circle'),('start','fluxo_inicial_mm_s','square-open'),('end','fluxo_final_mm_s','diamond-open')]:
            rs=[r for r in registros if r['investigacao_id']==inv and r.get(campo) is not None]
            if not rs:continue
            label=({'single':'Single value','start':'Start','end':'End'} if en else {'single':'Valor único','start':'Início','end':'Fim'})[etapa]
            fig.add_trace(go.Scatter(x=[float(r['oxigenio_vol_pct']) for r in rs],y=[float(r[campo]) for r in rs],mode='markers',name=f'{inv} · {label}',marker=dict(color=NAVY if inv=='PSI-25' else ORANGE,size=10,symbol=symbol),
                customdata=[[r['identificador_publicado'],str(r['largura_mm']),r['comentario_original'],('Note b' if en else 'Nota b') if r['oxigenio_nota_b'] else ('No explicit caveat' if en else 'Sem ressalva explícita')] for r in rs],
                hovertemplate='ID: %{customdata[0]}<br>O₂: %{x} vol%<br>'+('Airflow' if en else 'Escoamento')+': %{y} mm/s<br>'+('Width' if en else 'Largura')+': %{customdata[1]} mm<br>%{customdata[2]}<br>%{customdata[3]}<extra></extra>'))
    fig.update_layout(xaxis_title='Oxygen (vol%)' if en else 'Oxigênio (vol%)',yaxis_title='Airflow (mm/s)' if en else 'Escoamento (mm/s)')
    return estilo(fig,500)
