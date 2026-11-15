from pathlib import Path
from src.retrieval.chunking_documental_v2 import executar

if __name__ == '__main__':
    executar(Path(__file__).resolve().parent)
