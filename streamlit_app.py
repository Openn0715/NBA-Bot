import streamlit as st
import pandas as pd
import requests
import numpy as np
from scipy.stats import norm
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V7.1", layout="wide")
st.title("🛡️ NBA Sharps Elite V7.1：實戰意圖解讀器")
st.caption("核心：解讀莊家誘盤手法 | 明確下注方向與強度 | 偵測熱盤與騙盤")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBAMarketHunter:
    def __init__(self):
        self.team_map = {
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

    def get_data(self):
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=10).get_data_frames()[0]
        market_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        market_data = requests.get(market_url).json()
        return stats, market_data

    def detect_trap(self, h_en, a_en, mkt_s, mkt_t, stats_df):
        """核心模組：偵測騙盤與熱盤"""
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        
        # 1. 戰力基準盤
        fair_s = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.8)
        
        # 2. 讓分盤解讀
        s_pick = "-"
        s_trap_type = "正常盤"
        s_strength = 0
        
        # 若市場盤口顯著優於實力盤，且是熱門球隊 -> 疑似吸注盤 (騙盤)
        if mkt_s > fair_s + 2.0:
            s_pick = f"{self.team_map.get(a_en)} 受讓"
            s_trap_type = "🔥 熱盤誘大眾 (吸注)"
            s_strength = 75
        elif mkt_s < fair_s - 2.0:
            s_pick = f"{self.team_map.get(h_cn)} 讓分"
            s_trap_type = "🛡️ 莊家防禦盤 (看好強隊)"
            s_strength = 80
        else:
            s_pick = "無明確優勢"
            s_strength = 20

        # 3. 大小分意圖解讀
        avg_pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
        fair_t = (h_row['E_OFF_RATING'] + a_row['E_OFF_RATING']) * (avg_pace/100)
        
        t_pick = "-"
        t_intent = "平衡"
        if mkt_t > fair_t + 6:
            t_pick = "推薦：小分"
            t_intent = "🚫 過熱盤 (誘導大分)"
        elif mkt_t < fair_t - 6:
            t_pick = "推薦：大分"
            t_intent = "📉 恐慌盤 (誘導小分)"
        else:
            t_pick = "觀望"

        return s_pick, s_trap_type, s_strength, t_pick, t_intent

    def run(self):
        stats, markets = self.get_data()
        report = []
        if not markets or "error" in markets: return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                m_data = game['bookmakers'][0]['markets']
                curr_s = m_data[0]['outcomes'][0]['point']
                curr_t = m_data[1]['outcomes'][0]['point']
                
                s_pick, s_trap, strength, t_pick, t_intent = self.detect_trap(h_en, a_en, curr_s, curr_t, stats)
                
                report.append({
                    "市場強度 %": strength,
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "【讓分盤推薦】": s_pick,
                    "讓分意圖偵測": s_trap,
                    "【大小分推薦】": t_pick,
                    "大小分意圖解讀": t_intent,
                    "當前讓分": curr_s,
                    "當前總分": curr_t
                })
            except: continue

        return pd.DataFrame(report).sort_values(by="市場強度 %", ascending=False)

# ==========================================
# UI 渲染
# ==========================================
if st.button('🚀 執行盤口獵殺分析 (V7.1)'):
    with st.spinner('正在分析莊家佈局與誘盤信號...'):
        engine = NBAMarketHunter()
        df = engine.run()
        
        if not df.empty:
            # 使用更直觀的顯示方式
            st.markdown("### 🎯 莊家意圖解讀結果")
            st.table(df)
            
            st.markdown("""
            ---
            ### 📖 術語說明書
            1. **🔥 熱盤誘大眾 (吸注)**：莊家開出一個對熱門球隊「太過友好」的盤口，引誘資金進場，此時建議**反向操作**。
            2. **🛡️ 莊家防禦盤**：莊家不惜代價拉高門檻以減少損失，通常代表莊家極度看好該方向。
            3. **🚫 過熱盤**：公眾對於得分過度樂觀，盤口被推高至不合理範圍，建議關注**小分**。
            """)
        else:
            st.warning("⚠️ 暫無數據，請確認 API 狀態。")
