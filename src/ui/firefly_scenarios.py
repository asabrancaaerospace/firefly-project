"""Cálculo exploratório e comparação descritiva; sem previsão de inflamabilidade."""
import math


def partial_pressure(oxygen_percent, total_kpa):
    oxygen_percent, total_kpa = float(oxygen_percent), float(total_kpa)
    if not math.isfinite(oxygen_percent) or not 0 <= oxygen_percent <= 100:
        raise ValueError('Oxygen must be between 0 and 100%.')
    if not math.isfinite(total_kpa) or total_kpa <= 0:
        raise ValueError('Pressure must be positive and finite.')
    return oxygen_percent / 100 * total_kpa


def executar(base):
    import pandas as pd
    import streamlit as st
    from src.ui.firefly import t, cabecalho, carregar_pmma, carregar_sibal, erro, PDF
    cabecalho(t('Conditions & scenarios','Condições e cenários'),
              t('Compare published conditions. Calculate an atmospheric scenario without predicting fire behaviour.',
                'Compare condições publicadas. Calcule um cenário atmosférico sem prever o comportamento do fogo.'))
    comparar,cenario=st.tabs([t('Compare conditions','Comparar condições'),t('Oxygen calculator','Calculadora de oxigênio')])
    with cenario:
        st.write(t('User-defined scenario, not an experimental measurement.','Cenário definido pelo usuário, não uma medição experimental.'))
        a,b=st.columns(2)
        with a: oxygen=st.number_input(t('O₂ mole fraction (%)','Fração molar de O₂ (%)'),min_value=0.0,max_value=100.0,value=21.0,step=0.1,key='scenario_o2')
        with b: pressure=st.number_input(t('Total pressure (kPa)','Pressão total (kPa)'),min_value=0.01,value=101.325,step=1.0,format='%.3f',key='scenario_pressure')
        st.metric(t('Calculated O₂ partial pressure','Pressão parcial de O₂ calculada'),f'{partial_pressure(oxygen,pressure):.3f} kPa')
        st.latex(r'p_{O_2}=y_{O_2}\,P_{\mathrm{total}}')
        st.caption(t('Ideal gas mixture approximation. Divide the percentage by 100 to obtain the mole fraction.','Aproximação de mistura de gases ideais. Divida a porcentagem por 100 para obter a fração molar.'))
        st.warning(t('Equal oxygen partial pressures do not establish equal flammability. Oxygen fraction, total pressure, material, flow and gravity still matter. No safe/unsafe classification is calculated.',
                     'Pressões parciais de oxigênio iguais não estabelecem inflamabilidades iguais. Fração de oxigênio, pressão total, material, fluxo e gravidade continuam relevantes. Nenhuma classificação seguro/inseguro é calculada.'))
    with comparar:
        try: ps,_=carregar_pmma(base);ss=carregar_sibal(base)
        except Exception as exc:erro(exc);return
        itens={}
        for r in ps:
            itens[r['condicao_id']]=dict(id=r['condicao_id'],material='PMMA',investigation='PSI-25',flow=t('Opposed','Oposto'),width=str(r['largura_mm']),
                thickness=str(r['espessura_mm']),faces=str(r['faces']),airflow=str(r['escoamento_mm_s']),
                oxygen=str(r['o2_inicial'])+' → '+str(r['o2_final'])+' '+t('(whole test)','(teste inteiro)'),
                spread=t('Not tracked','Não rastreada') if r['propagacao_mm_s'] is None else str(r['propagacao_mm_s']),
                reuse=t('Not assessed here','Não avaliada aqui'),test=r['teste_id'],page=65,row=r['fonte']['linha_dados'])
        for r in ss:
            if r['tipo_fluxo']=='valor_unico_publicado':flow=str(r['fluxo_valor_unico_mm_s'])
            else:flow=str(r['fluxo_inicial_mm_s'])+' → '+str(r['fluxo_final_mm_s'])
            itens[r['registro_id']]=dict(id=r['registro_id'],material='SIBAL',investigation=r['investigacao_id'],flow=t('Concurrent','Concorrente'),width=str(r['largura_mm']),
                thickness=t('Not supplied by this table','Não fornecida nesta tabela'),faces=t('Not supplied by this table','Não fornecidas nesta tabela'),airflow=flow,
                oxygen=str(r['oxigenio_vol_pct'])+(' · '+t('note b','nota b') if r['oxigenio_nota_b'] else '')+' '+t('(record)','(registro)'),
                spread=t('Not supplied by this table','Não fornecida nesta tabela'),reuse=t('Reported','Relatada') if r['reutilizacao_relata'] is True else t('Not specified','Não informada'),test=r['registro_id'],page=104,row=r['fonte']['linha_dados'])
        if len(itens)<2:st.info(t('At least two records are required.','São necessários pelo menos dois registros.'));return
        ids=list(itens)
        a,b=st.columns(2)
        with a: left=st.selectbox(t('Condition A','Condição A'),ids,key='compare_a')
        with b: right=st.selectbox(t('Condition B','Condição B'),ids,index=1,key='compare_b')
        ra,rb=itens[left],itens[right]
        campos=[('material','Material','Material'),('investigation','Investigation','Investigação'),('flow','Flow direction','Direção do escoamento'),('width','Width (mm)','Largura (mm)'),('thickness','Thickness (mm)','Espessura (mm)'),('faces','Burning faces','Faces em queima'),('airflow','Airflow (mm/s)','Escoamento (mm/s)'),('oxygen','Published O₂ (vol%) and scope','O₂ publicado (vol%) e escopo'),('spread','Spread (mm/s)','Propagação (mm/s)'),('reuse','Sample reuse','Reutilização da amostra')]
        st.table(pd.DataFrame([{t('Variable','Variável'):t(en,pt),'A':ra[k],'B':rb[k]} for k,en,pt in campos]))
        if left==right:st.info(t('The same record is selected twice.','O mesmo registro foi selecionado duas vezes.'))
        elif ra['test']==rb['test']:st.warning(t('These conditions belong to the same test and are not independent replicates.','Estas condições pertencem ao mesmo teste e não são réplicas independentes.'))
        if ra['material']!=rb['material'] or ra['flow']!=rb['flow']:
            st.warning(t('Different materials and/or flow directions: a direct comparison of flame-spread response is not supported by these tables.',
                         'Materiais e/ou direções de escoamento diferentes: estas tabelas não sustentam comparação direta da resposta de propagação.'))
        st.caption(t('Matching displayed fields does not prove experimental equivalence. Pressure, apparatus, measurement method and reuse may be missing or differ. Arrows represent published endpoints, not additional measurements.',
                     'Campos exibidos iguais não comprovam equivalência experimental. Pressão, aparato, método e reutilização podem estar ausentes ou diferir. Setas representam extremos publicados, não medições adicionais.'))
        for label,r in [('A',ra),('B',rb)]:
            st.markdown(f'**{label}** · [{t("Source page","Página da fonte")} {r["page"]}]({PDF}#page={r["page"]}) · '+t('data row ','linha de dados ')+str(r['row']))
