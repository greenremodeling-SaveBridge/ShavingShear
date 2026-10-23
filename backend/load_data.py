import sqlite3
import pandas as pd

DB = "savebridge.db"
BASE_HEAT = 21.5
BASE_COOL = 16.0


def create_tables(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS building;
        DROP TABLE IF EXISTS usage_monthly;
        DROP TABLE IF EXISTS weather_monthly;
        DROP TABLE IF EXISTS baseline_result;
        DROP TABLE IF EXISTS settlement;

        CREATE TABLE building (
            bld_id      INTEGER PRIMARY KEY,
            addr        TEXT,
            sido        TEXT,
            sigungu     TEXT,
            bjdong      TEXT,
            bun         TEXT,
            ji          TEXT,
            area        REAL,
            struct      TEXT,
            purpose     TEXT,
            use_apr_day TEXT,
            year        INTEGER,
            floors      TEXT,
            retrofit_ym TEXT,
            data_source TEXT    -- measured / simulated_copy_of_bld1
        );

        CREATE TABLE usage_monthly (
            bld_id  INTEGER,
            ym      TEXT,
            elec    REAL,
            gas     REAL,
            total   REAL,
            PRIMARY KEY (bld_id, ym)
        );

        CREATE TABLE weather_monthly (
            ym    TEXT PRIMARY KEY,
            hdd   REAL,
            cdd   REAL,
            days  INTEGER
        );

        CREATE TABLE baseline_result (
            bld_id    INTEGER,
            ym        TEXT,
            actual    REAL,
            baseline  REAL,
            PRIMARY KEY (bld_id, ym)
        );

        CREATE TABLE settlement (
            bld_id      INTEGER,
            period      TEXT,
            saving_won  INTEGER,
            owner_won   INTEGER,
            tenant_won  INTEGER,
            verdict     TEXT,
            status      TEXT,
            PRIMARY KEY (bld_id, period)
        );
    """)
    print("  테이블 5개 생성 완료")


def load_building(conn):
    # 1. 서울 기존 샘플 건물 (ID 1)
    conn.execute("""
        INSERT INTO building VALUES
        (1, '서울 ○○구 ○○동', '서울특별시', '11680', '10100', '0761', '0026',
         1975.78, '철근콘크리트구조', '제1종근린생활시설', '20100218', 2010, '지상5/지하3', NULL, 'measured')
    """)

    # 2. 양평 블룸비스타호텔앤컨퍼런스 (ID 2)
    conn.execute("""
        INSERT INTO building VALUES
        (2, '경기도 양평군 강하면 강남로 316', '경기도', '41830', '32330', '1235', '0000',
         12500.0, '철근콘크리트구조', '숙박시설(관광호텔)', '20140515', 2014, '지상8/지하2', NULL, 'simulated_copy_of_bld1')
    """)
    print("  건물 2건 입력 완료 (1: 서울 샘플, 2: 양평 블룸비스타)")


# ※ 건물 2(양평 블룸비스타)에는 건물 1(서울 샘플)의 사용량이 그대로 복사된다.
#   블룸비스타의 실제 에너지 사용량이 아니다. 화면·발표에서 건물 2의 수치를
#   그 호텔의 사용량처럼 보여주면 안 된다.
def load_usage(conn):
    e = pd.read_csv("energy.csv", dtype={"ym": str})
    g = pd.read_csv("gas.csv", dtype={"ym": str})
    df = e.merge(g, on="ym", how="outer")
    df["total"] = df["elec"] + df["gas"]
    print(f"  원자료: 전기 {e['elec'].notna().sum()}개월 · 가스 {g['gas'].notna().sum()}개월 · "
          f"병합 {len(df)}행 ({df['ym'].min()}~{df['ym'].max()})")
    dup = df["ym"][df["ym"].duplicated()].tolist()
    if dup:
        print(f"  ⚠ 중복 월: {dup}")
    print(f"  total 결측(전기·가스 중 하나 없음): {df.loc[df['total'].isna(), 'ym'].tolist()}")

    # 이상치 제거 — 중앙값 2배 초과 행은 DB에 아예 들어가지 않는다.
    # 지표에 영향을 주므로 어떤 달이 빠졌는지 반드시 남긴다.
    med = df["total"].median()
    dropped = df[df["total"] > med * 2]
    if len(dropped):
        print(f"  ⚠ 이상치로 제외(중앙값 {med:,.0f}의 2배 초과): "
              f"{dropped[['ym', 'total']].to_dict('records')}")
    else:
        print(f"  이상치 제외 없음 (중앙값 {med:,.0f})")
    df = df[(df["total"] <= med * 2) | df["total"].isna()]

    for b_id in [1, 2]:
        df_b = df.copy()
        df_b["bld_id"] = b_id
        df_b[["bld_id", "ym", "elec", "gas", "total"]].to_sql(
            "usage_monthly", conn, if_exists="append", index=False
        )
    print(f"  사용량 입력 완료 (건물 2개분)")


def load_weather(conn):
    d = pd.read_csv("daily_temp.csv", parse_dates=["tm"])
    d["avgTa"] = pd.to_numeric(d["avgTa"], errors="coerce")
    d = d.dropna(subset=["avgTa"])
    d["hdd"] = (BASE_HEAT - d["avgTa"]).clip(lower=0)
    d["cdd"] = (d["avgTa"] - BASE_COOL).clip(lower=0)

    # 'M' 대신 'ME' 사용
    grp = d.set_index("tm")[["hdd", "cdd"]].resample("ME")
    m = grp.mean().round(3)
    m["days"] = grp.size()
    # days 는 '기온 값이 있는 날 수'다. 달력 일수와 다르면 일평균 사용량(total/days)이 부풀려진다.
    cal = pd.Series(m.index.days_in_month, index=m.index)
    short = m[m["days"] < cal]
    if len(short):
        print(f"  ⚠ 기온 결측일이 있는 달 (기온일수/달력일수): "
              f"{[(i.strftime('%Y%m'), int(r.days), int(cal[i])) for i, r in short.iterrows()]}")
    excluded = m[m["days"] < 25]
    if len(excluded):
        print(f"  ⚠ 기온 25일 미만으로 제외: {[i.strftime('%Y%m') for i in excluded.index]}")
    m = m[m["days"] >= 25]
    m.index = m.index.strftime("%Y%m")
    m.index.name = "ym"
    m.reset_index().to_sql("weather_monthly", conn, if_exists="append", index=False)
    print(f"  기상 입력 완료")


if __name__ == "__main__":
    conn = sqlite3.connect(DB)
    create_tables(conn)
    load_building(conn)
    load_usage(conn)
    load_weather(conn)
    conn.commit()
    conn.close()
    print("DB regenerated with 2 buildings successfully.")
