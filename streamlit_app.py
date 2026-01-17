import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 雙向數據獵殺 V17", layout="wide")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 錯誤：請在 Secrets 中設定 THE_ODDS_API_KEY")
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
# 2. 數據抓取模組
# ==========================================
class NBADataCore:
    @staticmethod
    def get_advanced_stats():
        # 抓取近 15 場數據作為基準
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced', 
            last_n_games=15
        ).get_data_frames()[0]
        return stats

# ==========================================
# 3. 核心分析引擎 (雙向獨立運算)
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

            # --- A. 讓分分析 (Spread) ---
            fair_spread = -((h_data['E_NET_RATING'] - a_data['E_NET_RATING']) + 2.5)
            mkt_s_data = game_mkt_spread['bookmakers'][0]['markets'][0]['outcomes'][0]
            mkt_spread = mkt_s_data['point']
            mkt_s_price = mkt_s_data['price']
            
            s_conf = 50
            s_diff = abs(fair_spread - mkt_spread)
            if s_diff > 2.5: s_conf += 25
            if mkt_s_price < -115: s_conf += 10
            
            s_rec = f"{NBA_TEAM_MAP.get(h_en)} {'讓分' if mkt_spread < 0 else '受讓'}" if fair_spread < mkt_spread else f"{NBA_TEAM_MAP.get(a_en)} {'讓分' if mkt_spread > 0 else '受讓'}"

            # --- B. 大小分分析 (Total) ---
            # 大小分基準公式：(兩隊進攻效率平均 * 預期節奏 / 100) * 2
            avg_off_rtg = (h_data['E_OFF_RATING'] + a_data['E_OFF_RATING']) / 2
            avg_pace = (h_data['E_PACE'] + a_data['E_PACE']) / 2
            fair_total = (avg_off_rtg * avg_pace / 100) * 2
            
            mkt_t_data = game_mkt_total['bookmakers'][0]['markets'][0]['outcomes'][0]
            mkt_total = mkt_t_data['point']
            mkt_t_price = mkt_t_data['price']
            
            t_conf = 50
            t_diff = abs(fair_total - mkt_total)
            if t_diff > 4.0: t_conf += 30
            if mkt_t_price < -115: t_conf += 5
            
            t_rec = "全場大分" if fair_total > mkt_total else "全場小分"

            return {
                "matchup": f"{NBA_TEAM_MAP.get(a_en)} @ {NBA_TEAM_MAP.get(h_en)}",
                "s_fair": round(fair_spread, 1), "s_mkt": mkt_spread, "s_conf": s_conf, "s_rec": s_rec,
                "t_fair": round(fair_total, 1), "t_mkt": mkt_total, "t_conf": t_conf, "t_rec": t_rec,
                "pace": round(avg_pace, 1)
            }
        except: return None

# ==========================================
# 4. 主程式 UI
# ==========================================
st.title("🏀 NBA 數據獵殺 V17：讓分/大小分雙向報告")
st.caption("每場比賽獨立分析：數據基準 vs 市場盤口 | 雙信心度分開顯示")

with st.spinner('正在同步數據與盤口...'):
    adv_stats = NBADataCore.get_advanced_stats()
    # 分別抓取讓分與大小分盤口
    base_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey=" + API_KEY + "&regions=us&oddsFormat=american"
    spread_data = requests.get(base_url + "&markets=spreads").json()
    total_data = requests.get(base_url + "&markets=totals").json()

    analyser = NBASuperAnalyser(adv_stats)

    for i, g_s in enumerate(spread_data):
        # 尋找對應的大小分數據
        g_t = next((t for t in total_data if t['id'] == g_s['id']), None)
        if not g_t: continue

        res = analyser.analyze_game(g_s, g_t)
        if not res: continue

        with st.container():
            st.markdown(f"### 🏟️ {res['matchup']}")
            
            col1, col2 = st.columns(2)
            
            # 讓分區塊
            with col1:
                st.markdown("<div style='background-color: #262730; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)
                st.subheader("🎯 讓分分析 (Spread)")
                st.write(f"數據基準: `{res['s_fair']}` | 市場盤口: `{res['s_mkt']}`")
                st.metric("讓分信心度", f"{res['s_conf']}%")
                st.markdown(f"**推薦下注：{res['s_rec']}**")
                st.markdown("</div>", unsafe_allow_html=True)

            # 大小分區塊
            with col2:
                st.markdown("<div style='background-color: #1e1e1e; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)
                st.subheader("📏 大小分分析 (Total)")
                st.write(f"數據基準: `{res['t_fair']}` | 市場盤口: `{res['t_mkt']}`")
                st.metric("大小分信心度", f"{res['t_conf']}%")
                st.markdown(f"**推薦下注：{res['t_rec']}**")
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.info(f"💡 戰術提示：本場預期節奏 {res['pace']}。若節奏高於 102，大分與強隊讓分優勢較明顯。")
            st.divider()

st.caption(f"最後更新：{datetime.now().strftime('%H:%M:%S')}")
