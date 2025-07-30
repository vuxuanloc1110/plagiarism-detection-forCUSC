import torch
from sentence_transformers import SentenceTransformer

def load_model():
    device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2").to(device)
    return model, device
