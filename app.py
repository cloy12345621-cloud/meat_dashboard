import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd

# 1. 페이지 기본 설정 (가장 안전한 기본 테마)
st.set_page_config(
    page_title="축산물 및 도축업 데이터 통합 대시보드",
    page_icon="🥩",
    layout="wide"
)

st.title("🥩 축산물 및 도축업 데이터 통합 대시보드")
st.caption("농림축산식품부, 행정안전부, 축산물품질평가원 실시간 API 연동 시스템")

# 2. 공공데이터 API 인증키 설정 (★여기에 본인의 실제 키를 넣으세요★)
MAFRA_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'       # 1, 3번 농식품부 API용 키
MOIS_API_KEY = 'f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23'      # 4번 행안부 API용 키
EKAPE_API_KEY = 'fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677'     # 2번 축평원 API용 키

# =================================================================
# 1번 API 섹션: 전국 도축장별 축종별 도축실적 (실시간 목록)
# =================================================================
st.markdown("### 📊 1. 전국 도축장별 축종별 도축실적")
st.caption("농림축산식품부 오픈API 데이터 (JSON)")

@st.cache_data(ttl=3600)
def load_api_1():
    url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000428_1/1/999"
    try:
        res = requests.get(url).json()
        rows = res['Grid_20161216000000000428_1']['row']
        df = pd.DataFrame(rows).rename(columns={
            'ROW_NUM': '번호', 'CTPRVN_NM': '시도명', 'LSTK_SLALTO_NM': '도축장명', 'LVS_CTGRY_NM': '축종', 'SLAU_IEM_CO': '도축실적(두/수)'
        })
        return df[['번호', '시도명', '도축장명', '축종', '도축실적(두/수)']]
    except:
        return pd.DataFrame({"안내": ["API 연동 대기 중이거나 인증키를 확인해 주세요."]})

st.dataframe(load_api_1(), use_container_width=True)


# =================================================================
# 3번 API 섹션: 시도별 종합 도축실적 통계
# =================================================================
st.markdown("---")
st.markdown("### 📈 2. 시도별 종합 도축실적 통계")
st.caption("농림축산식품부 오픈API 데이터 (JSON)")

@st.cache_data(ttl=3600)
def load_api_3():
    url = f"http://211.237.50.150:7080/openapi/{MAFRA_API_KEY}/json/Grid_20161216000000000423_1/1/999"
    try:
        res = requests.get(url).json()
        rows = res['Grid_20161216000000000423_1']['row']
        df = pd.DataFrame(rows).rename(columns={
            'ROW_NUM': '번호', 'CTPRVN_NM': '시도명', 'LVS_CTGRY_NM': '축종', 'SLAU_IEM_CO': '총 도축 실적'
        })
        return df[['번호', '시도명', '축종', '총 도축 실적']]
    except:
        return pd.DataFrame({"안내": ["API 연동 대기 중이거나 인증키를 확인해 주세요."]})

st.dataframe(load_api_3(), use_container_width=True)


# =================================================================
# 4번 API 섹션: 행정안전부_동물_도축업 조회서비스
# =================================================================
st.markdown("---")
st.markdown("### 🏢 3. 전국 동물 도축업 허가 및 시설 현황")
st.caption("행정안전부 오픈API 데이터 (JSON)")

@st.cache_data(ttl=3600)
def load_api_4():
    url = f"https://apis.data.go.kr/1741000/slaughterhouses?serviceKey={MOIS_API_KEY}&pageNo=1&numOfRows=30&_type=json"
    try:
        res = requests.get(url).json()
        items = res['body']['items']
        df = pd.DataFrame(items)
        df['사업장명'] = df['bldngNm'].fillna(df.get('bopsNm', '-'))
        df['도로명주소'] = df['rdnWhlAddr'].fillna(df.get('siteWhlAddr', '-'))
        df['인허가일자'] = df['prmisnDt']
        df['영업상태'] = df['opnStateNm'].fillna('영업중')
        return df[['사업장명', '도로명주소', '인허가일자', '영업상태']]
    except:
        return pd.DataFrame({"안내": ["API 연동 대기 중이거나 인증키를 확인해 주세요."]})

st.dataframe(load_api_4(), use_container_width=True)


# =================================================================
# 2번 API 섹션: 축산물 등급판정확인서 발급번호정보
# =================================================================
st.markdown("---")
st.markdown("### 🔍 4. 축산물 등급판정확인서 발급 정보 조회")
st.caption("축산물품질평가원 오픈API 데이터 (XML)")

animal_no = st.text_input("조회할 개체식별번호(이력번호 12자리)를 입력하세요:", value="160053500174")

if st.button("실시간 조회하기", type="primary"):
    ekape_url = f"http://data.ekape.or.kr/openapi-data/service/user/grade/confirm/issueNo?animalNo={animal_no}&serviceKey={EKAPE_API_KEY}"
    try:
        response = requests.get(ekape_url, timeout=5)
        root = ET.fromstring(response.text)
        
        issueNo = root.find('.//issueNo').text if root.find('.//issueNo') is not None else '-'
        issueDate = root.find('.//issueDate').text if root.find('.//issueDate') is not None else '-'
        abattNm = root.find('.//abattNm').text if root.find('.//abattNm') is not None else '-'
        judgeGradeNm = root.find('.//judgeGradeNm').text if root.find('.//judgeGradeNm') is not None else '-'
        
        result_df = pd.DataFrame({
            "항목": ["발급번호", "발급일자", "도축장명", "판정등급"],
            "데이터 내용": [issueNo, issueDate, abattNm, judgeGradeNm]
        })
        st.table(result_df)
    except:
        st.error("등급 조회 API 연동에 실패했습니다. 인증키를 확인해 주세요.")
