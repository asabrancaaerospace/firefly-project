# Data setup

The export copies selected resources into `data/nasa_oficial/` for LOCAL testing.
The entire `data/` directory is ignored by Git and is NOT sent to GitHub by a
normal `git add .`. `docs/DATA_MANIFEST.json` lists relative paths, sizes and hashes;
it does not contain the scientific text or the user's absolute paths.

## Runtime resources

- `raw/PSI-25/Report/BASS-II Summary Report.pdf`
- `extracted/tabelas_candidatas_bass_v1.json`
- `processed/bass_tabela51_v1/`: testes, condicoes, verificacao JSON files.
- `processed/bass_tabela71_v1/`: registros and verificacao JSON files.
- `processed/recortes_saffire_v1/`: recortes and verificacao JSON files.
- `processed/chunks_saffire_v2/`: chunks and verificacao JSON files.
- Any additional metadata referenced by the selected modules.

The PMMA/SIBAL loaders validate the original BASS PDF and input hashes. Supplying
only the processed tables does not satisfy those checks. Preserve file contents
byte-for-byte: reformatting JSON may invalidate recorded hashes.

The extraction pipeline additionally needs the original guide, SAFFIRE DoD and
SAFFIRE article at the paths in its selection configuration. The export does not
copy the entire original archive or promise a full pipeline reproduction without
those inputs. Metadata and extracted pages are included locally when available.

## Model and index

`python baixar_modelo_busca.py` downloads the E5 model into the library's normal
cache; it does not add weights to this repository. Network access is required for
the first download. Then run `python operar_indice_saffire_v2.py indexar` using the
same Python environment that will run the application. Indexes are generated
under `data/nasa_oficial/indexes/` and remain ignored by Git.

The current service expects a cached model and a matching existing index.
Copying a Windows Chroma directory is not a substitute for setting up Linux.

## Before public deployment

Review redistribution rights for each PDF and extracted full-text dataset.
For authorized files, define a versioned data bundle or a documented acquisition
procedure with expected hashes. Then explicitly revise `.gitignore` if selected
resources will be committed. Do not force-add all of `data/`.

Keep the reviewed files' original relative locations. Test from a fresh clone
and acquired data bundle, not just from the original development directory.
