import streamlit as st
import feedparser
from newspaper import Article, Config
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk
import ssl

# 웹 UI 디자인
st.set_page_config(page_title="오늘의 뉴스 요약 리포트", page_icon="📰", layout="wide")

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# NLTK 데이터 다운로드 (요약기에서 필요)
@st.cache_resource(show_spinner=False)
def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)

download_nltk_data()

# Google News RSS 피드 URL (한국어)
GENRES = {
    "정치": "https://news.google.com/rss/headlines/section/topic/POLITICS?hl=ko&gl=KR&ceid=KR:ko",
    "경제": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
    "사회": "https://news.google.com/rss/headlines/section/topic/NATION?hl=ko&gl=KR&ceid=KR:ko",
    "IT/과학": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko",
    "세계": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=ko&gl=KR&ceid=KR:ko",
}

def summarize_text(text, sentences_count=3):
    if not text or len(text.strip()) < 50:
        return "본문이 너무 짧거나 제공되지 않아 요약할 수 없습니다."
    
    try:
        # Sumy를 이용한 추출 요약
        # 'korean' 대신 'english' tokenizer를 사용해도 문장 분리에 무리 없음 (punkt 기반)
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        summary_sentences = summarizer(parser.document, sentences_count)
        
        summary = " ".join([str(s) for s in summary_sentences])
        if not summary.strip():
            raise ValueError("요약 결과가 비어있음")
        return summary
    except Exception as e:
        # 에러 발생 시 단순 문자열 자르기(Fallback)
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 30]
        if paragraphs:
            return " ".join(paragraphs[:sentences_count]) + "..."
        return "본문을 요약하는 중 오류가 발생했습니다."

@st.cache_data(ttl=1800, show_spinner=False)  # 30분 캐싱
def fetch_and_summarize_news(genre_url, max_articles=5):
    feed = feedparser.parse(genre_url)
    articles_data = []
    
    # User-Agent 설정 (크롤링 차단 방지)
    config = Config()
    config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    config.request_timeout = 10
    
    for entry in feed.entries[:max_articles]:
        title = entry.title
        link = entry.link
        published = entry.get("published", "")
        
        try:
            # 기사 본문 스크래핑
            article = Article(link, config=config, language='ko')
            article.download()
            article.parse()
            text = article.text
            image_url = article.top_image if article.top_image else None
            
            # 본문 요약
            summary = summarize_text(text, sentences_count=3)
            
        except Exception as e:
            summary = f"본문을 수집할 수 없습니다 (접근 제한 등)."
            image_url = None
            
        articles_data.append({
            "title": title,
            "link": link,
            "summary": summary,
            "image": image_url,
            "published": published
        })
        
    return articles_data

# -------------------
# Custom CSS for modern design
st.markdown("""
<style>
    .news-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .news-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
    }
    .news-title {
        color: #1a73e8;
        text-decoration: none;
        font-weight: bold;
        font-size: 1.25rem;
    }
    .news-title:hover {
        text-decoration: underline;
    }
    .news-date {
        color: #6c757d;
        font-size: 0.85rem;
        margin-bottom: 10px;
        display: block;
    }
    .news-summary {
        color: #343a40;
        line-height: 1.6;
        margin-top: 10px;
        padding-left: 10px;
        border-left: 3px solid #1a73e8;
    }
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .news-card { background-color: #1e1e1e; border-color: #2d2d2d; }
        .news-title { color: #8ab4f8; }
        .news-summary { color: #e8eaed; border-left: 3px solid #8ab4f8; }
        .news-date { color: #9aa0a6; }
    }
</style>
""", unsafe_allow_html=True)

st.title("📰 오늘의 뉴스 자동 요약 리포트")
st.markdown("매일 갱신되는 장르별 주요 뉴스를 인공지능 추출 기법으로 자동 요약하여 제공합니다. (API Key 불필요)")
st.markdown("---")

# 장르별 탭 생성
tab_objects = st.tabs(list(GENRES.keys()))

for tab, (genre, url) in zip(tab_objects, GENRES.items()):
    with tab:
        st.subheader(f"🏷️ {genre} 주요 뉴스")
        
        with st.spinner(f"최신 {genre} 뉴스를 로딩하고 요약 중입니다... 잠시만 기다려주세요."):
            news_items = fetch_and_summarize_news(url)
            
            if not news_items:
                st.warning("뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
            else:
                for item in news_items:
                    # Rendering Card Layout
                    with st.container():
                        st.markdown(f'''
                        <div class="news-card">
                            <a href="{item['link']}" target="_blank" class="news-title">{item['title']}</a>
                            <span class="news-date">{item['published']}</span>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if item['image']:
                                st.image(item['image'], use_container_width=True)
                            else:
                                st.markdown("<div style='text-align:center; padding: 20px; background:#e9ecef; border-radius:8px; color:#6c757d;'>이미지<br>없음</div>", unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f'<div class="news-summary">{item["summary"]}</div>', unsafe_allow_html=True)
                            
                        st.markdown("<br>", unsafe_allow_html=True)
