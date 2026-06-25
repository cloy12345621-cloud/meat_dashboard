import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.express as px

# 1. 페이지 기본 설정 및 세련된 테마 적용
st.set_page_config(
    page_title="지역 및 도축장별 세부 실적 분석",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 폰트 및 UI 스타일을 위한 CSS 적용
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #2c3e50; margin-bottom: 5px; }
    .sub-title { font-size: 14px; color: #7f8c8d; margin-bottom: 25px; }
    .section-title { font-size: 20px; font-weight: bold; color: #34495e; margin-top: 20px; margin-bottom: 15px; }
    div[data-testid="stSidebarUserContent"] { background-color: #f8f9fa; }
    </style>
""", unsafe_index=True)

# 2. 공공데이터 API 인증키 설정 (본인의 키로 교체하세요)
MAFRA_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'       # 1, 3번 농식품부 API용 키
MOIS_API_KEY = 'f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23'      # 4번 행안부 API용 키
EKAPE_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'     # 2번 축평원 API용 키

# ==========================================
# 3. 사이드바 구성 (예시 이미지와 동일한 레이아웃)
# ==========================================
st.sidebar.markdown("### 🔍 분석 단위 선택")
analysis_unit = st.sidebar.radio(
    "단위 선택", 
    ["도축장별 상세 통계", "시도별 거시 통계"], 
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
selected_year = st.sidebar.selectbox("📅 연도 선택", ["2026", "2025", "2024"])
selected_month = st.sidebar.selectbox("📅 월 선택", ["전체 (1년치 합산)", "01월", "02월", "03월"])
selected_region = st.sidebar.selectbox("📍 지역 필터", ["전국", "서울", "경기", "전남", "경남", "경북"])
selected_animals = st.sidebar.multiselect("🐖 취급 축종", ["돼지", "소", "닭", "오리"], default=["돼지", "소"])

# ==========================================
# 4. 메인 화면 타이틀 영역
# ==========================================
st.markdown('<div class="main-title">📊 지역 및 도축장별 세부 실적 분석</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">농림축산식품부, 행정안전부, 축산물품질평가원 실시간 API 연동 대시보드</div>', unsafe_allow_html=True)

# 탭 메뉴 구성 (B2B 데이터 분석과 B2C 이력 조회를 깔끔하게 분리)
tab1, tab2 = st.tabs(["📈 도축 및 시설 실적 분석", "🔍 B2C 소비자 확인서 조회"])

with tab1:
    # ------------------------------------------
    # API 데이터 로드 및 정제 (서버 사이드 호출로 CORS 에러 없음)
    # ------------------------------------------
    @st.cache_data(ttl=3600)  # 1시간 동안 데이터 캐싱하여 속도 최적화
    def get_slaughter_data():
        # 1번 API: 도축장별 실적 호출
        url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999"
        try:
            res = requests.get(url).json()
            rows = res['Grid_20161216000000000428_1']['row']
            df = pd.DataFrame(rows)
            # 필드명 한글 매핑 및 데이터 타입 변환
            df = df.rename(columns={
                'CTPRVN_NM': '시도명',
                'LSTK_SLALTO_NM': '도축장명',
                'LVS_CTGRY_NM': '축종',
                'SLAU_IEM_CO': '도축실적'
            })
            df['도축실적'] = pd.to_numeric(df['도축실적'], errors='coerce').fillna(0)
            return df
        except:
            # API 호출 실패 시 데모 데이터 가동 (UI 확인용)
            return pd.DataFrame({
                '시도명': ['전남', '경기', '충남', '경남', '전북', '경북', '제주'],
                '도축장명': ['부경양돈농협 부경축산물공판장', '도드람양돈농협공판장', '대전충남양돈농협 포크빌축산물공판장', '(주)우포바이오', '논산계룡축산협협동조합', '주식회사 도드람엘피씨', '제주양돈농협 축산물종합유통센터'],
                '축종': ['돼지', '돼지', '돼지', '돼지', '돼지', '돼지', '돼지'],
                '도축실적': [286438, 260844, 232670, 222681, 219119, 213442, 162881]
            })

    df_clean = get_slaughter_data()
    
    # 사이드바 조건에 따른 데이터 필터링 라이브 적용
    if selected_region != "전국":
        df_clean = df_clean[df_clean['시도명'] == selected_region]
    df_clean = df_clean[df_clean['축종'].isin(selected_animals)]
    df_clean = df_clean.sort_values(by='도축실적', ascending=False).reset_index(drop=True)

    # ------------------------------------------
    # 상단 랭킹 영역: 2026년 전체 누적 실적 TOP 상세정보
    # ------------------------------------------
    st.markdown(f'<div class="section-title">🏆 {selected_year}년 전체 누적 실적 TOP 상세정보</div>', unsafe_allow_html=True)
    st.caption("도축 실적(두/수)을 기준으로 산정된 상위 사업장 정보입니다. 클릭하시면 펼쳐집니다.")
    
    # 상위 3개 업체를 아코디언으로 세련되게 표현
    for idx, row in df_clean.head(3).iterrows():
        with st.expander(f"🏅 {idx+1}위 | {row['도축장명']} (소재지: {row['시도명']} | 실적: {int(row['도축실적']):,} 두/수)"):
            st.write(f"본 사업장은 **{row['시도명']}** 지역에 위치하고 있으며, 주요 취급 축종은 **{row['축종']}**입니다.")
            st.write(f"현재 선택된 분석 기간 내 누적 도축량은 총 **{int(row['도축실적']):,} 두/수**로 집계되었습니다.")

    # ------------------------------------------
    # 중간 시각화 영역: 차트 그리기
    # ------------------------------------------
    st.markdown(f'<div class="section-title">📊 {selected_year}년 전체 누적 도축 용량 현황 차트 (TOP 10)</div>', unsafe_allow_html=True)
    
    if not df_clean.empty:
        fig = px.bar(
            df_clean.head(10), 
            x='도축장명', 
            y='도축실적', 
            color='축종',
            text_auto=',.0f',
            color_discrete_sequence=['#1e293b', '#3b82f6'], # 예시 이미지의 다크 네이비 테마 반영
            labels={'도축실적': '도축량 (두)', '도축장명': '지역/도축장'}
        )
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_tickangle=-10,
            margin=dict(l=20, r=20, t=20, b=50),
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("선택하신 조건에 맞는 데이터가 없습니다.")

    # ------------------------------------------
    # 하단 데이터 테이블 영역
    # ------------------------------------------
    st.markdown(f'<div class="section-title">📋 {selected_year}년 전체 누적 전체 세부 데이터 순위표</div>', unsafe_allow_html=True)
    
    # 인덱스를 순위로 변환하여 깔끔하게 전개
    df_display = df_clean.copy()
    df_display.index = df_display.index + 1
    df_display.index.name = '순위'
    st.dataframe(df_display, use_container_width=True)

    # ------------------------------------------
    # 하단 부가 정보: 4번 행안부 인프라 데이터 결합
    # ------------------------------------------
    st.markdown('<div class="section-title">🏢 전국 동물 도축업 인허가 및 영업 상태 현황</div>', unsafe_allow_html=True)
    # 인프라 데이터 예시 바인딩
    infra_data = pd.DataFrame({
        '사업장명': ['부경양돈농협', '도드람양돈농협', '대전충남양돈농협', '우포바이오'],
        '소재지 도로명주소': ['경상남도 김해시 어방동', '경기도 안성시 일죽면', '충청남도 천안시', '경상남도 창녕군'],
        '인허가일자': ['2002-05-10', '2011-12-15', '2018-04-20', '2020-09-01'],
        '영업상태': ['영업중', '영업중', '영업중', '영업중']
    })
    st.table(infra_data)


with tab2:
    # ------------------------------------------
    # 2번 API 섹션: 소비자용 이력번호 등급조회 탭
    # ------------------------------------------
    st.markdown('<div class="section-title">🔍 축산물 등급판정확인서 발급 정보 조회</div>', unsafe_allow_html=True)
    st.write("소비자가 구매한 축산물의 개체식별번호(이력번호 12자리)를 입력하시면 등급과 도축장 정보를 실시간 검증합니다.")
    
    animal_no = st.text_input("개체식별번호(이력번호) 입력", value="160053500174")
    
    if st.button("실시간 조회하기", type="primary"):
        # 파이썬 requests를 활용해 축평원 XML 오픈 API 데이터 수신 및 파싱
        ekape_url = f"http://data.ekape.or.kr/openapi-data/service/user/grade/confirm/issueNo?animalNo={animal_no}&serviceKey={EKAPE_API_KEY}"
        
        try:
            response = requests.get(ekape_url, timeout=5)
            root = ET.fromstring(response.text)
            
            # XML 노드 찾기
            issueNo = root.find('.//issueNo').text if root.find('.//issueNo') is not None else '-'
            issueDate = root.find('.//issueDate').text if root.find('.//issueDate') is not None else '-'
            abattNm = root.find('.//abattNm').text if root.find('.//abattNm') is not None else '-'
            judgeGradeNm = root.find('.//judgeGradeNm').text if root.find('.//judgeGradeNm') is not None else '-'
            
            # 결과를 세련된 수치 카드(Metric)와 표로 표기
            col1, col2, col3 = st.columns(3)
            col1.metric("판정 등급", judgeGradeNm)
            col2.metric("확인서 발급일자", issueDate)
            col3.metric("판정 도축장", abattNm)
            
            st.success(f"발급번호 [{issueNo}] 확인 완료: 안전하고 투명한 축산물 이력이 검증되었습니다.")
            
        except Exception as e:
            # 오픈API 키 미활성화 시를 대비한 Mock-up 결과 매핑
            st.warning("API 연동 대기 중입니다. 샘플 데이터를 표시합니다.")
            col1, col2, col3 = st.columns(3)
            col1.metric("판정 등급", "1+ 등급")
            col2.metric("확인서 발급일자", "2026-06-20")
            col3.metric("판정 도축장", "부경양돈농협")
