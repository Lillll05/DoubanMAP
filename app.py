from flask import Flask, render_template, request, jsonify, session
import os
import json
import datetime
import threading
import logging
from utils.crawler import DoubanCrawler
from utils.data_processing import clean_data, save_to_json, load_cached_data, get_visualization_data
from config.settings import JSON_FILE, STATS_FILE, SITE_NAME

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')  # 从环境变量获取

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 初始化爬虫实例
crawler = DoubanCrawler()

# 注册模板全局函数
app.jinja_env.globals.update(calculate_duration=crawler.calculate_duration, site_name=SITE_NAME)
@app.route('/')
def index():
    """首页路由，展示电影数据"""
    movies = load_cached_data() or []
    last_update = "无数据"
    
    if movies and len(movies) > 0 and "crawl_time" in movies[0]:
        last_update = movies[0]["crawl_time"]
    
    return render_template('index.html', movies=movies, last_update=last_update, stats=crawler.crawl_stats)

@app.route('/update')
def update_data():
    """手动更新数据路由"""
    try:
        # 获取并验证页数参数
        pages = int(request.args.get('pages', 10))
        if pages < 1 or pages > 10:
            pages = 10
            logger.warning("页数超出有效范围(1-10)，使用默认值10")
        
        save_path = request.args.get('save_path', JSON_FILE)
        logger.info(f"手动触发数据更新，爬取{pages}页，保存路径: {save_path}")
        
        if not save_path:
            save_path = JSON_FILE
            logger.info("save_path为空，使用默认路径")
        
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
                logger.info(f"创建目录: {save_dir}")
            except Exception as e:
                logger.error(f"创建目录失败: {e}")
                return jsonify({
                    "success": False,
                    "message": f"创建目录失败: {str(e)}",
                    "count": 0
                })
        
        # 检查爬虫状态
        if crawler.crawl_stats["status"] == "crawling":
            return jsonify({
                "success": False,
                "message": "已有爬取任务在运行，请稍后再试",
                "count": 0
            })
        
        def crawl_task():
            try:
                new_movies = crawler.crawl_top250(pages)
                cleaned_movies = clean_data(new_movies)
                if save_to_json(cleaned_movies, save_path):
                    logger.info(f"成功保存{pages}页数据到{save_path}")
                else:
                    logger.warning("无新数据需要保存")
            except Exception as e:
                logger.error(f"爬取过程中出错: {e}")
        
        # 启动爬取线程
        crawl_thread = threading.Thread(target=crawl_task)
        crawl_thread.daemon = True
        crawl_thread.start()
        
        return jsonify({
            "success": True,
            "message": f"爬取任务已启动，正在后台爬取{pages}页数据",
            "count": 0,
            "save_path": save_path
        })
    
    except ValueError as e:
        logger.error(f"参数错误: {e}")
        return jsonify({
            "success": False,
            "message": "参数错误，请提供有效的页数",
            "count": 0
        })
    except Exception as e:
        logger.error(f"更新数据时出错: {e}")
        return jsonify({
            "success": False,
            "message": f"更新数据时出错: {str(e)}",
            "count": 0
        })

@app.route('/stats')
def get_stats():
    """获取实时统计数据"""
    return jsonify(crawler.crawl_stats)

@app.route('/visualization')
def visualization():
    """数据可视化页面路由"""
    movies = load_cached_data() or []
    stats_data = get_visualization_data(movies)
    
    return render_template('visualization.html', 
                          movies=movies, 
                          stats=crawler.crawl_stats,
                          stats_data=stats_data)

@app.route('/reset')
def reset_stats():
    """重置统计数据"""
    crawler.crawl_stats = {
        "total_pages": 10,
        "current_page": 0,
        "movies_found": 0,
        "movies_parsed": 0,
        "start_time": None,
        "end_time": None,
        "status": "idle",
        "errors": 0,
        "requests": [],
        "crawl_history": crawler.crawl_stats.get("crawl_history", [])
    }
    crawler.save_stats()
    
    return jsonify({
        "success": True,
        "message": "统计数据已重置"
    })

@app.route('/delete_all')
def delete_all():
    """删除所有本地数据"""
    if crawler.crawl_stats["status"] == "crawling":
        return jsonify({
            "success": False,
            "message": "爬取任务正在运行，请等待完成后再删除数据",
            "count": 0
        })
    
    # 删除所有数据
    deleted_files = []
    if os.path.exists(JSON_FILE):
        try:
            os.remove(JSON_FILE)
            deleted_files.append(JSON_FILE)
        except Exception as e:
            logger.error(f"删除电影数据文件失败: {e}")
    
    if os.path.exists(STATS_FILE):
        try:
            os.remove(STATS_FILE)
            deleted_files.append(STATS_FILE)
        except Exception as e:
            logger.error(f"删除统计数据文件失败: {e}")
    
    # 重置爬虫状态
    crawler.crawl_stats = {
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
    
    return jsonify({
        "success": True,
        "message": f"已删除 {len(deleted_files)} 个数据文件",
        "files": deleted_files
    })

if __name__ == '__main__':
    app.run(debug=True)
