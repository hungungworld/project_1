"""
무역 분석 대시보드
- baci_85_sample.csv (BACI 무역 데이터), country_codes_sample.csv (국가 코드-이름 매핑) 사용
- GitHub 배포를 고려해 모든 경로를 이 파일(app.py) 기준 상대경로로 처리
"""

from pathlib import Path
import base64

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 0. 경로 & 페이지 설정
# =========================================================
BASE_DIR = Path(__file__).resolve().parent

# (수정) data 폴더를 거치지 않고 바로 BASE_DIR에서 CSV 파일을 찾도록 변경했습니다.
BACI_PATH = BASE_DIR / "baci_85_sample.csv"
COUNTRY_PATH = BASE_DIR / "country_codes_sample.csv"

# (수정) 이전에 알려주신 실제 폰트 폴더 구조와 파일명(.ttf)에 맞게 변경했습니다.
FONT_PATH = BASE_DIR / "font" / "Pretendard-Bold.otf"

st.set_page_config(page_title="무역 분석 대시보드", layout="wide")

# =========================================================
# 1. 폰트 적용 (Pretendard)
# =========================================================
@st.cache_data(show_spinner=False)
def load_font_base64(path: Path):
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

_font_b64 = load_font_base64(FONT_PATH)

if _font_b64:
    # (수정) .ttf 파일이므로 opentype 대신 truetype으로 포맷 변경
    st.markdown(
        f"""
        <style>
        @font-face {{
            font-family: 'Pretendard';
            src: url(data:font/truetype;base64,{_font_b64}) format('truetype');
            font-weight: 400;
        }}
        html, body, [class*="css"], .stApp {{
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    PLOT_FONT = "Pretendard, sans-serif"
else:
    st.sidebar.warning(
        f"{FONT_PATH.name} 파일을 찾을 수 없습니다. "
        "리포지토리의 font 폴더에 파일이 있는지 확인해 주세요."
    )
    PLOT_FONT = "sans-serif"

# =========================================================
# 2. 색상 팔레트 (노랑 → 초록)
# =========================================================
HEATMAP_SCALE = [
    [0.0, "#FFF9C4"],   # 연한 노랑 (값이 작음)
    [0.5, "#AED581"],   # 연두
    [1.0, "#1B5E20"],   # 진한 초록 (값이 큼)
]
GRADE_COLORS = {"대": "#1B5E20", "중": "#8BC34A", "소": "#FFF176"}
MISSING_CELL_COLOR = "#D9D9D9"  # 히트맵 결측 셀 배경색

# =========================================================
# 3. 데이터 로드
# =========================================================
@st.cache_data(show_spinner=False)
def load_data():
    if not BACI_PATH.exists() or not COUNTRY_PATH.exists():
        return None, None
    baci = pd.read_csv(BACI_PATH)
    country = pd.read_csv(COUNTRY_PATH)
    return baci, country


baci_raw, country_map = load_data()

if baci_raw is None:
    st.error(
        f"데이터 파일을 찾을 수 없습니다.\n\n"
        f"'{BASE_DIR}' 폴더 안에 baci_85_sample.csv, country_codes_sample.csv "
        f"두 파일이 있는지 확인해 주세요."
    )
    st.stop()


# =========================================================
# 4. 결측치 처리
# =========================================================
def process_missing(df: pd.DataFrame, country_df: pd.DataFrame):
    df = df.copy()
    report = {"원본 행 수": len(df)}

    report["컬럼별_결측치"] = df.isna().sum()

    before = len(df)
    df = df.dropna(subset=["v"])
    report["무역액(v)_결측_제거"] = before - len(df)

    df = df.merge(country_df[["j", "country_name"]], on="j", how="left")
    unmapped = int(df["country_name"].isna().sum())
    df["country_name"] = df["country_name"].fillna(
        df["j"].apply(lambda x: f"기타(코드:{int(x)})")
    )
    report["국가명_미매핑"] = unmapped

    report["처리 후 행 수"] = len(df)
    return df, report

df, missing_report = process_missing(baci_raw, country_map)


# =========================================================
# 5. 무역액 등급(대/중/소) 부여
# =========================================================
def add_grade(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    try:
        df["등급"] = pd.qcut(df["v"], q=3, labels=["소", "중", "대"])
    except ValueError:
        df["등급"] = pd.qcut(df["v"].rank(method="first"), q=3, labels=["소", "중", "대"])
    return df

df = add_grade(df)

# =========================================================
# 6. 사이드바 필터
# =========================================================
st.sidebar.header("필터")

all_countries = sorted(df["country_name"].unique())
selected_countries = st.sidebar.multiselect(
    "국가 선택", options=all_countries, default=all_countries
)

grade_order = ["대", "중", "소"]
selected_grades = st.sidebar.multiselect(
    "무역액 등급 선택 (대·중·소)", options=grade_order, default=grade_order
)

if not selected_countries or not selected_grades:
    st.warning("사이드바에서 국가와 무역액 등급을 하나 이상 선택해 주세요.")
    st.stop()

filtered = df[
    df["country_name"].isin(selected_countries) & df["등급"].isin(selected_grades)
]

# =========================================================
# 7. 본문 - ① 타이틀
# =========================================================
st.title("무역 분석 대시보드")

# =========================================================
# 본문 - ② 결측치 처리 현황
# =========================================================
with st.expander("📋 baci_85_sample.csv 결측치 처리 현황", expanded=True):
    c1, c2, c3 = st.columns(3)
    c1.metric("원본 행 수", f"{missing_report['원본 행 수']:,}")
    c2.metric("무역액(v) 결측 제거", f"{missing_report['무역액(v)_결측_제거']:,}")
    c3.metric("국가명 미매핑(코드 처리)", f"{missing_report['국가명_미매핑']:,}")

    st.caption("컬럼별 결측치 개수 (원본 기준)")
    na_table = missing_report["컬럼별_결측치"].rename("결측치 수").to_frame()
    st.dataframe(na_table, use_container_width=True)
    st.caption(
        "· 무역액(v)이 없는 행은 분석에서 제외했습니다. "
        "· 수입국 코드(j)가 country_codes 목록에 없는 경우 삭제하지 않고 "
        "'기타(코드:번호)'로 표시해 데이터 손실 없이 표시합니다."
    )

# =========================================================
# 본문 - ③ 요약 지표
# =========================================================
col1, col2 = st.columns(2)
col1.metric("총 거래건수", f"{len(filtered):,} 건")
col2.metric("총 수출액(달러)", f"$ {filtered['v'].sum():,.1f}")

st.divider()

# =========================================================
# 본문 - ④ 히트맵 + 등급 분포
# =========================================================
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("국가 × 연도 수출액 히트맵 (상위 8개국)")

    top8 = (
        filtered.groupby("country_name")["v"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .index.tolist()
    )
    years = sorted(df["t"].unique())

    pivot = (
        filtered[filtered["country_name"].isin(top8)]
        .pivot_table(index="country_name", columns="t", values="v", aggfunc="sum")
    )
    pivot = pivot.reindex(index=top8, columns=years)

    z = pivot.values.astype(float)
    text = [
        ["결측치" if pd.isna(v) else f"{v:,.0f}" for v in row] for row in z
    ]

    heatmap = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[str(y) for y in years],
            y=pivot.index.tolist(),
            colorscale=HEATMAP_SCALE,
            text=text,
            texttemplate="%{text}",
            textfont={"size": 12},
            hovertemplate="국가: %{y}<br>연도: %{x}<br>수출액: %{z:,.1f}<extra></extra>",
            hoverongaps=False,
            xgap=3,
            ygap=3,
            colorbar=dict(title="수출액($)"),
        )
    )
    heatmap.update_layout(
        plot_bgcolor=MISSING_CELL_COLOR,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=PLOT_FONT, size=13),
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(heatmap, use_container_width=True)
    st.caption("🔲 회색 칸 = 해당 국가·연도 조합의 거래 데이터가 없음(결측치)")

with col_right:
    st.subheader("무역액 등급 분포")

    grade_counts = (
        filtered["등급"].value_counts().reindex(grade_order).fillna(0).astype(int)
    )
    bar = go.Figure(
        go.Bar(
            x=grade_counts.index.tolist(),
            y=grade_counts.values,
            marker_color=[GRADE_COLORS[g] for g in grade_counts.index],
            text=grade_counts.values,
            textposition="outside",
        )
    )
    bar.update_layout(
        font=dict(family=PLOT_FONT, size=13),
        yaxis_title="거래건수",
        xaxis_title="등급",
        margin=dict(l=10, r=10, t=10, b=30),
    )
    st.plotly_chart(bar, use_container_width=True)

st.divider()

# =========================================================
# 본문 - ⑤ 상위 5개국 무역액 등급 교차표
# =========================================================
st.subheader("상위 5개국 무역액 등급 교차표")

top5 = (
    filtered.groupby("country_name")["v"]
    .sum()
    .sort_values(ascending=False)
    .head(5)
    .index.tolist()
)
sub = filtered[filtered["country_name"].isin(top5)]

tab_raw, tab_norm = st.tabs(["원본건수", "정규화비율"])

with tab_raw:
    ct = pd.crosstab(sub["country_name"], sub["등급"])
    ct = ct.reindex(index=top5, columns=grade_order).fillna(0).astype(int)
    st.dataframe(
        ct.style.background_gradient(cmap="YlGn", axis=None),
        use_container_width=True,
    )
    st.caption("국가별 등급 거래건수(원본 집계)")

with tab_norm:
    ct_norm = pd.crosstab(sub["country_name"], sub["등급"], normalize="index")
    ct_norm = ct_norm.reindex(index=top5, columns=grade_order).fillna(0)
    st.dataframe(
        ct_norm.style.format("{:.1%}").background_gradient(cmap="YlGn", axis=None),
        use_container_width=True,
    )
    st.caption("국가별 등급 비율 (국가별 행 기준 100% 정규화)")