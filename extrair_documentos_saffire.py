"""Extração documental local. Preserva PDFs e não faz inferência nem indexação."""
import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pymupdf


def sha256(caminho):
    digest = hashlib.sha256()
    with caminho.open('rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            digest.update(bloco)
    return digest.hexdigest().upper()


def salvar_json(caminho, valor):
    caminho.write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding='utf-8')


def executar(base):
    base = Path(base).resolve()
    nasa = base / 'data' / 'nasa_oficial'
    selecao = nasa / 'metadata' / 'selecao_documental_saffire_v1.json'
    raw = nasa / 'raw'
    saida = nasa / 'extracted' / 'saffire_documental_v1'
    if not raw.is_dir():
        raise FileNotFoundError(f'Pasta raw não encontrada: {raw}')
    if saida.exists():
        raise FileExistsError(f'Saída já existe; não será sobrescrita: {saida}')
    manifesto = json.loads(selecao.read_text(encoding='utf-8-sig'))
    documentos = manifesto['documentos']
    if not documentos:
        raise ValueError('A seleção documental está vazia.')
    ids = [d['documento_id'] for d in documentos]
    hashes = [d['sha256'].upper() for d in documentos]
    if len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes):
        raise ValueError('Documento ou hash repetido na seleção.')
    por_hash = {h: [] for h in hashes}
    for caminho in sorted(raw.rglob('*')):
        if caminho.is_file() and caminho.suffix.lower() == '.pdf':
            digest = sha256(caminho)
            if digest in por_hash:
                por_hash[digest].append(caminho)
    faltantes = [d['nome_referencia'] for d in documentos
                 if not por_hash[d['sha256'].upper()]]
    if faltantes:
        raise FileNotFoundError('PDFs não encontrados pelo SHA-256: ' + '; '.join(faltantes))

    extraidos = []
    avisos = []
    for ficha in documentos:
        digest = ficha['sha256'].upper()
        copias = por_hash[digest]
        caminho = copias[0]
        paginas = []
        with pymupdf.open(caminho) as pdf:
            if pdf.needs_pass:
                raise ValueError(f'PDF protegido: {caminho.name}')
            if pdf.page_count != ficha['paginas_esperadas']:
                raise ValueError(f'Quantidade de páginas divergente: {caminho.name}')
            for numero, pagina in enumerate(pdf, 1):
                texto_nativo = pagina.get_text('text', sort=False)
                texto_ordenado = pagina.get_text('text', sort=True)
                blocos = []
                for bloco in pagina.get_text('blocks', sort=False):
                    if bloco[6] == 0:
                        blocos.append({'numero_bloco': bloco[5],
                                       'bbox_pontos_pdf': list(bloco[:4]),
                                       'texto': bloco[4]})
                rotulos = [r['rotulo'] for r in ficha['faixas_de_paginas']
                           if r['inicio'] <= numero <= r['fim']]
                if not rotulos:
                    raise ValueError(f'Página sem classificação: {ficha["documento_id"]}/{numero}')
                impresso = (numero + ficha['deslocamento_pagina_impressa']
                            if ficha.get('deslocamento_pagina_impressa') is not None else None)
                registro = {
                    'pagina_fisica': numero,
                    'pagina_impressa': impresso,
                    'rotulos_editoriais': rotulos,
                    'texto_ordem_nativa': texto_nativo,
                    'texto_ordenado_por_posicao': texto_ordenado,
                    'blocos_texto': blocos,
                    'caracteres_ordem_nativa': len(texto_nativo),
                    'contem_letras': any(c.isalpha() for c in texto_nativo),
                    'revisao_local_pendente': True,
                }
                paginas.append(registro)
                if not registro['contem_letras']:
                    avisos.append({'documento_id': ficha['documento_id'],
                                   'pagina_fisica': numero,
                                   'motivo': 'Sem letras extraídas; conferir visualmente. Não implica necessidade de OCR.'})
            metadados_pdf = pdf.metadata
        # Detecta alterações na origem durante esta execução.
        if any(sha256(copia) != digest for copia in copias):
            raise ValueError(f'PDF alterado durante a extração: {caminho.name}')
        extraidos.append({
            'documento_id': ficha['documento_id'],
            'sha256_pdf': digest,
            'caminhos_relativos_raw': [p.relative_to(raw).as_posix() for p in copias],
            'ficha_selecao': ficha,
            'metadados_internos_pdf_nao_verificados': metadados_pdf,
            'paginas': paginas,
        })

    relatorio = {
        'versao': 1,
        'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
        'pymupdf_versao': version('pymupdf'),
        'sha256_selecao': sha256(selecao),
        'documentos_unicos': len(extraidos),
        'ocorrencias_fisicas_selecionadas': sum(len(d['caminhos_relativos_raw']) for d in extraidos),
        'paginas_preservadas': sum(len(d['paginas']) for d in extraidos),
        'paginas_sem_texto': sum(not p['texto_ordem_nativa'].strip()
                                for d in extraidos for p in d['paginas']),
        'avisos': avisos,
        'indexacao_rag_executada': False,
        'validacao_cientifica_automatica': False,
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = Path(tempfile.mkdtemp(prefix='.extracao_saffire_', dir=saida.parent))
    try:
        salvar_json(temporario / 'paginas.json', {'documentos': extraidos})
        relatorio['sha256_paginas_json'] = sha256(temporario / 'paginas.json')
        salvar_json(temporario / 'verificacao.json', relatorio)
        if saida.exists():
            raise FileExistsError(f'Saída já existe: {saida}')
        temporario.rename(saida)
    finally:
        if temporario.exists():
            shutil.rmtree(temporario)
    print(f'Documentos únicos: {relatorio["documentos_unicos"]}')
    print(f'Ocorrências físicas selecionadas: {relatorio["ocorrencias_fisicas_selecionadas"]}')
    print(f'Páginas preservadas: {relatorio["paginas_preservadas"]}')
    print(f'Páginas sem texto: {relatorio["paginas_sem_texto"]}')
    print(f'Avisos para revisão: {len(avisos)}')
    print(f'Saída: {saida}')
    print('Extração concluída. Ordem de leitura e conteúdo ainda exigem conferência local.')
    return relatorio


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
    argumentos = parser.parse_args()
    try:
        executar(argumentos.base)
    except (OSError, ValueError, KeyError) as erro:
        parser.exit(1, f'Erro: {erro}\n')
