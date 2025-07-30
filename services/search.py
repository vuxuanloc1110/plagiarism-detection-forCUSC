# search.py

# ✅ Import cấu hình chung
from config import BRAVE_API_KEY, BRAVE_SEARCH_URL, INDEX_NAME
import asyncio
import aiohttp
# ✅ Import model và device
from models.model_loader import load_model
model, device = load_model()

# ✅ Import hàm xử lý docx/html/highlight
from services.docx_utils import (
    convert_text_to_html,
    read_text_file,
    split_into_sentences,
    split_into_sentences_txt
)

# ✅ Import tiền xử lý văn bản
from services.preprocess import (
    extract_keywords,
    select_top_tfidf_sentences_percentile,
    highlight_text,
)

# ✅ Import chức năng tìm kiếm Google
from services.google_search import (
    batch_google_search
)

# ✅ Thư viện hệ thống và NLP
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import torch
import time
import re
from sentence_transformers import util
import numpy as np
from elasticsearch import Elasticsearch

# ✅ Khởi tạo Elasticsearch (hoặc import es từ nơi khác)
es = Elasticsearch("http://localhost:9200")
# Load once at the top of the file
model, device = load_model()
def remove_html_tags(text):
    """Remove HTML tags from text"""
    if not text:
        return text
    # Remove HTML tags using regex
    clean_text = re.sub(r'<[^>]+>', '', text)
    # Also decode common HTML entities
    clean_text = clean_text.replace('&amp;', '&')
    clean_text = clean_text.replace('&lt;', '<')
    clean_text = clean_text.replace('&gt;', '>')
    clean_text = clean_text.replace('&quot;', '"')
    clean_text = clean_text.replace('&#39;', "'")
    return clean_text.strip()

async def batch_brave_search(sentences, max_workers=1):
    """Batch search sentences using Brave Search API"""
    
    async def search_single_sentence(session, sentence):
        """Search a single sentence using Brave Search API"""
        try:
            # Add 1 second delay before each request
            await asyncio.sleep(1)
            
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'X-Subscription-Token': BRAVE_API_KEY
            }
            
            params = {
                'q': f'"{sentence}"',  # Use quotes for exact phrase search
                'count': 1,  # Number of results to return
                'offset': 0,
                'search_lang': 'vi',
                'safesearch': 'moderate', 
            }
            
            async with session.get(BRAVE_SEARCH_URL, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract the best result
                    if data.get('web', {}).get('results'):
                        best_result = data['web']['results'][0]
                        snippet = remove_html_tags(best_result.get('description', ''))
                        title = remove_html_tags(best_result.get('title', ''))
                        return {
                            "result": "Found",
                            "snippet": snippet,
                            "url": best_result.get('url', ''),
                            "title": title
                        }
                    else:
                        return {"result": "Not Found", "snippet": "", "url": ""}
                else:
                    print(f"Brave Search API error: {response.status}")
                    return {"result": "Not Found", "snippet": "", "url": ""}
                    
        except Exception as e:
            print(f"Error searching sentence: {e}")
            return {"result": "Not Found", "snippet": "", "url": ""}
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_workers)
    
    async def search_with_semaphore(session, sentence):
        async with semaphore:
            return await search_single_sentence(session, sentence)
    
    # Execute all searches concurrently
    async with aiohttp.ClientSession() as session:
        tasks = [search_with_semaphore(session, sentence) for sentence in sentences]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions that occurred
    processed_results = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Search exception: {result}")
            processed_results.append({"result": "Not Found", "snippet": "", "url": ""})
        else:
            processed_results.append(result)
    
    return processed_results

async def search_similar_sentences(file_path, top_k=3, threshold=0.5, mode="both"):
    if mode not in ["elastic", "brave", "both"]:
        raise ValueError(f"Chế độ không hợp lệ: {mode}")

    print(f"🔧 Đang chạy với chế độ tìm kiếm: {mode}")  # 👉 Đặt ở đây

    start_time = time.time()
    doc_content, sentence_map = convert_text_to_html(file_path)
    input_sentences = list(sentence_map.values())
    
    sentence_embeddings = model.encode(input_sentences, convert_to_tensor=True, device=device, batch_size=256)
    best_matches = defaultdict(lambda: {"sentence_similarity": -1})
    seen_sentences = set()
    search_results = {}

    if mode in ["elastic", "both"]:
        # Hàm tìm kiếm một câu trong Elasticsearch
        def search_query(args):
            idx, sentence, embedding = args
            if sentence in seen_sentences:
                return None
            
            seen_sentences.add(sentence)
            query = {
                "size": top_k,
                "knn": {
                    "field": "embedding",
                    "query_vector": embedding.cpu().numpy().tolist(),
                    "k": top_k,
                    "num_candidates": 50,
                }
            }
            response = es.search(index=INDEX_NAME, body=query)
            return (sentence, {"idx": idx, "response": response, "embedding": embedding})

        # Tìm kiếm trong Elasticsearch song song
        search_start = time.time()
        with ThreadPoolExecutor(max_workers=min(16, len(input_sentences))) as executor:
            tasks = [(idx, input_sentences[idx - 1], sentence_embeddings[idx - 1]) 
                     for idx in range(1, len(input_sentences) + 1)]
            search_results_list = list(executor.map(search_query, tasks))
        
        # Lọc bỏ kết quả None
        search_results = {sentence: data for result in search_results_list if result for sentence, data in [result]}
        search_end = time.time()
        print(f"🔍 Hoàn thành tìm kiếm trong Elasticsearch ({search_end - search_start:.2f} giây)")

        # Xử lý kết quả Elasticsearch
        all_keywords = {sentence: set(extract_keywords(sentence)) for sentence in search_results}
        unique_keywords = set().union(*all_keywords.values())
        keyword_embeddings_global = {
            kw: model.encode(kw, convert_to_tensor=True, device=device) for kw in unique_keywords
        }

        for sentence, data in search_results.items():
            idx, response, sentence_embedding = data.values()
            keywords = all_keywords[sentence]

            for res in response["hits"]["hits"]:
                matched_sentence = res["_source"]["sentence"]
                matched_embedding = torch.tensor(res["_source"]["embedding"], device=device)

                common_keywords = keywords & set(extract_keywords(matched_sentence))
                if len(common_keywords) >= 3:
                    sentence_similarity = round(util.cos_sim(sentence_embedding, matched_embedding).item(), 4)

                    if sentence_similarity >= threshold:
                        if common_keywords:
                            kw_embeddings = torch.stack([keyword_embeddings_global[kw] for kw in common_keywords])
                            keyword_similarities = util.cos_sim(kw_embeddings, matched_embedding).mean().item()
                        else:
                            keyword_similarities = 0.0

                        if sentence_similarity > best_matches[sentence]["sentence_similarity"]:
                            best_matches[sentence] = {
                                "matched_sentence": matched_sentence,
                                "source": "Elasticsearch",
                                "filename": res["_source"].get("filename", ""),
                                "sentence_similarity": sentence_similarity,
                                "keywords_similarity": round(keyword_similarities, 4),
                                "sentence_id": idx,
                                "keywords": list(common_keywords),
                            }

    # Tìm các câu chưa match đủ tốt để tìm với Brave
    unmatched_sentences = []
    if mode in ["both", "brave"]:
        unmatched_sentences = [s for s in input_sentences if best_matches[s]["sentence_similarity"] < threshold]
        unmatched_sentences = [s for s in unmatched_sentences if len(s.split()) >= 5]

        if unmatched_sentences:
            top_indices = select_top_tfidf_sentences_percentile(unmatched_sentences, percentile=100)
            top_sentences = [unmatched_sentences[i] for i in top_indices]

            brave_start = time.time()
            brave_results = await batch_brave_search(top_sentences)
            brave_end = time.time()
            print(f"🔎 Hoàn thành tìm kiếm trong Brave Search ({brave_end - brave_start:.2f} giây)")

            for idx, (sentence, brave_result) in enumerate(zip(top_sentences, brave_results), start=1):
                if brave_result.get("result") == "Not Found":
                    continue

                snippet = brave_result.get("snippet", "").strip()
                brave_url = brave_result.get("url", "")
                if not snippet:
                    continue

                snippet_sentences = split_into_sentences(snippet)
                sentence_embedding = sentence_embeddings[input_sentences.index(sentence)]

                best_snippet = ""
                best_similarity = 0.0
                for snip_sent in snippet_sentences:
                    if not snip_sent:
                        continue
                    snip_embedding = model.encode(snip_sent, convert_to_tensor=True, device=device)
                    similarity = util.cos_sim(sentence_embedding, snip_embedding).item()
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_snippet = snip_sent

                if best_similarity >= 0.5:
                    best_matches[sentence] = {
                        "matched_sentence": best_snippet,
                        "source": "Brave Search",
                        "filename": brave_url,
                        "url": brave_url,
                        "sentence_similarity": round(best_similarity, 4),
                        "sentence_id": idx,
                        "keywords_similarity": 0,
                        "keywords": []
                    }

    print("✅ Hoàn thành toàn bộ quá trình tìm kiếm")

    results = sorted([
        {
            "original_sentence": orig,
            "matched_sentence": data.get("matched_sentence", ""),
            "source": data.get("source", ""),
            "highlighted_original_sentence": orig,
            "highlighted_matched_sentence": data.get("matched_sentence", ""), 
            "filename": data.get("filename", ""),
            "url": data.get("url", ""),
            "sentence_similarity": data.get("sentence_similarity", -1),
            "keywords_similarity": data.get("keywords_similarity", 0),
            "sentence_id": data.get("sentence_id", -1)
        }
        for orig, data in best_matches.items()
        if data.get("matched_sentence")
    ], key=lambda x: x["sentence_similarity"], reverse=True)

    doc_content = highlight_text(doc_content, results, sentence_map)
    print(f"⏳ Tổng thời gian thực thi: {time.time() - start_time:.2f} giây")

    return doc_content, results

import re
import os
def split_into_sentences_txt(text_or_path):

    # Bảo vệ dấu chấm đứng trước chuỗi có chứa '.docx' hoặc các mã UUID dạng <...docxdocx>
    protected_text = re.sub(r'\.(?=\s*<[^>]*?docx[^>]*?>)', '<DOT_DOCX>', text_or_path.strip())

    # Tách câu như bình thường
    sentence_endings = r'(?<=[.!?:])\s+'
    sentences = re.split(sentence_endings, protected_text)

    # Khôi phục lại '.docx'
    sentences = [s.replace('<DOT_DOCX>', '.').strip() for s in sentences if s.strip()]
    return sentences


async def search_similar_sentences_txt(file_path):
    """Tìm kiếm câu trùng lặp cho file .txt"""
    start_time = time.time()
    
    # Đọc nội dung file .txt
    text_content = read_text_file(file_path)
    if not text_content:
        return "", []

    # Chia nội dung thành các câu
    input_sentences = split_into_sentences(text_content)
    print(input_sentences)
    # Tạo sentence_map với ID đơn giản
    sentence_map = {f"sentence-{i+1}": sentence for i, sentence in enumerate(input_sentences)}
    
    # Tạo HTML đơn giản cho nội dung
    html_content = []
    for idx, sentence in enumerate(input_sentences, 1):
        html_content.append(f'<span id="sentence-{idx}">{sentence}</span>')
    doc_content = "<br><br>".join(html_content)

    # Mã hóa các câu
    sentence_embeddings = model.encode(input_sentences, convert_to_tensor=True, device=device, batch_size=256)
    
    # Tái sử dụng logic tìm kiếm từ search_similar_sentences
    best_matches = defaultdict(lambda: {"sentence_similarity": -1})
    seen_sentences = set()
    search_results = {}

    def search_query(args):
        idx, sentence, embedding = args
        if sentence in seen_sentences:
            return None
        seen_sentences.add(sentence)
        query = {
            "size": 3,
            "knn": {
                "field": "embedding",
                "query_vector": embedding.cpu().numpy().tolist(),
                "k": 3,
                "num_candidates": 50,
            }
        }
        response = es.search(index=INDEX_NAME, body=query)
        return (sentence, {"idx": idx, "response": response, "embedding": embedding})
    search_start = time.time()
    # Tìm kiếm trong Elasticsearch
    with ThreadPoolExecutor(max_workers=min(16, len(input_sentences))) as executor:
        tasks = [(idx, sentence, sentence_embeddings[idx - 1]) 
                 for idx, sentence in enumerate(input_sentences, 1)]
        search_results_list = list(executor.map(search_query, tasks))
    
    search_results = {sentence: data for result in search_results_list if result for sentence, data in [result]}


    search_end = time.time()
    print(f"🔍 Hoàn thành tìm kiếm trong Elasticsearch ({search_end - search_start:.2f} giây)")
    # Xử lý kết quả Elasticsearch
    all_keywords = {sentence: set(extract_keywords(sentence)) for sentence in search_results}
    unique_keywords = set().union(*all_keywords.values())
    keyword_embeddings_global = {kw: model.encode(kw, convert_to_tensor=True, device=device) 
                                for kw in unique_keywords}

    for sentence, data in search_results.items():
        idx, response, sentence_embedding = data.values()
        keywords = all_keywords[sentence]
        
        for res in response["hits"]["hits"]:
            matched_sentence = res["_source"]["sentence"]
            matched_embedding = torch.tensor(res["_source"]["embedding"], device=device)
            
            common_keywords = keywords & set(extract_keywords(matched_sentence))
            if len(common_keywords) >= 3:
                sentence_similarity = round(util.cos_sim(sentence_embedding, matched_embedding).item(), 4)

                if sentence_similarity >= 0.5:
                    kw_embeddings = torch.stack([keyword_embeddings_global[kw] for kw in common_keywords])
                    keyword_similarities = util.cos_sim(kw_embeddings, matched_embedding).mean().item()
                    
                    if sentence_similarity > best_matches[sentence]["sentence_similarity"]:
                        best_matches[sentence] = {
                            "matched_sentence": matched_sentence,
                            "source": "Elasticsearch",
                            "filename": res["_source"].get("filename", ""),
                            "sentence_similarity": sentence_similarity,
                            "keywords_similarity": round(keyword_similarities, 4),
                            "sentence_id": idx,
                            "keywords": list(common_keywords),
                        }

    # Tìm kiếm Google cho các câu không khớp
    unmatched_sentences = [s for s in input_sentences if best_matches[s]["sentence_similarity"] < 0.5]
    unmatched_sentences = [s for s in unmatched_sentences if len(s.split()) >= 5]
    if unmatched_sentences:
        top_indices = select_top_tfidf_sentences_percentile(unmatched_sentences, percentile=50)
        top_sentences = [unmatched_sentences[i] for i in top_indices]

        google_results = asyncio.run(batch_google_search(top_sentences))
        for idx, (sentence, google_result) in enumerate(zip(top_sentences, google_results), start=1):
            if google_result.get("result") == "Not Found":
                continue

            snippet = google_result.get("snippet", "").strip()
            google_url = google_result.get("url", "")
            if not snippet:
                continue

            snippet_sentences = split_into_sentences(snippet)
            sentence_embedding = sentence_embeddings[input_sentences.index(sentence)]
            best_snippet = ""
            best_similarity = 0.0

            for snip_sent in snippet_sentences:
                if not snip_sent:
                    continue
                snip_embedding = model.encode(snip_sent, convert_to_tensor=True, device=device)
                similarity = util.cos_sim(sentence_embedding, snip_embedding).item()
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_snippet = snip_sent

            if best_similarity >= 0.85:
                best_matches[sentence] = {
                    "matched_sentence": best_snippet,
                    "source": "Google Search",
                    "filename": google_url,
                    "url": google_url,
                    "sentence_similarity": round(best_similarity, 4),
                    "sentence_id": idx,
                    "keywords_similarity": 0,
                    "keywords": []
                }

    # Tạo kết quả
    results = sorted([
        {
            "original_sentence": orig,
            "matched_sentence": data.get("matched_sentence", ""),
            "source": data.get("source", ""),
            "highlighted_original_sentence": orig,
            "highlighted_matched_sentence": data.get("matched_sentence", ""), 
            "filename": data.get("filename", ""),
            "url": data.get("url", ""),
            "sentence_similarity": data.get("sentence_similarity", -1),
            "keywords_similarity": data.get("keywords_similarity", 0),
            "sentence_id": data.get("sentence_id", -1)
        }
        for orig, data in best_matches.items()
        if data.get("matched_sentence")
    ], key=lambda x: x["sentence_similarity"], reverse=True)

    # Highlight nội dung
    doc_content = highlight_text(doc_content, results, sentence_map)
    
    print(f"⏳ Tổng thời gian thực thi: {time.time() - start_time:.2f} giây")
    return doc_content, results
from werkzeug.utils import secure_filename