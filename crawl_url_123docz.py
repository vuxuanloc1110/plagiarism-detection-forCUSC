import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy import signals
import json
import os

# Biến toàn cục để lưu danh sách URL
urls_collected = []

# Load danh sách URL đã crawl trước đó (nếu có)
FILE_NAME = "collected_urls.json"

if os.path.exists(FILE_NAME):
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        try:
            urls_collected = json.load(f)
            print(f"🔄 Đã tải {len(urls_collected)} URL từ file {FILE_NAME}, tiếp tục crawl...")
        except json.JSONDecodeError:
            print(f"⚠️ File {FILE_NAME} bị lỗi, bắt đầu crawl từ đầu.")
            urls_collected = []

class LinkSpider(scrapy.Spider):
    name = 'link_spider'
    start_urls = ['https://123docz.com']
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 5,
    }

    def parse(self, response):
        for link in response.css('a::attr(href)').getall():
            if link.startswith('/'):
                link = response.urljoin(link)
            if "/user" in link or "/auth" in link:
                continue  # Bỏ qua link không cần thiết
            if link not in urls_collected:
                urls_collected.append(link)  # Lưu vào danh sách tránh trùng lặp
                yield {'URL': link}
                yield scrapy.Request(link, callback=self.parse)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(LinkSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        """Hàm này sẽ được gọi khi Spider kết thúc hoặc bị ngắt (Ctrl + C)"""
        print(f"\n🛑 Spider đã dừng! Tổng số URL đã thu thập: {len(urls_collected)}")

        # Lưu tiếp tục danh sách URL vào file JSON
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            json.dump(urls_collected, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ Danh sách URL đã lưu vào file `{FILE_NAME}`, sẽ tiếp tục từ đó trong lần sau.")

# Chạy Scrapy
if __name__ == "__main__":
    process = CrawlerProcess()
    process.crawl(LinkSpider)
    process.start()
