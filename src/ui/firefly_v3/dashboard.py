"""Firefly: apresentação bilíngue sobre os processadores existentes."""
import hashlib
import html
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from src.ui.firefly_v3.charts import pmma as figura_pmma, sibal as figura_sibal, estilo, NAVY, ORANGE

CATEGORIAS={
 'metodo_medicao':('Measurement method','Método de medição'),
 'metodos_e_condicoes':('Methods and conditions','Métodos e condições'),
 'resultado_experimental_publicado':('Published experimental result','Resultado experimental publicado'),
 'resultado_experimental_e_interpretacao':('Experimental result and interpretation','Resultado experimental e interpretação'),
 'resultados_computacionais':('Computational results','Resultados computacionais'),
 'modelagem':('Modelling','Modelagem'),
 'comparacao_entre_estudos':('Comparison across studies','Comparação entre estudos'),
 'ressalva_metodologica':('Methodological caveat','Ressalva metodológica'),
 'contexto_secundario_historico':('Historical context','Contexto histórico'),
 'organizacao_e_configuracao_descrita':('Data organisation and configuration','Organização de dados e configuração'),
 'legendas_e_observacoes_experimentais':('Captions and experimental observations','Legendas e observações experimentais')}
OBS={
 'extincao_quenching_relatada':('Quenching reported','Extinção relatada (quenching)'),
 'ausencia_de_blowoff_relatada':('No blowoff reported','Ausência de blowoff relatada'),
 'ausencia_de_ignicao_relatada':('No ignition reported','Ausência de ignição relatada'),
 'extincao_blowoff_relatada':('Blowoff reported','Extinção relatada (blowoff)'),
 'chama_em_uma_face_relatada':('One-sided flame reported','Chama em uma face relatada'),
 'ignicao_relatada':('Ignition reported','Ignição relatada'),
 'nao_informada_nesta_coluna':('Not specified in comments','Não informada nos comentários')}
PDF='https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf'


def t(en,pt):
    return en if st.session_state.get('firefly_language','en')=='en' else pt


def rotulo(chave, mapa=CATEGORIAS):
    return t(*mapa.get(chave,('Other evidence category','Outra categoria de evidência')))


def cobertura(base):
    pasta=Path(base)/'data/nasa_oficial/processed'
    bruto=(pasta/'recortes_saffire_v1/recortes.json').read_bytes()
    ver=json.loads((pasta/'chunks_saffire_v2/verificacao.json').read_text(encoding='utf-8-sig'))
    if hashlib.sha256(bruto).hexdigest().upper()!=ver['sha256_recortes_json'].upper():
        raise ValueError('Document excerpts do not match the chunk manifest.')
    rs=json.loads(bruto.decode('utf-8-sig'))['recortes']
    fontes={f['documento_id']:f for r in rs for f in r['fontes']}
    return rs,fontes


def carregar_pmma(base):
    from src.analysis.bass_explorador import carregar_acervo
    return carregar_acervo(base)


def carregar_sibal(base):
    from src.analysis.sibal_explorador import carregar
    return carregar(base)


@st.cache_resource(max_entries=1,show_spinner=False)
def servico(base):
    from src.retrieval.servico_documental_mvp import ServicoDocumental
    return ServicoDocumental(base)


def erro(exc):
    st.error(t('This section could not load its local data.','Esta seção não conseguiu carregar os dados locais.'))
    with st.expander(t('Technical details','Detalhes técnicos')): st.code(f'{type(exc).__name__}: {exc}')


def ir(pagina): st.session_state['firefly_page']=pagina


def cabecalho(titulo,descricao):
    st.title(titulo)
    st.caption(descricao)


def nota_pmma():
    return t('Conditions from the same test are not independent replicates. Initial/final oxygen describes the whole test. Missing spread values are not zero. No fitted curves or individual error bars.',
             'Condições do mesmo teste não são réplicas independentes. O oxigênio inicial/final descreve o teste inteiro. Propagação ausente não é zero. Sem curvas ajustadas ou barras de erro individuais.')


def overview(base):
    cabecalho(t('Combustion evidence, in view','Evidências de combustão em perspectiva'),
              t('Explore published experiments, inspect their conditions and trace findings to the source.','Explore experimentos publicados, examine suas condições e confira os achados nas fontes.'))
    p=s=None; rs=[]; fontes={}
    try: p,_=carregar_pmma(base)
    except Exception as exc: erro(exc)
    try: s=carregar_sibal(base)
    except Exception as exc: erro(exc)
    try: rs,fontes=cobertura(base)
    except Exception as exc: erro(exc)
    numeros=[(t('PMMA tests','Testes de PMMA'),len({r['teste_id'] for r in p}) if p is not None else None),
             (t('PMMA conditions','Condições de PMMA'),len(p) if p is not None else None),
             (t('SIBAL records','Registros SIBAL'),len(s) if s is not None else None),
             (t('Documents in search corpus','Documentos no acervo de busca'),len(fontes) if fontes else None)]
    for col,(label,value) in zip(st.columns(4),numeros): col.metric(label,'—' if value is None else value)
    st.caption(t('These counts describe different units; they must not be added as a total number of experiments.','As contagens representam unidades diferentes; não devem ser somadas como total de experimentos.'))
    a,b=st.columns([1.15,1])
    with a:
        st.subheader(t('Experimental data coverage','Cobertura dos dados experimentais'))
        if p is not None and s is not None:
            import plotly.graph_objects as go
            vals=[sum(r['propagacao_mm_s'] is not None for r in p),sum(r['propagacao_mm_s'] is None for r in p),sum(r['investigacao_id']=='PSI-25' for r in s),sum(r['investigacao_id']=='PSI-26' for r in s)]
            labels=[t('PMMA · numeric spread','PMMA · propagação numérica'),t('PMMA · not tracked','PMMA · não rastreada'),'SIBAL · BASS-II','SIBAL · BASS']
            fig=go.Figure(go.Bar(x=vals,y=labels,orientation='h',marker_color=[NAVY,ORANGE,NAVY,ORANGE],text=vals,textposition='outside',hovertemplate='%{y}: %{x}<extra></extra>'))
            estilo(fig,290);fig.update_layout(showlegend=False,margin=dict(l=180,r=35,t=10,b=40));fig.update_xaxes(title_text=t('Conditions / records','Condições / registros'),range=[0,max(vals)*1.2 if max(vals) else 1]);fig.update_yaxes(autorange='reversed')
            st.plotly_chart(fig,width='stretch')
    with b:
        st.subheader(t('What you can investigate','O que você pode investigar'))
        st.markdown(t('**PMMA · opposed flow**  \nThickness, width, burning faces and measured flame spread.\n\n**SIBAL · concurrent flow**  \nPublished airflow and oxygen conditions, observations and reuse caveats.\n\n**Saffire + combustion guide**  \nSearch selected documentary evidence in English or Portuguese.',
                         '**PMMA · escoamento oposto**  \nEspessura, largura, faces em queima e propagação medida.\n\n**SIBAL · escoamento concorrente**  \nCondições publicadas de fluxo e oxigênio, observações e ressalvas de reutilização.\n\n**Saffire + guia de combustão**  \nBusque evidências documentais selecionadas em inglês ou português.'))
    st.caption(t('Also available: Conditions & scenarios for side-by-side comparison and oxygen partial-pressure calculations; Sources & methodology for references and limitations.', 'Também disponível: Condições e cenários para comparação lado a lado e cálculo de pressão parcial de oxigênio; Fontes e metodologia para referências e limites.'))
    st.button(t('Explore investigation profiles','Explorar fichas de investigação'),key='go_investigations',on_click=ir,args=('investigations',))
    st.button(t('Inspect evidence coverage','Inspecionar cobertura das evidências'),key='go_coverage',on_click=ir,args=('coverage',))
    st.divider()
    for col,key,title,desc in zip(st.columns(3),['pmma','sibal','search'],
            [t('Explore PMMA','Explorar PMMA'),t('Explore SIBAL','Explorar SIBAL'),t('Search documents','Buscar documentos')],
            [t('Compare published conditions within the table.','Compare condições publicadas dentro da tabela.'),t('Inspect observations without assigning safety ratings.','Examine observações sem atribuir notas de segurança.'),t('Read the evidence and locate the original page.','Leia a evidência e localize a página original.')]):
        with col:
            st.markdown('**'+title+'**');st.write(desc)
            st.button(title,key='go_'+key,on_click=ir,args=(key,),width='stretch')
    st.caption(t('Selected-source MVP. No certified safety limits or automatic LLM synthesis. The search corpus is not the full NASA repository.',
                 'MVP com fontes selecionadas. Sem limites certificados de segurança ou síntese automática por LLM. O acervo de busca não representa todo o repositório NASA.'))


def experimental(base,modo):
    en=st.session_state.firefly_language=='en'
    pm=modo=='pmma'
    cabecalho('PMMA' if pm else 'SIBAL',t('BASS-II · opposed-flow flame spread · Table 5.1','BASS-II · propagação em escoamento oposto · Tabela 5.1') if pm else t('BASS / BASS-II · cotton–fiberglass fabric · Table 7.1','BASS / BASS-II · tecido de algodão e fibra de vidro · Tabela 7.1'))
    try:
        if pm: registros,testes=carregar_pmma(base)
        else: registros=carregar_sibal(base)
    except Exception as exc: erro(exc);return
    with st.expander(t('Filter published conditions','Filtrar condições publicadas'),expanded=False):
        a,b,c=st.columns(3)
        larg=sorted({r['largura_mm'] for r in registros},key=float)
        with a: widths=st.multiselect(t('Width (mm)','Largura (mm)'),larg,default=larg,key=modo+'_width')
        if pm:
            esp=sorted({r['espessura_mm'] for r in registros},key=float)
            faces=sorted({r['faces'] for r in registros})
            with b: thickness=st.multiselect(t('Thickness (mm)','Espessura (mm)'),esp,default=esp,key='ff_thickness')
            with c: sides=st.multiselect(t('Burning faces','Faces em queima'),faces,default=faces,key='ff_faces')
            nomes=sorted({r['teste'] for r in registros},key=lambda s:int(s[1:]))
            ts=st.multiselect(t('Tests','Testes'),nomes,default=nomes,key='ff_tests')
            states=st.multiselect(t('Spread availability','Disponibilidade da propagação'),['valor_publicado','nao_rastreada'],default=['valor_publicado','nao_rastreada'],format_func=lambda x:t('Published value','Valor publicado') if x=='valor_publicado' else t('Not tracked','Não rastreada'),key='ff_status')
            sel=[r for r in registros if r['largura_mm'] in widths and r['espessura_mm'] in thickness and r['faces'] in sides and r['teste'] in ts and r['status'] in states]
        else:
            inv=sorted({r['investigacao_id'] for r in registros}); obs=sorted({r['observacao_padronizada'] for r in registros})
            with b: invs=st.multiselect(t('Investigation','Investigação'),inv,default=inv,key='ff_inv')
            with c: obss=st.multiselect(t('Observation','Observação'),obs,default=obs,format_func=lambda x:rotulo(x,OBS),key='ff_obs')
            a,b=st.columns(2)
            with a: quality=st.multiselect(t('Oxygen caveat','Ressalva de oxigênio'),[True,False],default=[True,False],format_func=lambda v:t('Note b','Nota b') if v else t('No explicit caveat','Sem ressalva explícita'),key='ff_quality')
            with b: reuse=st.multiselect(t('Sample reuse','Reutilização da amostra'),['reported','unknown'],default=['reported','unknown'],format_func=lambda v:t('Reported','Relatada') if v=='reported' else t('Not specified','Não informada'),key='ff_reuse')
            sel=[r for r in registros if r['largura_mm'] in widths and r['investigacao_id'] in invs and r['observacao_padronizada'] in obss and r['oxigenio_nota_b'] in quality and ('reported' if r['reutilizacao_relata'] is True else 'unknown') in reuse]
        st.caption(t('Empty selections return no records.','Seleções vazias retornam zero registros.'))
    if not sel: st.info(t('No records match these filters.','Nenhum registro corresponde aos filtros.'));return
    if pm:
        valores=[len({r['teste_id'] for r in sel}),len(sel),sum(r['propagacao_mm_s'] is not None for r in sel),sum(r['propagacao_mm_s'] is None for r in sel)]
        labels=[t('Tests','Testes'),t('Conditions','Condições'),t('Numeric spread','Propagação numérica'),t('Not tracked','Não rastreadas')]
    else:
        valores=[len(sel),sum(r['investigacao_id']=='PSI-25' for r in sel),sum(r['oxigenio_nota_b'] for r in sel),sum(r['reutilizacao_relata'] is True for r in sel)]
        labels=[t('Records','Registros'),'BASS-II',t('Oxygen caveats','Ressalvas de oxigênio'),t('Reuse reported','Reutilizações relatadas')]
    for col,label,v in zip(st.columns(4),labels,valores):col.metric(label,v)
    st.plotly_chart(figura_pmma(sel,en) if pm else figura_sibal(sel,en),width='stretch')
    st.caption(nota_pmma() if pm else t('Circles: single values. Open squares/diamonds: start/end of the same record, not separate tests. Points may overlap. No spread rates are published in Table 7.1.',
        'Círculos: valores únicos. Quadrados/losangos abertos: início/fim do mesmo registro, não novos testes. Pontos podem se sobrepor. A Tabela 7.1 não publica velocidades de propagação.'))
    if not pm and any(r['oxigenio_nota_b'] for r in sel): st.warning(t('Selected oxygen readings include the possible inaccuracy identified in note b.','A seleção inclui leituras de oxigênio com possível inexatidão indicada na nota b.'))
    if not pm: st.caption(t('Reuse not specified does not mean a new sample. Reused samples are not automatically independent replicates.','Reutilização não informada não significa amostra nova. Amostras reutilizadas não são automaticamente réplicas independentes.'))
    linhas=[]
    for r in sel:
        linha={t('Record','Registro'):r['condicao_id'] if pm else r['registro_id'],t('Width (mm)','Largura (mm)'):float(r['largura_mm'])}
        if pm:
            linha.update({t('Test','Teste'):r['teste'],t('Thickness (mm)','Espessura (mm)'):float(r['espessura_mm']),t('Burning faces','Faces em queima'):r['faces'],t('Airflow (mm/s)','Escoamento (mm/s)'):r['escoamento_mm_s'],t('Spread (mm/s)','Propagação (mm/s)'):r['propagacao_mm_s'],t('Initial O₂ — whole test (vol%)','O₂ inicial — teste inteiro (vol%)'):float(r['o2_inicial']),t('Final O₂ — whole test (vol%)','O₂ final — teste inteiro (vol%)'):float(r['o2_final'])})
        else:
            linha.update({t('Investigation','Investigação'):r['investigacao_id'],'O₂ (vol%)':float(r['oxigenio_vol_pct']),t('Original airflow (cm/s)','Fluxo original (cm/s)'):r['fluxo_original_cm_s'],t('Original comment','Comentário original'):r['comentario_original'],t('O₂ caveat','Ressalva O₂'):t('Note b','Nota b') if r['oxigenio_nota_b'] else t('Not explicit','Não explícita'),t('Reuse','Reutilização'):t('Reported','Relatada') if r['reutilizacao_relata'] is True else t('Not specified','Não informada')})
        linhas.append(linha)
    st.subheader(t('Selected records','Registros selecionados'));st.dataframe(pd.DataFrame(linhas),hide_index=True,width='stretch')
    from .additions import pacote_exportacao
    pacote=pacote_exportacao(sel,'PMMA_Table_5.1' if pm else 'SIBAL_Table_7.1',st.session_state.firefly_language)
    a,b=st.columns(2)
    with a:st.download_button(t('Download filtered table (CSV)','Baixar tabela filtrada (CSV)'),pd.DataFrame(linhas).to_csv(index=False).encode('utf-8-sig'),file_name='firefly_'+modo+'_filtered.csv',mime='text/csv',key=modo+'_csv')
    with b:st.download_button(t('Download records + sources (JSON)','Baixar registros + fontes (JSON)'),json.dumps(pacote,ensure_ascii=False,indent=2),file_name='firefly_'+modo+'_sources.json',mime='application/json',key=modo+'_json')
    st.caption(t('CSV contains the displayed columns. JSON retains the record fields and source locations; neither file is an original NASA document.',
                 'O CSV contém as colunas exibidas. O JSON preserva campos dos registros e referências; nenhum dos arquivos é um documento original da NASA.'))
    if pm: st.caption(t('Blank spread cells mean not tracked, not zero.','Propagação em branco significa não rastreada, não zero.'))
    st.subheader(t('Inspect a source row','Inspecionar uma linha da fonte'))
    por_id={r['condicao_id'] if pm else r['registro_id']:r for r in sel}
    ident=st.selectbox(t('Record ID','ID do registro'),list(por_id),key=modo+'_source');r=por_id[ident]
    original=testes[r['teste_id']] if pm else r
    pagina=65 if pm else 104;impressa=57 if pm else 96
    st.markdown(f'[{t("Open NASA report","Abrir relatório NASA")} · {t("physical page","página física")} {pagina}]({PDF}#page={pagina})')
    st.caption(f'{t("Printed page","Página impressa")}: {impressa} · {t("data row","linha de dados")}: {r["fonte"]["linha_dados"]}')
    with st.expander(t('Original cells and traceability','Células originais e rastreabilidade')):
        cols=([t('Test','Teste'),t('Thickness (mm)','Espessura (mm)'),t('Width (cm)','Largura (cm)'),t('Faces','Faces'),t('Airflow (cm/s)','Escoamento (cm/s)'),t('Spread (mm/s)','Propagação (mm/s)'),t('Duration (min)','Duração (min)'),t('Initial O₂ (vol%)','O₂ inicial (vol%)'),t('Final O₂ (vol%)','O₂ final (vol%)')] if pm else [t('Record','Registro'),t('Width (cm)','Largura (cm)'),t('Airflow (cm/s)','Escoamento (cm/s)'),'O₂ (vol%)',t('Comments','Comentários')])
        st.table(pd.DataFrame({t('Field','Campo'):cols,t('Published value','Valor publicado'):original['celulas_originais']}))
        st.json(original['fonte'])
        st.caption(t('Source values and comments retain their original language.','Valores e comentários da fonte preservam seu idioma original.'))


def busca(base):
    cabecalho(t('Find the evidence','Encontre a evidência'),t('English and Portuguese queries · original source excerpts','Perguntas em inglês e português · trechos originais das fontes'))
    st.caption(t('Selected Saffire documents and combustion guide. Results are candidates, not validated answers; check the mission and conditions.','Documentos Saffire selecionados e guia de combustão. Os resultados são candidatos, não respostas validadas; confira missão e condições.'))
    with st.form('ff_search_form'):
        pergunta=st.text_area(t('Research question','Pergunta de pesquisa'),max_chars=2000,key='ff_question',placeholder=t('What airflow speed was reported for Saffire-III?','Qual velocidade de escoamento foi relatada para Saffire-III?'))
        enviar=st.form_submit_button(t('Search evidence','Buscar evidências'),type='primary')
    if enviar:
        st.session_state.pop('ff_result',None)
        try:
            if not pergunta.strip():raise ValueError(t('Enter a question.','Digite uma pergunta.'))
            with st.spinner(t('Searching local sources…','Buscando fontes locais…')): st.session_state.ff_result=servico(str(base)).consultar(pergunta)
        except Exception as exc:erro(exc)
    result=st.session_state.get('ff_result')
    if not result:return
    st.subheader(t('Retrieved evidence','Evidências recuperadas'))
    st.write(result['pergunta']);st.caption(f'{len(result["resultados"])} '+t('excerpts','trechos')+f' · {result["tempo_busca_s"]} s')
    st.caption(t('Submit again after editing the question. Source text is not automatically translated.','Envie novamente após editar a pergunta. O texto da fonte não é traduzido automaticamente.'))
    for r in result['resultados']:
        f=r['fontes'][0];title=f.get('titulo_documento',f.get('apelido_documento',f['documento_id']))
        with st.container(border=True):
            st.markdown(f'**{r["posicao"]}. {title}**')
            st.caption(rotulo(r['tipo_evidencia'])+' · '+t('Physical page ','Página física ')+str(f['pagina_fisica']))
            if r['posicao']==1:
                st.markdown('<div class="source-excerpt">'+html.escape(r['texto'])+'</div>',unsafe_allow_html=True)
            else:
                with st.expander(t('Read excerpt','Ler trecho')):
                    st.markdown('<div class="source-excerpt">'+html.escape(r['texto'])+'</div>',unsafe_allow_html=True)
            with st.expander(t('Source details and traceability','Detalhes da fonte e rastreabilidade')):
                for fonte in r['fontes']:
                    st.write(fonte.get('titulo_documento',fonte.get('apelido_documento',fonte['documento_id'])))
                    st.caption(t('Physical page: ','Página física: ')+str(fonte['pagina_fisica'])+' · '+t('Printed page: ','Página impressa: ')+str(fonte.get('pagina_impressa','—')))
                    st.code(fonte['documento_id'])
                    if fonte.get('sha256_pdf'):st.code('SHA-256: '+fonte['sha256_pdf'])
                st.code(r['recorte_id'])
                if r.get('nota_editorial'):st.write(r['nota_editorial']);st.caption(t('Original editorial note.','Nota editorial original.'))
    st.download_button(t('Download evidence report','Baixar relatório de evidências'),json.dumps(result,ensure_ascii=False,indent=2),file_name='firefly_evidence.json',mime='application/json')
    with st.expander(t('How results are ordered','Como os resultados são ordenados')):
        st.write(t('Dense semantic retrieval and lexical BM25 rankings are fused by reciprocal rank. Method questions may also use editorial evidence categories. This orders excerpts, not investigations by safety or risk. No LLM generates an answer.',
                   'As ordenações semântica e lexical BM25 são combinadas pela posição recíproca. Perguntas metodológicas também podem usar categorias editoriais de evidência. Isso ordena trechos, não investigações por segurança ou risco. Nenhum LLM gera respostas.'))
        if st.button(t('Reload search resources','Recarregar recursos de busca'),key='ff_reload'):
            servico.clear();st.session_state.pop('ff_result',None);st.rerun()


def metodologia(base):
    cabecalho(t('Sources & methodology','Fontes e metodologia'),t('Published evidence, explicit boundaries','Evidências publicadas, limites explícitos'))
    st.markdown(f'**NASA/TM-20210011385** · [NTRS](https://ntrs.nasa.gov/citations/20210011385)')
    st.write(t('PMMA: Table 5.1, physical page 65 / printed page 57. SIBAL: Table 7.1, physical page 104 / printed page 96.','PMMA: Tabela 5.1, página física 65 / impressa 57. SIBAL: Tabela 7.1, página física 104 / impressa 96.'))
    st.write(t('Airflow and width were converted from cm-based units to mm-based units by multiplying by ten. PMMA flame spread was already published in mm/s. Original cells remain available in each explorer.',
               'Fluxo e largura foram convertidos de unidades em cm para unidades em mm multiplicando por dez. A propagação de PMMA já foi publicada em mm/s. As células originais permanecem disponíveis em cada explorador.'))
    st.write(nota_pmma())
    st.write(t('SIBAL start/end values are endpoints within a record, not interpolated time series. Reuse and oxygen caveats must be retained. Neither “no blowoff” nor a blank comment establishes safety.',
               'Valores inicial/final de SIBAL são extremos de um registro, não séries temporais interpoladas. Ressalvas de reutilização e oxigênio são preservadas. “No blowoff” e comentários em branco não estabelecem segurança.'))
    try:
        rs,fontes=cobertura(base)
        st.subheader(t('Documentary search corpus','Acervo da busca documental'))
        for f in fontes.values():
            st.write(f.get('titulo_documento',f.get('apelido_documento',f['documento_id'])))
            with st.expander(t('Document identifier','Identificação documental')+' · '+f.get('apelido_documento',f['documento_id'][:16])):st.code(f['documento_id']);st.code(f.get('sha256_pdf',''))
        st.caption(str(len(rs))+t(' selected excerpts. Coverage is not the full NASA repository.',' recortes selecionados. A cobertura não representa todo o repositório NASA.'))
    except Exception as exc:erro(exc)
    st.subheader(t('Interpretation boundaries','Limites de interpretação'))
    st.write(t('Different materials, geometries, flow directions and oxygen conditions are not interchangeable. These data do not establish universal safe limits or validated lunar/Martian predictions. Automatic LLM synthesis, simulations and predictive models are not enabled in this MVP.',
               'Materiais, geometrias, direções de escoamento e condições de oxigênio diferentes não são intercambiáveis. Estes dados não estabelecem limites universais de segurança nem previsões lunares/marcianas validadas. Síntese automática por LLM, simulações e modelos preditivos não estão habilitados neste MVP.'))


def executar(base):
    st.set_page_config(page_title='Firefly | Firefly Project',layout='wide')
    from .brand import COLORS, contrast_text
    st.markdown('''<style>
    html, body, [data-testid="stApp"] {font-family:"Segoe UI",Arial,sans-serif;}
    h1,h2,h3 {color:#142D4E;letter-spacing:-0.025em;}
    h1 {font-size:2.2rem !important;} h2 {font-size:1.35rem !important;}
    [data-testid="stMetric"] {border-top:3px solid #B94E00;padding:12px 0;}
    [data-testid="stSidebar"] {border-right:1px solid #E3E8EF;}
    .block-container {padding-top:2.2rem;max-width:1440px;}
    button {border-radius:5px !important;}
    [data-testid="stCaptionContainer"] {color:#4B607A;}
    [data-testid="stMarkdownContainer"] a {color:#142D4E;text-decoration:underline;}
    [data-testid="stMarkdownContainer"] a:hover {color:#B94E00;}
    [data-testid="stAlert"] {background-color:#F3F5F8;border-left:3px solid #B94E00;}
    [data-testid="stAlert"] p {color:#142D4E;}
    .source-excerpt {white-space:pre-wrap;line-height:1.65;font-family:"Segoe UI",Arial,sans-serif;}
    </style>'''.replace('#B94E00',COLORS['orange']),unsafe_allow_html=True)
    st.markdown(f'''<style>[data-testid="stBaseButton-primary"] {{background-color:{COLORS['blue']};color:{contrast_text(COLORS['blue'])};border-color:{COLORS['blue']};}} [data-testid="stMarkdownContainer"] a {{color:{COLORS['blue']};}}</style>''',unsafe_allow_html=True)
    with st.sidebar:
        logo=next((Path(base)/'assets'/('firefly_logo'+ext) for ext in ('.png','.svg','.jpg','.jpeg') if (Path(base)/'assets'/('firefly_logo'+ext)).is_file()),None)
        if logo is not None:st.logo(str(logo),size='large')
        else:st.markdown('## Firefly')
        st.caption('Firefly Project')
        st.selectbox('Language / Idioma',['en','pt-BR'],format_func=lambda v:'English' if v=='en' else 'Português',key='firefly_language')
        nomes={'overview':t('Overview','Visão geral'),'investigations':t('Investigations','Investigações'),'pmma':'PMMA','sibal':'SIBAL','search':t('Evidence search','Busca de evidências'),'coverage':t('Evidence coverage','Cobertura das evidências'),'scenarios':t('Conditions & scenarios','Condições e cenários'),'sources':t('Sources & methodology','Fontes e metodologia')}
        page=st.radio(t('Workspace','Área de trabalho'),list(nomes),format_func=nomes.get,key='firefly_page')
        st.divider();st.caption(t('Microgravity combustion\n\nScientific exploration · Local MVP','Combustão em microgravidade\n\nExploração científica · MVP local'))
    if page=='investigations':
        from .investigations import executar as mostrar_investigacoes
        mostrar_investigacoes(base)
    elif page=='coverage':
        from .additions import mostrar_cobertura
        mostrar_cobertura(base)
    elif page=='overview':overview(base)
    elif page in ('pmma','sibal'):experimental(base,page)
    elif page=='search':busca(base)
    elif page=='scenarios':
        from src.ui.firefly_v3.scenarios import executar as mostrar_cenarios
        mostrar_cenarios(base)
    else:metodologia(base)
