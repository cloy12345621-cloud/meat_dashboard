import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.express as px

# 1. 페이지 테마 설정
st.set_page_config(
    page_title="축산물 물류 및 도축 데이터 분석 인텔리전스",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 가독성 스타일링
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght=400;500;600;700;800;900&display=swap');
    html, body, [class*="css"], .stMarkdown {
        font-family: 'Pretendard', sans-serif !important;
        color: #1e293b;
        letter-spacing: -0.04em !important;
    }
    .main-title { 
        font-size: 35px; font-weight: 800; color: #0f172a; margin-bottom: 6px;
        background: linear-gradient(135deg, #0f172a 0%, #2563eb 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .sub-title { font-size: 15px; font-weight: 500; color: #64748b; margin-bottom: 35px; }
    .section-title { 
        font-size: 21px; font-weight: 700; color: #0f172a; margin-bottom: 20px; 
        border-left: 6px solid #2563eb; padding-left: 12px;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff !important; border: 1px solid #e2e8f0 !important;
        border-radius: 14px !important; padding: 18px 24px !important;
    }
    </style>
""", unsafe_allow_html=True)

# API 인증키 설정
MAFRA_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'
EKAPE_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'
MOIS_API_KEY = 'f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23'

# ==========================================
# 🗺️ 사이드바 필터링 시스템
# ==========================================
st.sidebar.markdown("### 🎛️ 인텔리전스 필터")
selected_year = st.sidebar.selectbox("📅 기준 연도", ["2026년", "2025년"])
selected_region = st.sidebar.selectbox("📍 분석 지역 선택", ["전국", "전남", "경기", "충남", "경남", "경북", "제주"])
selected_animals = st.sidebar.multiselect("🐖 분석 축종", ["돼지", "소", "닭"], default=["돼지", "소", "닭"])

st.markdown('<div class="main-title">📈 축산물 물류 및 도축 실적 통합 인텔리전스</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">농림축산식품부 오픈 API 실시간 연동 시스템</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 거시 통계 및 시설 현황 분석", "🔍 B2C 실시간 축산물 이력 검증"])

with tab1:
    # [데이터 로드 엔진] 예외 추적 기능을 포함한 100% 리얼 데이터 바인딩
    @st.cache_data(ttl=600)
    def get_mafra_real_data():
        url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/1000"
        try:
            response = requests.get(url, timeout=15)
            res_json = response.json()
            
            # API 최상위 루트 키 찾기 (대소문자 무관)
            main_key = None
            for k in res_json.keys():
                if k.lower() == 'grid_20161216000000000428_1':
                    main_key = k
                    break
            
            if main_key and 'row' in res_json[main_key]:
                rows = res_json[main_key]['row']
                df = pd.DataFrame(rows)
                
                # 컬럼명을 모두 소문자로 변경하여 키 에러 원천 차단
                df.columns = df.columns.str.lower()
                
                # 규격서 필드 매핑
                rename_dict = {
                    'ctprvn_nm': '시도명',
                    'lstk_slalto_nm': '도축장명',
                    'lvs_ctgry_nm': '축종',
                    'slau_iem_co': '도축실적'
                }
                df = df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns})
                
                # 필수 컬럼 보장 및 클리닝
                required = ['시도명', '도축장명', '축종', '도축실적']
                for col in required:
                    if col not in df.columns:
                        df[col] = 0 if col == '도축실적' else "정보없음"
                
                df['시도명'] = df['시도명'].astype(str).str.strip()
                df['도축장명'] = df['도축장명'].astype(str).str.strip()
                df['축종'] = df['축종'].astype(str).str.strip()
                df['도축실적'] = pd.to_numeric(df['도축실적'], errors='coerce').fillna(0)
                
                return df[required], None
            else:
                return pd.DataFrame(), f"API 응답 구조 이상: {list(res_json.keys())}"
        except Exception as e:
            return pd.DataFrame(), f"통신 또는 파싱 에러 발생: {str(e)}"

    # 실제 API 호출 실행
    raw_df, error_msg = get_mafra_real_data()

    # 에러가 발생했다면 화면에 즉시 리포팅하여 원인 파악
    if error_msg:
        st.error(f"❌ API 로드 실패 디버깅 정보: {error_msg}")

    # 데이터가 정상적으로 존재할 때 필터링 공정 진행
    if not raw_df.empty:
        # 지역 필터링 (글자 포함 여부로 매칭률 극대화, 예: '전남' -> '전라남도' 둘 다 걸리도록)
        if selected_region != "전국":
            # 두 글자 지역명 매칭 보정 (경기 -> 경기도, 전남 -> 전라남도 등)
            region_keyword = selected_region[:2]
            raw_df = raw_df[raw_df['시도명'].str.contains(region_keyword, na=False)]
            
        # 축종 필터링
        if selected_animals:
            raw_df = raw_df[raw_df['축종'].isin(selected_animals)]
            
        # 도축실적 기준 역순 정렬
        raw_df = raw_df.sort_values(by='도축실적', ascending=False).reset_index(drop=True)

    # 대시보드 레이아웃 분할 배치
    col_graph, col_table = st.columns([6, 4])
    
    with col_graph:
        st.markdown('<div class="section-title">🏆 누적 도축 실적 분석 (실시간 API 데이터 TOP 10)</div>', unsafe_allow_html=True)
        if not raw_df.empty:
            top_10 = raw_df.head(10).copy()
            top_10 = top_10.sort_values(by='도축실적', ascending=True)
            
            fig = px.bar(
                top_10,
                x='도축실적',
                y='도축장명',
                color='축종',
                orientation='h',
                text_auto=',.0f',
                color_discrete_map={'돼지': '#2563eb', '소': '#0f172a', '닭': '#94a3b8'},
                labels={'도축실적': '도축량 (두/수)', '도축장명': ''}
            )
            fig.update_layout(
                plot_bgcolor='rgba(248, 250, 252, 0.4)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Pretendard", size=12), margin=dict(l=10, r=40, t=10, b=10), height=420
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 선택하신 필터 조건(지역/축종)에 부합하는 데이터가 API 결과 내에 존재하지 않거나 호출된 데이터가 비어 있습니다. 사이드바 필터를 변경해 보세요.")

    with col_table:
        st.markdown('<div class="section-title">📋 API 원본 실적 순위 전체 데이터 시트</div>', unsafe_allow_html=True)
        if not raw_df.empty:
            display_df = raw_df.copy()
            display_df.index = display_df.index + 1
            display_df.index.name = '순위'
            st.dataframe(display_df, use_container_width=True, height=385)
        else:
            st.info("표시할 실시간 API 원본 데이터가 없습니다.")

with tab2:
    st.markdown('<div class="section-title">🔍 실시간 축산물 등급판정 시스템 검증</div>', unsafe_allow_html=True)
    animal_no = st.text_input("개체식별번호(이력번호 12자리) 입력", value="160053500174")
    submit_btn = st.button("실시간 검증 실행", type="primary")
    
    if submit_btn:
        ekape_url = f"http://data.ekape.or.kr/openapi-data/service/user/grade/confirm/issueNo?animalNo={animal_no}&serviceKey={EKAPE_API_KEY}"
        try:
            response = requests.get(ekape_url, timeout=5)
            xml_data = response.content.decode('utf-8', errors='ignore')
            if response.status_code == 200 and "<response>" in xml_data:
                root = ET.fromstring(xml_data)
                st.success("✅ 축산물품질평가원 원장 조회 동기화 완료")
                
                abatt_node = root.find('.//abattNm')
                grade_node = root.find('.//judgeGradeNm')
                
                st.write(f"🏢 **도축장명:** {abatt_node.text if abatt_node is not None else '정보 없음'}")
                st.write(f"🎖️ **판정등급:** {grade_node.text if grade_node is not None else '정보 없음'}")
        except:
            st.error("축산물품질평가원 API 연동 실패")
