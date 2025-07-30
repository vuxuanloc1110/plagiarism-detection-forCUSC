
# Hệ thống Crawl Dữ Liệu và Kiểm Tra Đạo Văn

## 1. Yêu cầu hệ thống

- Python: `3.10`
- Cài đặt các thư viện cần thiết bằng cách chạy lệnh:

```bash
pip install -r requirements.txt
```

### Các thư viện chính:
- Scrapy==2.12.0
- selenium==4.29.0
- beautifulsoup4==4.13.4
- requests==2.32.3
- FastAPI, Flask, Elasticsearch, etc.

> **Lưu ý:** Đảm bảo đúng phiên bản để tránh lỗi không tương thích.

---

## 2. Hướng dẫn Crawl dữ liệu

### Crawl từ website [123docz.net](https://123docz.net)

1. Chạy file sau để crawl danh sách URL con:
    ```bash
    python crawl_url_123docz.py
    ```
    > Output sẽ được lưu vào file `.json`. Hãy sử dụng giãn cách thời gian giữa các lần crawl để tránh bị chặn IP.

2. Chạy tiếp để tải nội dung văn bản từ danh sách URL đã crawl:
    ```bash
    python download_file_123docz.py
    ```
    > Output là các file `.txt` chứa nội dung tài liệu.

---

### Crawl từ website [tailieu.vn](https://tailieu.vn)

1. Chạy file sau để crawl danh sách URL:
    ```bash
    python crawl_tailieuvn.py
    ```
    > Output sẽ được lưu vào file `.json`.

2. Chạy tiếp để tải nội dung văn bản từ danh sách URL:
    ```bash
    python download_tailieuvn.py
    ```
    > Output là các file `.txt` chứa nội dung tài liệu.

---

## 3. Cài đặt và chạy Website tìm kiếm + Kiểm tra đạo văn

### Bước 1: Clone repository và cài đặt thư viện
```bash
git clone <link-repo>
cd <repo-folder>
pip install -r requirements.txt
```

### Bước 2: Cài đặt Elasticsearch bằng Docker

1. Tải Docker tại [https://www.docker.com](https://www.docker.com)
2. Tạo mạng Docker:
    ```bash
    docker network create elastic
    ```
3. Tải và chạy Elasticsearch:
    ```bash
    docker pull docker.elastic.co/elasticsearch/elasticsearch:8.5.3
    docker run --name elasticsearch \
        --net elastic \
        -p 9200:9200 -p 9300:9300 \
        -e "discovery.type=single-node" \
        -e "xpack.security.enabled=false" \
        -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
        -d docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    ```

### Bước 3: Chạy ứng dụng

```bash
python app.py
```

> Ứng dụng sẽ khởi chạy đầy đủ các chức năng tìm kiếm và kiểm tra đạo văn dựa trên dữ liệu crawl được.

---

## Ghi chú

- Hãy đảm bảo mạng ổn định khi crawl.
- Các website có thể thay đổi cấu trúc HTML, nên cần kiểm tra lại định kỳ và cập nhật script nếu cần.

---

## Liên hệ

Nếu bạn có bất kỳ câu hỏi hay góp ý nào, vui lòng mở issue hoặc liên hệ với nhóm phát triển.
