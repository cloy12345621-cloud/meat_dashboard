import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET

# ==========================================
# 0. API 인증키 설정
# ==========================================
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23" 
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"

# ==========================================
# 1. 페이지 설정 및 디자인
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
    
    .debug-box { background-color: #3F1D1D; border-left: 5px solid #EF4444; padding: 20px; border-radius: 8px; margin: 20px 0; color: #FCA5A5; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 데이터 파이프라인 (발견된 실제 컬럼명 적용)
# ==========================================
def auto_detect_numeric_col(df, possible_names, new_col_name='AMOUNT'):
    if df.empty:
        df[new_col_name] = 0
        return df
        
    col_map = {c.upper(): c for c in df.columns}
    
    for p_name in possible_names:
        upper_name = p_name.upper()
        if upper_name in col_map:
            actual_col = col_map[upper_name]
            cleaned_data = df[actual_col].astype(str).str.replace(',', '', regex=False).str.strip()
            df[new_col_name] = pd.to_numeric(cleaned_data, errors='coerce').fillna(0)
            
            # 데이터를 찾아서 변환에 성공했다면 즉시 리턴
            if df[new_col_name].sum() > 0:
                return df
                
    df[new_col_name] = 0
    return df

def find_actual_col(df, possible_names):
    """축종 등 텍스트 컬럼을 유연하게 찾아주는 헬퍼 함수"""
    col_map = {c.upper(): c for c in df.columns}
    for p_name in possible_names:
        if p_name.upper() in col_map:
            return col_map[p_name.upper()]
    return None

@st.cache_data(ttl=3600)
def fetch_mafra_data():
    url_sido = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000423_1/1/999"
    url_factory = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999"
    
    df_sido = pd.DataFrame()
    df_factory = pd.DataFrame()
    
    try:
        res1 = requests.get(url_sido, timeout=10).json()
        df_sido = pd.DataFrame(res1.get('Grid_20161216000000000423_1', {}).get('row', []))
        # 💡 유저님이 찾아주신 THSMON, THSMON_ACMTL 추가
        df_sido = auto_detect_numeric_col(df_sido, ['THSMON', 'THSMON_ACMTL', 'AUCO_LSTK_AMN', 'SLAU_AMN', 'MT_AMN'])
    except Exception:
        pass 

    try:
        res2 = requests.get(url_factory, timeout=10).json()
        df_factory = pd.DataFrame(res2.get('Grid_20161216000000000428_1', {}).get('row', []))
        # 💡 여기도 동일하게 적용
        df_factory = auto_detect_numeric_col(df_factory, ['THSMON', 'THSMON_ACMTL', 'SLAU_AMN', 'AUCO_LSTK_AMN', 'MT_AMN'])
        
        bpl_col = find_actual_col(df_factory, ['BPL_NM', 'FCLTY_NM'])
        if bpl_col:
            df_factory['join_key'] = df_factory[bpl_col].astype(str).str.replace(" ", "", regex=True)
        else:
            df_factory['join_key'] = ""
    except Exception:
        pass
        
    return df_sido, df_factory

@st.cache_data(ttl=3600)
def fetch_portal_data():
    url_house = f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey={PORTAL_API_KEY}&type=json&pIndex=1&pSize=1000"
    df_house = pd.DataFrame()
    
    try:
        res = requests.get(url_house, timeout=10).json()
        if 'slaughterhouses' in res:
            df_house = pd.DataFrame(res['slaughterhouses'])
        elif 'row' in res:
            df_house = pd.DataFrame(res['row'])
            
        if not df_house.empty:
            name_col = find_actual_col(df_house, ['bplNm', 'BPL_NM'])
            if name_col:
                df_house['join_key'] = df_house[name_col].astype(str).str.replace(" ", "", regex=True)
            else:
                df_house['join_key'] = ""
    except Exception:
        pass
        
    return df_house

def verify_grade_confirm_mafra(issue_no):
    url_grade = f"https://apis.data.go.kr/B552895/EkapeEngineGradeConfirmInfoService/getGradeConfirmInfo?serviceKey={MAFRA_API_KEY}&issueNo={issue_no}"
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
    except Exception:
        pass
    return None

# ==========================================
# 3. 사이드바 제어
# ==========================================
df_sido, df_factory = fetch_mafra_data()
df_house = fetch_portal_data()

df_master = pd.DataFrame()
if not df_factory.empty and not df_house.empty and 'join_key' in df_factory.columns and 'join_key' in df_house.columns:
    df_master = pd.merge(df_factory, df_house, on='join_key', how='inner')

with st.sidebar:
    st.markdown("<h2 style='color: #DDA853; font-weight: 800;'>MEATRICS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top:-15px;'>Livestock Data Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    region_col = find_actual_col(df_sido, ['CTRD_NM', 'SIDO_NM'])
    
    if not df_sido.empty and region_col:
        sido_options = list(df_sido[region_col].dropna().unique())
        selected_sido = st.multiselect("분석 대상 지역 필터", options=sido_options, default=sido_options)
    else:
        selected_sido = []
        st.warning("API 데이터 로딩 중입니다...")
        
    st.markdown("---")
    st.markdown("<div style='font-size:0.8rem; color:#475569;'>📊 농식품부 연동 완료<br>🏛️ 행안부 연동 완료</div>", unsafe_allow_html=True)


# ==========================================
# 4. 메인 대시보드 렌더링
# ==========================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
st.markdown("<p style='color: #94A3B8; font-size: 1.1rem; margin-bottom: 2rem;'>농림축산식품부 실적 데이터 & 행정안전부 도축업 인프라 융합 플랫폼</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 전국 도축 트렌드 (농식품부 실적)", "🏛️ 통합 거시 데이터 (농식품부+행안부)", "🔍 실시간 이력 역추적 체인"])

with tab1:
    if not df_sido.empty and selected_sido and region_col:
        filtered_sido = df_sido[df_sido[region_col].isin(selected_sido)]
        total_slaughter = filtered_sido['AMOUNT'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"<div class='metric-card'><div class='metric-title'>전국 도축 총량</div><div class='metric-value'>{int(total_slaughter):,}<span class='metric-unit'>두</span></div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='metric-card'><div class='metric-title'>집계된 지역 수</div><div class='metric-value'>{len(selected_sido)}<span class='metric-unit'>곳</span></div></div>", unsafe_allow_html=True)
        with col3:
            top_region = filtered_sido.groupby(region_col)['AMOUNT'].sum().idxmax() if total_slaughter > 0 else "N/A"
            st.markdown(f"<div class='metric-card'><div class='metric-title'>물량 1위 지역</div><div class='metric-value' style='color:#F43F5E;'>{top_region}</div></div>", unsafe_allow_html=True)
            
        if total_slaughter == 0:
            st.markdown("""
                <div class='debug-box'>
                    <h4 style='margin-top:0; color:#F87171;'>🚨 데이터 추적 알림 (Debug Mode)</h4>
                    API 응답은 정상이나, 해당 월의 수량 데이터가 모두 0으로 비어있을 수 있습니다.
                </div>
            """, unsafe_allow_html=True)
            st.dataframe(df_sido, use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            with c1:
                chart_data = filtered_sido.groupby(region_col, as_index=False)['AMOUNT'].sum().sort_values(by='AMOUNT', ascending=True)
                fig_sido = px.bar(chart_data, x='AMOUNT', y=region_col, orientation='h', color='AMOUNT', color_continuous_scale='Blues', template='plotly_dark')
                fig_sido.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_sido, use_container_width=True)
            with c2:
                # 💡 유저님이 찾아주신 축종 컬럼명(LVSTCKSPC_NM) 적용
                species_col = find_actual_col(filtered_sido, ['LVSTCKSPC_NM', 'LSTK_KND_NM'])
                if species_col:
                    fig_kind = px.pie(filtered_sido, names=species_col, values='AMOUNT', hole=0.4, template='plotly_dark', color_discrete_sequence=px.colors.sequential.GoldReds)
                    fig_kind.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig_kind, use_container_width=True)
    else:
        st.info("데이터가 없습니다. API 통신 상태를 확인해주세요.")

with tab2:
    st.markdown("### 🏛️ 부처간 데이터 융합 마스터 인벤토리")
    if not df_master.empty:
        df_display = df_master.sort_values(by='AMOUNT', ascending=False)
        st.dataframe(df_display, use_container_width=True)
    else:
        st.warning("데이터 병합 대기 중입니다. (행안부/농식품부 양쪽에서 모두 데이터가 들어와야 표출됩니다)")

with tab3:
    st.markdown("### 🔍 등급서(농식품부) ➔ 도축장 정보(행안부) 역추적")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        cert_number = st.text_input("축산물등급판정확인서 발급번호 입력", placeholder="예: 001-2026-0625-99")
    with col_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        search_triggered = st.button("역추적 실행", use_container_width=True)
        
    if search_triggered and cert_number:
        grade_info = verify_grade_confirm_mafra(cert_number)
        if grade_info:
            target_abatt = grade_info['abattNm'].replace(" ", "")
            st.markdown(f"""
                <div style='background: #1E293B; border-left: 5px solid #DDA853; padding: 25px; border-radius: 12px; margin: 15px 0;'>
                    <h4 style='color:#DDA853; margin-top:0;'>📜 축산물 품질 정보</h4>
                    <p><b>판정등급:</b> {grade_info['gradeNm']} | <b>도체중량:</b> {grade_info['weight']} | <b>출신업체:</b> {grade_info['abattNm']}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if not df_master.empty and target_abatt:
                trace_result = df_master[df_master['join_key'] == target_abatt]
                if not trace_result.empty:
                    addr_col = find_actual_col(trace_result, ['rdnWhlAddr', 'ADDR', 'LOCPLC'])
                    addr = trace_result[addr_col].values[0] if addr_col else "상세주소 미상"
                    st.info(f"📍 도축장 행안부 등록 주소: {addr}")
                else:
                    st.warning("도축장명이 행안부 DB에 매칭되지 않습니다.")
        else:
            st.error("API 연결 실패 또는 원장 데이터 없음.")
