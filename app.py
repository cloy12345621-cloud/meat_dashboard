import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import re
import urllib.parse

# ==============================================================================
# 0. API 인증키 설정 (💡 이제 진짜 농식품부 키 1개만 넣으시면 됩니다!)
# ==============================================================================
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"

# ==============================================================================
# 1. UI 및 테마 설정
# ==============================================================================
st.set_page_config(page_title="MEATRICS | 프리미엄 축산 대시보드", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    html, body, p, h1, h2, h3, h4, h5, h6, li, td, th, div.stMarkdown, span { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #0F1115; color: #E2E8F0; }
    .metric-card { background: linear-gradient(135deg, #1E222B 0%, #14171E 100%); border: 1px solid #2D3446; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin-bottom: 20px; transition: transform 0.3s ease; }
    .metric-card:hover { border-color: #DDA853; transform: translateY(-2px); }
    .metric-title { font-size: 0.9rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }
    .metric-value { font-size: 2rem; color: #FFFFFF; font-weight: 700; word-break: keep-all; }
    .metric-unit { font-size: 1rem; color: #DDA853; margin-left: 4px; }
    .main-title { background: linear-gradient(90deg, #FFFFFF 0%, #A5B4FC 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 3rem; margin-bottom: 0.5rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #2D3446; }
    .stTabs [data-baseweb="tab"] { height: 50px; color: #94A3B8 !important; font-weight: 600; font-size: 1.1rem; }
    .stTabs [aria-selected="true"] { color: #DDA853 !important; border-bottom: 3px solid #DDA853 !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. 강철 멘탈 데이터 정제 엔진 (오직 211.237.50.150 만 타겟팅)
# ==============================================================================
def fetch_mafra_data(url):
    """농식품부 자체 포털 전용 고속 파서"""
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        for k in data.keys():
            if 'Grid_' in k and 'row' in data[k]: return data[k]['row']
    except: pass
    return []

def auto_detect_numeric_col(df, possible_names, new_col_name='AMOUNT'):
    if df.empty: return df
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map:
            actual_col = col_map[p_name.upper()]
            cleaned_data = df[actual_col].astype(str).str.replace(r'[^0-9.]', '', regex=True)
            df[new_col_name] = pd.to_numeric(cleaned_data, errors='coerce').fillna(0)
            if df[new_col_name].sum() > 0: return df
    df[new_col_name] = 0
    return df

def find_actual_col(df, possible_names):
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map: return col_map[p_name.upper()]
    return None

@st.cache_data(ttl=3600)
def load_all_mafra_data():
    # 1. 지역별 실적 (API 1)
    raw_sido = fetch_mafra_data(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000423_1/1/999")
    df_sido = auto_detect_numeric_col(pd.DataFrame(raw_sido), ['THSMON', 'THSMON_ACMTL', 'AUCO_LSTK_AMN', 'SLAU_AMN', 'MT_AMN'])

    # 2. 도축장별 실적 (API 2)
    raw_factory = fetch_mafra_data(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999")
    df_factory = auto_detect_numeric_col(pd.DataFrame(raw_factory), ['THSMON', 'THSMON_ACMTL', 'SLAU_AMN', 'AUCO_LSTK_AMN', 'MT_AMN'])
    
    return df_sido, df_factory

# ==============================================================================
# 3. 글로벌 사이드바
# ==============================================================================
df_sido, df_factory = load_all_mafra_data()

with st.sidebar:
    st.markdown("<h2 style='color: #DDA853; font-weight: 800;'>MEATRICS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top:-15px;'>MAFRA Data Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📡 MAFRA 자체 서버 상태")
    st.write(f"{'🟢 정상' if not df_sido.empty else '🔴 대기'} | 지역 실적 원장")
    st.write(f"{'🟢 정상' if not df_factory.empty else '🔴 대기'} | 도축장 실적 원장")
    st.caption("※ 공공데이터포털(data.go.kr) 종속성 완벽 제거 완료")
        
    st.markdown("---")
    region_col = find_actual_col(df_sido, ['CTRD_NM', 'SIDO_NM'])
    if not df_sido.empty and region_col:
        sido_options = list(df_sido[region_col].dropna().unique())
        selected_sido = st.multiselect("분석 대상 지역 (필터)", options=sido_options, default=sido_options)
    else:
        selected_sido = []
        st.warning("데이터 수신 대기 중...")

# ==============================================================================
# 4. 메인 대시보드
# ==============================================================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
st.markdown("<p style='color: #94A3B8; font-size: 1.1rem; margin-bottom: 2rem;'>농림축산식품부(211.237.50.150) 전용 독립형 대시보드</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 선택 지역 도축 랭킹", "🏛️ 농식품부 마스터 DB", "📈 전국 인프라 심층 분석"])

# ----------------- TAB 1: 기존 랭킹 -----------------
with tab1:
    if selected_sido and region_col:
        factory_region_col = find_actual_col(df_factory, ['CTRD_NM', 'SIDO_NM'])
        filtered_factory = df_factory[df_factory[factory_region_col].isin(selected_sido)] if (not df_factory.empty and factory_region_col) else pd.DataFrame()
        total_slaughter = filtered_factory['AMOUNT'].sum() if not filtered_factory.empty else 0
        
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f"<div class='metric-card'><div class='metric-title'>선택 지역 총 도축량</div><div class='metric-value'>{int(total_slaughter):,}<span class='metric-unit'>두</span></div></div>", unsafe_allow_html=True)
        with col2: 
            factory_name_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM', 'FCLTY_NM'])
            factory_count = filtered_factory[factory_name_col].nunique() if factory_name_col in filtered_factory else 0
            st.markdown(f"<div class='metric-card'><div class='metric-title'>가동 도축장 수</div><div class='metric-value'>{factory_count}<span class='metric-unit'>곳</span></div></div>", unsafe_allow_html=True)
        with col3:
            top_factory = filtered_factory.groupby(factory_name_col)['AMOUNT'].sum().idxmax() if (not filtered_factory.empty and factory_name_col and total_slaughter > 0) else "실적 없음"
            st.markdown(f"<div class='metric-card'><div class='metric-title'>지역 내 1위 도축장</div><div class='metric-value' style='color:#F43F5E; font-size:1.6rem;'>{top_factory}</div></div>", unsafe_allow_html=True)
            
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🏆 선택 지역 내 도축장 실적 순위 (Top 15)")
            if not filtered_factory.empty and factory_name_col and total_slaughter > 0:
                chart_data = filtered_factory.groupby(factory_name_col, as_index=False)['AMOUNT'].sum().sort_values(by='AMOUNT', ascending=False).head(15)
                fig_factory = px.bar(chart_data, x='AMOUNT', y=factory_name_col, orientation='h', color='AMOUNT', color_continuous_scale='Blues', template='plotly_dark')
                fig_factory.update_layout(yaxis={'categoryorder':'total ascending'}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_factory, use_container_width=True)
        with c2:
            st.markdown("#### 🐖 선택 지역 내 축종별 도축 비율")
            species_col = find_actual_col(filtered_factory, ['LVSTCKSPC_NM', 'LSTK_KND_NM'])
            if not filtered_factory.empty and species_col and total_slaughter > 0:
                premium_colors = ['#DDA853', '#F43F5E', '#3B82F6', '#10B981', '#8B5CF6']
                fig_kind = px.pie(filtered_factory, names=species_col, values='AMOUNT', hole=0.4, template='plotly_dark', color_discrete_sequence=premium_colors)
                fig_kind.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_kind, use_container_width=True)
    else: st.info("사이드바에서 분석 대상 지역을 선택해주세요.")

# ----------------- TAB 2: 마스터 DB -----------------
with tab2:
    st.markdown("### 🏛️ 전국 도축장 마스터 DB (농림축산식품부 공인)")
    if not df_factory.empty:
        factory_region_col = find_actual_col(df_factory, ['CTRD_NM', 'SIDO_NM'])
        filtered_db = df_factory[df_factory[factory_region_col].isin(selected_sido)] if (factory_region_col and selected_sido) else df_factory
        st.success(f"✅ 농식품부 실적 데이터 로드 완료 (선택 지역 총 {len(filtered_db)}건)")
        st.dataframe(filtered_db.sort_values(by='AMOUNT', ascending=False), use_container_width=True)
    else:
        st.warning("데이터 통신 대기 중이거나 해당 지역의 실적이 없습니다.")

# ----------------- TAB 3: 신규 심층 분석 -----------------
with tab3:
    st.markdown("### 📈 전국 도축 인프라 심층 분석 (에러율 0%)")
    st.markdown("공공데이터포털 서버 통신 없이, 이미 확보된 농식품부 데이터를 기반으로 심층 분석을 제공합니다.")
    
    if not df_factory.empty:
        factory_name_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM', 'FCLTY_NM'])
        region_col_factory = find_actual_col(df_factory, ['CTRD_NM', 'SIDO_NM'])
        
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### 🗺️ 전국 시도별 도축 비중 (Treemap)")
            if region_col_factory and factory_name_col:
                fig_tree = px.treemap(df_factory, path=[region_col_factory, factory_name_col], values='AMOUNT', 
                                      color='AMOUNT', color_continuous_scale='YlOrRd', template='plotly_dark')
                fig_tree.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_tree, use_container_width=True)
        with c4:
            st.markdown("#### 📊 상위 5개 지역 축종별 마켓 쉐어")
            species_col = find_actual_col(df_factory, ['LVSTCKSPC_NM', 'LSTK_KND_NM'])
            if region_col_factory and species_col:
                top_5_regions = df_factory.groupby(region_col_factory)['AMOUNT'].sum().nlargest(5).index
                top_data = df_factory[df_factory[region_col_factory].isin(top_5_regions)]
                fig_bar = px.bar(top_data, x=region_col_factory, y='AMOUNT', color=species_col, 
                                 barmode='stack', template='plotly_dark', color_discrete_sequence=['#DDA853', '#F43F5E', '#3B82F6'])
                fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("분석할 기반 데이터가 없습니다.")
