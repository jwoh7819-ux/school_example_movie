import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="centered")
st.title("🎬 어제의 박스오피스")

# ==========================================
# 2. 조회 날짜 계산 (한국 시간 기준 '어제')
# ==========================================
# 서버의 시간대와 상관없이 항상 한국 시간(KST)을 기준으로 계산합니다.
kst = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(kst)
yesterday_kst = today_kst - timedelta(days=1)

# API 요청에 필요한 yyyymmdd 형식으로 변환 (예: 20261020)
target_dt = yesterday_kst.strftime('%Y%m%d')

st.markdown(f"**🗓️ 조회 일자:** {yesterday_kst.strftime('%Y년 %m월 %d일')}")

# ==========================================
# 3. 인증키 불러오기 (비밀 금고)
# ==========================================
# Streamlit Cloud의 Advanced Settings -> Secrets에 설정된 값을 가져옵니다.
try:
    kobis_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("🚨 **오류 확인:** API 키가 없습니다. Streamlit Cloud의 설정(Secrets)에서 `KOBIS_KEY`를 등록해 주세요.")
    st.stop() # 코드를 여기서 멈춥니다.

# ==========================================
# 4. KOBIS API 요청
# ==========================================
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
params = {
    "key": kobis_key,
    "targetDt": target_dt
}

try:
    # API 서버에 데이터 요청하기
    response = requests.get(url, params=params)
    response.raise_for_status() # 인터넷 연결이나 서버 문제 등 HTTP 오류가 발생하면 예외 처리
    data = response.json()      # 응답 데이터를 파이썬 딕셔너리 형태로 변환
except Exception as e:
    st.error("🚨 **오류 확인:** API 요청에 실패했습니다. 네트워크 상태나 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()

# ==========================================
# 5. 응답 데이터 검증 및 오류 안내
# ==========================================
# 인증키가 틀렸을 때 KOBIS는 200 성공 코드와 함께 faultInfo를 보냅니다.
if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 이유")
    st.error(f"🚨 **오류 확인:** 인증키가 유효하지 않습니다. Secrets에 입력한 키가 맞는지 확인해 주세요. ({fault_msg})")
    st.stop()

# 정상적인 응답 구조(boxOfficeResult -> dailyBoxOfficeList)가 맞는지 확인합니다.
if "boxOfficeResult" not in data or "dailyBoxOfficeList" not in data["boxOfficeResult"]:
    st.error("🚨 **오류 확인:** 예상치 못한 응답 구조입니다. KOBIS API 공식 문서가 변경되었는지 확인해 주세요.")
    st.stop()

movie_list = data["boxOfficeResult"]["dailyBoxOfficeList"]

# 결과 목록이 비어있는 경우 (아직 집계 전이거나 데이터가 없는 경우)
if len(movie_list) == 0:
    st.warning("⚠️ **오류 확인:** 조회된 영화 목록이 없습니다. KOBIS에서 아직 어제 데이터를 집계하지 않았을 수 있습니다. 나중에 다시 시도해 주세요.")
    st.stop()

# ==========================================
# 6. 데이터프레임 변환 및 전처리 (문자열 -> 숫자)
# ==========================================
# 리스트 형태의 데이터를 판다스 데이터프레임으로 변환합니다.
df = pd.DataFrame(movie_list)

# KOBIS API는 숫자값도 모두 텍스트(문자열)로 주므로, 차트나 표를 위해 진짜 숫자로 바꿔줍니다.
df['rank'] = df['rank'].astype(int)
df['audiCnt'] = df['audiCnt'].astype(int)
df['audiAcc'] = df['audiAcc'].astype(int)
df['scrnCnt'] = df['scrnCnt'].astype(int)

# ==========================================
# 7. 대시보드 화면 구성
# ==========================================

# 🥇 [1위 영화 지표 카드]
top1 = df.iloc[0] # 첫 번째 줄이 1위 영화입니다.
st.subheader(f"🥇 1위: {top1['movieNm']}")

# 3개의 열을 만들어 지표 카드를 나란히 배치합니다.
col1, col2, col3 = st.columns(3)
col1.metric("일일 관객수", f"{top1['audiCnt']:,} 명")
col2.metric("누적 관객수", f"{top1['audiAcc']:,} 명")
col3.metric("상영 스크린 수", f"{top1['scrnCnt']:,} 개")

st.divider() # 구분선

# 📊 [상위 5편 관객수 막대그래프]
st.subheader("📊 상위 5편 일일 관객수")
# 1~5위 데이터만 자르고, x축을 영화명으로, y축을 일일 관객수로 쓰기 위해 인덱스를 영화명으로 바꿉니다.
top5_df = df.head(5)[['movieNm', 'audiCnt']].set_index('movieNm')
st.bar_chart(top5_df)

st.divider()

# 📋 [전체 박스오피스 순위 표]
st.subheader("📋 상세 순위표")
# 필요한 컬럼만 선택하고, 사용자에게 보여주기 좋게 한글 이름으로 바꿉니다.
display_df = df[['rank', 'movieNm', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
display_df.columns = ['순위', '영화명', '개봉일', '관객수', '누적관객', '스크린수']

# 데이터프레임을 화면에 출력합니다. (숫자 인덱스 숨기기, 화면 꽉 채우기 적용)
st.dataframe(display_df, hide_index=True, use_container_width=True)
