from pathlib import Path
from src.retrieval.auditoria_recuperacao_v2 import executar

if __name__ == '__main__':
    executar(Path(__file__).resolve().parent)
