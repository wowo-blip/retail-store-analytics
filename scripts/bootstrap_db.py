"""只初始化本项目的独立实例；密码在本地随机生成，不输出。"""
from pathlib import Path
import json
import secrets
import pymysql

ROOT = Path(__file__).resolve().parents[1]


def main():
    secret_path = ROOT / '.runtime/db-admin.json'
    if secret_path.exists():
        credentials = json.loads(secret_path.read_text())
    else:
        credentials = {'root': secrets.token_urlsafe(30), 'etl': secrets.token_urlsafe(30), 'reader': secrets.token_urlsafe(30)}
        # Save first so an interrupted provisioning can be resumed without losing the root password.
        secret_path.write_text(json.dumps(credentials), encoding='utf-8')
    try:
        conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password=credentials['root'], autocommit=True)
    except pymysql.err.OperationalError as exc:
        if exc.args[0] != 1045:
            raise
        conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='', autocommit=True)
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT @@datadir')
            actual = Path(cur.fetchone()[0]).resolve()
            assert actual == (ROOT / '.runtime/mysql-data').resolve(), '拒绝操作非项目实例'
            cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (credentials['root'],))
            cur.execute('CREATE DATABASE IF NOT EXISTS retail_analytics CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            for name, key in [('retail_etl', 'etl'), ('retail_reader', 'reader')]:
                cur.execute(f"CREATE USER IF NOT EXISTS '{name}'@'127.0.0.1' IDENTIFIED BY %s", (credentials[key],))
                cur.execute(f"ALTER USER '{name}'@'127.0.0.1' IDENTIFIED BY %s", (credentials[key],))
            cur.execute("GRANT SELECT, INSERT, CREATE, REFERENCES, INDEX ON retail_analytics.* TO 'retail_etl'@'127.0.0.1'")
            cur.execute("GRANT SELECT ON retail_analytics.* TO 'retail_reader'@'127.0.0.1'")
    lines = ['MYSQL_HOST=127.0.0.1', 'MYSQL_PORT=3307', 'MYSQL_DATABASE=retail_analytics',
             'MYSQL_USER=retail_reader', f"MYSQL_PASSWORD={credentials['reader']}",
             'MYSQL_ETL_USER=retail_etl', f"MYSQL_ETL_PASSWORD={credentials['etl']}"]
    (ROOT / '.env').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('MySQL 项目实例已配置：127.0.0.1:3307 / retail_analytics；读写账户分离，密码未输出。')


if __name__ == '__main__':
    main()
