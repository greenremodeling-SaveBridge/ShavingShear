"""Pretendard Variable 을 화면에 쓰는 글자만 남겨 woff2 로 줄인다.

포함 범위
  - KS X 1001 한글 2,350자 (일상 문장 거의 전부)
  - 한글 자모 (입력 중 조합 글자)
  - 영문·숫자·문장부호·단위 기호
  - src/ 와 ../web/backup.json 에 실제로 나오는 모든 글자

실행:  python3 scripts/subset-font.py
"""
import pathlib
from fontTools import subset

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'node_modules/pretendard/dist/web/variable/woff2/PretendardVariable.woff2'
OUT = ROOT / 'src/assets/PretendardSubset.woff2'

chars = {chr(c) for c in range(0x20, 0x7F)}
chars |= set('·×÷±°²³µ©®™€₩•…‘’“”–—−≤≥≈≠∞→←↑↓↗↘○●◇◆□■▲▼△▽★☆①②③④⑤⑥⑦⑧⑨⑩₂ℓ㎡㎾ ')
for b1 in range(0xB0, 0xC9):
    for b2 in range(0xA1, 0xFF):
        try:
            chars.add(bytes([b1, b2]).decode('euc-kr'))
        except UnicodeDecodeError:
            pass
chars |= {chr(c) for c in range(0x3131, 0x318F)}
files = list((ROOT / 'src').rglob('*.js*')) + [ROOT / 'index.html', ROOT.parent / 'web/backup.json']
for f in files:
    if f.exists():
        chars |= set(f.read_text(encoding='utf-8'))
chars = {c for c in chars if c.isprintable() or c == ' '}

opts = subset.Options()
opts.flavor = 'woff2'
opts.layout_features = ['*']
opts.name_IDs = ['*']
opts.notdef_outline = True
font = subset.load_font(str(SRC), opts)
sub = subset.Subsetter(opts)
sub.populate(unicodes=[ord(c) for c in chars])
sub.subset(font)
OUT.parent.mkdir(parents=True, exist_ok=True)
subset.save_font(font, str(OUT), opts)
print(f'{len(chars)} chars -> {OUT.name} {OUT.stat().st_size/1024:.0f} KB')
