import os
import re
import json
import time
import random
import datetime
import requests
from bs4 import BeautifulSoup
import logging
import threading
from collections import defaultdict
from config.settings import BASE_URL, MAX_RETRIES, JSON_FILE, STATS_FILE

# 配置日志
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

class DoubanCrawler:
    def __init__(self):
        self.crawl_stats = {
            "total_pages": 10,
            "current_page": 0,
            "movies_found": 0,
            "movies_parsed": 0,
            "start_time": None,
            "end_time": None,
            "status": "idle",
            "errors": 0,
            "requests": [],
            "crawl_history": []
        }
        self.stats_lock = threading.Lock()
        self.USER_AGENTS = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        ]

    def update_stats(self, key, value):
        with self.stats_lock:
            self.crawl_stats[key] = value

    def increment_stats(self, key, amount=1):
        with self.stats_lock:
            if key in self.crawl_stats:
                self.crawl_stats[key] += amount
            else:
                self.crawl_stats[key] = amount

    def add_request_record(self, url, status, delay, error=None):
        record = {
            "url": url,
            "status": status,
            "delay": delay,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": error if error else ""
        }
        
        with self.stats_lock:
            self.crawl_stats["requests"].append(record)
            if len(self.crawl_stats["requests"]) > 100:
                self.crawl_stats["requests"] = self.crawl_stats["requests"][-100:]

    def save_stats(self):
        try:
            with self.stats_lock:
                if self.crawl_stats["status"] == "completed" and self.crawl_stats["end_time"]:
                    history_entry = {
                        "time": self.crawl_stats["end_time"],
                        "movies_found": self.crawl_stats["movies_found"],
                        "duration": self.calculate_duration(self.crawl_stats["start_time"], self.crawl_stats["end_time"])
                    }
                    self.crawl_stats["crawl_history"].append(history_entry)
                    if len(self.crawl_stats["crawl_history"]) > 20:
                        self.crawl_stats["crawl_history"] = self.crawl_stats["crawl_history"][-20:]
                
                with open(STATS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.crawl_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")

    def calculate_duration(self, start_time, end_time):
        if not start_time or not end_time:
            return 0
        
        try:
            start = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            end = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            return (end - start).total_seconds()
        except Exception as e:
            logger.error(f"计算持续时间失败: {e}")
            return 0

    def get_random_headers(self):
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

    def get_page(self, url, retries=MAX_RETRIES):
        start_time = datetime.datetime.now()
        
        for attempt in range(retries):
            try:
                delay = random.uniform(2, 5)
                logger.info(f"请求 {url}，延迟 {delay:.2f}秒")
                time.sleep(delay)

                headers = self.get_random_headers()
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()

                if "检测到有异常请求" in response.text or "豆瓣安全中心" in response.text:
                    logger.warning("触发反爬机制，等待更长时间后重试...")
                    self.add_request_record(url, "blocked", delay, "Anti-bot triggered")
                    time.sleep(30)
                    self.increment_stats("errors")
                    continue

                response.encoding = "utf-8"
                duration = (datetime.datetime.now() - start_time).total_seconds()
                self.add_request_record(url, "success", delay, None)
                return BeautifulSoup(response.text, "html.parser")

            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 ({attempt+1}/{retries}): {e}")
                self.add_request_record(url, "error", delay, str(e))
                self.increment_stats("errors")
                
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"等待 {wait_time}秒后重试...")
                    time.sleep(wait_time)

        logger.error(f"无法获取页面: {url}")
        return None

    def parse_movie(self, item):
        try:
            title = item.find("span", class_="title").text.strip() if item.find("span", class_="title") else "未知标题"
            other_title = item.find("span", class_="other").text.strip() if item.find("span", class_="other") else ""
            link = item.find("a")["href"].strip() if item.find("a") and "href" in item.find("a").attrs else ""
            rating = item.find("span", class_="rating_num").text.strip() if item.find("span", class_="rating_num") else "0.0"
            
            rating_count = "0"
            star_div = item.find("div", class_="star")
            if star_div:
                rating_span = star_div.find_all("span")
                if rating_span and len(rating_span) >= 4:
                    rating_count_text = rating_span[-1].text.strip()
                    rating_count_match = re.search(r'(\d+)', rating_count_text)
                    rating_count = rating_count_match.group(1) if rating_count_match else "0"

            quote = item.find("span", class_="inq").text.strip() if item.find("span", class_="inq") else ""

            director, year, country, genre = "", "", "", ""
            bd_div = item.find("div", class_="bd")
            if bd_div:
                p_tag = bd_div.find('p')
                if p_tag:
                    info_text = p_tag.get_text(strip=True)
                    director_match = re.search(r'导演:\s*(.*?)\s*主演', info_text)
                    director = director_match.group(1).strip() if director_match else ""
                    
                    if not director:
                        director_match = re.search(r'导演:\s*(.*?)(?:\s*/\s*|$)', info_text)
                        director = director_match.group(1).strip() if director_match else ""
                    
                    info_parts = re.split(r'\s*/\s*', info_text)
                    for part in info_parts:
                        if re.match(r'^\d{4}$', part.strip()):
                            year = part.strip()
                        elif re.match(r'^[\u4e00-\u9fa5]+$', part.strip()):
                            country = part.strip() if not country else country + "/" + part.strip()
                        elif re.match(r'^[\u4e00-\u9fa5\w\s]+$', part.strip()):
                            genre = part.strip() if not genre else genre + "/" + part.strip()
                    
                    if not year:
                        year_match = re.search(r'(\d{4})', info_text)
                        year = year_match.group(1) if year_match else ""

            movie_id = hash(f"{title}{year}{director}") & 0xFFFFFFFF
            crawl_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.increment_stats("movies_parsed")
            
            return {
                "id": movie_id,
                "title": title,
                "other_title": other_title,
                "link": link,
                "rating": float(rating) if rating else 0.0,
                "rating_count": int(rating_count) if rating_count else 0,
                "director": director,
                "year": int(year) if year and year.isdigit() else None,
                "country": country,
                "genre": genre,
                "quote": quote,
                "crawl_time": crawl_time
            }

        except Exception as e:
            logger.error(f"解析电影信息时出错: {e}")
            return None

    def crawl_top250(self, pages):
        if not isinstance(pages, int) or pages < 1 or pages > 10:
            logger.warning(f"无效的页数参数: {pages}，使用默认值10")
            pages = 10
        
        self.update_stats("total_pages", pages)
        self.update_stats("current_page", 0)
        self.update_stats("movies_found", 0)
        self.update_stats("movies_parsed", 0)
        self.update_stats("errors", 0)
        self.update_stats("requests", [])
        self.update_stats("start_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.update_stats("end_time", None)
        self.update_stats("status", "crawling")
        self.save_stats()
        
        all_movies = []
        logger.info(f"开始爬取豆瓣Top250电影数据，共{pages}页...")

        for start in range(0, pages * 25, 25):
            page_num = start // 25 + 1
            url = f"{BASE_URL}?start={start}"
            logger.info(f"正在爬取第{page_num}页: {url}")
            self.update_stats("current_page", page_num)
            
            soup = self.get_page(url)
            if not soup:
                logger.warning(f"无法获取页面内容: {url}")
                continue

            items = soup.find_all("div", class_="item")
            if not items:
                logger.error(f"未找到电影列表项，可能被反爬: {url}")
                continue

            found_count = len(items)
            self.increment_stats("movies_found", found_count)
            logger.info(f"找到 {found_count} 部电影")

            for item in items:
                movie = self.parse_movie(item)
                if movie:
                    all_movies.append(movie)

            self.save_stats()

        self.update_stats("end_time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.update_stats("status", "completed")
        duration = self.calculate_duration(self.crawl_stats["start_time"], self.crawl_stats["end_time"])
        logger.info(f"成功爬取 {len(all_movies)} 部电影，耗时 {duration:.2f} 秒")
        self.save_stats()
        
        return all_movies
