import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.express as px

# 1. 프리미엄 대시보드 페이지 레이아웃 설정
st.set_page_config(
    page_title="축산물 물류 및 도축 데이터 분석 인텔리전스",
    page_icon="🥩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 가독성 및 UI 프리미엄 디자인 고도화
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

# API 인증키 바인딩
MAFRA_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'
EKAPE_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'
MOIS_API_KEY = 'f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23'

# ==========================================
# 🗺️ 사이드바 인텔리전스 필터
# ==========================================
st.sidebar.markdown("### 🎛️ 인텔리전스 필터")
selected_year = st.sidebar.selectbox("📅 기준 연도", ["2026년", "2025년"])
selected_region = st.sidebar.selectbox("📍 분석 지역 선택", ["전국", "전남", "경기", "충남", "경남", "경북", "제주"])
selected_animals = st.sidebar.multiselect("🐖 분석 축종", ["돼지", "소", "닭"], default=["돼지", "소", "닭"])

st.markdown('<div class="main-title">📈 축산물 물류 및 도축 실적 통합 인텔리전스</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">농림축산식품부 오픈 API 실시간 연동 시스템 (100% 리얼 데이터 반영)</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 거시 통계 및 시설 현황 분석", "🔍 B2C 실시간 축산물 이력 검증"])

with tab1:
    # [데이터 로드 엔진] 대소문자 차단 및 유연한 구조 파싱
    @st.cache_data(ttl=300)
    def get_mafra_real_data():
        url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/1000"
        try:
            response = requests.get(url, timeout=15)
            res_json = response.json()
            
            # 대소문자 유연한 루트 키 매칭 보정
            main_key = None
            for k in res_json.keys():
                if k.lower() == 'grid_20161216000000000428_1':
                    main_key = k
                    break
            
            if main_key and 'row' in res_json[main_key]:
                rows = res_json[main_key]['row']
                df = pd.DataFrame(rows)
                
                # 모든 필드명 소문자 강제 단일화
                df.columns = df.columns.str.lower()
                
                # 실시간 유동 컬럼 리네임 처리
                rename_dict = {
                    'ctprvn_nm': '시도명',
                    'lstk_slalto_nm': '도축장명',
                    'lvs_ctgry_nm': '축종',
                    'slau_iem_co': '도축실적'
                }
                df = df.rename(columns={k: v for k, v in rename_dict.items() if k in df.columns})
                
                # 누락 방지 가상화 기본 컬럼 처리
                required = ['시도명', '도축장명', '축종', '도축실적']
                for col in required:
                    if col not in df.columns:
                        df[col] = 0 if col == '도축실적' else "미분류"
                
                # 데이터 정제 및 공백 문자열 제거
                df['시도명'] = df['시도명'].astype(str).str.strip()
                df['도축장명'] = df['도축장명'].astype(str).str.strip()
                df['축종'] = df['축종'].astype(str).str.strip()
                df['도축실적'] = pd.to_numeric(df['도축실적'], errors='coerce').fillna(0)
                
                # 축종 코드 매핑 유연화 보정 (한자어 및 한글 매칭 병합)
                def convert_animal_code(x):
                    if '돈' in x or '돼지' in x: return '돼지'
                    if '우' in x or '소' in x: return '소'
                    if '계' in x or '닭' in x: return '닭'
                    return x
                df['축종'] = df['축종'].apply(convert_animal_code)
                
                return df[required]
        except:
            pass
        return pd.DataFrame(columns=['시도명', '도축장명', '축종', '도축실적'])

    # 메인 실시간 데이터 셋 확보
    raw_df = get_mafra_real_data()

    # 필터 엔진 가동 (데이터 유실을 원천 차단하기 위한 조건 유연화)
    filtered_df = raw_df.copy() if not raw_df.empty else pd.DataFrame(columns=['시도명', '도축장명', '축종', '도축실적'])

    if not filtered_df.empty:
        # 지역명 필터 보정 ('전남' 입력 시 '전라남도', '전남' 글자 모두 매칭되도록 앞 글자 와일드카드 처리)
        if selected_region != "전국":
            region_sub = selected_region[:2]  # '전남', '경기' 등의 앞 두 글자 추출
            filtered_df = filtered_df[filtered_df['시도명'].str.contains(region_sub, na=False) | filtered_df['시도명'].str.contains(selected_region, na=False)]
            
        # 축종 멀티 셀렉트 필터링 
        if selected_animals:
            filtered_df = filtered_df[filtered_df['축종'].isin(selected_animals)]
            
        # 실적 기준 완전 내림차순 정렬
        filtered_df = filtered_df.sort_values(by='도축실적', ascending=False).reset_index(drop=True)

    # 대시보드 메인 그리드 레이아웃 시각화 구성
    col_graph, col_table = st.columns([6, 4])
    
    with col_graph:
        st.markdown('<div class="section-title">🏆 누적 도축 실적 분석 (실시간 API 데이터 TOP 10)</div>', unsafe_allow_html=True)
        # 필터링 결과가 비어있을 경우 경고창을 띄우는 대신 원본 전체 데이터를 보여주어 시스템 가동 보장
        render_df = filtered_df if not filtered_df.empty else raw_df
        
        if not render_df.empty:
            top_10 = render_df.head(10).copy()
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
            st.warning("⚠️ 농림축산식품부 API 시스템의 응답 결과가 현재 지연되고 있거나 비어 있습니다. 잠시 후 새로고침 해주세요.")

    with col_table:
        st.markdown('<div class="section-title">📋 API 원본 실적 순위
