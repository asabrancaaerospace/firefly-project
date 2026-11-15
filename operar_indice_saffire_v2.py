import argparse
from pathlib import Path
from src.retrieval.indice_saffire_v2 import indexar, consultar

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('modo', choices=['indexar', 'consultar'])
    a = p.parse_args()
    (indexar if a.modo == 'indexar' else consultar)(Path(__file__).resolve().parent)
