import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET

# ==========================================
# 0. API 인증키 설정 (출처별 분리)
# ==========================================
# ⚠️ 사이트가 다르므로 발급받은 키도 다를 수 있습니다. 각각 알맞은 키를 넣어주세요.

# 1. 행정안전부 도축업 (공공데이터포털 data.go.kr 발급 키)
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23" 

# 2. 농림축산식품부/축평원 데이터 3종 (농식품부 공공데이터 발급 키)
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"


# ==========================================
# 1. 페이지 설정 및 프리미엄 UI 커스텀
# ==========================================
st.set_page_config(
    page_title="MEATRICS | 프리미엄 축산 통합 데이터 플랫폼",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', -apple-system, sans-serif !important; }
    .stApp { background-color: #0F1115; color: #E2E8F0; }
    
    .metric-card {
        background: linear-gradient(135deg, #1E222B 0%, #14171E 100%);
        border: 1px solid #2D3446;
        border-radius: 16px; padding: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3); margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .metric-card:hover { border-color: #DDA853; transform: translateY(-2px); }
    .metric-title { font-size: 0.9rem; color: #94A3B8; font-weight: 600; text-transform: uppercase; margin-bottom: 8px; }
    .metric-value { font-size: 2rem; color: #FFFFFF; font-weight: 700; }
    .metric-unit { font-size: 1rem; color: #DDA853; margin-left: 4px; }
    
    .main-title {
        background: linear-gradient(90deg, #FFFFFF 0%, #A5B4FC 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800; font-size: 3rem; margin-bottom: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; border-bottom: 1px solid #2D3446; }
    .stTabs [data-baseweb="tab"] { height: 50px; color: #94A3B8 !important; font-weight: 600; font-size: 1.1rem; }
    .stTabs [aria-selected="true"] { color: #DDA853 !important; border-bottom: 3px solid #DDA853 !important; }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 데이터 파이프라인 (기관별 분류 수집)
# ==========================================

@st.cache_data(ttl=3600)
def fetch_mafra_data():
    """ 
    [농림축산식품부 데이터] 
    2번: 시도별 도축실적 / 3번: 도축장별 도축실적 
    """
    url_sido = f"http://211.237.50.150:7080/openapi/fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677/json/Grid_20161216000000000423_1/1/999"
    url_factory = f"http://211.237.50.150:7080/openapi/fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677/json/Grid_20161216000000000428_1/1/999"
    
    df_sido = pd.DataFrame()
    df_factory = pd.DataFrame()
    
    try:
        res1 = requests.get(url_sido, timeout=10).json()
        df_sido = pd.DataFrame(res1.get('Grid_20161216000000000423_1', {}).get('row', []))
        if not df_sido.empty:
            df_sido['AUCO_LSTK_AMN'] = pd.to_numeric(df_sido['AUCO_LSTK_AMN'], errors='coerce').fillna(0)
    except Exception as e:
        pass # 에러 발생 시 빈 데이터프레임 유지

    try:
        res2 = requests.get(url_factory, timeout=10).json()
        df_factory = pd.DataFrame(res2.get('Grid_20161216000000000428_1', {}).get('row', []))
        if not df_factory.empty:
            df_factory['SLAU_AMN'] = pd.to_numeric(df_factory['SLAU_AMN'], errors='coerce').fillna(0)
            df_factory['join_key'] = df_factory['BPL_NM'].str.replace(" ", "", regex=True) # 매핑용 키
    except Exception as e:
        pass
        
    return df_sido, df_factory


@st.cache_data(ttl=3600)
def fetch_portal_data():
    """ 
    [공공데이터포털 데이터] 
    4번: 행정안전부 동물 도축업 조회
    """
    url_house = f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey=f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23&type=json&pIndex=1&pSize=1000"
    df_house = pd.DataFrame()
    
    try:
        res = requests.get(url_house, timeout=10).json()
        if 'slaughterhouses' in res:
            df_house = pd.DataFrame(res['slaughterhouses'])
        elif 'row' in res:
            df_house = pd.DataFrame(res['row'])
            
        if not df_house.empty:
            df_house['join_key'] = df_house['bplNm'].str.replace(" ", "", regex=True) # 매핑용 키
    except Exception as e:
        pass
        
    return df_house

def verify_grade_confirm_mafra(issue_no):
    """
    [농림축산식품부/축평원] 
    1번: 축산물등급판정확인서 발급번호정보
    """
    # 농식품부/축평원 API 스키마
    url_grade = f"https://apis.data.go.kr/B552895/EkapeEngineGradeConfirmInfoService/getGradeConfirmInfo?serviceKey=fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677&issueNo={issue_no}"
    
    try:
        response = requests.get(url_grade, timeout=5)
        root = ET.fromstring(response.content)
        item = root.find('.//item')
        if item is not None:
            return {
                "issueNo": item.findtext('issueNo', default=issue_no),
                "judgeDt": item.findtext('judgeDt', default='-'),
                "gradeNm": item.findtext('gradeNm', default='-'),
                "abattNm": item.findtext('abattNm', default=''), 
                "weight": item.findtext('weight', default='-'),
                "inspectResult": item.findtext('inspectResult', default='적합')
            }
    except Exception as e:
        pass
    return None


# ==========================================
# 3. 데이터 결합 및 사이드바 (농식품부 + 행안부 융합)
# ==========================================
df_sido, df_factory = fetch_mafra_data()
df_house = fetch_portal_data()

# 두 기관의 데이터 병합 (농식품부 실적 + 행안부 위치/인허가)
df_master = pd.DataFrame()
if not df_factory.empty and not df_house.empty:
    df_master = pd.merge(df_factory, df_house, on='join_key', how='inner')

with st.sidebar:
    st.markdown("<h2 style='color: #DDA853; font-weight: 800;'>MEATRICS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top:-15px;'>Livestock Data Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    if not df_sido.empty and 'CTRD_NM' in df_sido.columns:
        sido_options = list(df_sido['CTRD_NM'].unique())
        selected_sido = st.multiselect("분석 대상 지역 필터", options=sido_options, default=sido_options)
    else:
        selected_sido = []
        st.warning("API 통신 대기 중이거나 인증키 확인이 필요합니다.")
        
    st.markdown("---")
    st.markdown("<div style='font-size:0.8rem; color:#475569;'>📊 농림축산식품부(실적/등급) 3종<br>🏛️ 행정안전부(인프라) 1종 연동됨</div>", unsafe_allow_html=True)


# ==========================================
# 4. 메인 대시보드 렌더링
# ==========================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
st.markdown("<p style='color: #94A3B8; font-size: 1.1rem; margin-bottom: 2rem;'>농림축산식품부 실적 데이터 & 행정안전부 도축업 인프라 융합 플랫폼</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 전국 도축 트렌드 (농식품부 실적)", "🏛️ 통합 거시 데이터 (농식품부+행안부)", "🔍 실시간 이력 역추적 체인"])

with tab1:
    if not df_sido.empty and selected_sido:
        filtered_sido = df_sido[df_sido['CTRD_NM'].isin(selected_sido)]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_slaughter = filtered_sido['AUCO_LSTK_AMN'].sum()
            st.markdown(f"<div class='metric-card'><div class='metric-title'>전국 도축 총량</div><div class='metric-value'>{total_slaughter:,}<span class='metric-unit'>두</span></div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='metric-card'><div class='metric-title'>집계된 지역 수</div><div class='metric-value'>{len(selected_sido)}<span class='metric-unit'>곳</span></div></div>", unsafe_allow_html=True)
        with col3:
            top_region = filtered_sido.groupby('CTRD_NM')['AUCO_LSTK_AMN'].sum().idxmax() if not filtered_sido.empty else "N/A"
            st.markdown(f"<div class='metric-card'><div class='metric-title'>물량 1위 지역</div><div class='metric-value' style='color:#F43F5E;'>{top_region}</div></div>", unsafe_allow_html=True)
            
        c1, c2 = st.columns(2)
        with c1:
            chart_data = filtered_sido.groupby('CTRD_NM', as_index=False)['AUCO_LSTK_AMN'].sum().sort_values(by='AUCO_LSTK_AMN', ascending=True)
            fig_sido = px.bar(chart_data, x='AUCO_LSTK_AMN', y='CTRD_NM', orientation='h', color='AUCO_LSTK_AMN', color_continuous_scale='Blues', template='plotly_dark')
            fig_sido.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_sido, use_container_width=True)
        with c2:
            fig_kind = px.pie(filtered_sido, names='LSTK_KND_NM', values='AUCO_LSTK_AMN', hole=0.4, template='plotly_dark', color_discrete_sequence=px.colors.sequential.GoldReds)
            fig_kind.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_kind, use_container_width=True)
    else:
        st.info("데이터가 없습니다. API 통신 상태를 확인해주세요.")

with tab2:
    st.markdown("### 🏛️ 부처간 데이터 융합 마스터 인벤토리")
    if not df_master.empty:
        st.success("✅ 농식품부 실적 데이터(3번)와 행안부 인허가 데이터(4번)가 도축장명을 기준으로 성공적으로 결합되었습니다.")
        df_display = df_master.sort_values(by='SLAU_AMN', ascending=False)
        st.dataframe(
            df_display[['BPL_NM', 'LSTK_KND_NM', 'SLAU_AMN', 'trdStateNm', 'rdnWhlAddr', 'CTRD_NM']], 
            column_config={
                "BPL_NM": "도축장명(공통키)", "LSTK_KND_NM": "축종(농식품부)", "SLAU_AMN": "도축실적(농식품부)",
                "trdStateNm": "인허가상태(행안부)", "rdnWhlAddr": "상세주소(행안부)", "CTRD_NM": "관할시도"
            },
            use_container_width=True
        )
    else:
        st.warning("데이터 병합 대기 중입니다. 두 기관의 API 키가 모두 정상인지 확인해주세요.")

with tab3:
    st.markdown("### 🔍 등급서(농식품부) ➔ 도축장 정보(행안부) 역추적")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        cert_number = st.text_input("축산물등급판정확인서 발급번호 입력 (농식품부 1번 API)")
    with col_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        search_triggered = st.button("역추적 실행", use_container_width=True)
        
    if search_triggered and cert_number:
        grade_info = verify_grade_confirm_mafra(cert_number)
        if grade_info:
            target_abatt = grade_info['abattNm'].replace(" ", "")
            
            st.markdown(f"""
                <div style='background: #1E293B; border-left: 5px solid #DDA853; padding: 25px; border-radius: 12px; margin: 15px 0;'>
                    <h4 style='color:#DDA853; margin-top:0;'>📜 [농식품부] 축산물 품질 정보 확인 완료</h4>
                    <p><b>판정등급:</b> {grade_info['gradeNm']} | <b>도체중량:</b> {grade_info['weight']} | <b>출신업체:</b> {grade_info['abattNm']}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if not df_master.empty and target_abatt:
                trace_result = df_master[df_master['join_key'] == target_abatt]
                if not trace_result.empty:
                    addr = trace_result['rdnWhlAddr'].values[0]
                    state = trace_result['trdStateNm'].values[0]
                    st.info(f"📍 **[행안부 데이터 매칭 성공]** 해당 도축장 주소: {addr} (상태: {state})")
                else:
                    st.warning("등급서상의 도축장명이 행안부 인프라 DB에 매칭되지 않습니다.")
        else:
            st.error("농식품부 원장에서 데이터를 찾을 수 없거나 API 연결에 실패했습니다.")
