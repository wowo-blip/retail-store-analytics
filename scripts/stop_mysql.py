from pathlib import Path
import json
import pymysql
ROOT=Path(__file__).resolve().parents[1]
credentials=json.loads((ROOT/'.runtime/db-admin.json').read_text())
try:
    conn=pymysql.connect(host='127.0.0.1',port=3307,user='root',password=credentials['root'])
except pymysql.err.OperationalError as exc:
    if exc.args[0]==2003:
        print('Project MySQL is already stopped.')
    else:raise
else:
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT @@datadir')
            actual=Path(cur.fetchone()[0]).resolve()
            expected=(ROOT/'.runtime/mysql-data').resolve()
            if actual!=expected:
                raise RuntimeError(f'拒绝停止非项目实例：数据目录应为 {expected}，实际为 {actual}')
            cur.execute('SHUTDOWN')
    print('Project MySQL stopped safely.')
