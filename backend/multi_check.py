"""
세이빙 셰어 — 다건물 기저선 검증  (2026-10-22)

같은 기저선 모델(baseline.py)을 서울 비주거 건물 여러 동에 그대로 돌려서
"한 건물에서만 되는 것 아니냐"는 질문에 숫자로 답한다.

  실행:  backend 폴더에서
         .venv\\Scripts\\python multi_check.py              (Windows, 켜기.bat 을 한 번 돌린 뒤)
         python multi_check.py --n 30 --dong 11680-10100   (옵션)

  필요:  공공데이터포털 인증키 (건축HUB 건축물대장 + 건물에너지 활용신청이 된 키)
         실행하면 키를 물어본다. 환경변수 DATA_GO_KR_KEY 로 넣어도 된다. 키는 파일에 저장하지 않는다.

  결과:  multi_check_out/ 폴더
           buildings.csv   대상 건물 목록 (주소는 지번까지만)
           results.csv     건물별 지표 (예선 방식 · 공사 직전 36개월 방식)
           summary.md      발표용 요약표
           cache/          API 응답 저장 — 중간에 끊겨도 다시 실행하면 이어서 한다

■ 공정하게 하기 위한 규칙 (발표 때 그대로 말할 수 있게)
  1. 건물은 조건(비주거 · 연면적 · 준공연도 · 한 지번에 건물 하나)만 걸고 무작위로 뽑는다. 결과를 보고 고르지 않는다.
  2. 모든 건물에 같은 코드, 같은 기준(baseline.py)을 쓴다. 건물마다 손대지 않는다.
  3. 데이터가 부족한 건물(36개월 미만 등)도 '제외 이유'와 함께 결과에 남긴다.
  4. 기상은 서울 ASOS(108) 하나를 쓴다 → 대상도 서울 건물로 한정한다.
"""

import argparse
import json
import os
import random
import sqlite3
import sys
import time
import warnings

import pandas as pd
import requests

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import baseline as B  # noqa: E402

OUT = os.path.join(HERE, "multi_check_out")
CACHE = os.path.join(OUT, "cache")
DB = os.path.join(HERE, "savebridge.db")

# 엔드포인트 — 예선 때 직접 호출로 확인한 주소 (https 는 실패, http 로)
URL_TITLE = "http://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
URL_ELEC = "http://apis.data.go.kr/1613000/BldEngyHubService/getBeElctyUsgInfo"
URL_GAS = "http://apis.data.go.kr/1613000/BldEngyHubService/getBeGasUsgInfo"

# 기본 대상 동 — 시연 건물과 같은 동(강남구 역삼동). 다른 동은 --dong 으로 추가 (시군구코드-법정동코드)
DEFAULT_DONGS = ["11680-10100"]
RESIDENTIAL = ("주택", "아파트", "다세대", "연립", "다가구", "기숙사")

KEY = None


# ───────────────────────── API ─────────────────────────
SCHEME = {"first": "http"}      # 되는 쪽을 기억한다 (예선 때는 http 만 됐고, 포털 안내는 https)


def swap(url, scheme):
    return scheme + "://" + url.split("://", 1)[1]


def fetch(url, params, tries=6, quiet=False):
    """http/https 를 번갈아 시도. 공급기관 서버가 느릴 때(코드 05 SERVICETIMEOUT · '서비스 연결실패')는 기다렸다 다시.
    반환: (dict 또는 None, 마지막 원문)"""
    p = dict(params, serviceKey=KEY, _type="json")
    last = ""
    for i in range(tries):
        sc = SCHEME["first"] if i % 2 == 0 else ("https" if SCHEME["first"] == "http" else "http")
        try:
            r = requests.get(swap(url, sc), params=p, timeout=40)
            r.encoding = "utf-8"
            last = r.text
            if "LIMITED_NUMBER" in last:
                sys.exit("\n오늘 호출 한도를 넘었어요. 내일 다시 실행하면 받은 데까지 이어서 해요.")
            if "SERVICE_KEY_IS_NOT_REGISTERED" in last:
                sys.exit("\n등록되지 않은 키라고 나와요. 활용신청이 '승인'인지, 키가 맞는지 확인해 주세요.")
            try:
                d = r.json()
            except ValueError:
                d = None
            if d and "response" in d:
                SCHEME["first"] = sc
                return d, last
            why = "서비스 연결실패(공급기관 서버 응답 없음)" if ("SERVICETIMEOUT" in last or "<returnReasonCode>05" in last) else last[:120].replace("\n", " ")
        except requests.RequestException as e:
            why = type(e).__name__
        wait = min(60, 3 * 2 ** i)
        if not quiet:
            print(f"  {sc} 실패 → {wait}초 뒤 다시 ({i + 1}/{tries}) · {why}")
        time.sleep(wait)
    return None, last


def call(url, params, tries=6):
    """캐시 → 호출. 실패하면 None (그 달은 결측으로 둔다). 성공한 응답만 저장한다"""
    os.makedirs(CACHE, exist_ok=True)
    tag = url.rsplit("/", 1)[-1] + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    path = os.path.join(CACHE, tag.replace(":", "") + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    d, _ = fetch(url, params, tries)
    if d is None:
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    time.sleep(0.2)
    return d


def clean_key(k):
    """붙여넣기로 섞이는 따옴표·공백·제어문자(Ctrl+V 가 \x16 으로 들어오는 경우 등)를 걷어낸다"""
    k = "".join(ch for ch in str(k or "") if ch.isprintable()).strip().strip('"').strip("'").strip()
    if k.lower().startswith("servicekey="):
        k = k.split("=", 1)[1]
    return k


def read_key():
    """키 파일(backend\\data_go_kr_key.txt) → 환경변수 → 직접 입력 순서. 입력한 키는 저장하지 않는다"""
    path = os.path.join(HERE, "data_go_kr_key.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            k, src = f.read(), "data_go_kr_key.txt"
    elif os.environ.get("DATA_GO_KR_KEY"):
        k, src = os.environ["DATA_GO_KR_KEY"], "환경변수"
    else:
        print("공공데이터포털 '일반 인증키'를 붙여넣고 Enter (마우스 오른쪽 클릭으로 붙여넣으면 확실해요)")
        k, src = input("인증키: "), "직접 입력"
    k = clean_key(k)
    if not k:
        sys.exit("키가 비어 있어요.")
    print(f"  키 확인: {src} · {len(k)}자 · {k[:4]}…{k[-4:]}")
    return k


def check_key():
    """시연 건물(역삼동 761-26)로 먼저 한 번 불러서, 키·서버 문제면 바로 알려 준다"""
    p = {"sigunguCd": "11680", "bjdongCd": "10100", "bun": "0761", "ji": "0026", "numOfRows": 1, "pageNo": 1}
    for name, url, extra in (("건축물대장", URL_TITLE, {}), ("건물에너지(전기)", URL_ELEC, {"useYm": "202401"})):
        d, raw = fetch(url, dict(p, **extra), tries=6)
        if d is None:
            sys.exit(f"  {name}: 여러 번 시도했지만 응답이 없어요. 공급기관(건축HUB) 서버 문제일 가능성이 커요.\n"
                     f"  10~30분 뒤 다시 실행해 주세요. 마지막 응답: {raw[:200]}")
        print(f"  {name}: 정상 ({SCHEME['first']})")


def items_of(d):
    if not d:
        return []
    body = d["response"].get("body") or {}
    it = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    x = it.get("item") or []
    return x if isinstance(x, list) else [x]


# ───────────────────────── 1. 건물 고르기 ─────────────────────────
def list_buildings(sigungu, bjdong):
    rows, page = [], 1
    while True:
        d = call(URL_TITLE, {"sigunguCd": sigungu, "bjdongCd": bjdong, "numOfRows": 100, "pageNo": page})
        xs = items_of(d)
        rows += xs
        total = int(((d or {}).get("response", {}).get("body", {}) or {}).get("totalCount") or 0)
        print(f"  건축물대장 {sigungu}-{bjdong} {len(rows)}/{total}", end="\r")
        if not xs or len(rows) >= total:
            break
        page += 1
    print()
    return rows


def pick(rows, n, seed):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["bun"] = df["bun"].astype(str).str.zfill(4)
    df["ji"] = df["ji"].astype(str).str.zfill(4)
    df["lot"] = df["sigunguCd"].astype(str) + "-" + df["bjdongCd"].astype(str) + "-" + df["bun"] + "-" + df["ji"]
    cnt = df.groupby("lot").size()
    df = df[df["lot"].map(cnt) == 1]                                        # 한 지번에 건물 하나 (에너지가 지번 단위라서)
    df = df[~df["mainPurpsCdNm"].fillna("").str.contains("|".join(RESIDENTIAL))]   # 비주거
    df["totArea"] = pd.to_numeric(df["totArea"], errors="coerce")
    df = df[(df["totArea"] >= 500) & (df["totArea"] <= 30000)]
    df["year"] = pd.to_numeric(df["useAprDay"].astype(str).str[:4], errors="coerce")
    df = df[(df["year"] >= 1980) & (df["year"] <= 2016)]                   # 이자지원 요건(2016 이전 사용승인)과 맞춤
    print(f"  조건을 만족하는 건물 {len(df)}동 → 무작위 {min(n, len(df))}동 (seed {seed})")
    random.seed(seed)
    idx = sorted(random.sample(list(df.index), min(n, len(df))))
    return df.loc[idx, ["lot", "sigunguCd", "bjdongCd", "bun", "ji", "platPlc", "mainPurpsCdNm", "totArea", "year"]]


# ───────────────────────── 2. 사용량 받기 ─────────────────────────
def months(last):
    out, y, m = [], 2020, 1
    while f"{y}{m:02d}" <= last:
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def usage(b, yms):
    rec = []
    for ym in yms:
        row = {"ym": ym}
        for col, url in (("elec", URL_ELEC), ("gas", URL_GAS)):
            xs = items_of(call(url, {"sigunguCd": b.sigunguCd, "bjdongCd": b.bjdongCd, "bun": b.bun, "ji": b.ji,
                                     "useYm": ym, "numOfRows": 10, "pageNo": 1}))
            row[col] = float(xs[0]["useQty"]) if xs and xs[0].get("useQty") not in (None, "") else None
        rec.append(row)
    return pd.DataFrame(rec)


# ───────────────────────── 3. 같은 모델로 평가 ─────────────────────────
def weather():
    with sqlite3.connect(DB) as c:
        return pd.read_sql("SELECT ym, hdd, cdd, days FROM weather_monthly", c)


def clean(u, w):
    """load_data.py 와 같은 정리: 전기·가스 합계, 중앙값 2배 초과 달 제외, 기상과 결합"""
    u = u.copy()
    gas_any = u["gas"].notna().any()
    u["gas"] = u["gas"].fillna(0) if not gas_any else u["gas"]
    u["total"] = u["elec"] + u["gas"]
    u = u[u["total"].notna() & (u["total"] > 0)]
    if len(u):
        med = u["total"].median()
        u = u[u["total"] <= med * 2]
    return u.merge(w, on="ym").sort_values("ym").reset_index(drop=True), gas_any


def evaluate(df):
    out = {}
    for mode in ("legacy", "recent"):
        B.BASELINE_MODE = mode
        try:
            r = B.run_baseline(df[["ym", "elec", "gas", "total", "hdd", "cdd", "days"]])
            m = r["metrics"]
            out[mode] = {"cv": m["cv_rmse"], "r2": m["r2"], "nmbe": m.get("nmbe"),
                         "train": r["eval_window"]["train"], "valid": r["eval_window"]["valid"]}
        except Exception as e:  # noqa: BLE001
            out[mode] = {"error": str(e)[:80]}
    B.BASELINE_MODE = "recent"
    return out


def summarize(res):
    ok = res[res["status"] == "평가"]
    lines = ["# 다건물 기저선 검증 요약", "",
             f"- 대상: 서울 비주거 건물 무작위 {len(res)}동 (한 지번 한 건물 · 연면적 500~30,000㎡ · 1980~2016 사용승인)",
             f"- 평가 가능: {len(ok)}동 · 제외 {len(res) - len(ok)}동 (이유는 results.csv)",
             "- 모델: 세이빙 셰어와 같은 코드(baseline.py) · 입력 난방도일·냉방도일 · 일평균 사용량",
             "- 기상: 서울 ASOS(108) 일자료", ""]
    if len(ok):
        lines += ["| 방식 | CV(RMSE) ≤ 15% | NMBE ±5% | 둘 다 (ASHRAE G14 월별) | R² ≥ 0.75 | CV 중앙값 | R² 중앙값 |",
                  "|---|---|---|---|---|---|---|"]
        for mode, name in (("legacy", "예선 방식 (2020~ 앞 36개월)"), ("recent", "공사 직전 36개월 (현재)")):
            cv, r2, nb = ok[f"{mode}_cv"], ok[f"{mode}_r2"], ok[f"{mode}_nmbe"]
            n = cv.notna().sum()
            if not n:
                continue
            a = (cv <= 15).sum()
            b_ = (nb.abs() <= 5).sum()
            both = ((cv <= 15) & (nb.abs() <= 5)).sum()
            c = (r2 >= 0.75).sum()
            lines.append(f"| {name} | {a}/{n} ({a / n:.0%}) | {b_}/{n} ({b_ / n:.0%}) | **{both}/{n} ({both / n:.0%})** | "
                         f"{c}/{n} ({c / n:.0%}) | {cv.median():.1f}% | {r2.median():.3f} |")
        lines += ["", "※ 기준을 통과하지 못한 건물은 세이빙 셰어가 금액을 확정하지 않고 '범위로 제시'하는 대상입니다.",
                  "※ 이 결과는 '모델이 공사 전 사용량을 얼마나 재현하는가'이며, 그린리모델링 절감 효과를 입증하는 값이 아닙니다."]
    return "\n".join(lines)


def main():
    global KEY
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="뽑을 건물 수 (기본 30 · 호출 수 ≈ n × 개월 × 2)")
    ap.add_argument("--dong", action="append", help="시군구코드-법정동코드 (여러 번 가능). 기본 강남구 역삼동")
    ap.add_argument("--last", default="202604", help="마지막 사용연월 (공개 시차 약 4개월)")
    ap.add_argument("--seed", type=int, default=20261022)
    a = ap.parse_args()

    KEY = read_key()
    check_key()
    os.makedirs(OUT, exist_ok=True)

    print("1) 건물 목록 받는 중")
    cand = pd.concat([pick(list_buildings(*d.split("-")), 10 ** 6, a.seed) for d in (a.dong or DEFAULT_DONGS)])
    random.seed(a.seed)
    cand = cand.loc[sorted(random.sample(list(cand.index), min(a.n, len(cand))))] if len(cand) else cand
    cand.to_csv(os.path.join(OUT, "buildings.csv"), index=False, encoding="utf-8-sig")
    if cand.empty:
        sys.exit("조건에 맞는 건물이 없어요. --dong 으로 다른 동을 넣어 보세요.")

    yms, w = months(a.last), weather()
    print(f"2) 사용량 받는 중 — {len(cand)}동 × {len(yms)}개월 × 전기·가스 (처음엔 오래 걸려요. 중단해도 이어서 돼요)")
    res = []
    for i, b in enumerate(cand.itertuples(), 1):
        u = usage(b, yms)
        df, gas_any = clean(u, w)
        row = {"lot": b.lot, "용도": b.mainPurpsCdNm, "연면적": b.totArea, "사용승인": b.year,
               "전기_개월": int(u["elec"].notna().sum()), "가스_개월": int(u["gas"].notna().sum()), "가스_있음": gas_any,
               "평가_개월": len(df)}
        if len(df) < B.TRAIN_MONTHS + B.VALID_MONTHS:
            row["status"] = f"제외: {len(df)}개월 (36개월 미만)"
        else:
            row["status"] = "평가"
            for mode, v in evaluate(df).items():
                for k in ("cv", "r2", "nmbe", "train", "valid", "error"):
                    if k in v:
                        row[f"{mode}_{k}"] = v[k]
        res.append(row)
        rc = row.get("recent_cv")
        print(f"  [{i}/{len(cand)}] {b.lot} {b.mainPurpsCdNm} · {row['status']}" + (f" · CV {rc}% R² {row.get('recent_r2')}" if rc is not None else ""))

    res = pd.DataFrame(res)
    for mode in ("legacy", "recent"):
        for k in ("cv", "r2", "nmbe"):
            if f"{mode}_{k}" not in res:
                res[f"{mode}_{k}"] = None
            res[f"{mode}_{k}"] = pd.to_numeric(res[f"{mode}_{k}"], errors="coerce")
    res.to_csv(os.path.join(OUT, "results.csv"), index=False, encoding="utf-8-sig")
    s = summarize(res)
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as f:
        f.write(s)
    print("\n" + s + f"\n\n저장: {OUT}")


if __name__ == "__main__":
    main()
