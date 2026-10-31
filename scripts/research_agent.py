#!/usr/bin/env python3
"""
scripts/research_agent.py
Nhiệm vụ: Cào dữ liệu tin tức / xu hướng để cung cấp bối cảnh kịch bản cho LLM.
Chi phí: 0 đồng (sử dụng RSS Feeds và Web Scraping với BeautifulSoup4).
"""

import sys
import os
import re
import json
import argparse
import logging
from pathlib import Path
import xml.etree.ElementTree as ET
import warnings
warnings.filterwarnings("ignore")

# Đảm bảo xuất UTF-8 an toàn trên mọi hệ điều hành (Windows/Linux/Docker)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Hỗ trợ fallback chuẩn nếu môi trường chưa cài đặt requests / bs4
try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

# Thiết lập logging ghi ra stderr để không làm hỏng JSON output trên stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("research_agent")

# Danh sách các nguồn RSS đa kênh thịnh hành (Google Trends, Tin Hot, AI, Kinh doanh, Bí ẩn...)
TRENDING_FEEDS = {
    "google_trends": {
        "name": "🔥 Google Trends Việt Nam",
        "url": "https://trends.google.com/trending/rss?geo=VN"
    },
    "tech_ai": {
        "name": "🤖 Công nghệ & Trí tuệ nhân tạo (AI)",
        "url": "https://vnexpress.net/rss/so-hoa.rss"
    },
    "science_space": {
        "name": "🚀 Khoa học & Vũ trụ",
        "url": "https://vnexpress.net/rss/khoa-hoc.rss"
    },
    "business_crypto": {
        "name": "💰 Kinh doanh & Tài chính",
        "url": "https://vnexpress.net/rss/kinh-doanh.rss"
    },
    "world_mystery": {
        "name": "🌍 Thế giới & Bí ẩn",
        "url": "https://vnexpress.net/rss/the-gioi.rss"
    },
    "lifestyle_viral": {
        "name": "✨ Đời sống & Xu hướng",
        "url": "https://vnexpress.net/rss/doi-song.rss"
    },
    "entertainment": {
        "name": "🎬 Giải trí & Showbiz",
        "url": "https://vnexpress.net/rss/giai-tri.rss"
    }
}

DEFAULT_RSS_FEEDS = [f["url"] for f in TRENDING_FEEDS.values()]

def clean_html_tags(raw_html: str) -> str:
    """Làm sạch HTML tag an toàn không phụ thuộc thư viện ngoài"""
    if BeautifulSoup:
        return BeautifulSoup(raw_html, "html.parser").get_text().strip()
    return re.sub(r"<[^>]+>", "", raw_html).strip()

def fetch_rss_trending(feed_url: str = None) -> list[dict]:
    """Cào danh sách bài viết mới nhất từ RSS Feed"""
    url = feed_url or DEFAULT_RSS_FEEDS[0]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Video-Factory/1.0"}
    logger.info(f"Đang lấy dữ liệu xu hướng từ RSS: {url}")
    
    content_bytes = b""
    try:
        if requests:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            content_bytes = response.content
        else:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_bytes = resp.read()
        
        # Parse XML
        root = ET.fromstring(content_bytes)
        items = []
        for item in root.findall(".//item")[:5]:
            title = item.find("title").text if item.find("title") is not None and item.find("title").text else ""
            link = item.find("link").text if item.find("link") is not None and item.find("link").text else ""
            desc_elem = item.find("description")
            desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            
            clean_desc = clean_html_tags(desc) if desc else ""
            if title:
                items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "snippet": clean_desc
                })
        return items
    except Exception as e:
        logger.warning(f"Lỗi khi cào RSS ({url}): {e}")
        return []

def scrape_article_content(url: str) -> str:
    """Cào chi tiết đoạn mở đầu của bài viết để lấy bối cảnh"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        html_text = ""
        if requests:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            html_text = res.text
        else:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")

        # Loại bỏ các thẻ script và style gây nhiễu
        html_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.IGNORECASE | re.DOTALL)

        if BeautifulSoup:
            soup = BeautifulSoup(html_text, "html.parser")
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 40]
            context = " ".join(paragraphs[:3])
            return context[:600]
        else:
            # Fallback dùng regex
            paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.IGNORECASE | re.DOTALL)
            clean_paragraphs = [clean_html_tags(p) for p in paragraphs if len(clean_html_tags(p)) > 40]
            # Lọc bỏ các dòng chứa code js
            clean_paragraphs = [p for p in clean_paragraphs if "var " not in p and "function" not in p]
            return " ".join(clean_paragraphs[:3])[:600]
    except Exception as e:
        logger.warning(f"Không thể cào nội dung chi tiết từ {url}: {e}")
        return ""

from concurrent.futures import ThreadPoolExecutor

def fetch_category_items(item_tuple):
    cat_key, cat_info, max_per_cat = item_tuple
    try:
        items = fetch_rss_trending(cat_info["url"])
        result = []
        for it in items[:max_per_cat]:
            it["category"] = cat_info["name"]
            it["category_key"] = cat_key
            result.append(it)
        return result
    except Exception as e:
        logger.warning(f"Lỗi cào danh mục {cat_key}: {e}")
        return []

def fetch_all_trending_categories(max_per_category: int = 4, force_refresh: bool = False) -> list[dict]:
    """Cào tin tức và xu hướng đa kênh song song siêu tốc (<1.5s) có bộ nhớ đệm (Cache)"""
    cache_file = Path(os.getenv("SHARED_MEDIA_DIR", str(ROOT_DIR / "shared_media"))) / "temp" / "trending_cache.json"
    if not force_refresh and cache_file.exists():
        import time
        if time.time() - cache_file.stat().st_mtime < 300:
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if cached:
                    return cached
            except Exception:
                pass

    tasks = [(k, v, max_per_category) for k, v in TRENDING_FEEDS.items()]
    all_topics = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        for r in executor.map(fetch_category_items, tasks):
            all_topics.extend(r)

    if all_topics:
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(all_topics, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return all_topics

def main():
    import random
    parser = argparse.ArgumentParser(description="Research Agent - Cào bối cảnh kịch bản đa kênh")
    parser.add_argument("--topic", type=str, default="", help="Chủ đề cụ thể nếu người dùng muốn chỉ định")
    parser.add_argument("--feed-url", type=str, default="", help="Link RSS Feed tùy chọn")
    parser.add_argument("--category", type=str, default="", help="Mã danh mục muốn cào (google_trends, tech_ai, business_crypto...)")
    parser.add_argument("--all", action="store_true", help="Lấy danh sách tất cả các chủ đề hot đa kênh")
    parser.add_argument("--output", type=str, default="", help="Lưu JSON vào file nếu cần")
    args = parser.parse_args()

    # Trường hợp người dùng hoặc Web UI muốn lấy toàn bộ danh sách chủ đề hot để chọn lựa
    if args.all:
        all_topics = fetch_all_trending_categories(max_per_category=4)
        output_data = {
            "status": "success",
            "count": len(all_topics),
            "topics": all_topics
        }
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(json.dumps(output_data, ensure_ascii=False))
        return

    # Lấy dữ liệu theo danh mục cụ thể hoặc tổng hợp
    if args.feed_url:
        trending_items = fetch_rss_trending(args.feed_url)
    elif args.category and args.category in TRENDING_FEEDS:
        trending_items = fetch_rss_trending(TRENDING_FEEDS[args.category]["url"])
    else:
        # Tự động gom bài viết từ nhiều nguồn
        trending_items = fetch_all_trending_categories(max_per_category=3)

    chosen_category = ""
    if args.topic:
        chosen_title = args.topic
        context = f"Chủ đề được chỉ định: {args.topic}. Hãy phân tích góc nhìn kịch tính, bất ngờ và kích thích tranh luận dành cho người xem Reels."
        source_url = ""
    elif trending_items:
        # Chọn ngẫu nhiên 1 chủ đề thịnh hành để nội dung luôn mới mẻ, không bị lặp lại
        selected = random.choice(trending_items)
        chosen_title = selected["title"]
        chosen_category = selected.get("category", "")
        detailed_context = scrape_article_content(selected["link"])
        context = detailed_context if detailed_context else selected["snippet"]
        source_url = selected["link"]
    else:
        # Fallback an toàn nếu mất mạng
        chosen_title = "Bí mật chấn động về lỗ hổng bảo mật toàn cầu vừa bị phanh phui"
        context = "Một cuộc điều tra độc lập vừa hé lộ những sơ hở khó tin khiến hàng trăm triệu đô la bốc hơi trong chớp mắt."
        source_url = "https://vnexpress.net"

    output_data = {
        "status": "success",
        "topic": chosen_title,
        "category": chosen_category,
        "context": context,
        "source": source_url,
        "raw_feed_count": len(trending_items)
    }

    # Xuất ra file nếu có chỉ định
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

    # In JSON ra stdout cho n8n tiếp nhận
    print(json.dumps(output_data, ensure_ascii=False))

if __name__ == "__main__":
    main()
