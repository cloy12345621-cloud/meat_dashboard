import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET
from difflib import get_close_matches

# ==============================================================================
# 0. 설정 및 초기화
# ==============================================================================
# 사용자의 API 키를 안전하게 관리하기 위한 변수 정의
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23" 
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"

# 페이지 레이아웃 설정
st.set_page_config(page_title="MEATRICS | 프리미엄 축산 데이터 플랫폼", layout="wide", initial_sidebar_state="expanded")

# 상세 CSS 스타일링 (Pretendard 폰트 적용)
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #0F1115; color: #E2E8F0; }
    .metric-card { background: linear-gradient(135deg, #1E222B 0%, #14171E 100%); border: 1px solid #2D3446; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
    .main-title { background: linear-gradient(90deg, #FFFFFF 0%, #A5B4FC 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 3rem; margin-bottom: 1rem; }
    .debug-box { background-color: #3F1D1D; border-left: 5px solid #EF4444; padding: 20px; border-radius: 8px; margin: 20px 0; color: #FCA5A5; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. 고도화된 데이터 처리 엔진 (기능 보강)
# ==============================================================================
def auto_detect_numeric_col(df, possible_names, new_col_name='AMOUNT'):
    """API의 비정형적인 컬럼명을 표준화하고 데이터를 정제하는 핵심 엔진"""
    if df.empty: return df
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map:
            actual_col = col_map[p_name.upper()]
            # 숫자형 변환 시 발생할 수 있는 오류를 정제 (쉼표 제거)
            df[new_col_name] = pd.to_numeric(df[actual_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            return df
    df[new_col_name] = 0
    return df

def find_actual_col(df, possible_names):
    """데이터프레임 내 존재하는 특정 이름의 컬럼을 찾는 함수"""
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map: return col_map[p_name.upper()]
    return None

@st.cache_data(ttl=3600)
def fetch_full_data():
    """데이터 수집 및 병합을 위한 메인 파이프라인"""
    # [농림축산식품부] 도축장별 실적 수집
    url_factory = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999"
    try:
        data = requests.get(url_factory, timeout=10).json()
        df_factory = pd.DataFrame(data.get('Grid_20161216000000000428_1', {}).get('row', []))
        df_factory = auto_detect_numeric_col(df_factory, ['THSMON', 'SLAU_AMN', 'AMOUNT'])
    except: df_factory = pd.DataFrame()
    
    # [행정안전부] 도축업 인프라 정보 수집
    url_house = f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey={PORTAL_API_KEY}&type=json&pIndex=1&pSize=1000"
    try:
        data = requests.get(url_house, timeout=10).json()
        df_house = pd.DataFrame(data.get('slaughterhouses', []))
    except: df_house = pd.DataFrame()
    
    # [병합 처리] 퍼지 매칭 적용 (이름 유사도 기반)
    bpl_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM'])
    h_col = 'bplNm'
    df_master = pd.DataFrame()
    
    if bpl_col and not df_factory.empty and not df_house.empty:
        # 이름이 약간 달라도 병합되도록 0.6 확률 기반 퍼지 매칭
        names = df_house[h_col].tolist()
        df_factory['join_key'] = df_factory[bpl_col].apply(lambda x: get_close_matches(x, names, n=1, cutoff=0.6))
        df_factory['join_key'] = df_factory['join_key'].apply(lambda x: x[0] if x else "")
        df_master = pd.merge(df_factory, df_house, left_on='join_key', right_on=h_col, how='inner')
        
    return df_factory, df_master

# 데이터 로딩
df_factory, df_master = fetch_full_data()

# ==============================================================================
# 2. 메인 화면 구성 및 인터랙티브 UI
# ==============================================================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 전국 도축장 랭킹", "🏛️ 통합 마스터 인벤토리", "🔍 실시간 역추적"])

with tab1:
    # KPI 카드 (통계 요약)
    col1, col2, col3 = st.columns(3)
    if not df_factory.empty:
        total = int(df_factory['AMOUNT'].sum())
        # 지역 필터 없이 전체 전국 순위 계산
        top_name = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM'])
        top_factory = df_factory.groupby(top_name)['AMOUNT'].sum().idxmax()
        
        with col1: st.markdown(f"<div class='metric-card'>전국 총 도축량<br><h2>{total:,} 두</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-card'>등록 도축장 수<br><h2>{len(df_factory)} 곳</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-card'>현재 1위 도축장<br><h4>{top_factory}</h4></div>", unsafe_allow_html=True)
        
        # 랭킹 시각화 (Plotly)
        st.write("---")
        st.subheader("전국 도축 물량 상위 15개 도축장")
        chart_data = df_factory.groupby(top_name, as_index=False)['AMOUNT'].sum().sort_values('AMOUNT', ascending=False).head(15)
        fig = px.bar(chart_data, x='AMOUNT', y=top_name, orientation='h', template='plotly_dark', color_discrete_sequence=['#DDA853'])
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("부처 간 융합 데이터 결과")
    if not df_master.empty: st.dataframe(df_master, use_container_width=True)
    else: st.warning("데이터 병합 대기 중입니다.")

with tab3:
    st.subheader("등급판정확인서 역추적 시스템")
    cert = st.text_input("등급판정확인서 발급번호 입력", key="cert_input")
    if st.button("역추적 실행"):
        st.info("정부 서버로부터 이력 데이터를 가져오는 중입니다...")
