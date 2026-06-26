import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import xml.etree.ElementTree as ET
from difflib import get_close_matches
import re

# ==============================================================================
# 0. API 인증키 설정 (두 개의 키 모두 사용!)
# ==============================================================================
PORTAL_API_KEY = "f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23"  # 행정안전부용
MAFRA_API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"           # 농식품부용

# ==============================================================================
# 1. UI 및 테마 설정
# ==============================================================================
st.set_page_config(page_title="MEATRICS | 프리미엄 축산 대시보드", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    /* 💡 아이콘 깨짐 방지를 위해 * 대신 텍스트 태그에만 폰트 적용 */
    html, body, p, div, h1, h2, h3, h4, h5, h6, span { font-family: 'Pretendard', sans-serif; }
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
# 2. 고도화된 데이터 정제 엔진
# ==============================================================================
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

def normalize_name(name):
    if not isinstance(name, str): return ""
    return re.sub(r'\(주\)|주식회사|\s', '', name)

@st.cache_data(ttl=3600)
def fetch_and_merge_data():
    df_sido, df_factory, df_house, df_master = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    portal_error_msg = ""
    
    # 1. 농식품부 시도별 실적
    try:
        res1 = requests.get(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000423_1/1/999", timeout=10)
        df_sido = pd.DataFrame(res1.json().get('Grid_20161216000000000423_1', {}).get('row', []))
        df_sido = auto_detect_numeric_col(df_sido, ['THSMON', 'THSMON_ACMTL', 'AUCO_LSTK_AMN', 'SLAU_AMN', 'MT_AMN'])
    except: pass

    # 2. 농식품부 도축장별 실적
    try:
        res2 = requests.get(f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999", timeout=10)
        df_factory = pd.DataFrame(res2.json().get('Grid_20161216000000000428_1', {}).get('row', []))
        df_factory = auto_detect_numeric_col(df_factory, ['THSMON', 'THSMON_ACMTL', 'SLAU_AMN', 'AUCO_LSTK_AMN', 'MT_AMN'])
        bpl_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM', 'FCLTY_NM', 'ABATT_NM', 'ENTRPS_NM'])
        if bpl_col and not df_factory.empty:
            df_factory['join_key'] = df_factory[bpl_col].apply(normalize_name)
    except: pass

    # 3. 행안부 도축업 인프라 (💡 에러 메시지 캡처 기능 추가)
    try:
        res3 = requests.get(f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey={PORTAL_API_KEY}&type=json&pIndex=1&pSize=1000", timeout=10)
        portal_error_msg = res3.text[:500] # 만약 실패할 경우 원본 텍스트를 저장해둡니다.
        data = res3.json()
        
        if 'response' in data and 'body' in data['response'] and 'items' in data['response']['body']:
            items = data['response']['body']['items']
            df_house = pd.DataFrame(items.get('item', items)) if isinstance(items, dict) else pd.DataFrame(items)
        elif 'slaughterhouses' in data: df_house = pd.DataFrame(data['slaughterhouses'])
        elif 'row' in data: df_house = pd.DataFrame(data['row'])
            
        if not df_house.empty:
            name_col = find_actual_col(df_house, ['bplNm', 'BPL_NM'])
            if name_col: df_house['join_key'] = df_house[name_col].apply(normalize_name)
    except Exception as e:
        if not portal_error_msg: portal_error_msg = str(e)

    # 4. 퍼지 매칭 병합
    if not df_factory.empty and not df_house.empty and 'join_key' in df_factory.columns and 'join_key' in df_house.columns:
        valid_factory = df_factory[df_factory['join_key'] != ""]
        house_names = df_house[df_house['join_key'] != ""]['join_key'].tolist()
        
        valid_factory['match_key'] = valid_factory['join_key'].apply(lambda x: get_close_matches(x, house_names, n=1, cutoff=0.4))
        valid_factory['match_key'] = valid_factory['match_key'].apply(lambda x: x[0] if x else "")
        
        df_master = pd.merge(valid_factory[valid_factory['match_key'] != ""], df_house, left_on='match_key', right_on='join_key', how='inner')

    return df_sido, df_factory, df_house, df_master, portal_error_msg

def verify_grade_confirm(issue_no):
    url_grade = f"https://apis.data.go.kr/B552895/EkapeEngineGradeConfirmInfoService/getGradeConfirmInfo?serviceKey={MAFRA_API_KEY}&issueNo={issue_no}"
    try:
        response = requests.get(url_grade, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            item = root.find('.//item')
            if item is not None:
                return {"success": True, "data": {
                    "issueNo": item.findtext('issueNo', default=issue_no), "judgeDt": item.findtext('judgeDt', default='-'),
                    "gradeNm": item.findtext('gradeNm', default='-'), "abattNm": item.findtext('abattNm', default=''), 
                    "weight": item.findtext('weight', default='-'), "inspectResult": item.findtext('inspectResult', default='적합')
                }}
            else:
                return {"success": False, "msg": "조회된 데이터가 없습니다. 발급번호를 확인해주세요.", "raw": response.text[:300]}
        elif response.status_code == 500:
            return {"success": False, "msg": "정부(축산물품질평가원) 서버 장애입니다 (상태코드 500). 잠시 후 다시 시도해주세요.", "raw": ""}
        else:
            return {"success": False, "msg": f"서버 통신 오류 (상태코드: {response.status_code})", "raw": response.text[:300]}
    except Exception as e:
        return {"success": False, "msg": f"네트워크 오류: {str(e)}", "raw": ""}

# ==============================================================================
# 3. 글로벌 사이드바
# ==============================================================================
df_sido, df_factory, df_house, df_master, portal_error = fetch_and_merge_data()

with st.sidebar:
    st.markdown("<h2 style='color: #DDA853; font-weight: 800;'>MEATRICS</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top:-15px;'>Livestock Data Intelligence</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("### 📡 API 서버 연결 상태")
    st.write(f"{'✅' if not df_sido.empty else '❌'} 농식품부 (지역 실적)")
    st.write(f"{'✅' if not df_factory.empty else '❌'} 농식품부 (도축장 실적)")
    st.write(f"{'✅' if not df_house.empty else '❌'} 행정안전부 (도축 인프라)")
    
    # 💡 행안부 데이터가 안 들어올 경우 사이드바에 에러 메시지를 표시합니다!
    if df_house.empty:
        with st.expander("⚠️ 행안부 연결 실패 원인 (클릭)"):
            st.write("아래 메시지가 `SERVICE_KEY_IS_NOT_REGISTERED`라면 키 인코딩/디코딩 문제이거나 서비스 신청이 안 된 것입니다.")
            st.code(portal_error)
            
    st.markdown("---")
    region_col = find_actual_col(df_sido, ['CTRD_NM', 'SIDO_NM'])
    if not df_sido.empty and region_col:
        sido_options = list(df_sido[region_col].dropna().unique())
        selected_sido = st.multiselect("분석 대상 지역 필터", options=sido_options, default=sido_options)
    else:
        selected_sido = []
        st.warning("데이터 통신 대기 중...")

# ==============================================================================
# 4. 메인 대시보드 렌더링
# ==============================================================================
st.markdown("<div class='main-title'>Livestock Data Intelligence</div>", unsafe_allow_html=True)
st.markdown("<p style='color: #94A3B8; font-size: 1.1rem; margin-bottom: 2rem;'>부처 간 공공데이터 융합 대시보드</p>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 지역 내 도축장 랭킹 분석", "🏛️ 필터링된 마스터 인벤토리", "🔍 실시간 이력 역추적 체인"])

with tab1:
    if selected_sido and region_col:
        factory_region_col = find_actual_col(df_factory, ['CTRD_NM', 'SIDO_NM'])
        filtered_factory = df_factory[df_factory[factory_region_col].isin(selected_sido)] if (not df_factory.empty and factory_region_col) else pd.DataFrame()
        total_slaughter = filtered_factory['AMOUNT'].sum() if not filtered_factory.empty else 0
        
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f"<div class='metric-card'><div class='metric-title'>선택 지역 총 도축량</div><div class='metric-value'>{int(total_slaughter):,}<span class='metric-unit'>두</span></div></div>", unsafe_allow_html=True)
        with col2: 
            factory_count = filtered_factory['join_key_x'].nunique() if 'join_key_x' in filtered_factory else (filtered_factory['join_key'].nunique() if 'join_key' in filtered_factory else 0)
            st.markdown(f"<div class='metric-card'><div class='metric-title'>가동 도축장 수</div><div class='metric-value'>{factory_count}<span class='metric-unit'>곳</span></div></div>", unsafe_allow_html=True)
        with col3:
            factory_name_col = find_actual_col(df_factory, ['SLAU_PLACE_NM', 'BPL_NM', 'FCLTY_NM'])
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
    else: st.info("사이드바에서 지역을 선택해주세요.")

with tab2:
    st.markdown("### 🏛️ 부처간 데이터 융합 마스터 인벤토리 (필터 연동)")
    if not df_master.empty:
        master_region_col = find_actual_col(df_master, ['CTRD_NM', 'SIDO_NM'])
        filtered_master = df_master[df_master[master_region_col].isin(selected_sido)] if (master_region_col and selected_sido) else df_master
        st.success(f"✅ 농식품부(실적)와 행안부(주소)가 성공적으로 병합되었습니다. (해당 지역 {len(filtered_master)}건)")
        st.dataframe(filtered_master.sort_values(by='AMOUNT', ascending=False), use_container_width=True)
    else:
        st.warning("데이터 병합 대기 중이거나 실패했습니다. 왼쪽 사이드바의 [행안부 연결 실패 원인]을 확인하세요.")

with tab3:
    st.markdown("### 🔍 등급서(농식품부) ➔ 도축장 정보(행안부) 역추적")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        cert_number = st.text_input("축산물등급판정확인서 발급번호 입력 (예: 160053500176)", key="cert_input")
    with col_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        search_triggered = st.button("역추적 실행", use_container_width=True)
        
    if search_triggered and cert_number:
        result = verify_grade_confirm(cert_number)
        
        if result.get("success"):
            g_info = result["data"]
            target_abatt = normalize_name(g_info['abattNm'])
            st.markdown(f"""
                <div style='background: #1E293B; border-left: 5px solid #DDA853; padding: 25px; border-radius: 12px; margin: 15px 0;'>
                    <h4 style='color:#DDA853; margin-top:0;'>📜 축산물 품질 정보</h4>
                    <p><b>판정등급:</b> {g_info['gradeNm']} | <b>도체중량:</b> {g_info['weight']} | <b>출신업체:</b> {g_info['abattNm']}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if not df_master.empty and target_abatt:
                master_names = df_master['match_key'].tolist()
                closest_match = get_close_matches(target_abatt, master_names, n=1, cutoff=0.4)
                
                if closest_match:
                    trace_result = df_master[df_master['match_key'] == closest_match[0]]
                    addr_col = find_actual_col(trace_result, ['rdnWhlAddr', 'ADDR', 'LOCPLC'])
                    addr = trace_result[addr_col].values[0] if addr_col else "미상"
                    st.success(f"📍 행안부 인프라 추적 완료: **{addr}**")
                else: st.warning("해당 도축장 이름이 행안부 DB에 매칭되지 않습니다.")
        else:
            st.error(f"❌ {result.get('msg')}")
            if result.get("raw"):
                with st.expander("원본 에러 로그 확인"):
                    st.code(result.get("raw"))
