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
    .stTabs [aria-selected="true"] { color: #DDA853 !
