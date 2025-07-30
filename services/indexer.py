# Những hàm hỗ trợ cần nằm trong indexer.py
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
import torch
import re
from docx import Document

# Elasticsearch & model khởi tạo dùng chung
ES_HOST = "http://localhost:9200"
INDEX_NAME = "documents"
es = Elasticsearch([ES_HOST])
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2").to(device)
EMBEDDING_DIMS = model.encode("test").shape[0]

# ✅ Các hàm cần thiết
def create_index():
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(
            index=INDEX_NAME,
            body={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "filename": {"type": "keyword"},
                        "sentence": {"type": "text"},
                        "sentence_hash": {"type": "keyword"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": EMBEDDING_DIMS,
                            "index": True,
                            "similarity": "cosine"
                        }
                    }
                }
            }
        )

def split_text_into_sentences(text):
    return re.split(r'(?<=[.!?:])\s+', text)

def create_paragraph_hash(paragraph):
    normalized_para = re.sub(r'\s+', '', paragraph.lower())
    return hash(normalized_para)

def is_sentence_already_indexed(sent_hash):
    query = {
        "query": {"term": {"sentence_hash": str(sent_hash)}}
    }
    res = es.search(index=INDEX_NAME, body=query, size=1)
    return res["hits"]["total"]["value"] > 0

def read_docx(file_path):
    doc = Document(file_path)
    text_content = ""
    for para in doc.paragraphs:
        text_content += para.text + "\n"
    return text_content

# ✅ Hàm chính để dùng từ Flask
def index_file(file_path, filename):
    create_index()
    actions = []
    batch_size = 300
    indexed_count = 0
    skipped_count = 0

    if filename.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text_content = f.read()
    elif filename.endswith(".docx"):
        text_content = read_docx(file_path)
    else:
        return

    sentences = split_text_into_sentences(text_content)
    for sentence in sentences:
        if len(sentence.split()) < 3:
            skipped_count += 1
            continue

        sent_hash = create_paragraph_hash(sentence)
        if is_sentence_already_indexed(sent_hash):
            skipped_count += 1
            continue

        embedding = model.encode(sentence).tolist()
        actions.append({
            "_index": INDEX_NAME,
            "_source": {
                "filename": filename,
                "sentence": sentence,
                "sentence_hash": str(sent_hash),
                "embedding": embedding
            }
        })
        indexed_count += 1
        if len(actions) >= batch_size:
            helpers.bulk(es, actions)
            actions = []

    if actions:
        helpers.bulk(es, actions)

    print(f"✅ File {filename} đã index xong: {indexed_count} câu")
