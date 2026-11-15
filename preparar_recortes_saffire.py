"""Execute na raiz do projeto: python preparar_recortes_saffire.py."""
from pathlib import Path
from src.ingestion.recortes_documentais import executar

if __name__ == '__main__':
    executar(Path(__file__).resolve().parent)
