"""Exportação rastreável e cobertura das tabelas carregadas."""
import copy
from datetime import datetime, timezone


def pacote_exportacao(registros, conjunto, idioma):
    return {'platform':'Firefly','project':'Firefly Project','interface_version':'3',
            'dataset':conjunto,'exported_at_utc':datetime.now(timezone.utc).isoformat(),
            'interface_language':idioma,'record_count':len(registros),
            'selection':'filtered records; original source locations preserved',
            'records':copy.deepcopy(registros),'safety_certification':False}


def cobertura_tabelas(pmma, sibal):
    def n(rs,k):return sum(r.get(k) is not None for r in rs)
    return [dict(material='PMMA',records=len(pmma),flow=n(pmma,'escoamento_mm_s'),
                 spread=n(pmma,'propagacao_mm_s'),oxygen=sum(r.get('o2_inicial') is not None and r.get('o2_final') is not None for r in pmma),width=n(pmma,'largura_mm'),
                 reuse=None,pressure=None),
            dict(material='SIBAL',records=len(sibal),flow=sum(r.get('fluxo_valor_unico_mm_s') is not None or (r.get('fluxo_inicial_mm_s') is not None and r.get('fluxo_final_mm_s') is not None) for r in sibal),
                 spread=None,oxygen=n(sibal,'oxigenio_vol_pct'),width=n(sibal,'largura_mm'),
                 reuse=sum(r.get('reutilizacao_relata') is True for r in sibal),pressure=None)]


def mostrar_cobertura(base):
    import pandas as pd
    import streamlit as st
    from .dashboard import t,carregar_pmma,carregar_sibal,cabecalho,erro
    cabecalho(t('Evidence coverage','Cobertura das evidências'),t('What the selected tables contain — and what they do not establish.','O que as tabelas selecionadas contêm — e o que não permitem estabelecer.'))
    try:p,_=carregar_pmma(base);s=carregar_sibal(base)
    except Exception as exc:erro(exc);return
    rows=cobertura_tabelas(p,s)
    labels={'records':t('Conditions / records','Condições / registros'),'flow':t('Airflow reported','Fluxo informado'),
            'spread':t('Numeric spread','Propagação numérica'),'oxygen':t('Oxygen reported','Oxigênio informado'),
            'width':t('Width reported','Largura informada'),'reuse':t('Reuse explicitly reported','Reutilização explicitamente relatada'),
            'pressure':t('Pressure in these tables','Pressão nestas tabelas')}
    tabela=[]
    for k,label in labels.items():
        linha={t('Variable','Variável'):label}
        for r in rows:
            linha[r['material']]=t('Not supplied / not assessed','Não fornecida / não avaliada') if r[k] is None else str(r[k])
        tabela.append(linha)
    st.dataframe(pd.DataFrame(tabela),hide_index=True,width='stretch')
    st.caption(t('Counts describe conditions/records, not independent experiments. An unavailable field here does not prove that the quantity is absent elsewhere in the report or NASA repository.',
                 'As contagens descrevem condições/registros, não experimentos independentes. Um campo indisponível aqui não prova ausência da grandeza em outras partes do relatório ou do repositório NASA.'))
    a,b=st.columns(2)
    with a:
        st.subheader('PMMA')
        st.write(t('Table 5.1 publishes flame spread values; untracked conditions are retained. Initial/final oxygen describes the whole test, not each flow condition.',
                   'A Tabela 5.1 publica valores de propagação; condições não rastreadas são preservadas. O oxigênio inicial/final descreve o teste inteiro, não cada condição de fluxo.'))
        st.markdown('[NASA/TM-20210011385 · Table 5.1](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=65)')
    with b:
        st.subheader('SIBAL')
        st.write(t('Table 7.1 provides conditions and observations, not spread rates. Missing reuse information is not evidence of a new sample. Note b identifies two oxygen readings with possible inaccuracy.',
                   'A Tabela 7.1 fornece condições e observações, não taxas de propagação. Reutilização não informada não comprova amostra nova. A nota b identifica duas leituras de oxigênio com possível inexatidão.'))
        st.markdown('[NASA/TM-20210011385 · Table 7.1](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=104)')
    st.info(t('Next evidence to seek: comparable pressure, apparatus and measurement conditions before combining datasets or fitting predictive models.',
              'Próximas evidências a buscar: condições comparáveis de pressão, aparato e medição antes de combinar conjuntos ou ajustar modelos preditivos.'))
