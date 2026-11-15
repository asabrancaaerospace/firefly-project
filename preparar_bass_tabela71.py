from pathlib import Path
from src.ingestion.bass_tabela71 import executar

if __name__ == '__main__':
    executar(Path(__file__).resolve().parent)
