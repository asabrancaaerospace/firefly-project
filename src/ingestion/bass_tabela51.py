"""Adaptador específico da Tabela 5.1 do NASA/TM-20210011385."""
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pymupdf

HASH_RELATORIO = '5FFA911FD9B6356F204646003FB9342E341810DCDFDF5CB15756E7F01EC5F770'


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open('rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            digest.update(bloco)
    return digest.hexdigest().upper()


def numero(texto: str) -> Decimal:
    if not re.fullmatch(r'\d+(?:\.\d+)?', texto.strip()):
        raise ValueError(f'Número não reconhecido: {texto!r}')
    return Decimal(texto.strip())


def lista_numerica(texto: str) -> list[Decimal]:
    texto = re.sub(r',\s*and\s+', ', ', texto.strip())
    partes = re.split(r'\s*,\s*|\s+and\s+', texto)
    return [numero(parte) for parte in partes]


def decimal_texto(valor: Decimal) -> str:
    return format(valor, 'f')


def normalizar_espacos(celulas: list) -> list[str]:
    return [' '.join((celula or '').split()) for celula in celulas]


def estruturar(tabela: dict) -> tuple[list, list]:
    testes, condicoes = [], []
    linhas = tabela['linhas']
    if len(linhas) != 20:
        raise ValueError('Esperadas 20 linhas na Tabela 5.1.')
    for indice, linha in enumerate(linhas, 1):
        c = linha['celulas_originais']
        if len(c) != 9 or c[0] != f'M{indice}' or linha['linha_dados'] != indice:
            raise ValueError(f'Estrutura inesperada na linha de dados {indice}.')
        if c[3] not in {'1', '2'}:
            raise ValueError(f'Número de faces inesperado em {c[0]}.')
        velocidades = lista_numerica(c[4])
        propagacoes = (
            [None] * len(velocidades)
            if c[5] == 'Not tracked' else lista_numerica(c[5])
        )
        if len(velocidades) != len(propagacoes):
            raise ValueError(f'Quantidades de velocidades incompatíveis em {c[0]}.')
        teste_id = f'PSI25_T51_{c[0]}'
        fonte = {'documento_sha256': HASH_RELATORIO, 'tabela': '5.1',
                 'pagina_fisica': 65, 'pagina_impressa': 57, 'linha_dados': indice}
        testes.append({
            'teste_id': teste_id, 'identificador_publicado': c[0],
            'investigacao_id': 'PSI-25', 'material': 'PMMA',
            'contexto_material': 'Relatório, seção 5, páginas físicas 63–64.',
            'espessura_mm': decimal_texto(numero(c[1])),
            'largura_cm_publicada': c[2],
            'largura_mm': decimal_texto(numero(c[2]) * Decimal('10')),
            'faces_em_queima': int(c[3]),
            'tempo_queima_min': decimal_texto(numero(c[6])),
            'oxigenio_inicial_vol_pct': decimal_texto(numero(c[7])),
            'oxigenio_final_vol_pct': decimal_texto(numero(c[8])),
            'escopo_oxigenio': 'Início e fim do teste completo; não medição por condição.',
            'celulas_originais': c, 'fonte': fonte,
        })
        for ordem, (velocidade, propagacao) in enumerate(zip(velocidades, propagacoes), 1):
            condicoes.append({
                'condicao_id': f'{teste_id}_C{ordem:02}', 'teste_id': teste_id,
                'ordem_na_lista_publicada': ordem,
                'escoamento_cm_s': decimal_texto(velocidade),
                'escoamento_mm_s': decimal_texto(velocidade * Decimal('10')),
                'propagacao_mm_s': None if propagacao is None else decimal_texto(propagacao),
                'status_propagacao': 'nao_rastreada' if propagacao is None else 'valor_publicado',
                'fonte': fonte,
            })
    return testes, condicoes


def comparar_texto(texto: str) -> str:
    # Ignora somente espaços: sinais, dígitos e ordem continuam obrigatórios.
    return ''.join(texto.split())


def ler_linha_geometrica(caracteres: list, caixa) -> str:
    if caixa is None:
        raise ValueError('Célula sem coordenadas; necessária revisão.')
    x0, y0, x1, y1 = caixa
    selecionados = []
    for caractere in caracteres:
        if not caractere['c'].strip():
            continue
        a, b, c, d = caractere['bbox']
        if x0 <= (a+c)/2 < x1 and y0 <= (b+d)/2 < y1:
            selecionados.append(caractere)
    if not selecionados:
        raise ValueError(f'Célula vazia na leitura geométrica: {caixa}')
    alturas = [c['origin'][1] for c in selecionados]
    if max(alturas) - min(alturas) > 2.5:
        raise ValueError('Célula com múltiplas linhas ou bases inesperadas; revisar geometria.')
    return ''.join(c['c'] for c in sorted(selecionados, key=lambda c: c['origin'][0]))


def conferir_por_posicao(pagina, tabela_pdf, esperado: list) -> None:
    if tabela_pdf.row_count != 21 or tabela_pdf.col_count != 9:
        raise ValueError('Geometria inesperada: esperadas 21 linhas e 9 colunas.')
    if len(esperado) != 21 or any(len(r) != 9 for r in esperado):
        raise ValueError('Estrutura inesperada no JSON candidato.')
    nativo = tabela_pdf.extract()
    if [comparar_texto(c or '') for c in nativo[0]] != [comparar_texto(c) for c in esperado[0]]:
        raise ValueError(f'Cabeçalhos divergentes: {nativo[0]!r}')
    caracteres = [
        c for bloco in pagina.get_text('rawdict')['blocks']
        if bloco.get('type') == 0
        for linha in bloco.get('lines', [])
        for span in linha.get('spans', [])
        for c in span.get('chars', [])
    ]
    divergencias = []
    for i in range(1, 21):
        caixas = tabela_pdf.rows[i].cells
        if len(caixas) != 9:
            raise ValueError(f'Número inesperado de células na linha {i}.')
        for j, caixa in enumerate(caixas):
            leitura = ler_linha_geometrica(caracteres, caixa)
            referencia = esperado[i][j]
            if comparar_texto(leitura) != comparar_texto(referencia):
                divergencias.append((i, j+1, referencia, leitura))
    if divergencias:
        for i, j, referencia, leitura in divergencias[:15]:
            print(f'Linha {i}, coluna {j}: esperado={referencia!r}; geométrico={leitura!r}')
        raise ValueError(f'{len(divergencias)} células divergentes após leitura geométrica; nenhuma saída gravada.')
    print('Conferência geométrica: 180 células de dados e 9 cabeçalhos OK')


def executar(base: Path) -> None:
    nasa = base / 'data' / 'nasa_oficial'
    entrada = nasa / 'extracted' / 'tabelas_candidatas_bass_v1.json'
    pdf = nasa / 'raw' / 'PSI-25' / 'Report' / 'BASS-II Summary Report.pdf'
    destino = nasa / 'processed' / 'bass_tabela51_v1'
    if destino.exists():
        raise FileExistsError(f'Destino já existe; nada será sobrescrito: {destino}')
    if sha256(pdf) != HASH_RELATORIO:
        raise ValueError('O PDF não corresponde à versão revisada do relatório.')
    dados = json.loads(entrada.read_text(encoding='utf-8-sig'))
    if dados['documento_sha256'] != HASH_RELATORIO:
        raise ValueError('O JSON aponta para outro documento.')
    selecionadas = [t for t in dados['tabelas'] if t['tabela'] == '5.1']
    if len(selecionadas) != 1:
        raise ValueError('Esperada exatamente uma Tabela 5.1.')
    tabela = selecionadas[0]
    if (tabela['pagina_fisica'], tabela['pagina_impressa']) != (65, 57):
        raise ValueError('Referências de página inesperadas.')
    esperado = [tabela['cabecalhos_originais']] + [r['celulas_originais'] for r in tabela['linhas']]
    with pymupdf.open(pdf) as documento:
        pagina = documento[64]
        tabelas = pagina.find_tables().tables
        if len(tabelas) != 1:
            raise ValueError('Extração do PDF encontrou quantidade inesperada de tabelas.')
        conferir_por_posicao(pagina, tabelas[0], esperado)
    testes, condicoes = estruturar(tabela)
    numericas = sum(c['propagacao_mm_s'] is not None for c in condicoes)
    if (len(testes), len(condicoes), numericas) != (20, 43, 39):
        raise ValueError('Contagens inesperadas; nenhuma saída foi gravada.')
    verificacao = {
        'testes': len(testes), 'condicoes_listadas': len(condicoes),
        'condicoes_com_propagacao_numerica': numericas,
        'condicoes_sem_propagacao_rastreada': len(condicoes) - numericas,
        'testes_sem_propagacao_rastreada': ['M6', 'M12'],
        'pdf_sha256': HASH_RELATORIO, 'json_entrada_sha256': sha256(entrada),
        'pymupdf_versao': pymupdf.VersionBind,
        'conferencia_celulas_com_pdf': True,
        'metodo_conferencia': 'Coordenadas dos caracteres por célula; dados em linha única; somente espaços ignorados.',
        'adaptador_versao': '1.1-geometria',
        'status': 'Estruturado; interpretação científica ainda sujeita a revisão.',
        'observacoes': [
            'Condições do mesmo teste não são réplicas independentes.',
            'Ordem da lista publicada não estabelece duração de cada condição.',
            'O2 inicial/final não foi interpolado nem atribuído a cada condição.',
            'Valores decimais são strings para preservar precisão; null significa ausência.',
            'Conversões: largura cm × 10 = mm; escoamento cm/s × 10 = mm/s.',
        ],
    }
    destino.mkdir(parents=True, exist_ok=False)
    for nome, conteudo in [('testes.json', testes), ('condicoes.json', condicoes), ('verificacao.json', verificacao)]:
        with (destino / nome).open('x', encoding='utf-8') as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)
            arquivo.write('\n')
    print('PDF e células da tabela conferidos: OK')
    print('Testes:', len(testes))
    print('Condições listadas:', len(condicoes))
    print('Com propagação numérica:', numericas)
    print('Sem propagação rastreada:', len(condicoes) - numericas)
    print('Saída:', destino)
