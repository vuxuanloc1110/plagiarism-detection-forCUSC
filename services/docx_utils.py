from bs4 import BeautifulSoup
def read_text_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"❌ Lỗi khi đọc file {file_path}: {e}")
        return ""

# Hàm chia nội dung thành từng đoạn
import zipfile
import shutil
import os
from docx import Document
def clean_docx_images(input_path, output_path):
    import zipfile
    import shutil
    import os

    temp_extract_path = "temp_docx_extract"

    try:
        # Bước 1: Giải nén từng file một, bỏ qua ảnh lỗi
        with zipfile.ZipFile(input_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                try:
                    zip_ref.extract(member, temp_extract_path)
                except Exception as e:
                    print(f"⚠️ Bỏ qua file lỗi: {member} ({e})")
                    continue

        # Bước 2: Xoá toàn bộ ảnh + quan hệ ảnh
        media_path = os.path.join(temp_extract_path, "word", "media")
        rels_path = os.path.join(temp_extract_path, "word", "_rels", "document.xml.rels")

        if os.path.exists(media_path):
            shutil.rmtree(media_path)

        if os.path.exists(rels_path):
            os.remove(rels_path)

        # Bước 3: Tạo lại file docx
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_write:
            for root, _, files in os.walk(temp_extract_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_extract_path)
                    zip_write.write(full_path, arcname)

    except Exception as e:
        print(f"❌ Lỗi khi làm sạch ảnh trong file DOCX: {e}")
        return False

    finally:
        shutil.rmtree(temp_extract_path, ignore_errors=True)

    return True
def split_text_into_sentences(text):
    # Tách câu theo dấu chấm, chấm hỏi, chấm than, hoặc dấu hai chấm
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]    # Loại bỏ khoảng trắng dư thừa
    return sentences
from docx import Document
import re
def split_into_sentences(text):
   """Chia đoạn văn bản thành các câu dựa trên dấu chấm (.), dấu hỏi (?), dấu chấm than (!)"""
   sentence_endings = r'(?<=[.!?:])\s+'
   sentences = re.split(sentence_endings, text.strip())
   return [s.strip() for s in sentences if s.strip()]  # Loại bỏ câu rỗng
from docx import Document
import re
def convert_text_to_html(docx_path):
    clean_path = docx_path.replace(".docx", "_noimg.docx")
    success = clean_docx_images(docx_path, clean_path)

    if not success:
        return "", {}

    try:
        doc = Document(clean_path)
    except Exception as e:
        print(f"❌ Lỗi khi mở file đã làm sạch ảnh: {e}")
        return "", {}
    html_content = []
    sentence_map = {}  # Lưu ID câu và nội dung để xử lý highlight
    sentence_idx = 1
    def split_into_sentences(text):
        # Improved Vietnamese sentence splitting (adjust as needed)
        pattern = r'(?<=[.!?])\s+'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    for para in doc.paragraphs:
        if not para.text.strip():
            continue  # Bỏ qua đoạn trống

        # Analyze all runs in this paragraph to understand structure
        runs_with_positions = []
        position = 0
        for run in para.runs:
            run_length = len(run.text)
            runs_with_positions.append({
                'text': run.text,
                'start': position,
                'end': position + run_length,
                'bold': run.bold,
                'italic': run.italic,
                'underline': run.underline
            })
            position += run_length

        # Get the full plain text of the paragraph
        plain_text = para.text
        
        # Split into sentences
        sentences = split_into_sentences(plain_text)
        
        # Find where each sentence appears in the paragraph text
        sentence_positions = []
        start_pos = 0
        for sentence in sentences:
            # Find the position of this sentence in the original paragraph
            sentence_start = plain_text.find(sentence, start_pos)
            if sentence_start >= 0:  # Only if found
                sentence_positions.append({
                    'text': sentence,
                    'start': sentence_start,
                    'end': sentence_start + len(sentence)
                })
                start_pos = sentence_start + len(sentence)
        
        # Process each sentence
        sentence_html = []
        for sentence_info in sentence_positions:
            sentence_text = sentence_info['text']
            sentence_start = sentence_info['start']
            sentence_end = sentence_info['end']
            
            # Create HTML for this sentence with proper formatting
            formatted_parts = []
            current_pos = sentence_start
            
            # Go through each run that overlaps with this sentence
            for run in runs_with_positions:
                # Check if this run overlaps with the current sentence
                if run['end'] <= sentence_start or run['start'] >= sentence_end:
                    continue  # This run doesn't overlap with the sentence
                
                # Calculate overlap
                overlap_start = max(run['start'], sentence_start)
                overlap_end = min(run['end'], sentence_end)
                
                if overlap_start < overlap_end:
                    # Extract the part of the run that overlaps with the sentence
                    overlap_text = plain_text[overlap_start:overlap_end]
                    
                    # Apply formatting
                    formatted_text = overlap_text
                    if run['bold']:
                        formatted_text = f"<strong>{formatted_text}</strong>"
                    if run['italic']:
                        formatted_text = f"<em>{formatted_text}</em>"
                    if run['underline']:
                        formatted_text = f"<u>{formatted_text}</u>"
                    
                    formatted_parts.append(formatted_text)
                    current_pos = overlap_end
            
            # Combine all formatted parts for this sentence
            formatted_sentence = "".join(formatted_parts)
            if not formatted_sentence.strip():
                formatted_sentence = sentence_text  # Fallback if no formatting was applied
                
            # Store in sentence map
            sentence_map[f"sentence-{sentence_idx}"] = sentence_text
            
            # Create the HTML span for this sentence
            sentence_html.append(f'<span id="sentence-{sentence_idx}">{formatted_sentence}</span>')
            sentence_idx += 1
        
        # Add this paragraph's HTML to the collection
        if sentence_html:
            html_content.append(" ".join(sentence_html))

    # Join paragraphs with double line breaks
    return "<br><br>".join(html_content), sentence_map
def split_into_sentences_txt(text_or_path):

    # Bảo vệ dấu chấm đứng trước chuỗi có chứa '.docx' hoặc các mã UUID dạng <...docxdocx>
    protected_text = re.sub(r'\.(?=\s*<[^>]*?docx[^>]*?>)', '<DOT_DOCX>', text_or_path.strip())

    # Tách câu như bình thường
    sentence_endings = r'(?<=[.!?:])\s+'
    sentences = re.split(sentence_endings, protected_text)

    # Khôi phục lại '.docx'
    sentences = [s.replace('<DOT_DOCX>', '.').strip() for s in sentences if s.strip()]
    return sentences
def clean_text(text):
    """Xóa các thẻ HTML, khoảng trắng dư và chuẩn hóa chuỗi để so sánh."""
    text = BeautifulSoup(text, "html.parser").get_text()  # Loại bỏ tag HTML
    text = re.sub(r"\s+", " ", text).strip()  # Chuẩn hóa khoảng trắng
    return text
import re
