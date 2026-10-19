"""
백업 스냅샷 생성  —  python make_backup.py

실제 API 응답을 web/backup.json 에 저장합니다.  (이 경로 하나만 덮어씁니다)
시연 중에 서버가 죽으면 화면이 이 파일로 버팁니다.

※ 데이터나 코드를 고쳤으면 반드시 다시 돌리세요.
  안 그러면 백업 화면에 옛날 숫자가 뜹니다.

저장 내용
  기존 키 (프론트가 읽음, 이름 유지)
    building · eligibility · baseline · profile · measures · demo
    allocation(19건) · settlement · explain
  추가 키
    meta  — 생성 시각, DB 파일 수정 시각·해시, 데이터 마지막 월, 지표, 평가 구간
            "이 백업은 언제 어떤 데이터로 만들었나"를 숨기지 않기 위함

실행하면 직전 백업과 지표를 비교해 출력합니다. 다르면 이유를 확인하세요.
"""

import hashlib
import json
import os
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

import main
from main import (get_building, get_eligibility, get_baseline, get_demo,
                  get_settlement, get_explain, get_profile, get_measures,
                  post_allocation, AllocationRequest)

# 화면 ① 의 기본 주소 코드와 같아야 합니다
CODES = ("11680", "10100", "0761", "0026")
OUT = "web/backup.json"


def _db_meta():
    p = main.DB
    if not os.path.exists(p):
        return {"path": p, "exists": False}
    with open(p, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:12]
    return {
        "path": p,
        "exists": True,
        "modified": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds"),
        "sha256_12": digest,
    }


def build():
    main._cache.clear()                     # 반드시 현재 DB 로 다시 계산
    demo = get_demo()
    base = get_baseline(1)
    snap = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "db": _db_meta(),
            "data_last_month": base["monthly_baseline"][-1]["ym"],
            "metrics": base["metrics"],
            "verdict": base["verdict"],
            "eval_window": base["eval_window"],
            "note": "지표는 정렬된 데이터의 앞 24행 학습 · 다음 12행 검증 결과이며 전체 기간 성능이 아닙니다",
        },
        "building": get_building(*CODES),
        "eligibility": get_eligibility(1),
        "baseline": base,
        "profile": get_profile(1),
        "measures": get_measures(1),
        "demo": demo,
        # 슬라이더가 5% 단위이므로 19가지를 모두 저장해 둔다
        "allocation": [
            post_allocation(AllocationRequest(
                invest_won=50_000_000, owner_ratio=r / 100, period_years=10))
            for r in range(5, 100, 5)
        ],
        "settlement": {},
        "explain": {},
    }

    cases = [(c["year"], c["quarter"]) for c in demo["cases"]] + [(2026, 3)]
    for y, q in cases:
        s = get_settlement(year=y, quarter=q, owner_ratio=0.7)
        snap["settlement"][f"{y}Q{q}"] = s
        for m in s["months"]:
            if m["ym"] not in snap["explain"]:
                snap["explain"][m["ym"]] = get_explain(1, m["ym"])

    # 직전 백업과 비교 — 숫자가 바뀌었으면 보여준다
    prev = None
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            prev = None

    os.makedirs("web", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))

    kb = os.path.getsize(OUT) / 1024
    print(f"\n  {OUT}  {kb:.1f} KB")
    print(f"  DB {snap['meta']['db']}")
    print(f"  데이터 마지막 월 {snap['meta']['data_last_month']} · "
          f"평가 {base['eval_window']['train']} 학습 / {base['eval_window']['valid']} 검증")
    print(f"  지표 {base['metrics']}  판정 {base['verdict']}")
    if prev:
        pm = prev.get("baseline", {}).get("metrics")
        pg = prev.get("meta", {}).get("generated_at", "기록 없음")
        if pm != base["metrics"]:
            print(f"  ⚠ 직전 백업({pg}) 지표 {pm} → 지금 {base['metrics']}")
        missing = set(prev) - set(snap)
        if missing:
            print(f"  ⚠ 직전 백업에 있던 키가 빠짐: {sorted(missing)}")
    print(f"  분배안 {len(snap['allocation'])}건 · "
          f"정산 {len(snap['settlement'])}분기 · 설명 {len(snap['explain'])}개월")
    print(f"  시연 분기: {', '.join(snap['settlement'])}")
    print("\n  발표 노트북에 이 파일을 같이 올리세요.\n")


if __name__ == "__main__":
    build()
