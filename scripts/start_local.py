"""启动当前项目的 MySQL 与 Streamlit，后台进程不弹出额外窗口。"""
from pathlib import Path
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from retail.config import engine
from sqlalchemy import text


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):
            return True
    except OSError:
        return False


def background(name,args):
    with (ROOT/f'.runtime/{name}.stdout.log').open('a',encoding='utf-8') as out, (ROOT/f'.runtime/{name}.stderr.log').open('a',encoding='utf-8') as err:
        process=subprocess.Popen(args,cwd=ROOT,stdout=out,stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (ROOT/f'.runtime/{name}.pid').write_text(str(process.pid))
    return process


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    datadir=ROOT/'.runtime/mysql-data'
    if not datadir.exists() or not (ROOT/'.env').exists():
        raise RuntimeError('请先按 README 初始化项目 MySQL 实例与 .env。')
    if not listening(3307):
        binary=shutil.which('mysqld')
        if not binary:
            raise RuntimeError('找不到 mysqld，请将 MySQL bin 加入 PATH。')
        background('mysql',[binary,'--no-defaults',f'--basedir={Path(binary).parents[1].as_posix()}',
                           f'--datadir={datadir.as_posix()}','--port=3307','--bind-address=127.0.0.1',
                           '--mysqlx=0','--skip-log-bin','--innodb-buffer-pool-size=128M','--console'])
        for _ in range(40):
            if listening(3307):break
            time.sleep(.5)
    db=engine()
    with db.connect() as conn:
        actual=Path(conn.execute(text('SELECT @@datadir')).scalar()).resolve()
        if actual!=datadir.resolve():
            raise RuntimeError('3307 被其他 MySQL 实例占用，已停止启动。')
    if not listening(8502):
        background('dashboard',[sys.executable,'-m','streamlit','run','app.py','--server.port=8502',
                                '--server.address=127.0.0.1','--server.headless=true','--browser.gatherUsageStats=false'])
    for _ in range(40):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8502/_stcore/health',timeout=1) as response:
                if response.read()==b'ok': break
        except OSError:
            time.sleep(.5)
    else:
        raise RuntimeError('看板未就绪，请检查 .runtime/dashboard.stderr.log。')
    print('项目已运行：http://127.0.0.1:8502')
    if not args.no_browser:
        import webbrowser
        webbrowser.open('http://127.0.0.1:8502')


if __name__=='__main__':
    main()
