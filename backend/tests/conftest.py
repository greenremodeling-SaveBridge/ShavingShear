"""
테스트용 합성 DB.

※ 실제 공공데이터가 아닙니다. 코드 로직(정산 상태·절감량·설명)을 검증하기 위한 가짜 값입니다.
  실제 지표 검증은 verify_metrics.py 를 실제 savebridge.db 에 돌려서 합니다.
"""
import math
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MISSING = {"202110", "202208"}          # 실제 원자료와 같은 결측월


def _months():
    out = []
    for y in range(2020, 2027):
        for m in range(1, 13):
            ym = f"{y}{m:02d}"
            if ym > "202604":
                return out
            out.append(ym)
    return out


def make_db(path, retrofit_ym=None):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE building (bld_id INTEGER PRIMARY KEY, addr TEXT, sido TEXT, sigungu TEXT,
            bjdong TEXT, bun TEXT, ji TEXT, area REAL, struct TEXT, purpose TEXT,
            use_apr_day TEXT, year INTEGER, floors TEXT, retrofit_ym TEXT);
        CREATE TABLE usage_monthly (bld_id INTEGER, ym TEXT, elec REAL, gas REAL, total REAL,
            PRIMARY KEY (bld_id, ym));
        CREATE TABLE weather_monthly (ym TEXT PRIMARY KEY, hdd REAL, cdd REAL, days INTEGER);
    """)
    conn.execute("INSERT INTO building VALUES (1,'서울 ○○구 ○○동','서울특별시','11680','10100',"
                 "'0761','0026',1975.78,'철근콘크리트구조','제1종근린생활시설','20100218',2010,"
                 "'지상5/지하3',?)", (retrofit_ym,))
    for i, ym in enumerate(_months()):
        m = int(ym[4:])
        temp = 12.5 - 14 * math.cos((m - 1) / 12 * 2 * math.pi)
        hdd = max(0.0, 21.5 - temp)
        cdd = max(0.0, temp - 16.0)
        days = 30
        conn.execute("INSERT INTO weather_monthly VALUES (?,?,?,?)", (ym, hdd, cdd, days))
        elec = (550 + 25 * cdd + 8 * hdd + (i % 3) * 10) * days
        gas = (40 * hdd + 60) * days
        if "202304" <= ym <= "202310":
            gas *= 2.1                  # 2023 운영 변화 재현 (이상 감지 대상)
        if ym in MISSING:
            conn.execute("INSERT INTO usage_monthly VALUES (1,?,NULL,?,NULL)", (ym, gas))
        else:
            conn.execute("INSERT INTO usage_monthly VALUES (1,?,?,?,?)", (ym, elec, gas, elec + gas))
    conn.commit()
    conn.close()


@pytest.fixture
def api(tmp_path, monkeypatch):
    """공사 전(retrofit_ym = NULL) 합성 DB에 붙은 API"""
    monkeypatch.setenv("SB_USE_GEMINI", "0")
    import main
    db = tmp_path / "t.db"
    make_db(db)
    monkeypatch.setattr(main, "DB", str(db))
    main._cache.clear()
    from fastapi.testclient import TestClient
    yield TestClient(main.app), main, db
    main._cache.clear()
