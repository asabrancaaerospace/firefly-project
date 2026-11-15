# Firefly — Firefly Project

An interactive dashboard for exploring NASA microgravity combustion evidence.

## What users can explore

- **Overview:** coverage of the available experimental and documentary data.
- **Investigations:** study objectives, materials, findings and limitations.
- **PMMA:** 20 tests and 43 conditions; 39 numeric flame-spread observations.
- **SIBAL:** 31 records, including 27 BASS-II and 4 BASS records.
- **Evidence search:** English and Portuguese queries, multilingual semantic
  retrieval and lexical search, with original excerpts and source locations.
- **Evidence coverage:** available information and remaining gaps.
- **Conditions and scenarios:** side-by-side comparisons and oxygen partial
  pressure calculations.
- **Sources and methodology:** provenance, transformations and limitations.

These counts represent different units and must not be added as independent
experiments. The interface supports English and Portuguese. Source quotations
retain their original language.

## Implementation and scientific scope

Python, Streamlit and Plotly provide the interface and visualizations. The search
uses `intfloat/multilingual-e5-small`, Chroma and hybrid ranking. This version
retrieves evidence; **it does not generate answers using an LLM**.

The MVP is an evidence exploration tool. It does not predict fire safety,
certify materials or establish causation from cross-study comparisons. Missing
measurements remain missing; repeated conditions are not independent replicates.

## Access and release status

This repository contains the application source and selected verification tools.
A public hosted application has not been verified as part of this export.
Add the tested live URL here before submitting the final global evaluation link.

**A fresh clone is not yet a self-contained deployment.** Research resources,
model weights and generated vector indexes are excluded. See
[data setup](docs/DATA_SETUP.md) and [deployment](docs/DEPLOYMENT.md).

## Local execution

Use the project root as the working directory. Install dependencies in a virtual
environment after checking Python and package compatibility:

```text
python -m pip install -r requirements.txt
```

Restore the verified resources as described in `docs/DATA_SETUP.md`. Prepare the
model cache and build the index in that same environment:

```text
python baixar_modelo_busca.py
python operar_indice_saffire_v2.py indexar
python testar_firefly_v3.py
python verificar_firefly_acervo.py
python iniciar_firefly_v3.py
```

The launcher runs locally. Cloud deployments use `app_firefly_v3.py` directly.
UI tests alone do not establish scientific validity or prove that hosted search
works. Some pipeline tests require additional original documentary PDFs.

## Reproducibility

`docs/ENVIRONMENT.json` records the export environment. `requirements.txt` pins
the listed packages from that environment; it is not a complete dependency lock
or a claim that Windows builds will install unchanged on Linux. Rebuild the
index in the target environment, since its identity includes package versions.

## Sources and licensing

See [source notes](docs/SOURCES.md). Scientific content and code have separate
rights. This export does not select a software license on behalf of the team.
Before release, choose a code license with the contributors and document rights
for every redistributed document or excerpt. NASA hosting alone does not grant
redistribution rights over all third-party publications.
