import os
import json
import time
import datetime
import logging
from config.settings import JSON_FILE, CACHE_EXPIRE

# 配置日志
logger = logging.getLogger(__name__)

def clean_data(movies):
    """数据清洗与预处理"""
    if not movies:
        return []

    cleaned = []
    unique_ids = set()

    for movie in movies:
        if not movie:
            continue

        # 去重处理
        if movie["id"] in unique_ids:
            continue
        unique_ids.add(movie["id"])

        # 处理空值
        for key in movie:
            if movie[key] == "" or movie[key] is None:
                if key == "year":
                    movie[key] = "未知年份"
                elif key in ["country", "genre"]:
                    movie[key] = "未知"
                else:
                    movie[key] = "N/A"

        cleaned.append(movie)

    return cleaned

def save_to_json(movies, filename=JSON_FILE):
    """保存数据到JSON文件"""
    if not movies:
        logger.warning("无新数据需要保存")
        return False

    try:
        # 尝试读取现有数据
        existing_movies = []
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    existing_movies = json.load(f)
            except json.JSONDecodeError:
                logger.warning("JSON文件损坏，将创建新文件")

        # 创建ID集合用于去重
        existing_ids = {m["id"] for m in existing_movies}

        # 添加新电影
        new_movies = [m for m in movies if m["id"] not in existing_ids]

        if not new_movies:
            logger.info("没有发现新电影")
            return False

        # 合并新旧数据
        all_movies = existing_movies + new_movies

        # 按评分排序
        all_movies.sort(key=lambda x: x["rating"], reverse=True)

        # 保存数据
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(all_movies, f, ensure_ascii=False, indent=2)

        logger.info(f"成功保存{len(new_movies)}条新数据，总计{len(all_movies)}条数据")
        return True

    except Exception as e:
        logger.error(f"保存数据时出错: {e}")
        return False

def load_cached_data(filename=JSON_FILE):
    """加载缓存数据"""
    if os.path.exists(filename):
        # 检查缓存是否过期
        file_time = os.path.getmtime(filename)
        current_time = time.time()

        if current_time - file_time < CACHE_EXPIRE:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"从缓存加载了 {len(data)} 条数据")
                    return data
            except Exception as e:
                logger.error(f"加载缓存数据失败: {e}")

    return None

def get_visualization_data(movies):
    """为可视化准备数据"""
    if not movies:
        return {
            "rating_distribution": [],
            "year_distribution": [],
            "genre_distribution": []
        }
    
    # 评分分布
    rating_distribution = {}
    for movie in movies:
        if "rating" in movie:
            rating = round(movie["rating"] * 2) / 2  # 四舍五入到0.5
            if rating not in rating_distribution:
                rating_distribution[rating] = 0
            rating_distribution[rating] += 1
    
    # 转换为列表并排序
    rating_data = sorted(rating_distribution.items())
    
    # 年份分布
    year_distribution = {}
    for movie in movies:
        if "year" in movie and movie["year"] and movie["year"] != "未知年份":
            year = movie["year"]
            decade = (year // 10) * 10  # 计算年代
            decade_label = f"{decade}s"
            if decade_label not in year_distribution:
                year_distribution[decade_label] = 0
            year_distribution[decade_label] += 1
    
    # 转换为列表并排序
    year_data = sorted(year_distribution.items(), key=lambda x: int(x[0][:-1]))
    
    # 类型分布
    genre_distribution = {}
    for movie in movies:
        if "genre" in movie and movie["genre"] and movie["genre"] != "未知":
            genres = [g.strip() for g in movie["genre"].split("/")]
            for genre in genres:
                if genre not in genre_distribution:
                    genre_distribution[genre] = 0
                genre_distribution[genre] += 1
    
    # 转换为列表并排序，取前10个
    genre_data = sorted(genre_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "rating_distribution": rating_data,
        "year_distribution": year_data,
        "genre_distribution": genre_data
    }
