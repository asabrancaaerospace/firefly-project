"""Seleção de condições, mantendo observações ausentes e vínculo com testes."""
import json
from pathlib import Path
from src.analysis.bass_visualizacao import carregar_dados


def carregar_acervo(base: Path):
    pontos, ausentes = carregar_dados(base)
    pasta = base/'data'/'nasa_oficial'/'processed'/'bass_tabela51_v1'
    testes = json.loads((pasta/'testes.json').read_text(encoding='utf-8-sig'))
    por_nome = {t['identificador_publicado']:t for t in testes}
    registros = [{**p,'status':'valor_publicado'} for p in pontos]
    for c in ausentes:
        t = por_nome[c['teste']]
        registros.append({
            'condicao_id':c['condicao_id'],'teste_id':t['teste_id'],'teste':c['teste'],
            'escoamento_mm_s':float(c['escoamento_mm_s']),'propagacao_mm_s':None,
            'espessura_mm':t['espessura_mm'],'largura_mm':t['largura_mm'],
            'faces':t['faces_em_queima'],'o2_inicial':t['oxigenio_inicial_vol_pct'],
            'o2_final':t['oxigenio_final_vol_pct'],'fonte':t['fonte'],
            'status':'nao_rastreada',
        })
    registros.sort(key=lambda r:(int(r['teste'][1:]),r['condicao_id']))
    return registros, {t['teste_id']:t for t in testes}


def filtrar(registros, faces, espessuras, larguras, testes, status):
    return [r for r in registros if r['faces'] in faces
            and r['espessura_mm'] in espessuras and r['largura_mm'] in larguras
            and r['teste'] in testes and r['status'] in status]


def resumir(registros):
    return {'testes':len({r['teste_id'] for r in registros}),
            'condicoes':len(registros),
            'numericas':sum(r['propagacao_mm_s'] is not None for r in registros),
            'nao_rastreadas':sum(r['propagacao_mm_s'] is None for r in registros)}
