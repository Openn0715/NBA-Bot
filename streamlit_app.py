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
st.set_page_config(page_title="NBA Sharps Elite V7.2", layout="wide")
st.title("🛡️ NBA Sharps Elite V7.2：意圖解讀與過盤率精算")
st.caption("核心：解讀莊家佈局 | 精算動態過盤率 | 實戰投注指南")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBAMarketSniper:
    def __init__(self):
        self.std_dev = 12.0  # NBA 比分差標準差基準
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

    def calculate_metrics(self, h_en, a_en, mkt_s, mkt_t, stats_df):
        """核心：計算意圖、推薦與過盤率"""
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        
        # 1. 計算數據基準盤 (Fair Line)
        pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
        fair_s = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.8)
        fair_t = (h_row['E_OFF_RATING'] + a_row['E_OFF_RATING']) * (pace/100)
        
        # 2. 讓分盤意圖與推薦
        adj_std = self.std_dev * (pace / 100)
        z_score = (mkt_s - fair_s) / adj_std
        p_home_cover = norm.cdf(z_score)
        p_away_cover = 1 - p_home_cover
        
        # 讓分判斷邏輯
        s_pick = "-"
        s_prob = 0.5
        s_intent = "市場平衡"
        
        if p_home_cover > 0.54:
            s_pick = f"{self.team_map.get(h_en)} 讓分" if mkt_s < 0 else f"{self.team_map.get(h_en)} 受讓"
            s_prob = p_home_cover
            s_intent = "🛡️ 莊家防禦盤" if mkt_s < fair_s else "🔥 熱盤誘餌"
        elif p_away_cover > 0.54:
            s_pick = f"{self.team_map.get(a_en)} 讓分" if mkt_s > 0 else f"{self.team_map.get(a_en)} 受讓"
            s_prob = p_away_cover
            s_intent = "🛡️ 莊家防禦盤" if mkt_s > fair_s else "🔥 熱盤誘餌"
        else:
            s_pick = "❌ NO BET"
            s_prob = 0.5
            s_intent = "數據高度重合"

        # 3. 大小分意圖與推薦
        t_pick = "-"
        t_prob = 0.5
        t_intent = "平衡"
        # 模擬總分標準差約 15 分
        z_t = (fair_t - mkt_t) / 15.0
        p_over = norm.cdf(z_t) if fair_t > mkt_t else norm.cdf((mkt_t - fair_t) / 15.0)
        
        if mkt_t < fair_t - 5:
            t_pick = "推薦：大分"
            t_prob = norm.cdf((fair_t - mkt_t) / 15.0)
            t_intent = "📉 恐慌盤 (低估)"
        elif mkt_t > fair_t + 5:
            t_pick = "推薦：小分"
            t_prob = norm.cdf((mkt_t - fair_t) / 15.0)
            t_intent = "🚫 過熱盤 (誘導大分)"
        else:
            t_pick = "觀望"
            t_prob = 0.5

        return s_pick, s_intent, s_prob, t_pick, t_intent, t_prob

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
                
                s_pick, s_intent, s_prob, t_pick, t_intent, t_prob = self.calculate_metrics(h_en, a_en, curr_s, curr_t, stats)
                
                report.append({
                    "讓分推薦 (Cover)": s_pick,
                    "預估過盤率 %": f"{round(s_prob * 100, 1)}%",
                    "讓分意圖偵測": s_intent,
                    "大小分推薦": t_pick,
                    "大小分勝率": f"{round(t_prob * 100, 1)}%",
                    "大小分意圖": t_intent,
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "目前盤口 (S/T)": f"{curr_s} / {curr_t}",
                    "信號強度": int((s_prob - 0.5) * 500)  # 用於排序
                })
            except: continue

        return pd.DataFrame(report).sort_values(by="信號強度", ascending=False)

# ==========================================
# UI 渲染
# ==========================================
if st.button('🎯 執行意圖與勝率精算分析'):
    with st.spinner('正在解碼莊家佈局並精算過盤機率...'):
        engine = NBAMarketSniper()
        df = engine.run()
        
        if not df.empty:
            st.markdown("### 🏹 NBA 實戰推薦清單 (依信號強度排序)")
            
            # 美化表格顯示
            display_df = df.drop(columns=["信號強度"])
            st.table(display_df)
            
            st.success("✅ 分析完成！建議優先關注『預估過盤率』超過 58% 且顯示『莊家防禦盤』的場次。")
            
            st.markdown("""
            ---
            ### 🎓 如何解讀分析結果？
            1. **預估過盤率 (%)**：基於數據基準線與當前盤口的常態分佈機率。**55% 以上**具備長期投注價值。
            2. **🛡️ 莊家防禦盤**：代表莊家不惜開出偏離數據的盤口來躲避高手資金，這通常是最穩的方向。
            3. **🔥 熱盤誘餌**：莊家故意開出「甜頭盤」吸引公眾，若此時過盤率仍高，請確認是否有未公佈的傷病資訊。
            4. **❌ NO BET**：當數據與盤口完全契合，代表莊家開得很準，沒有任何獲利空間。
            """)
        else:
            st.warning("⚠️ 暫無盤口數據，請確認 API Key 餘額或開賽時段。")
