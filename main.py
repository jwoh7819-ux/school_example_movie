import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import altair as alt

# ==========================================
# 1. 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="일일 박스오피스", page_icon="🎬", layout="centered")
st.title("🎬 일일 박스오피스 조회")

# ==========================================
# 2. 날짜 선택기(달력) 설정
# ==========================================
kst = pytz.timezone('Asia/Seoul')
today_kst = datetime.now(kst)
yesterday_kst = today_kst - timedelta(days=1)

selected_date = st.date_input(
    "조회할 날짜를 선택하세요:",
    value=yesterday_kst.date(),
    max_value=yesterday_kst.date()
)

target_dt = selected_date.strftime('%Y%m%d')

# ==========================================
# 3. 인증키 불러오기
# ==========================================
try:
    kobis_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("🚨 **오류 확인:** API 키가 없습니다. Streamlit Cloud의 설정(Secrets)에서 `KOBIS_KEY`를 등록해 주세요.")
    st.stop()

# ==========================================
# 4. KOBIS 박스오피스 API 요청
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

if "faultInfo" in data:
    fault_msg = data["faultInfo"].get("message", "알 수 없는 이유")
    st.error(f"🚨 **오류 확인:** 인증키가 유효하지 않습니다. ({fault_msg})")
    st.stop()

if "boxOfficeResult" not in data or "dailyBoxOfficeList" not in data["boxOfficeResult"]:
    st.error("🚨 **오류 확인:** 예상치 못한 응답 구조입니다.")
    st.stop()

movie_list = data["boxOfficeResult"]["dailyBoxOfficeList"]

if len(movie_list) == 0:
    st.warning("⚠️ 그날은 아직 집계 전입니다.")
    st.stop()

# ==========================================
# 5. 데이터 전처리
# ==========================================
df = pd.DataFrame(movie_list)

df['rank'] = df['rank'].astype(int)
df['rankInten'] = df['rankInten'].astype(int)
df['audiCnt'] = df['audiCnt'].astype(int)
df['audiInten'] = df['audiInten'].astype(int) # 전일 대비 일일 관객수 증감
df['audiAcc'] = df['audiAcc'].astype(int)
df['scrnCnt'] = df['scrnCnt'].astype(int)

def format_rank_change(val):
    if val > 0:
        return f"🔺 {val}"
    elif val < 0:
        return f"🔻 {abs(val)}"
    else:
        return "-"

df['순위변동'] = df['rankInten'].apply(format_rank_change)

def add_trophy(row):
    if row['audiAcc'] >= 1000000:
        return row['movieNm'] + " 🏆"
    return row['movieNm']

df['영화명'] = df.apply(add_trophy, axis=1)

# ==========================================
# 6. 1위 영화 상세 정보 가져오기 (KOBIS 영화상세정보 API)
# ==========================================
top1 = df.iloc[0]
movie_cd = top1['movieCd'] # 1위 영화의 고유 코드

info_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
info_params = {
    "key": kobis_key,
    "movieCd": movie_cd
}

movie_info_text = "상세 정보를 불러올 수 없습니다."
try:
    info_res = requests.get(info_url, params=info_params)
    info_data = info_res.json()
    if "movieInfoResult" in info_data:
        minfo = info_data["movieInfoResult"]["movieInfo"]
        directors = ", ".join([d['peopleNm'] for d in minfo.get('directors', [])])
        genres = ", ".join([g['genreNm'] for g in minfo.get('genres', [])])
        actors = ", ".join([a['peopleNm'] for a in minfo.get('actors', [])[:3]]) # 주요 배우 3명까지만
        showTm = minfo.get('showTm', '정보없음')
        
        movie_info_text = f"**장르:** {genres} &nbsp;|&nbsp; **감독:** {directors} &nbsp;|&nbsp; **상영시간:** {showTm}분\n\n**주요 배우:** {actors if actors else '정보없음'}"
except Exception:
    pass

# ==========================================
# 7. 대시보드 화면 구성
# ==========================================

# 🥇 [1위 영화 지표 카드 및 상세정보]
st.subheader(f"🥇 1위: {top1['영화명']}")
st.info(movie_info_text) # 1위 영화 상세정보 출력

col1, col2, col3 = st.columns(3)
# st.metric의 delta 인자를 사용하면 자동으로 증감을 초록색/빨간색으로 표시해 줍니다.
col1.metric("일일 관객수", f"{top1['audiCnt']:,} 명", delta=f"{top1['audiInten']:,} 명 (전일대비)")
col2.metric("누적 관객수", f"{top1['audiAcc']:,} 명", delta=f"{top1['audiCnt']:,} 명 (오늘추가)")
col3.metric("상영 스크린 수", f"{top1['scrnCnt']:,} 개")

st.divider()

# 📊 [상위 5편 관객수 막대그래프 - 스크롤 줌 방지]
st.subheader("📊 상위 5편 일일 관객수")
top5_df = df.head(5)

# Altair를 사용하여 스크롤해도 그래프가 확대/축소되지 않도록 고정합니다.
chart = alt.Chart(top5_df).mark_bar(color='#FF4B4B').encode(
    x=alt.X('영화명', sort=None, title='영화명', axis=alt.Axis(labelAngle=0)), # 라벨 가로 출력
    y=alt.Y('audiCnt', title='일일 관객수 (명)'),
    tooltip=['영화명', 'audiCnt'] # 마우스를 올렸을 때 관객수 표시
).properties(
    height=400
)

st.altair_chart(chart, use_container_width=True)

st.divider()

# 📋 [전체 박스오피스 순위 표]
st.subheader("📋 상세 순위표")
display_df = df[['rank', '순위변동', '영화명', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
display_df.columns = ['순위', '순위변동', '영화명', '개봉일', '관객수', '누적관객', '스크린수']

st.dataframe(display_df, hide_index=True, use_container_width=True)
