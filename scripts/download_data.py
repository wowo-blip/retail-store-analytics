"""从 UCI 官方地址下载 Online Retail II，并校验固定版本哈希。"""
from hashlib import sha256
from pathlib import Path
import sys
from urllib.request import urlopen
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from retail.config import SOURCE,SOURCE_URL,SOURCE_ZIP,SOURCE_ZIP_SHA256


def file_sha256(path):
    digest=sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    SOURCE_ZIP.parent.mkdir(parents=True,exist_ok=True)
    SOURCE.parent.mkdir(parents=True,exist_ok=True)
    if not SOURCE_ZIP.exists() or file_sha256(SOURCE_ZIP)!=SOURCE_ZIP_SHA256:
        temporary=SOURCE_ZIP.with_suffix('.download')
        with urlopen(SOURCE_URL,timeout=60) as response, temporary.open('wb') as target:
            while block:=response.read(1024*1024):
                target.write(block)
        if file_sha256(temporary)!=SOURCE_ZIP_SHA256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError('UCI 下载文件的 SHA-256 与项目固定版本不一致。')
        temporary.replace(SOURCE_ZIP)
    with ZipFile(SOURCE_ZIP) as archive:
        member='online_retail_II.xlsx'
        if member not in archive.namelist():
            raise RuntimeError(f'UCI ZIP 缺少预期文件：{member}')
        with archive.open(member) as source, SOURCE.open('wb') as target:
            while block:=source.read(1024*1024):
                target.write(block)
    print(f'数据已就绪：{SOURCE}；ZIP SHA-256={SOURCE_ZIP_SHA256}')


if __name__=='__main__':
    main()
