"""Adaptador da Tabela 7.1: mantém mudanças de fluxo e observações distintas."""
import json
import re
from pathlib import Path
from decimal import Decimal
from collections import Counter
import pymupdf
from src.ingestion.bass_tabela51 import (
    HASH_RELATORIO, sha256, numero, decimal_texto,
    comparar_texto, ler_linha_geometrica,
)

OBSERVACOES = {
    'Quenched': 'extincao_quenching_relatada',
    'No blowoff': 'ausencia_de_blowoff_relatada',
    'No ignition': 'ausencia_de_ignicao_relatada',
    'Blow-off': 'extincao_blowoff_relatada',
    'Reused, did not ignite': 'ausencia_de_ignicao_relatada',
    'Reused, one-sided flame': 'chama_em_uma_face_relatada',
    'Reused, ignited': 'ignicao_relatada',
}


def estruturar(tabela):
    if len(tabela['linhas']) != 31:
        raise ValueError('Esperadas 31 linhas na Tabela 7.1.')
    registros=[]
    for i,linha in enumerate(tabela['linhas'],1):
        c=linha['celulas_originais']
        if len(c)!=5 or linha['linha_dados']!=i:
            raise ValueError(f'Estrutura inesperada na linha {i}.')
        codigo,largura,fluxo,oxigenio,comentario=c
        if not re.fullmatch(r'GMT\d+-T\d+[ab]?',codigo):
            raise ValueError(f'Identificador não reconhecido: {codigo}')
        bass= comentario=='BASS'
        if bass != (i>=28):
            raise ValueError('Vínculo BASS/BASS-II divergente do contexto revisado.')
        investigacao='PSI-26' if bass else 'PSI-25'
        nota_b=oxigenio.endswith('b')
        if nota_b != (i in (1,2)):
            raise ValueError('Marcador da nota b inesperado.')
        o2=numero(oxigenio[:-1] if nota_b else oxigenio)
        if not Decimal('0')<o2<=Decimal('100'):
            raise ValueError('Oxigênio fora do intervalo físico.')
        valores=fluxo.split(' to ')
        if len(valores) not in (1,2):
            raise ValueError('Formato de fluxo não reconhecido.')
        convertidos=[decimal_texto(numero(v)*Decimal('10')) for v in valores]
        if re.fullmatch(r'-+',comentario) or bass:
            observacao='nao_informada_nesta_coluna'
        elif comentario in OBSERVACOES:
            observacao=OBSERVACOES[comentario]
        else:
            raise ValueError(f'Comentário não reconhecido: {comentario!r}')
        reutilizacao= True if comentario.startswith('Reused,') else None
        registros.append({
            'registro_id':f'{investigacao}_T71_{codigo}',
            'identificador_publicado':codigo,'investigacao_id':investigacao,
            'material':'SIBAL','configuracao_fluxo':'concorrente',
            'largura_mm':decimal_texto(numero(largura)*Decimal('10')),
            'fluxo_original_cm_s':fluxo,
            'tipo_fluxo':'valor_unico_publicado' if len(valores)==1 else 'inicio_e_fim_publicados',
            'fluxo_valor_unico_mm_s':convertidos[0] if len(valores)==1 else None,
            'fluxo_inicial_mm_s':convertidos[0] if len(valores)==2 else None,
            'fluxo_final_mm_s':convertidos[1] if len(valores)==2 else None,
            'oxigenio_vol_pct':decimal_texto(o2),
            'oxigenio_nota_b':nota_b,
            'oxigenio_ressalva':('Leitura pode ser inexata, conforme nota b da tabela.' if nota_b else None),
            'reutilizacao_relata':reutilizacao,
            'observacao_padronizada':observacao,
            'comentario_original':comentario,
            'celulas_originais':c,
            'fonte':{'documento_sha256':HASH_RELATORIO,'tabela':'7.1',
                     'pagina_fisica':104,'pagina_impressa':96,'linha_dados':i,
                     'contexto_investigacoes_pagina_fisica':103},
        })
    if len({r['registro_id'] for r in registros})!=31:
        raise ValueError('Identificadores repetidos.')
    return registros


def conferir_celulas(pagina,tabela_pdf,tabela_json):
    esperado=[tabela_json['cabecalhos_originais']]+[r['celulas_originais'] for r in tabela_json['linhas']]
    if tabela_pdf.row_count!=32 or tabela_pdf.col_count!=5 or len(esperado)!=32:
        raise ValueError('Geometria inesperada da Tabela 7.1.')
    cabecalho=tabela_pdf.extract()[0]
    if [comparar_texto(c or '') for c in cabecalho]!=[comparar_texto(c) for c in esperado[0]]:
        raise ValueError(f'Cabeçalho divergente: {cabecalho!r}')
    caracteres=[c for b in pagina.get_text('rawdict')['blocks'] if b.get('type')==0
                for l in b.get('lines',[]) for s in l.get('spans',[]) for c in s.get('chars',[])]
    for i in range(1,32):
        for j,caixa in enumerate(tabela_pdf.rows[i].cells):
            chars=caracteres
            marcador=''
            if i in (1,2) and j==3:
                # Nesta célula específica há uma nota b sobrescrita, conferida visualmente.
                if caixa is None: raise ValueError('Célula de oxigênio sem coordenadas.')
                x0,y0,x1,y1=caixa
                dentro=[c for c in caracteres if c['c'].strip() and
                        x0<=(c['bbox'][0]+c['bbox'][2])/2<x1 and
                        y0<=(c['bbox'][1]+c['bbox'][3])/2<y1]
                letras=[c for c in dentro if c['c']=='b']
                numeros=[c for c in dentro if c['c']!='b']
                if len(letras)!=1 or not numeros:
                    raise ValueError('Nota b não localizada inequivocamente.')
                b=letras[0]
                if b['origin'][0]<=max(c['origin'][0] for c in numeros) or b['origin'][1]>=min(c['origin'][1] for c in numeros):
                    raise ValueError('Posição da nota b inesperada.')
                chars=numeros
                marcador='b'
            leitura=ler_linha_geometrica(chars,caixa)+marcador
            if comparar_texto(leitura)!=comparar_texto(esperado[i][j]):
                raise ValueError(f'Linha {i}, coluna {j+1}: esperado={esperado[i][j]!r}; extraído={leitura!r}')
    print('Conferência geométrica: 155 células de dados e 5 cabeçalhos OK')


def executar(base: Path):
    nasa=base/'data'/'nasa_oficial'
    entrada=nasa/'extracted'/'tabelas_candidatas_bass_v1.json'
    pdf=nasa/'raw'/'PSI-25'/'Report'/'BASS-II Summary Report.pdf'
    destino=nasa/'processed'/'bass_tabela71_v1'
    if destino.exists():raise FileExistsError(f'Destino existente; nada será sobrescrito: {destino}')
    if sha256(pdf)!=HASH_RELATORIO:raise ValueError('Hash do PDF divergente.')
    dados=json.loads(entrada.read_text(encoding='utf-8-sig'))
    if dados['documento_sha256']!=HASH_RELATORIO:raise ValueError('Referência do JSON divergente.')
    tabelas=[t for t in dados['tabelas'] if t['tabela']=='7.1']
    if len(tabelas)!=1:raise ValueError('Esperada uma Tabela 7.1.')
    tabela=tabelas[0]
    if (tabela['pagina_fisica'],tabela['pagina_impressa'])!=(104,96):raise ValueError('Páginas divergentes.')
    with pymupdf.open(pdf) as documento:
        pagina=documento[103];candidatas=pagina.find_tables().tables
        if len(candidatas)!=1:raise ValueError('Quantidade de tabelas inesperada no PDF.')
        conferir_celulas(pagina,candidatas[0],tabela)
    registros=estruturar(tabela)
    resumo={
        'registros':len(registros),
        'por_investigacao':dict(Counter(r['investigacao_id'] for r in registros)),
        'leituras_oxigenio_com_ressalva':sum(r['oxigenio_nota_b'] for r in registros),
        'registros_com_reutilizacao_explicita':sum(r['reutilizacao_relata'] is True for r in registros),
        'por_observacao':dict(Counter(r['observacao_padronizada'] for r in registros)),
        'pdf_sha256':HASH_RELATORIO,'json_entrada_sha256':sha256(entrada),
        'pymupdf_versao':pymupdf.VersionBind,'conferencia_celulas_com_pdf':True,
        'notas':[
            'Ausência de indicação de reutilização não comprova amostra nova.',
            'Comentários não fornecem uma classificação universal de segurança.',
            'No blowoff não significa ausência de combustão.',
            'Não foram criados pontos intermediários, velocidades de propagação ou datas completas.',
            'Fluxos inicial/final não são automaticamente limiares exatos de extinção.',
            'Identificadores GMT foram preservados sem inferir o ano.',
            'Os 31 registros não são necessariamente réplicas independentes.',
        ],
    }
    destino.mkdir(parents=True,exist_ok=False)
    for nome,conteudo in [('registros.json',registros),('verificacao.json',resumo)]:
        with (destino/nome).open('x',encoding='utf-8') as f:json.dump(conteudo,f,ensure_ascii=False,indent=2);f.write('\n')
    print('Registros:',len(registros))
    print('BASS-II:',resumo['por_investigacao']['PSI-25'])
    print('BASS:',resumo['por_investigacao']['PSI-26'])
    print('Oxigênio com ressalva:',resumo['leituras_oxigenio_com_ressalva'])
    print('Reutilização explicitamente indicada:',resumo['registros_com_reutilizacao_explicita'])
    print('Saída:',destino)
