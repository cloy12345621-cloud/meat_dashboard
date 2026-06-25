import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET
from difflib import get_close_matches

# ==========================================
# 0. API 인증키 설정
# ==========================================
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23" 
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"

# ==========================================
# 1. 페이지 설정 및 프리미엄 CSS
# ==========================================
st.set_page_config(page_title="MEATRICS | 축산 데이터 플랫폼", layout="wide")
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #0F1115; color: #E2E8F0; }
    .metric-card { background: linear-gradient(135deg, #1E222B 0%, #14171E 100%); border: 1px solid #2D3446; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
    .main-title { background: linear-gradient(90deg, #FFFFFF 0%, #A5B4FC 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 3rem; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #2D3446; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 처리 및 정제 함수
# ==========================================
def auto_detect_numeric_col(df, possible_names, new_col_name='AMOUNT'):
    if df.empty: return df
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map:
            actual_col = col_map[p_name.upper()]
            df[new_col_name] = pd.to_numeric(df[actual_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            return df
    df[new_col_name] = 0
    return df

def find_actual_col(df, possible_names):
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map: return col_map[p_name.upper()]
    return None

@st.cache_data(ttl=3600)
def fetch_data():
    # 농식품부 도축장 실적
    url_factory = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999"
    df_factory = pd.DataFrame(requests.get(url_factory).json().get('Grid_20161216000000000428_1', {}).get('row', []))
    df_factory = auto_detect_numeric_col(df_factory, ['THSMON', 'SLAU_AMN', 'AMOUNT'])
    
    # 행안부 도축업 인프라
    url_house = f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey={PORTAL_API_KEY}&type=json&pIndex=1&pSize=1000"
    df_house = pd.DataFrame(requests.get(url_house).json().get('slaughterhouses', []))
    
    # 퍼지 매칭 병합
    bpl_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM'])
    h_col = 'bplNm'
    
    if bpl_col and not df_factory.empty and not df_house.empty:
        house_names = df_house[h_col].tolist()
        df_factory['join_key'] = df_factory[bpl_col].apply(lambda x: get_close_matches(x, house_names, n=1, cutoff=0.6))
        df_factory['join_key'] = df_factory['join_key'].apply(lambda x: x[0] if x else "")
        df_master = pd.merge(df_factory, df_house, left_on='join_key', right_on=h_col, how='inner')
    else: df_master = pd.DataFrame()
    return df_factory, df_master

df_factory, df_master = fetch_data()

# ==========================================
# 3. 메인 UI (3단 탭 및 시각화)
# ==========================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📊 도축장 랭킹 분석", "🏛️ 통합 마스터 인벤토리", "🔍 실시간 역추적"])

with tab1:
    col1, col2, col3 = st.columns(3)
    if not df_factory.empty:
        total = int(df_factory['AMOUNT'].sum())
        name_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM'])
        top_factory = df_factory.groupby(name_col)['AMOUNT'].sum().idxmax()
        
        with col1: st.markdown(f"<div class='metric-card'>총 도축량<br><h2>{total:,} 두</h2></div>", unsafe_allow_html=True)
        with col2: st.markdown(f"<div class='metric-card'>전체 도축장 수<br><h2>{len(df_factory)} 곳</h2></div>", unsafe_allow_html=True)
        with col3: st.markdown(f"<div class='metric-card'>전국 1위 도축장<br><h4>{top_factory}</h4></div>", unsafe_allow_html=True)
        
        chart_data = df_factory.groupby(name_col, as_index=False)['AMOUNT'].sum().sort_values('AMOUNT', ascending=False).head(15)
        fig = px.bar(chart_data, x='AMOUNT', y=name_col, orientation='h', template='plotly_dark', color_discrete_sequence=['#DDA853'])
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("부처 간 융합 데이터 결과")
    if not df_master.empty: st.dataframe(df_master, use_container_width=True)
    else: st.warning("데이터 병합 대기 중입니다.")

with tab3:
    st.subheader("실시간 등급판정확인서 역추적")
    cert = st.text_input("발급번호 입력", key="cert_input")
    if st.button("역추적 실행"):
        st.info("데이터 조회 중...")
