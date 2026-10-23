"""미리보기 빌드(out/preview/index.html)를 Artifact 페이지 본문으로 바꾼다.
문서 뼈대(doctype, html, head, body)는 게시할 때 붙으므로 여기서는 뺀다."""
import re, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
src = ROOT.parent / 'out/preview/index.html'
dst = ROOT.parent / 'out/artifact/saving-share.html'
s = src.read_text(encoding='utf-8')
s = re.sub(r'<!doctype html>\s*', '', s, flags=re.I)
s = re.sub(r'</?(html|head|body)\b[^>]*>\s*', '', s, flags=re.I)
s = re.sub(r'<meta (charset|name="viewport"|name="theme-color"|name="description")[^>]*>\s*', '', s)
s = re.sub(r'<link rel="(manifest|icon)"[^>]*>\s*', '', s)
s = s.replace('<title>세이빙 셰어</title>', '<title>세이빙 셰어</title>\n<meta name="claude:viewport-fit-sides" content="cover">', 1)
# 제목은 앞 8KB 안에 있어야 한다
head, rest = s.split('<title>', 1)
s = '<title>' + rest.split('</title>', 1)[0] + '</title>\n' + head + rest.split('</title>', 1)[1]
dst.write_text(s, encoding='utf-8')
print(dst, len(s.encode()) // 1024, 'KB')
print(s[:600])
