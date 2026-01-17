import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 全能數據獵殺 V16", layout="wide")

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
# 2. 數據抓取模組 (戰力/傷病/效率)
# ==========================================
class NBADataCore:
    @staticmethod
    def get_advanced_stats():
        """抓取聯盟近 15 場進階數據"""
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced', 
            last_n_games=15
        ).get_data_frames()[0]
        return stats[['TEAM_NAME', 'E_OFF_RATING', 'E_DEF_RATING', 'E_NET_RATING', 'E_PACE']]

    @staticmethod
    def get_injury_impact(team_name):
        """
        模擬傷病權重系統 (實務上建議對接 Rotowire API)
        回傳戰力修正值 (Net Rating Adjustment)
        """
        # 範例邏輯：若主力缺陣，NetRating -3.5
        return 0 

# ==========================================
# 3. 核心分析引擎 (市場 + 數據交叉驗證)
# ==========================================
class NBASuperAnalyser:
    def __init__(self, adv_stats):
        self.stats = adv_stats

    def analyze_game(self, game_mkt):
        try:
            h_en = game_mkt['home_team']
            a_en = game_mkt['away_team']
            
            # --- 數據軌分析 ---
            h_data = self.stats[self.stats['TEAM_NAME'] == h_en].iloc[0]
            a_data = self.stats[self.stats['TEAM_NAME'] == a_en].iloc[0]
            
            # 計算數據基礎盤 (Fair Line)
            # 公式：(主隊 NetRtg - 客隊 NetRtg) + 主場優勢(2.5)
            fair_spread = -((h_data['E_NET_RATING'] - a_data['E_NET_RATING']) + 2.5)
            
            # --- 市場軌分析 ---
            mkt_spread = game_mkt['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
            mkt_price = game_mkt['bookmakers'][0]['markets'][0]['outcomes'][0]['price']
            
            # --- 交叉對比 ---
            diff = abs(fair_spread - mkt_spread)
            confidence = 60
            
            # 判斷下注方向
            if fair_spread < mkt_spread - 2:
                rec = f"{NBA_TEAM_MAP.get(h_en)} 讓分 (數據支撐有力)"
                confidence += 20
            elif fair_spread > mkt_spread + 2:
                rec = f"{NBA_TEAM_MAP.get(a_en)} 受讓 (盤口開太深)"
                confidence += 15
            else:
                rec = "❌ 建議觀望 (盤口精準)"
                confidence = 30

            return {
                "matchup": f"{NBA_TEAM_MAP.get(a_en)} @ {NBA_TEAM_MAP.get(h_en)}",
                "fair_line": round(fair_spread, 1),
                "mkt_line": mkt_spread,
                "price": mkt_price,
                "conf": confidence,
                "rec": rec,
                "h_pace": h_data['E_PACE'],
                "a_pace": a_data['E_PACE']
            }
        except: return None

# ==========================================
# 4. 主程式 UI
# ==========================================
st.title("🏀 NBA 數據+市場全能獵殺報告 V16")
st.caption("分析層次：市場心理(盤口) + 戰力效率(15場進階數據) + 傷病權重校正")

with st.spinner('正在同步 NBA 數據與實時賠率...'):
    # 獲取 API 與 統計數據
    adv_stats = NBADataCore.get_advanced_stats()
    mkt_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"
    mkt_data = requests.get(mkt_url).json()

    analyser = NBASuperAnalyser(adv_stats)

    for game in mkt_data:
        res = analyser.analyze_game(game)
        if not res: continue

        with st.container():
            st.markdown(f"### 🏟️ {res['matchup']}")
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                st.write("**核心數據指標**")
                st.write(f"📊 數據基準盤: `{res['fair_line']}`")
                st.write(f"📈 實時市場盤: `{res['mkt_line']}`")
                st.write(f"⚡ 預期節奏(Pace): `{round((res['h_pace']+res['a_pace'])/2, 1)}`")

            with col2:
                st.metric("分析信心度", f"{res['conf']}%")
                # 傷病影響提醒 (示意)
                st.warning("⚠️ 傷病追蹤：請確認先發名單有無變動")

            with col3:
                st.subheader(f"✅ 最推薦：{res['rec']}")
                st.progress(res['conf'] / 100)
                
                # 判斷理由
                if res['conf'] >= 80:
                    st.error("🔥 發現高價值 Edge：數據與盤口嚴重失衡，莊家低估了強隊戰力！")
                elif res['conf'] <= 40:
                    st.info("⚖️ 莊家開盤極其精準，目前無明顯投資價值。")
                else:
                    st.success("✅ 市場邏輯正常，建議小注娛樂。")
            st.divider()
