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
            assert Path(cur.fetchone()[0]).resolve()==(ROOT/'.runtime/mysql-data').resolve()
            cur.execute('SHUTDOWN')
    print('Project MySQL stopped safely.')
