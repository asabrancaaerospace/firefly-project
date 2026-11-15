"""Compara busca densa e híbrida no mesmo índice v2. Não reindexa nem usa LLM."""
import json
from datetime import datetime, timezone
from pathlib import Path
from src.retrieval.indice_saffire_v2 import preparar, cliente, validar_vetores, sha
from src.retrieval.auditoria_recuperacao_v2 import ranking_exato
from src.retrieval.busca_hibrida import buscar, VERSAO


def main():
    base=Path(__file__).resolve().parent
    questoes=json.loads((base/'docs/perguntas_busca_bilingue_v1.json').read_text(encoding='utf-8-sig'))['perguntas']
    nasa,chunks,entradas,modelo,assinatura,identidade,pasta=preparar(base)
    manifesto=json.loads((pasta/'manifesto.json').read_text(encoding='utf-8'))
    if manifesto['assinatura']!=identidade or manifesto['status']!='completo':
        raise ValueError('Índice v2 incompatível ou incompleto.')
    recorte_bytes=(nasa/'processed/recortes_saffire_v1/recortes.json').read_bytes()
    verificacao=json.loads((nasa/'processed/chunks_saffire_v2/verificacao.json').read_text(encoding='utf-8-sig'))
    if sha(recorte_bytes)!=verificacao['sha256_recortes_json']:
        raise ValueError('Recortes divergem da origem dos chunks v2.')
    recortes=json.loads(recorte_bytes.decode('utf-8-sig'))['recortes']
    mapa_rec={r['recorte_id']:r for r in recortes}
    mapa_chunk={c['chunk_id']:c for c in chunks}
    db=cliente(pasta)
    col=db.get_collection(name='saffire_documental',embedding_function=None)
    dados=col.get(include=['embeddings','documents'])
    if set(dados['ids'])!=set(mapa_chunk) or col.metadata.get('assinatura')!=identidade:
        raise ValueError('Conteúdo do índice incompatível.')
    for ident,texto in zip(dados['ids'],dados['documents']):
        if texto!=mapa_chunk[ident]['texto']:
            raise ValueError('Texto armazenado divergente.')
    consultas=[]
    for item in questoes:
        pergunta=item['pergunta']
        texto='query: '+pergunta
        if len(modelo.tokenizer(texto,truncation=False)['input_ids'])>assinatura['limite_efetivo']:
            raise ValueError('Pergunta longa demais.')
        vetor=modelo.encode([texto],prompt='',normalize_embeddings=True,
                            convert_to_numpy=True,show_progress_bar=False)
        validar_vetores(vetor,1)
        denso_chunks=ranking_exato(dados['ids'],dados['embeddings'],vetor[0])
        # Referências e gabaritos não são argumentos de buscar().
        resultado=buscar(recortes,chunks,denso_chunks,pergunta)
        completo={}
        for canal in ['denso','hibrido_sem_intencao','hibrido']:
            lista=[]
            for pos,r in enumerate(resultado[canal][:5],1):
                fonte=mapa_rec[r['recorte_id']]
                lista.append({**r,'posicao':pos,'tipo_evidencia':fonte['tipo_evidencia'],
                    'texto_recorte':fonte['texto_para_busca'],'nota_editorial':fonte['nota_editorial'],
                    'fontes':[{'documento_id':f['documento_id'],'documento':f.get('apelido_documento'),
                               'pagina_fisica':f['pagina_fisica']} for f in fonte['fontes']]})
            completo[canal]=lista
        posicoes={canal:[i for i,r in enumerate(resultado[canal],1)
                        if mapa_rec[r['recorte_id']]['tipo_evidencia']=='metodo_medicao']
                  for canal in ['denso','hibrido_sem_intencao','hibrido']}
        consultas.append({**item,'termos_consulta':resultado['termos_lexicais_consulta'],
            'top5_recortes_por_canal':completo,'ranking_recortes':resultado,
            'posicoes_tipo_metodo_medicao':posicoes,'intencao_metodologica':resultado['intencao_metodologica'],
            'avaliacao_cientifica':'pendente; posição/página não comprovam suporte'})
        print(f"{item['id']}: recorte(s) de método — denso {posicoes['denso']}; híbrido {posicoes['hibrido']}")
        if item['id'].startswith('DIAG_'):
            print('  Híbrido top 5:',[(r['fontes'][0]['documento'],r['fontes'][0]['pagina_fisica'],r['tipo_evidencia']) for r in completo['hibrido']])
    reports=nasa/'reports'
    reports.mkdir(exist_ok=True)
    caminho=reports/('busca_hibrida_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    caminho.write_text(json.dumps({'assinatura_indice':identidade,'politica_busca':VERSAO,
        'unidade_ranking':'recorte; não comparar diretamente posições com ranking antigo de chunks',
        'politica':'Denso: melhor similaridade de chunk por recorte. Lexical: BM25 texto+título+tipo editorial; glossário bilíngue limitado. Fusão RRF k=60. Para intenção metodológica, terceiro canal por tipo editorial: método, condições, ressalvas. Reportadas ablações com e sem esse prior. Não é classificação validada de pertinência ao experimento.',
        'consultas':consultas,'aprovacao_automatica':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Consultas concluídas: {len(consultas)}')
    print(f'Relatório: {caminho}')
    print('Índice preservado; nenhum LLM executado. Revisão de relevância pendente.')


if __name__=='__main__':
    main()
