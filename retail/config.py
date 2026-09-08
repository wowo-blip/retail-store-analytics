from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, URL

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip'
SOURCE_ZIP_SHA256 = '572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb'
SOURCE_ZIP = ROOT / '.runtime/online-retail-ii.zip'
SOURCE = ROOT / 'data/raw/online_retail_II.xlsx'
PROCESSED = ROOT / 'data/processed/retail_lines.parquet'
REPORTS = ROOT / 'reports'
load_dotenv(ROOT / '.env')


def engine(role='reader'):
    prefix = 'MYSQL_ETL_' if role == 'etl' else 'MYSQL_'
    user = os.getenv(prefix + 'USER')
    password = os.getenv(prefix + 'PASSWORD')
    if not user or not password:
        raise RuntimeError('数据库连接未配置，请按 README 创建 .env。')
    url = URL.create('mysql+pymysql', username=user, password=password,
                     host=os.getenv('MYSQL_HOST', '127.0.0.1'),
                     port=int(os.getenv('MYSQL_PORT', '3307')),
                     database=os.getenv('MYSQL_DATABASE', 'retail_analytics'),
                     query={'charset': 'utf8mb4'})
    return create_engine(url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
