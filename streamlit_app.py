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
st.set_page_config(page_title="NBA Sharps Elite V7.2.1", layout="wide")
st.title("🛡️ NBA Sharps Elite V7.2.1：邏輯校正與實戰版")
st.caption("修正：讓分/受讓標籤對應錯誤 | 強化：過盤率精算與意圖偵測")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBAMarketSniper:
    def __init__(self):
        self.std_dev = 12.0
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

    def run(self):
        stats_df, markets = self.get_data()
        report = []
        if not markets or "error" in markets: return pd.DataFrame()

        for game in markets:
            try:
                # 1. 提取基本資訊
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                # 2. 取得盤口（從 bookmakers 深入提取，確保名稱與點數對應）
                outcome = game['bookmakers'][0]['markets'][0]['outcomes']
                # 這裡強制指定：哪一隊的 point 是負的，哪一隊就是讓分方
                team_0_name = self.team_map.get(outcome[0]['name'], outcome[0]['name'])
                team_0_point = outcome[0]['point']
                team_1_name = self.team_map.get(outcome[1]['name'], outcome[1]['name'])
                team_1_point = outcome[1]['point']

                # 總分盤口
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']

                # 3. 數據計算 (Fair Line)
                h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
                a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                # 理論上主隊應該讓的分數 (負數代表主隊強)
                fair_s_home = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.8)

                # 4. 讓分推薦與機率 (以 team_0 為主體計算)
                adj_std = self.std_dev * (pace / 100)
                # 計算 team_0 過盤機率
                # 如果 team_0 是主隊，基準是 fair_s_home；如果是客隊，基準是 -fair_s_home
                base_fair = fair_s_home if outcome[0]['name'] == h_en else -fair_s_home
                z_score = (team_0_point - base_fair) / adj_std
                p_0_cover = norm.cdf(z_score)
                p_1_cover = 1 - p_0_cover

                # 5. 決定推薦方向
                if p_0_cover > 0.53:
                    rec_team = team_0_name
                    rec_type = "讓分" if team_0_point < 0 else "受讓"
                    prob = p_0_cover
                    intent = "🛡️ 莊家防禦" if team_0_point < base_fair else "🔥 熱盤誘餌"
                elif p_1_cover > 0.53:
                    rec_team = team_1_name
                    rec_type = "讓分" if team_1_point < 0 else "受讓"
                    prob = p_1_cover
                    intent = "🛡️ 莊家防禦" if team_1_point < (base_fair*-1) else "🔥 熱盤誘餌"
                else:
                    rec_team, rec_type, prob, intent = "❌", "NO BET", 0.5, "觀望"

                # 6. 大小分推薦
                fair_t = (h_row['E_OFF_RATING'] + a_row['E_OFF_RATING']) * (pace/100)
                t_rec = "大分" if mkt_t < fair_t - 5 else ("小分" if mkt_t > fair_t + 5 else "觀望")
                t_prob = norm.cdf(abs(fair_t - mkt_t) / 15.0) if t_rec != "觀望" else 0.5

                report.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "讓分推薦隊伍": rec_team,
                    "盤口類型": rec_type,
                    "預估過盤率 %": f"{round(prob * 100, 1)}%",
                    "莊家意圖": intent,
                    "大小分建議": t_rec,
                    "大小分機率": f"{round(t_prob * 100, 1)}%",
                    "實際盤口 (讓分/總分)": f"{team_0_name if team_0_point < 0 else team_1_name} ({min(team_0_point, team_1_point)}) / {mkt_t}",
                    "sort_key": prob
                })
            except: continue
            
        return pd.DataFrame(report).sort_values(by="sort_key", ascending=False)

# --- UI 渲染 ---
if st.button('🎯 執行 V7.2.1 獵殺分析'):
    with st.spinner('校準正負號邏輯並偵測意圖中...'):
        engine = NBAMarketSniper()
        df = engine.run()
        if not df.empty:
            st.table(df.drop(columns=["sort_key"]))
            st.info("💡 邏輯更新：現在系統會嚴格比對 API 隊伍名稱與其對應的 point 正負號，確保讓分/受讓標記 100% 準確。")
        else:
            st.warning("⚠️ 暫無數據。")
