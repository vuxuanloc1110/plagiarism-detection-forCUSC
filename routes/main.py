# from flask import Blueprint, request, render_template, redirect, url_for, flash
# import os
# from werkzeug.utils import secure_filename

# from config import UPLOAD_FOLDER
# from services.search import search_similar_sentences, search_similar_sentences_txt
# from services.indexer import index_file

# main = Blueprint('main', __name__)
# ALLOWED_EXTENSIONS = {'txt', 'docx'}

# # ✅ Hàm kiểm tra định dạng file
# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# # ✅ Route 1: Trang chính kiểm tra đạo văn
# @main.route("/", methods=["GET", "POST"])
# def index():
#     doc_content = ""
#     sentences = []
#     results = []

#     if request.method == "POST":
#         if "file" not in request.files:
#             return redirect(request.url)

#         file = request.files["file"]
#         if file.filename == "":
#             return redirect(request.url)

#         if file and allowed_file(file.filename):
#             filename = secure_filename(file.filename)
#             file_path = os.path.join(UPLOAD_FOLDER, filename)
#             os.makedirs(UPLOAD_FOLDER, exist_ok=True)
#             file.save(file_path)

#             try:
#                 if filename.endswith(".docx"):
#                     doc_content, results = search_similar_sentences(file_path)
#                 elif filename.endswith(".txt"):
#                     doc_content, results = search_similar_sentences_txt(file_path)
#                 else:
#                     return render_template("index.html", error="Định dạng file không được hỗ trợ. Vui lòng tải lên file .docx hoặc .txt")

#                 sentences = doc_content.split("\n") if doc_content else []

#             except Exception as e:
#                 print(f"Lỗi khi xử lý file: {e}")
#                 doc_content, sentences, results = "", [], []

#     return render_template("index.html", doc_content=doc_content, sentences=sentences, results=results)

# # ✅ Route 2: Upload nhiều file để index vào Elasticsearch
# @main.route("/upload-index", methods=["GET", "POST"])
# def upload_index():
#     if request.method == "POST":
#         if "files" not in request.files:
#             flash("Không có file nào được chọn")
#             return redirect(request.url)

#         files = request.files.getlist("files")
#         if not files or all(f.filename == '' for f in files):
#             flash("Chưa chọn file hợp lệ")
#             return redirect(request.url)

#         indexed = 0
#         for file in files:
#             if file and allowed_file(file.filename):
#                 filename = secure_filename(file.filename)
#                 save_path = os.path.join("Project/download_tailieuvn_text", filename)
#                 os.makedirs(os.path.dirname(save_path), exist_ok=True)
#                 file.save(save_path)
#                 index_file(save_path, filename)
#                 indexed += 1

#         flash(f"✅ Đã upload và index {indexed} file vào     Elasticsearch!")
#         return redirect(url_for("main.upload_index"))

#     return render_template("upload_index.html")
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates  
import os
import aiofiles

from config import UPLOAD_FOLDER
from services.search import search_similar_sentences, search_similar_sentences_txt
from services.indexer import index_file

templates = Jinja2Templates(directory="templates")
router = APIRouter()

ALLOWED_EXTENSIONS = {"txt", "docx"}

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    print("🔍 Extension:", ext)
    return ext in ALLOWED_EXTENSIONS

# ✅ Route GET: hiển thị giao diện chính
@router.get("/", response_class=HTMLResponse)
async def index_get(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "doc_content": "",
        "sentences": [],
        "results": []
    })

# ✅ Route POST: xử lý file đạo văn
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER
from fastapi import Form

upload_cache = {}  # Biến toàn cục để lưu tạm kết quả (có thể thay bằng session)

@router.post("/", response_class=HTMLResponse)
async def index_post(
    request: Request,
    file: UploadFile = File(...),
    mode: str = Form(...)
):
    if not file.filename or not allowed_file(file.filename):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "❌ Tệp không hợp lệ. Vui lòng chọn tệp .docx hoặc .txt",
            "doc_content": "",
            "sentences": [],
            "results": []
        })

    filename = file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    try:
        if filename.endswith(".docx"):
            doc_content, results = await search_similar_sentences(file_path, mode=mode)
        else:
            doc_content, results = await search_similar_sentences_txt(file_path, mode=mode)

        sentences = doc_content.split("\n") if doc_content else []

        # Lưu tạm kết quả
        upload_cache["doc_content"] = doc_content
        upload_cache["sentences"] = sentences
        upload_cache["results"] = results

        return RedirectResponse(url="/result", status_code=HTTP_303_SEE_OTHER)

    except Exception as e:
        print(f"❌ Lỗi xử lý file: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "❌ Lỗi xử lý file",
            "doc_content": "",
            "sentences": [],
            "results": []
        })
@router.get("/result", response_class=HTMLResponse)
async def show_result(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "doc_content": upload_cache.get("doc_content", ""),
        "sentences": upload_cache.get("sentences", []),
        "results": upload_cache.get("results", [])
    })
@router.get("/upload-index", response_class=HTMLResponse)
async def upload_index_get(request: Request):
    return templates.TemplateResponse("upload_index.html", {"request": request})

@router.post("/upload-index", response_class=HTMLResponse)
async def upload_index_post(request: Request, files: list[UploadFile] = File(...)):
    if not files or all(not f.filename for f in files):
        return templates.TemplateResponse("upload_index.html", {
            "request": request,
            "message": "❌ Chưa chọn file hợp lệ"
        })

    indexed = 0
    for file in files:
        if file and allowed_file(file.filename):
            filename = file.filename
            save_path = os.path.join("Project/download_tailieuvn_text", filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            async with aiofiles.open(save_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            index_file(save_path, filename)
            indexed += 1

    return templates.TemplateResponse("upload_index.html", {
        "request": request,
        "message": f"✅ Đã upload và index {indexed} file vào Elasticsearch!"
    })
