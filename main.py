def main():
    print("Hello from dviz-lab!")


if __name__ == "__main__":
    main()

import re
import html
from itertools import combinations
from collections import Counter

import pandas as pd
import streamlit as st

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import altair as alt
import plotly.express as px
import networkx as nx

from konlpy.tag import Okt
from wordcloud import WordCloud

# ----------------------- 페이지 설정 ---------------------------
st.set_page_config(
    page_title='K팝 데몬 헌터스 팬덤 분석 대시보드',
    page_icon='🎬',
    layout='wide'
)


# ------------------ 상단 타이틀 ----------------------
st.title("🎬 넷플릭스 「K팝 데몬 헌터스」 팬덤 형성 요인 분석 대시보드")

st.markdown("""
### 홍익대학교 산업데이터공학과 C373022 장윤서

**과목:** 데이터 시각화 프로젝트 시험 3차 · **데이터 소스:** Naver News API
""")
st.divider()


# --------- 이 프로젝트에 대한 개요 ----------- 
# =========================================== AI의 도움 받음 =========================================
# 프로젝트에 대한 개요를 가독성 좋게 시각화 하고 싶어서 마크다운 내의 html을 작성할때 ai의 도움을 받았습니다. 
st.markdown("""
<div style="line-height:1.75;">


  </div>

  <div style="margin-top:6px; font-size:16px; color:#374151;">
    이 애플리케이션은 네이버 뉴스 기사(제목·요약) 데이터를 바탕으로
    <span style="color:#111827; font-weight:800;">「K팝 데몬 헌터스」</span> 이슈를 분석해<br>
    <span style="color:#4f46e5; font-weight:800;">기사량 추이</span> →
    <span style="color:#4f46e5; font-weight:800;">핵심 키워드</span> →
    <span style="color:#4f46e5; font-weight:800;">키워드 네트워크</span>
    흐름으로 팬덤 형성 요인을 정리합니다.
  </div>

  <div style="margin-top:14px; font-size:17px; color:#111827; font-weight:800;">
    🧭 사용법
  </div>

  <ol style="margin:6px 0 0 0; padding-left:20px; font-size:15.5px; color:#374151;">
    <li><b style="color:#111827;">사이드바에서 기간/집계 단위</b>를 먼저 선택하세요.</li>
    <li><b style="color:#111827;">Top N / 포커스 키워드</b>로 관심 주제를 좁히면 아래 그래프·테이블·네트워크가 함께 바뀝니다.</li>
    <li>네트워크가 복잡하면 <b style="color:#111827;">min_count</b>를 올려 핵심 연결만 보세요.</li>
  </ol>

  <div style="margin-top:10px; font-size:14.5px; color:#b45309;">
    <b>주의</b>: 기사량은 팬덤 “규모”가 아니라 <b>언론 노출(관심도)</b> 지표입니다.
  </div>

</div>
""", unsafe_allow_html=True)

def kpi(col, title, value, color="#111827", note=None):
    note_html = (
        f"<div style='font-size:14px; color:#6b7280; margin-top:4px; line-height:1.35;'>{note}</div>"
        if note else ""
    )

    col.markdown(f"""
    <div style="padding: 4px 0;">
      <div style="font-size:15.5px; color:#6b7280; font-weight:700; letter-spacing:0.2px;">
        {title}
      </div>
      <div style="font-size:34px; color:{color}; font-weight:900; line-height:1.05; margin-top:2px;">
        {value}
      </div>
      {note_html}
    </div>
    """, unsafe_allow_html=True)


# =====================================================================================================
st.divider()


# ----------- 데이터 로드 ----------------------
df = pd.read_csv('kpop_demon_hunters.csv')

df['dt'] = pd.to_datetime(df['pubDate'],utc=True)
df['dt'] = df['dt'].dt.tz_convert('Asia/Seoul').dt.tz_localize(None)

df['date'] = df['dt'].dt.date
df['hour'] = df['dt'].dt.hour

df['title'] = df['title'].astype(str)
df['description'] = df['description'].astype(str)

df['text'] = df['title'] + ' ' + df['description']
df['text'] = df['text'].apply(lambda x: html.unescape(re.sub('<[^>]+>', ' ', x)))
df['text'] = df['text'].str.replace(r'\s+', ' ', regex=True).str.strip()

# ------------- 폰트 설정 -------------------- 
font_path = "NotoSansKR-VariableFont_wght.ttf"
fm.fontManager.addfont(font_path)
font_name = fm.FontProperties(fname=font_path).get_name()
plt.rcParams['font.family'] = font_name
plt.rcParams['axes.unicode_minus'] = False


# ----------------- 사이드바 -----------------------
st.sidebar.header('대시보드 설정')

min_d = df["dt"].dt.date.min()
max_d = df["dt"].dt.date.max()

start_d, end_d = st.sidebar.date_input(
    "기간 선택", value=(min_d, max_d), min_value=min_d, max_value=max_d
)

unit = st.sidebar.selectbox('관심도 추이 집계 단위', ['일별', '주별'])

top_n = st.sidebar.slider('Top N 키워드', 10, 80, 30, 5)

min_count = st.sidebar.slider('네트워크 min_count(엣지 최소 동시출현)', 1, 30, 3, 1)

central_top_n = st.sidebar.slider('중심성 Top N', 5, 30, 10, 1)


# ------ 기간 필터 ------------------
mask = (df["dt"].dt.date >= start_d) & (df["dt"].dt.date <= end_d)
df_f = df.loc[mask].copy()

# ----------------- 전처리/명사 추출 -----------------------
okt = Okt()
stop_words = ['케데헌', '데몬', '헌터스','넷플릭스']

nouns_list = []
for t in df_f['text'].tolist():
    ns = okt.nouns(t)
    ns = [w for w in ns if len(w) >= 2 and not re.fullmatch(r'\d+', w) and w not in stop_words]
    nouns_list.append(ns)

df_f['nouns'] = nouns_list

# ----------------- 키워드 빈도 + 포커스 키워드 -----------------------
word_counter = Counter()

for nouns in df_f['nouns'].tolist():
    word_counter.update(nouns)

top_words = [w for w,c in word_counter.most_common(top_n)]
focus_keyword = st.sidebar.selectbox('포커스 키워드(담론 좁혀보기)', ['전체'] + top_words)

if focus_keyword == '전체':
    df_show = df_f.copy()
else:
    df_show = df_f[df_f['nouns'].apply(lambda xs: focus_keyword in xs)].copy()


# ----- 요약 지표 --------------------
st.subheader('📌 데이터 요약')

c1, c2, c3, c4 = st.columns(4)

total_articles = len(df_f)
unique_days = df_f['date'].nunique()

day_counts = df_f.groupby('date').size()
peak_day = day_counts.sort_values(ascending=False).index[0]
peak_count = int(day_counts.max())

c1, c2, c3, c4 = st.columns(4)

kpi(c1, "기사 수", f"{total_articles:,}", color="#111827")
kpi(c2, "분석 일수", f"{unique_days:,}일", color="#111827")
kpi(c3, "피크 날짜", str(peak_day), color="#4f46e5", note="관심도 급증 시점")
kpi(c4, "피크 기사 수", f"{peak_count:,}", color="#ef4444", note="최대 노출")

st.divider()


# --------------- altair chart ------------
st.subheader('📂  관심도(기사량) 추이')


if unit == '일별':
    ts = df_f.groupby('date').size().reset_index(name='count')
    ts['x'] = pd.to_datetime(ts['date'])
else:
    df_f['week'] = df_f['dt'].dt.to_period('W').dt.start_time.dt.date
    ts = df_f.groupby('week').size().reset_index(name='count')
    ts['x'] = pd.to_datetime(ts['week'])





chart = (
    alt.Chart(ts)
    .mark_line(point=True)
    .encode(
        x=alt.X('x:T', title='기간'),
        y=alt.Y('count:Q', title='기사 수'),
        tooltip=[alt.Tooltip('x:T', title='기간'), alt.Tooltip('count:Q', title='기사 수')]
    )
    .properties(height=280)
)
st.altair_chart(chart, use_container_width=True)




st.markdown(
    """
그래프의 최대 피크(12/09 전후)는 골든글로브 공식 발표로 **[K팝 데몬 헌터스]가 후보에 오른 소식이 확산**되며,  
언론 노출이 폭발한 구간으로 해석될 수 있다.

또한 피크 직후 기사량이 빠르게 감소하는 흐름은, 이 관심이 **지속 담론이라기보다 ‘수상/후보’ 같은 이벤트성 이슈에 의해 단기적으로 증폭된 버즈**였음을 시사한다.

- 참고 기사1: [조선비즈 기사 바로가기](https://biz.chosun.com/entertainment/enter_general/2025/12/09/TN3DVT2CSFEXLDGRCUNWRWAAWI/)
- 참고 기사2: [연합뉴스 기사 바로가기](https://www.yna.co.kr/view/AKR20251209001200071)
"""
)

st.divider()






# ----------- seaborn chart ---------------------

st.subheader('📂  핵심 키워드 Top N')

top_df = pd.DataFrame(word_counter.most_common(top_n), columns=['keyword', 'count'])

fig_kw = plt.figure(figsize=(8, 6))
ax = sns.barplot(data=top_df.head(20), y='keyword', x='count',color='gray')
ax.set_title('상위 키워드 Top 20')
ax.set_xlabel('빈도')
ax.set_ylabel('키워드')
st.pyplot(fig_kw)

st.markdown(
    '''
- 애니메이션/영화/감독/콘텐츠가 함께 나타나며, 단순 화제성을 넘어 작품성에 대한 팬덤 담론의 한 축을 이룬다.
- 글로벌/미국/세계/골든글로브/후보가 포함되어 있는 것으로 보아, 팬덤 확산에 해외 반응, 시상식 이슈 등이 주요한 진입 요인이 된 것을 확인할 수 있다. 

'''
)

st.divider()
# ----------------- plotly ---------------------
st.subheader('📂 담론 프레임 비중')
st.markdown('- 선택 기간에 기사들이 어떤 프레임(시상식/글로벌/콘텐츠/음악)으로 설명되는지 비중으로 확인할 수 있습니다.')

theme_map = {
    '시상식/성과': ['골든글로브', '후보', '수상', '어워즈', '빌보드', '차트', '1위', '흥행', '인기'],
    '글로벌/해외': ['글로벌', '미국', '세계', '현지', '해외'],
    '콘텐츠/제작': ['애니메이션', '영화', '감독', '작품', '콘텐츠', '소재', '문화'],
    '음악/아이돌': ['음악', '아이돌', '유튜브', '무대', '컬처']
}

theme_counter = Counter()
for ns in df_f['nouns'].tolist():
    s = set(ns)
    for theme, kws in theme_map.items():
        if any(k in s for k in kws):
            theme_counter[theme] += 1

theme_df = pd.DataFrame(theme_counter.items(), columns=['theme', 'articles'])

fig_theme = px.pie(theme_df, values='articles', names='theme', hole=0.45)
st.plotly_chart(fig_theme, use_container_width=True)



st.divider()
# ------------- 워드 클라우드 --------------
st.subheader('📂 워드클라우드')
st.markdown(
    ''' 
- 워드클라우드는 선택 기간에 기사에서 가장 많이 반복된 핵심 화제를 한눈에 보여줍니다.
- 크게 보이는 단어는 팬덤 확산 담론이 어떤 축으로 형성됐는지 보여줍니다. 
'''
)


wc = WordCloud(
    font_path = font_path,
    width = 900,
    height = 450,
    background_color='white'
).generate_from_frequencies(dict(word_counter.most_common(top_n)))

fig_wc = plt.figure(figsize=(10, 5))
plt.imshow(wc)
plt.axis('off')
st.pyplot(fig_wc)



# ------------------- 포커스 기사 테이블 --------------
st.subheader('📂 포커스 키워드 기반 기사 확인')
st.markdown('''
- 사이드바에서 포커스 키워드를 선택하면, 그 키워드가 포함된 기사만 아래 표에 모입니다. 
- 표에서 제목,요약을 확인하며 이 키워드가 어떤 맥락인지 확인할 수 있습니다. 
             ''')

df_show = df_show.sort_values('dt', ascending=False)
st.dataframe(df_show[['dt', 'title', 'description']].head(20), use_container_width=True)



st.divider()




# ---------- 키워드 동시 출현 ---------------
st.subheader('📂  키워드 동시 출현 네트워크')


vocab = set(top_words)

edge_counter = Counter()
for ns in df_show['nouns'].tolist():
    words = [w for w in ns if w in vocab]
    words = list(set(words))
    if len(words) >= 2:
        for a, b in combinations(sorted(words), 2):
            edge_counter[(a, b)] += 1



edges = [(a, b, w) for (a, b), w in edge_counter.items() if w >= min_count]


G = nx.Graph()
G.add_weighted_edges_from(edges)


fig_net = plt.figure(figsize=(10, 7))

pos = nx.spring_layout(G, k=0.7, seed=7)

deg = dict(G.degree())
node_sizes = [deg[n] * 200 for n in G.nodes()]

nx.draw_networkx_nodes(G, 
                       pos, 
                       node_size=node_sizes, 
                       alpha=0.85,
                       node_color='purple'
                       )

nx.draw_networkx_edges(G, 
                       pos, 
                       alpha=0.3
                       )

nx.draw_networkx_labels(G, 
                        pos,
                        font_family=font_name, 
                        font_size=10,
                        font_color='white'
                        )

plt.title('키워드 동시출현 네트워크')
plt.axis('off')
st.pyplot(fig_net)


dc = nx.degree_centrality(G)
dc_top = sorted(dc.items(), key=lambda x: x[1], reverse=True)[:central_top_n]
dc_df = pd.DataFrame(dc_top, columns=['keyword', 'degree_centrality'])

st.markdown('**중심성 Top 키워드**')
st.dataframe(dc_df, use_container_width=True)

st.divider()







# AI 링크 첨부 :https://chatgpt.com/share/693fab66-140c-8008-9492-664212ec9882