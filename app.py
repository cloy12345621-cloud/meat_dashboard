# ⚠️ 본인의 인증키를 여기에 입력하세요 (Decoding된 키가 에러 확률이 적습니다)
API_KEY = "fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677"

@st.cache_data(ttl=3600)
def load_slaughter_data():
    """ 
    2. 시도별 도축실적 & 3. 도축장별 축종별 도축실적 API 호출
    주소 뒷부분에 인증키(key)와 요청 제한 수(1/999)를 매핑합니다.
    """
    # [2번 API] 시도별 도축실적 (최대 999건 대량 로드)
    url_sido = f"http://211.237.50.150:7080/openapi/{fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677}/json/Grid_20161216000000000423_1/1/999"
    
    # [3번 API] 도축장별 축종별 도축실적 (최대 999건 대량 로드)
    url_factory = f"http://211.237.50.150:7080/openapi/{fd487f73ec35ea535a3576023f80e8c388c468cd8c69d8f0221ba152c7f6d677}/json/Grid_20161216000000000428_1/1/999"
    
    # 기본 데이터프레임 초기화 (API 장애 대비)
    df_sido = pd.DataFrame()
    df_factory = pd.DataFrame()
    
    try:
        res_sido = requests.get(url_sido).json()
        df_sido = pd.DataFrame(res_sido['Grid_20161216000000000423_1']['row'])
        # 문자열로 들어오는 실적 데이터를 연산을 위해 숫자로 변환
        if 'AUCO_LSTK_AMN' in df_sido.columns:
            df_sido['AUCO_LSTK_AMN'] = pd.to_numeric(df_sido['AUCO_LSTK_AMN'])
    except Exception as e:
        st.sidebar.error(f"시도별 API 로드 실패: {e}")
        # 예외 발생 시 빈 데이터 대신 구동을 위한 데모 데이터 dummy 처리 로직 진입 가능

    try:
        res_factory = requests.get(url_factory).json()
        df_factory = pd.DataFrame(res_factory['Grid_20161216000000000428_1']['row'])
        if 'SLAU_AMN' in df_factory.columns:
            df_factory['SLAU_AMN'] = pd.to_numeric(df_factory['SLAU_AMN'])
    except Exception as e:
        st.sidebar.error(f"도축장별 API 로드 실패: {e}")
        
    return df_sido, df_factory


@st.cache_data(ttl=3600)
def load_slaughterhouse_info():
    """ 
    4. 행정안전부_동물_도축업 조회서비스 (공공데이터포털 End Point)
    """
    endpoint = "https://apis.data.go.kr/1741000/slaughterhouses"
    
    # 공공데이터포털 표준 파라미터 구조 (JSON 포맷으로 1000건 대량 요청)
    params = {
        "serviceKey": f0c7c3349d71c4359761cd1d223198091f1e486eaeef0324e1f36c5cb0274e23,
        "type": "json",
        "pIndex": 1,
        "pSize": 1000 
    }
    
    try:
        response = requests.get(endpoint, params=params)
        res_json = response.json()
        
        # 행안부 API 특유의 구조에 맞춰 key값 파싱 (실제 제공되는 데이터 key에 맞게 수정 필요할 수 있음)
        if 'slaughterhouses' in res_json:
            return pd.DataFrame(res_json['slaughterhouses'])
        elif 'row' in res_json:
            return pd.DataFrame(res_json['row'])
        else:
            # 예상치 못한 구조일 경우 전체를 데이터프레임화 시도
            return pd.DataFrame(res_json)
    except Exception as e:
        st.sidebar.error(f"행안부 도축업 인프라 API 로드 실패: {e}")
        return pd.DataFrame()
