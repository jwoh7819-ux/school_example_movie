import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="일일 박스오피스", page_icon="🎬", layout="centered")
st.title("🎬 일일 박스오피스 조회")

# ==========================================
# 2. 날짜 선택기(달력) 설정
# ==========================================
# 서버 시간과 무관하게 한국 시간(KST)을 기준으로 '어제'를 계산합니다.
kst = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(kst)
yesterday_kst = today_kst - timedelta(days=1)

# 달력 위젯 생성 (기본값과 가장 늦게 선택할 수 있는 날짜를 '어제'로 고정)
selected_date = st.date_input(
    "조회할 날짜를 선택하세요:",
    value=yesterday_kst.date(),
    max_value=yesterday_kst.date()
)

# API가 이해할 수 있는 yyyymmdd 모양의 글자로 변환합니다.
target_dt = selected_date.strftime('%Y%m%d')

# ==========================================
# 3. 인증키 불러오기 (비밀 금고)
# ==========================================
try:
    kobis_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("🚨 **오류 확인:** API 키가 없습니다. Streamlit Cloud의 설정(Secrets)에서 `KOBIS_KEY`를 등록해 주세요.")
    st.stop()

# ==========================================
# 4. KOBIS API 요청
# ==========================================
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": kobis_key,
    "targetDt": target_dt
}

try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
except Exception:
    st.error("🚨 **오류 확인:** API 요청에 실패했습니다. 네트워크 상태나 KOBIS 서버를 확인해 주세요.")
    st.stop()

# ==========================================
# 5. 오류 및 데이터 집계 상태 확인
# ==========================================
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 이유")
    st.error(f"🚨 **오류 확인:** 인증키가 유효하지 않습니다. ({fault_msg})")
    st.stop()

if "boxOfficeResult" not in data or "dailyBoxOfficeList" not in data["boxOfficeResult"]:
    st.error("🚨 **오류 확인:** 예상치 못한 응답 구조입니다.")
    st.stop()

movie_list = data["boxOfficeResult"]["dailyBoxOfficeList"]

# 고른 날짜에 데이터가 아예 비어서 온 경우 안내
if len(movie_list) == 0:
    st.warning("⚠️ 그날은 아직 집계 전입니다.")
    st.stop()

# ==========================================
# 6. 데이터 전처리 (표 꾸미기)
# ==========================================
df = pd.DataFrame(movie_list)

# 계산이나 조건문에 쓰기 위해 문자열로 온 숫자들을 진짜 숫자로 바꿔줍니다.
df['rank'] = df['rank'].astype(int)
df['rankInten'] = df['rankInten'].astype(int)
df['audiCnt'] = df['audiCnt'].astype(int)
df['audiAcc'] = df['audiAcc'].astype(int)
df['scrnCnt'] = df['scrnCnt'].astype(int)

# 전날 대비 순위 증감에 따라 빨간 위 화살표, 파란 아래 화살표를 붙이는 함수
def format_rank_change(val):
    if val > 0:
        return f"🔺 {val}"
    elif val < 0:
        return f"🔻 {abs(val)}" # 음수 기호를 떼고 화살표만 붙입니다.
    else:
        return "-"

df['순위변동'] = df['rankInten'].apply(format_rank_change)

# 누적 관객수가 100만 명을 넘으면 영화명 옆에 트로피(🏆)를 붙이는 함수
def add_trophy(row):
    if row['audiAcc'] >= 1000000:
        return row['movieNm'] + " 🏆"
    return row['movieNm']

df['영화명'] = df.apply(add_trophy, axis=1)

# ==========================================
# 7. 대시보드 화면 구성
# ==========================================

# 🥇 [1위 영화 지표 카드]
top1 = df.iloc[0]
st.subheader(f"🥇 1위: {top1['영화명']}")

col1, col2, col3 = st.columns(3)
col1.metric("일일 관객수", f"{top1['audiCnt']:,} 명")
col2.metric("누적 관객수", f"{top1['audiAcc']:,} 명")
col3.metric("상영 스크린 수", f"{top1['scrnCnt']:,} 개")

st.divider()

# 📊 [상위 5편 관객수 막대그래프]
st.subheader("📊 상위 5편 일일 관객수")
# x축을 트로피가 붙은 '영화명'으로 설정하여 차트를 그립니다.
top5_df = df.head(5)[['영화명', 'audiCnt']].set_index('영화명')
st.bar_chart(top5_df)

st.divider()

# 📋 [전체 박스오피스 순위 표]
st.subheader("📋 상세 순위표")
# 순위 변동 기호와 트로피가 들어간 새로운 컬럼들을 선택해 표를 만듭니다.
display_df = df[['rank', '순위변동', '영화명', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
display_df.columns = ['순위', '순위변동', '영화명', '개봉일', '관객수', '누적관객', '스크린수']

st.dataframe(display_df, hide_index=True, use_container_width=True)
