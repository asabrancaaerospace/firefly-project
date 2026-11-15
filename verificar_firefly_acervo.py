"""Verificação local: usa os leitores científicos anteriores, sem LLM ou embeddings."""
from pathlib import Path
from src.ui.firefly import carregar_pmma, carregar_sibal, cobertura
from src.ui.firefly_charts import pmma, sibal


def main():
    base=Path(__file__).resolve().parent
    p,_=carregar_pmma(base);s=carregar_sibal(base);recortes,fontes=cobertura(base)
    numericos=[r for r in p if r['propagacao_mm_s'] is not None]
    fig=pmma(p)
    esperados={r['condicao_id']:(float(r['escoamento_mm_s']),float(r['propagacao_mm_s'])) for r in numericos}
    obtidos={d[0]:(float(x),float(y)) for tr in fig.data for x,y,d in zip(tr.x,tr.y,tr.customdata)}
    if len(esperados)!=len(numericos) or esperados!=obtidos or sum(len(tr.x) for tr in fig.data)!=len(numericos):
        raise ValueError('Pontos PMMA divergem dos registros.')
    fig_s=sibal(s)
    count=sum(1 if r['tipo_fluxo']=='valor_unico_publicado' else 2 for r in s)
    if sum(len(tr.x) for tr in fig_s.data)!=count:
        raise ValueError('Marcadores SIBAL divergem dos extremos publicados.')
    print('PMMA:',len({r['teste_id'] for r in p}),'testes;',len(p),'condições;',len(numericos),'pontos numéricos')
    print('SIBAL:',len(s),'registros;',count,'marcadores (extremos não são novos testes)')
    print('Acervo documental:',len(fontes),'documentos;',len(recortes),'recortes')
    print('Leitores e figuras: OK. Nenhum arquivo científico foi modificado.')
    print('Ainda conferir visualmente referências e executar uma busca no painel.')


if __name__=='__main__':main()
