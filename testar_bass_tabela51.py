import copy
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from src.ingestion.bass_tabela51 import estruturar, executar, lista_numerica


def main():
    base = Path(__file__).resolve().parent
    nasa = base / 'data' / 'nasa_oficial'
    entrada = nasa / 'extracted' / 'tabelas_candidatas_bass_v1.json'
    pdf = nasa / 'raw' / 'PSI-25' / 'Report' / 'BASS-II Summary Report.pdf'
    tabela = next(t for t in json.loads(entrada.read_text(encoding='utf-8-sig'))['tabelas'] if t['tabela']=='5.1')
    testes, condicoes = estruturar(tabela)
    assert len(testes) == 20 and len(condicoes) == 43
    assert len({c['condicao_id'] for c in condicoes}) == 43
    assert condicoes[0]['escoamento_mm_s'] == '90'
    assert condicoes[0]['propagacao_mm_s'] == '0.071'
    assert testes[0]['largura_mm'] == '22.0'
    assert [(c['escoamento_mm_s'], c['propagacao_mm_s']) for c in condicoes if c['teste_id']=='PSI25_T51_M2'] == [('200', '0.052'), ('150', '0.033')]
    ausentes = [c for c in condicoes if c['propagacao_mm_s'] is None]
    assert len(ausentes) == 4
    assert {c['teste_id'] for c in ausentes} == {'PSI25_T51_M6', 'PSI25_T51_M12'}
    assert all('oxigenio_inicial_vol_pct' not in c for c in condicoes)
    assert lista_numerica('10, 6, 5, and 3') == list(map(Decimal, ['10','6','5','3']))
    invalida = copy.deepcopy(tabela)
    invalida['linhas'][1]['celulas_originais'][5] = '0.052'
    try:
        estruturar(invalida)
    except ValueError:
        pass
    else:
        raise AssertionError('Pares incompletos deveriam ser rejeitados.')
    with tempfile.TemporaryDirectory(prefix='teste_bass51_') as pasta:
        temporario = Path(pasta)
        destino = temporario / 'data' / 'nasa_oficial'
        (destino/'extracted').mkdir(parents=True)
        (destino/'raw'/'PSI-25'/'Report').mkdir(parents=True)
        shutil.copyfile(entrada, destino/'extracted'/entrada.name)
        shutil.copyfile(pdf, destino/'raw'/'PSI-25'/'Report'/pdf.name)
        executar(temporario)
        resultado = json.loads((destino/'processed'/'bass_tabela51_v1'/'condicoes.json').read_text(encoding='utf-8'))
        assert len(resultado) == 43
        try:
            executar(temporario)
        except FileExistsError:
            pass
        else:
            raise AssertionError('Deveria impedir sobrescrita.')
    print('Testes funcionais: OK')


if __name__ == '__main__':
    main()
