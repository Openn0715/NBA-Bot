import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 數據獵殺 V17.1 穩定版", layout="wide")

# 獲取 Secrets
try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 錯誤：請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

NBA_TEAM_MAP = {
    'Atlanta Hawks': '老鷹', 'Boston Celtics': '塞爾提克', 'Brooklyn Nets': '籃網',
    'Charlotte Hornets': '黃蜂', 'Chicago Bulls': '公牛', 'Cleveland Cavaliers': '騎士',
    'Dallas Mavericks': '獨行俠', 'Denver Nuggets': '金塊', 'Detroit Pistons': '活塞',
    'Golden State Warriors': '勇士', 'Houston Rockets': '火箭', 'Indiana Pacers': '溜馬',
    'LA Clippers': '快艇', 'Los Angeles Clippers': '快艇', 'Los Angeles Lakers': '湖人',
    'Memphis Grizzlies': '灰熊', 'Miami Heat': '熱火', 'Milwaukee Bucks': '公鹿',
    'Minnesota Timberwolves': '灰狼', 'New Orleans Pelicans': '鵜鶘', 'New York Knicks': '尼克',
    'Oklahoma City Thunder': '雷霆', 'Orlando Magic': '魔術', 'Philadelphia 76ers': '76人',
    'Phoenix Suns': '太陽', 'Portland Trail Blazers': '拓荒者', 'Sacramento Kings': '國王',
    'San Antonio Spurs': '馬刺', 'Toronto Raptors': '暴龍', 'Utah Jazz': '爵士',
    'Washington Wizards': '巫師'
}

# ==========================================
# 2. 數據抓取模組 (加入快取防止白屏)
# ==========================================
@st.cache_data(ttl=3600)  # 快取 1 小時，避免頻繁請求 API 導致當機
def fetch_nba_stats():
    try:
        # 增加 headers 模擬瀏覽器，防止被 NBA 官網封鎖
        headers = {
            'Host': 'stats.nba.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'x-nba-stats-origin': 'stats',
            'Referer': 'https://stats.nba.com/'
        }
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced', 
            last_n_games=15,
            headers=headers,
            timeout=30 # 設定超時
        ).get_data_frames()[0]
        return stats
    except Exception as e:
        st.error(f"⚠️ NBA 官方數據連接超時，請重試。錯誤: {e}")
        return None

@st.cache_data(ttl=300) # 賠率快取 5 分鐘
def fetch_odds_data(url):
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return None

# ==========================================
# 3. 核心分析引擎
# ==========================================
class NBASuperAnalyser:
    def __init__(self, adv_stats):
        self.stats = adv_stats

    def analyze_game(self, game_mkt_spread, game_mkt_total):
        try:
            h_en = game_mkt_spread['home_team']
            a_en = game_mkt_spread['away_team']
            h_data = self.stats[self.stats['TEAM_NAME'] == h_en].iloc[0]
            a_data = self.stats[self.stats['TEAM_NAME'] == a_en].iloc[0]

            # A. 讓分分析
            fair_spread = -((h_data['E_NET_RATING'] - a_data['E_NET_RATING']) + 2.5)
            mkt_s_data = game_mkt_spread['bookmakers'][0]['markets'][0]['outcomes'][0]
            mkt_spread, mkt_s_price = mkt_s_data['point'], mkt_s_data['price']
            
            s_conf = 50 + (min(abs(fair_spread - mkt_spread) * 8, 40))
            s_rec = f"{NBA_TEAM_MAP.get(h_en)} {'讓分' if mkt_spread < 0 else '受讓'}" if fair_spread < mkt_spread else f"{NBA_TEAM_MAP.get(a_en)} {'讓分' if mkt_spread > 0 else '受讓'}"

            # B. 大小分分析
            avg_off_rtg = (h_data['E_OFF_RATING'] + a_data['E_OFF_RATING']) / 2
            avg_pace = (h_data['E_PACE'] + a_data['E_PACE']) / 2
            fair_total = (avg_off_rtg * avg_pace / 100) * 2
            
            mkt_t_data = game_mkt_total['bookmakers'][0]['markets'][0]['outcomes'][0]
            mkt_total = mkt_t_data['point']
            
            t_conf = 50 + (min(abs(fair_total - mkt_total) * 6, 45))
            t_rec = "全場大分" if fair_total > mkt_total else "全場小分"

            return {
                "matchup": f"{NBA_TEAM_MAP.get(a_en)} @ {NBA_TEAM_MAP.get(h_en)}",
                "s_fair": round(fair_spread, 1), "s_mkt": mkt_spread, "s_conf": int(s_conf), "s_rec": s_rec,
                "t_fair": round(fair_total, 1), "t_mkt": mkt_total, "t_conf": int(t_conf), "t_rec": t_rec,
                "pace": round(avg_pace, 1)
            }
        except: return None

# ==========================================
# 4. 執行與 UI
# ==========================================
st.title("🏀 NBA 數據獵殺 V17.1 穩定版")

with st.spinner('數據同步中... 若停留過久請刷新頁面'):
    adv_stats = fetch_nba_stats()
    
    if adv_stats is not None:
        base_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&oddsFormat=american"
        spread_data = fetch_odds_data(base_url + "&markets=spreads")
        total_data = fetch_odds_data(base_url + "&markets=totals")

        if spread_data and total_data:
            analyser = NBASuperAnalyser(adv_stats)
            for g_s in spread_data:
                g_t = next((t for t in total_data if t['id'] == g_s['id']), None)
                if not g_t: continue
                res = analyser.analyze_game(g_s, g_t)
                if not res: continue

                with st.container():
                    st.markdown(f"### 🏟️ {res['matchup']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("🎯 讓分 (Spread)")
                        st.metric("讓分信心度", f"{res['s_conf']}%")
                        st.write(f"數據基準: `{res['s_fair']}` | 推薦: **{res['s_rec']}**")
                    with c2:
                        st.subheader("📏 大小分 (Total)")
                        st.metric("大小分信心度", f"{res['t_conf']}%")
                        st.write(f"數據基準: `{res['t_fair']}` | 推薦: **{res['t_rec']}**")
                    st.divider()
        else:
            st.error("無法取得盤口數據，請檢查 API Key 是否正確。")
    else:
        st.info("💡 提示：NBA 伺服器回應較慢，請嘗試點擊右上角的三條線選單並選擇 'Rerun'。")
