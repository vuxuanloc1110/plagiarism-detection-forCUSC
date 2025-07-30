import re
from services.docx_utils import clean_text
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import underthesea
COLOR_MAP = {
    (80, 100): "#e2dea6",  # Light blue, easy on eyes
    (60, 79): "#b68b4c",   # Pastel orange, warm
    (50, 59): "#e89e98"    # Light green, fresh
}

def get_color(similarity):
    """Lấy màu dựa trên độ trùng lặp"""
    similarity = int(similarity * 100)
    
    for (low, high), color in COLOR_MAP.items():
        if low <= similarity <= high:
            return color
    return "black"
def highlight_keywords(text, keywords):
    """Làm nổi bật các từ khóa bằng thẻ <strong> để hiển thị in đậm"""
    if not keywords:
        return text

    for kw in sorted(keywords, key=len, reverse=True):  # Sắp xếp theo độ dài để tránh lỗi lồng ghép từ khóa
        text = re.sub(rf'\b({re.escape(kw)})\b', r'<strong>\1</strong>', text, flags=re.IGNORECASE)
    
    return text
def highlight_text(content, matches, sentence_map):
    """Tô màu các câu trùng khớp dựa trên mức độ tương đồng."""
    # Tạo ánh xạ ngược từ nội dung (sau khi chuẩn hóa) sang ID

    reversed_map = {clean_text(v): k for k, v in sentence_map.items()}

    for match in matches:
        original_sentence = clean_text(match["original_sentence"])  # Chuẩn hóa nội dung gốc
        similarity = match.get("sentence_similarity", 0)        
        color = get_color(similarity)

        # Tìm ID của câu gốc
        sentence_id = reversed_map.get(original_sentence)

        if not sentence_id:
            print(f"⚠️ Không tìm thấy câu: {match['original_sentence']}")  # Debug
            continue

        # Highlight nội dung
        pattern = rf'(<span id="{sentence_id}">)(.*?)(</span>)'
        replacement = rf'\1<span style="background-color: {color}">\2</span>\3'

        content = re.sub(pattern, replacement, content, count=1)
    return content
def extract_keywords(sentence):
    """Tách từ khóa có ý nghĩa từ câu gốc (1-3 từ)"""
    pos_tags = underthesea.pos_tag(sentence)
    
    keywords = []
    temp_phrase = []  # Lưu trữ cụm từ ghép

    for word, pos in pos_tags:
        if pos in ["V", "A"]:  # Chỉ lấy danh từ, động từ, tính từ
            temp_phrase.append(word)
            if len(temp_phrase) == 3:  # Chỉ lấy cụm từ tối đa 3 từ
                keywords.append(" ".join(temp_phrase))
                temp_phrase = []
        else:
            if temp_phrase:
                keywords.append(" ".join(temp_phrase))
                temp_phrase = []
    
    # Thêm cụm cuối cùng (nếu có)
    if temp_phrase:
        keywords.append(" ".join(temp_phrase))

    return keywords
def select_top_tfidf_sentences_percentile(sentences, percentile=10):
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(sentences)
    tfidf_scores = tfidf_matrix.mean(axis=1)
    tfidf_scores = np.squeeze(np.asarray(tfidf_scores))  # Convert to 1D array

    # Tính số lượng câu cần lấy theo phần trăm
    top_count = int(np.ceil(len(sentences) * percentile / 100))

    # Lấy chỉ số các câu có TF-IDF cao nhất
    top_indices = np.argsort(tfidf_scores)[-top_count:][::-1]  # Sort and get the top sentences

    return top_indices