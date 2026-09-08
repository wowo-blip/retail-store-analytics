"""首次在 Windows 本地配置独立 MySQL（需事先安装 MySQL 8.4 并加入 PATH）。"""
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.start_local import listening,background


def main():
    runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
    datadir=runtime/'mysql-data'
    binary=shutil.which('mysqld')
    if not binary:raise RuntimeError('找不到 mysqld，请安装 MySQL 8.4 并将 bin 加入 PATH。')
    if not datadir.exists():
        if listening(3307):raise RuntimeError('3307 端口已被占用；拒绝初始化其他实例。')
        subprocess.run([binary,'--no-defaults','--initialize-insecure',
                        f'--basedir={Path(binary).parents[1].as_posix()}',f'--datadir={datadir.as_posix()}','--console'],
                       check=True,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    if not (datadir/'mysql').exists():raise RuntimeError('数据目录初始化不完整，请检查 MySQL 日志。')
    if not listening(3307):
        background('mysql',[binary,'--no-defaults',f'--basedir={Path(binary).parents[1].as_posix()}',
                            f'--datadir={datadir.as_posix()}','--port=3307','--bind-address=127.0.0.1',
                            '--mysqlx=0','--skip-log-bin','--innodb-buffer-pool-size=128M','--console'])
        for _ in range(40):
            if listening(3307):break
            time.sleep(.5)
    subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap_db.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'scripts/download_data.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'-m','retail.etl'],check=True,cwd=ROOT)
    subprocess.run([sys.executable,'-m','retail.report'],check=True,cwd=ROOT)
    print('配置完成。执行 start-project.cmd 启动看板。')


if __name__=='__main__':main()
