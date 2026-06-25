import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.express as px

# 1. 페이지 레이아웃 설정
st.set_page_config(
    page_title="축산물 물류 및 도축 데이터 분석 인텔리전스",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 기본 UI 스타일 적용
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght=400;500;600;700;800;900&display=swap');
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Pretendard', sans-serif !important;
        letter-spacing: -0.04em !important;
    }
    .main-title { font-size: 32px; font-weight: 800; color: #0f172a; margin-bottom: 20px; }
    .section-title { font-size: 20px; font-weight: 700; color: #0f172a; margin-bottom: 15px; border-left: 6px solid #2563eb; padding-left: 12px; }
    </style>
""", unsafe_allow_html=True)

# API 인증키 설정
MAFRA_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'
EKAPE_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'

st.markdown('<div class="main-title">📈 축산물 물류 및 도축 실적 통합 인텔리전스</div>', unsafe_allow_html=True)

# 사이드바 설정
st.sidebar.markdown("### 🎛️ 인텔리전스 필터")
selected_region = st.sidebar.selectbox("📍 분석 지역 선택", ["전국", "전남", "경기", "충남", "경남", "경북", "제주"])
selected_animals = st.sidebar.multiselect("🐖 분석 축종", ["돼지", "소", "닭"], default=["돼지", "소", "닭"])

tab1, tab2 = st.tabs(["📊 거시 통계 분석", "🔍 실시간 이력 검증"])

with tab1:
    st.markdown('<div class="section-title">🚨 시스템 실시간 API 통신 및 데이터 상태 모니터링</div>', unsafe_allow_html=True)
    
    url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/1000"
    
    raw_df = pd.DataFrame(columns=['시도명', '도축장명', '축종', '도축실적'])
    filtered_df = pd.DataFrame(columns=['시도명', '도축장명', '축종', '도축실적'])
    
    # 예외가 나더라도 화면을 터뜨리지 않고 에러 내용을 고스란히 화면에 찍기
    try:
        response = requests.get(url, timeout=10)
        st.info(f"📡 API 서버 응답 코드: {response.status_code}")
        
        res_json = response.json()
        
        # [모니터링 🔍] JSON의 첫 단추가 어떻게 생겼는지 화면에 디버깅용으로 강제 수록
        with st.expander("🔍 [디버깅] 공공데이터포털 API 원본 수신 데이터 구조 보기", expanded=True):
            st.json(res_json)
            
        # 루트 키 찾기
        main_key = None
        for k in res_json.keys():
            if k.lower() == 'grid_20161216000000000428_1':
                main_key = k
                break
                
        if main_key and 'row' in res_json[main_key]:
            rows = res_json[main_key]['row']
            df = pd.DataFrame(rows)
            df.columns = df.columns.str.lower()
            
            rename_dict = {
                'ctprvn_nm': '시도명',
                'lstk_slalto_nm': '도축장명',
                'lvs_ctgry_nm': '축종',
                'slau_iem_co': '도축실적'
            }
            df = df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns})
            
            # 컬럼 강제 고정
            for c in ['시도명', '도축장명', '축종']:
                if c in df.columns: df[c] = df[c].astype(str).str.strip()
                else: df[c] = "미분류"
            
            if '도축실적' in df.columns:
                df['도축실적'] = pd.to_numeric(df['도축실적'], errors='coerce').fillna(0)
            else:
                df['도축실적'] = 0
                
            def convert_animal(x):
                if '돈' in x or '돼지' in x: return '돼지'
                if '우' in x or '소' in x: return '소'
                if '계' in x or '닭' in x: return '닭'
                return x
            df['축종'] = df['축종'].apply(convert_animal)
            
            raw_df = df[['시도명', '도축장명', '축종', '도축실적']]
        else:
            st.error("❌ JSON 응답 내부에 'Grid_20161216000000000428_1' 또는 'row' 키가 존재하지 않습니다.")
            
    except Exception as e:
        st.error(f"💥 네트워크 통신 혹은 코드 예외 발생: {str(e)}")

    # 데이터 필터링 공정
    if not raw_df.empty:
        filtered_df = raw_df.copy()
        if selected_region != "전국":
            reg_sub = selected_region[:2]
            filtered_df = filtered_df[filtered_df['시도명'].str.contains(reg_sub, na=False)]
        if selected_animals:
            filtered_df = filtered_df[filtered_df['축종'].isin(selected_animals)]
        filtered_df = filtered_df.sort_values(by='도축실적', ascending=False).reset_index(drop=True)

    # 렌더링 파트 (절대 빈 변수 참조로 터지지 않게 안전 분기)
    col_graph, col_table = st.columns([6, 4])
    
    with col_graph:
        st.markdown('<div class="section-title">🏆 누적 도축 실적 분석 TOP 10</div>', unsafe_allow_html=True)
        display_target = filtered_df if not filtered_df.empty else raw_df
        
        if not display_target.empty:
            top_10 = display_target.head(10).copy().sort_values(by='도축실적', ascending=True)
            fig = px.bar(
                top_10, x='도축실적', y='도축장명', color='축종', orientation='h', text_auto=',.0f',
                color_discrete_map={'돼지': '#2563eb', '소': '#0f172a', '닭': '#94a3b8'}
            )
            fig.update_layout(plot_bgcolor='rgba(248,250,252,0.4)', paper_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 현재 표시할 수 있는 실시간 데이터 레코드가 0건입니다.")

    with col_table:
        st.markdown('<div class="section-title">📋 데이터 테이블 시트</div>', unsafe_allow_html=True)
        if not display_target.empty:
            st.dataframe(display_target, use_container_width=True, height=380)
        else:
            st.info("시트에 노출할 데이터 프레임이 비어 있습니다.")

with tab2:
    st.markdown('<div class="section-title">🔍 실시간 축산물 등급판정 시스템 검증</div>', unsafe_allow_html=True)
    animal_no = st.text_input("개체식별번호(이력번호 12자리) 입력", value="160053500174")
    if st.button("실시간 검증 실행", type="primary"):
        ekape_url = f"http://data.ekape.or.kr/openapi-data/service/user/grade/confirm/issueNo?animalNo={animal_no}&serviceKey={EKAPE_API_KEY}"
        try:
            res = requests.get(ekape_url, timeout=5)
            if res.status_code == 200:
                root = ET.fromstring(res.content.decode('utf-8', errors='ignore'))
                abatt_node = root.find('.//abattNm')
                grade_node = root.find('.//judgeGradeNm')
                st.success(f"🏢 도축장: {abatt_node.text if abatt_node is not None else '정보없음'} | 🎖️ 등급: {grade_node.text if grade_node is not None else '정보없음'}")
        except:
            st.error("축평원 API 호출 실패")
