import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 日志目录
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 文件路径
JSON_FILE = os.path.join(DATA_DIR, 'movies.json')
STATS_FILE = os.path.join(DATA_DIR, 'stats.json')  # 统计结果文件
LOG_FILE = os.path.join(LOG_DIR, 'crawler.log')

# 爬虫配置
BASE_URL = "https://movie.douban.com/top250"
MAX_RETRIES = 3
CACHE_EXPIRE = 3600  # 缓存过期时间（秒）

# 网站配置
SITE_NAME = "豆瓣电影Top250爬虫"
