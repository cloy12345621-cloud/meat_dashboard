import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET
import re
import urllib.parse

# ==============================================================================
# 0. API 인증키 설정
# ==============================================================================
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"           # 211.237.50.150 용 (1, 2번 탭)
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23"  # data.go.kr 용 (3번 탭) 디코딩 키

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
# 2. 데이터 정제 엔진
# ==============================================================================
def get_safe_key(key):
    return urllib.parse.unquote(key)

def fetch_api_data(url, params=None):
    try:
        res = requests.get(url, params=params, timeout=15)
        try:
            data = res.json()
            for k in data.keys():
                if 'Grid_' in k and 'row' in data[k]: return data[k]['row']
        except: pass
        try:
            root = ET.fromstring(res.content)
            items = [{child.tag: child.text for child in item} for item in root.findall('.//item') + root.findall('.//row')]
            if items: return items
        except: pass
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
    raw_sido = fetch_api_data(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000423_1/1/999")
    df_sido = auto_detect_numeric_col(pd.DataFrame(raw_sido), ['THSMON', 'THSMON_ACMTL', 'AUCO_LSTK_AMN', 'SLAU_AMN', 'MT_AMN'])

    raw_factory = fetch_api_data(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999")
    df_factory = auto_detect_numeric_col(pd.DataFrame(raw_factory), ['THSMON', 'THSMON_ACMTL', 'SLAU_AMN', 'AUCO_LSTK_AMN', 'MT_AMN'])
    return df_sido, df_factory

def search_livestock_trace_info(search_no):
    """💡 각 API가 실패할 경우 그 원문(로그)을 모아서 UI로 전달합니다."""
    safe_key = get_safe_key(PORTAL_API_KEY)
    result_data = {}
    debug_logs = []
    
    # 1. 축산물등급판정확인서 (API 3)
    url_grade = "http://apis.data.go.kr/B552895/EkapeEngineGradeConfirmInfoService/getGradeConfirmInfo"
    try:
        res_grade = requests.get(url_grade, params={"serviceKey": safe_key, "issueNo": search_no}, timeout=10)
        if res_grade.status_code == 200:
            root = ET.fromstring(res_grade.content)
            item = root.find('.//item')
            if item is not None:
                result_data['grade'] = {
                    "발급번호": item.findtext('issueNo', default='-'),
                    "판정일자": item.findtext('judgeDt', default='-'),
                    "판정등급": item.findtext('gradeNm', default='-'),
                    "도축장명(기업)": item.findtext('abattNm', default='-'),
                    "도체중량": item.findtext('weight', default='-'),
                    "합격여부": item.findtext('inspectResult', default='적합')
                }
            else:
                debug_logs.append(f"[등급판정 API 거부/데이터없음] {res_grade.text[:200]}")
        else:
            debug_logs.append(f"[등급판정 API 통신에러 {res_grade.status_code}] {res_grade.text[:200]}")
    except Exception as e:
        debug_logs.append(f"[등급판정 API 시스템에러] {str(e)}")

    # 2. 축산물통합이력정보 (API 4)
    url_history = "http://apis.data.go.kr/B552895/MacarnisTraceDetailService/getTraceNoSearch"
    try:
        res_hist = requests.get(url_history, params={"serviceKey": safe_key, "traceNo": search_no}, timeout=10)
        if res_hist.status_code == 200:
            root = ET.fromstring(res_hist.content)
            item = root.find('.//item')
            if item is not None:
                result_data['history'] = {
                    "이력번호": item.findtext('traceNo', default='-'),
                    "축종/품종": item.findtext('lsTypeNm', default='-'),
                    "성별": item.findtext('sexNm', default='-'),
                    "출생일자": item.findtext('birthYmd', default='-'),
                    "농장명(기업)": item.findtext('farmNm', default='-'),
                    "사육지주소": item.findtext('farmAddr', default='-')
                }
            else:
                debug_logs.append(f"[통합이력 API 거부/데이터없음] {res_hist.text[:200]}")
        else:
            debug_logs.append(f"[통합이력 API 통신에러 {res_hist.status_code}] {res_hist.text[:200]}")
    except Exception as e:
        debug_logs.append(f"[통합이력 API 시스템에러] {str(e)}")

    return result_data, debug_logs

# ==============================================================================
# 3. 글로벌 사이드바
# ==============================================================================
df_sido, df_factory = load_all_mafra_data()

with st.sidebar:
    st.markdown("<h2 style='color: #DDA853; font-weight: 800;'>MEATRICS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top:-15px;'>MAFRA Data Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📡 메인 데이터 상태")
    st.write(f"{'🟢 수신 완료' if not df_sido.empty else '🔴 대기'} | 지역별 통계 원장")
    st.write(f"{'🟢 수신 완료' if not df_factory.empty else '🔴 대기'} | 도축장 실적 원장")
        
    st.markdown("---")
    region_col = find_actual_col(df_sido, ['CTRD_NM', 'SIDO_NM'])
    if not df_sido.empty and region_col:
        sido_options = list(df_sido[region_col].dropna().unique())
        selected_sido = st.multiselect("분석 대상 지역 (필터)", options=sido_options, default=sido_options)
    else:
        selected_sido = []
        st.warning("데이터 로딩 중...")

# ==============================================================================
# 4. 메인 대시보드
# ==============================================================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
st.markdown("<p style='color: #94A3B8; font-size: 1.1rem; margin-bottom: 2rem;'>선택 지역 기반 실적 분석 및 실시간 품질 역추적 플랫폼</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 지역 내 도축장 랭킹 분석", "🏛️ 농식품부 공인 마스터 DB", "🔍 실시간 이력 & 기업 정보 역추적"])

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

with tab2:
    st.markdown("### 🏛️ 전국 도축장 마스터 DB (농림축산식품부 공인)")
    if not df_factory.empty:
        factory_region_col = find_actual_col(df_factory, ['CTRD_NM', 'SIDO_NM'])
        filtered_db = df_factory[df_factory[factory_region_col].isin(selected_sido)] if (factory_region_col and selected_sido) else df_factory
        st.success(f"✅ 농식품부 원장 데이터 정제 완료 (총 {len(filtered_db)}개 시설 데이터 표출)")
        st.dataframe(filtered_db.sort_values(by='AMOUNT', ascending=False), use_container_width=True)

with tab3:
    st.markdown("### 🔍 이력번호 / 발급번호 기반 실시간 데이터 추적 시스템")
    
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        search_no = st.text_input("조회할 이력번호(12자리) 또는 등급판정 발급번호 입력", placeholder="예시: 002129200127 또는 160053500176")
    with col_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        search_triggered = st.button("실시간 역추적 실행", use_container_width=True)
        
    if search_triggered and search_no:
        clean_number = re.sub(r'[^0-9a-zA-Z]', '', search_no)
        
        with st.spinner("정부 서버(등급판정, 통합이력)를 조회 중입니다..."):
            info, debug_logs = search_livestock_trace_info(clean_number)
            
        if info:
            c3, c4 = st.columns(2)
            if 'grade' in info:
                with c3:
                    st.markdown("#### 📜 등급판정확인 원장 (API 3)")
                    g = info['grade']
                    st.markdown(f"""
                        <div class='metric-card' style='border-left: 5px solid #DDA853;'>
                            <p style='margin:4px 0;'><b>🏢 도축장명 (기업):</b> <span style='color:#FFFFFF; font-weight:bold;'>{g['도축장명(기업)']}</span></p>
                            <p style='margin:4px 0;'><b>📅 도축 판정일자:</b> {g['판정일자']}</p>
                            <p style='margin:4px 0;'><b>🏆 최종 판정등급:</b> <span style='color:#F43F5E; font-weight:bold; font-size:1.2rem;'>{g['판정등급']}</span></p>
                            <p style='margin:4px 0;'><b>⚖️ 도체 중량:</b> {g['도체중량']} kg</p>
                            <p style='margin:4px 0;'><b>✅ 위생 검사:</b> {g['합격여부']}</p>
                        </div>
                    """, unsafe_allow_html=True)
            if 'history' in info:
                with c4:
                    st.markdown("#### 🧬 통합 이력 정보 (API 4)")
                    h = info['history']
                    st.markdown(f"""
                        <div class='metric-card' style='border-left: 5px solid #3B82F6;'>
                            <p style='margin:4px 0;'><b>🚜 사육 농장명 (기업):</b> <span style='color:#FFFFFF; font-weight:bold;'>{h['농장명(기업)']}</span></p>
                            <p style='margin:4px 0;'><b>🐖 축종 및 품종:</b> {h['축종/품종']}</p>
                            <p style='margin:4px 0;'><b>⚥ 개체 성별:</b> {h['성별']}</p>
                            <p style='margin:4px 0;'><b>🎂 개체 출생일자:</b> {h['출생일자']}</p>
                            <p style='margin:4px 0;'><b>📍 사육지 주소:</b> {h['사육지주소']}</p>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            # 💡 에러 발생 시 그 이유를 펼쳐볼 수 있게 제공합니다!
            st.error("❌ 조회 실패. 정부 서버 통신 오류이거나 등록되지 않은 번호입니다. 아래 디버그 창을 확인하세요.")
            with st.expander("🛠️ 정부 서버 응답 원본 보기 (에러 원인 파악)"):
                st.write("공공데이터포털(data.go.kr)이 아래와 같은 에러를 반환했습니다:")
                for log in debug_logs:
                    st.code(log)
