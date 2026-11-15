"""Download the E5 model to its normal cache; run before index creation."""
from sentence_transformers import SentenceTransformer

if __name__ == "__main__":
    SentenceTransformer("intfloat/multilingual-e5-small", device="cpu",
                        trust_remote_code=False)
    print("Model cached. Next: python operar_indice_saffire_v2.py indexar")
