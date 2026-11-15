"""Prepare verified resources on a clean host. Never logs credentials."""
import base64
import gc
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

FILES = (
    'extracted/tabelas_candidatas_bass_v1.json',
    'processed/bass_tabela51_v1/testes.json',
    'processed/bass_tabela51_v1/condicoes.json',
    'processed/bass_tabela51_v1/verificacao.json',
    'processed/bass_tabela71_v1/registros.json',
    'processed/bass_tabela71_v1/verificacao.json',
    'processed/recortes_saffire_v1/recortes.json',
    'processed/recortes_saffire_v1/verificacao.json',
    'processed/chunks_saffire_v2/chunks.json',
    'processed/chunks_saffire_v2/verificacao.json',
)
PDF = 'data/nasa_oficial/raw/PSI-25/Report/BASS-II Summary Report.pdf'
PDF_URL = 'https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def download(url, limit, headers=None):
    request = Request(url, headers={'User-Agent': 'Firefly-Research-MVP', **(headers or {})})
    with urlopen(request, timeout=120) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Downloaded resource exceeds its expected size limit.')
    return data


def write_verified(path, content, expected):
    if digest(content) != expected.lower():
        raise ValueError('Resource hash mismatch: ' + path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.download')
    temporary.write_bytes(content)
    temporary.replace(path)


def prepare_data(base, secrets):
    base = Path(base)
    manifest = {item['path']: item for item in json.loads(
        (base / 'docs/DATA_MANIFEST.json').read_text(encoding='utf-8-sig'))}
    wanted = {'data/nasa_oficial/' + name for name in FILES}
    for name in wanted | {PDF}:
        if name not in manifest:
            raise ValueError('Missing manifest entry: ' + name)
        if (base / name).exists() and digest((base / name).read_bytes()) != manifest[name]['sha256'].lower():
            raise ValueError('Existing resource changed: ' + name)
    missing = [name for name in wanted if not (base / name).exists()]
    if missing:
        config = secrets()
        repo = config['FIREFLY_DATA_REPO']
        # Fixed HTTPS endpoint: credentials are sent only to GitHub's API.
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('FIREFLY_DATA_REPO must be owner/repository.')
        token = config['FIREFLY_DATA_TOKEN']
        packet = json.loads(download(
            'https://api.github.com/repos/' + repo + '/contents/dados_hospedagem.json',
            8 * 1024 * 1024,
            {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github.raw+json'}))
        if packet.get('formato') != 'firefly_dados_para_revisao_v1':
            raise ValueError('Unsupported data bundle.')
        checked = {}
        for entry in packet['arquivos']:
            name = entry['path']
            if name not in wanted or name in checked:
                raise ValueError('Unexpected or repeated bundle path.')
            raw = base64.b64decode(entry['conteudo_base64'], validate=True)
            sha = digest(raw)
            if (sha != manifest[name]['sha256'].lower() or sha != entry['sha256'].lower()
                    or len(raw) != entry['bytes']):
                raise ValueError('Bundle integrity check failed: ' + name)
            json.loads(raw.decode('utf-8-sig'))
            checked[name] = raw
        if set(checked) != wanted:
            raise ValueError('Incomplete data bundle.')
        for name in missing:
            write_verified(base / name, checked[name], manifest[name]['sha256'])
    if not (base / PDF).exists():
        write_verified(base / PDF, download(PDF_URL, 65 * 1024 * 1024), manifest[PDF]['sha256'])


def prepare_search(base):
    # Keep model loading/encoding on CPU and limit CPU contention on shared hosts.
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    import torch
    torch.set_num_threads(2)
    from sentence_transformers import SentenceTransformer
    from src.retrieval.indice_saffire_v2 import MODELO, preparar, indexar
    model = SentenceTransformer(MODELO, device='cpu', trust_remote_code=False)
    del model
    gc.collect()
    prepared = preparar(base)
    folder = prepared[-1]
    identity = prepared[-2]
    del prepared
    gc.collect()
    marker = folder / 'manifesto.json'
    valid = False
    if marker.is_file() and (folder / 'chroma').is_dir():
        item = json.loads(marker.read_text(encoding='utf-8'))
        valid = item.get('status') == 'completo' and item.get('assinatura') == identity
    if not valid:
        indexar(base)
    # Check the stored collection, not merely the existence of its directory.
    from src.retrieval.servico_documental_mvp import ServicoDocumental
    service = ServicoDocumental(base)
    del service
    gc.collect()


def prepare(base, secrets):
    prepare_data(base, secrets)
    prepare_search(base)
