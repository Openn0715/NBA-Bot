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
st.set_page_config(page_title="NBA Sharps Elite V6.4", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.4：機率分佈與防偏誤版")
st.caption("核心：從點預測轉向 P(Cover) 機率模型 | 解決結構性受讓偏誤")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

# ==========================================
# 核心引擎 (機率分佈架構)
# ==========================================
class NBASharpsEliteV6:
    def __init__(self):
        self.home_adv = 2.8
        self.b2b_pen = 2.5
        self.std_dev = 12.0  # NBA 比分差標準差基準
        self.spread_trap_limit = 6.5
        self.total_trap_limit = 10.0
        self.prob_threshold = 0.53  # 觸發建議的機率門檻
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
        # 獲取近 15 場進階數據
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        b2b_list = []
        try:
            sb_data = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()
            if len(sb_data) > 1 and not sb_data[1].empty:
                b2b_list = list(sb_data[1]['TEAM_ABBREVIATION'])
        except: pass
        
        # 獲取市場盤口 (The Odds API)
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    def calculate_cover_probability(self, fair_spread, mkt_spread, pace):
        """核心：使用常態分佈計算過盤機率"""
        adj_std = self.std_dev * (pace / 100)
        # 使用正態分佈累積函數計算
        z_score = (mkt_spread - fair_spread) / adj_std
        p_home_cover = norm.cdf(z_score)
        return p_home_cover, 1 - p_home_cover

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []

        if not markets or (isinstance(markets, dict) and "error" in markets):
            return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                if h_en not in stats['TEAM_NAME'].values or a_en not in stats['TEAM_NAME'].values: continue
                
                h_row = stats[stats['TEAM_NAME'] == h_en].iloc[0]
                a_row = stats[stats['TEAM_NAME'] == a_en].iloc[0]
                h_b2b, a_b2b = h_en in b2b_list, a_en in b2b_list

                # 1. 基礎先驗預測 (Prior)
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_off = h_row['E_OFF_RATING'] - (self.b2b_pen if h_b2b else 0)
                a_off = a_row['E_OFF_RATING'] - (self.b2b_pen if a_b2b else 0)
                
                h_p = ((h_off + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100
                a_p = ((a_off + h_row['E_DEF_RATING']) / 2) * pace / 100
                fair_s = a_p - h_p

                # 2. 市場盤口
                m_data = game['bookmakers'][0]['markets']
                mkt_s = m_data[0]['outcomes'][0]['point']
                mkt_t = m_data[1]['outcomes'][0]['point']

                # 3. 機率分佈計算
                p_h_cover, p_a_cover = self.calculate_cover_probability(fair_s, mkt_s, pace)
                
                if p_h_cover > self.prob_threshold:
                    pick, prob = h_cn, p_h_cover
                elif p_a_cover > self.prob_threshold:
                    pick, prob = a_cn, p_a_cover
                else:
                    pick, prob = "觀望", 0.5

                # 4. 誘盤過濾與下注比例
                edge_s = abs(fair_s - mkt_s)
                risk_desc = "-"
                if edge_s > self.spread_trap_limit: 
                    pick, risk_desc = "NO BET", "🚨 誘盤風險"
                
                strength = int(max(0, (prob - self.prob_threshold) / 0.1) * 100) if pick not in ["觀望", "NO BET"] else 0

                # 5. 大小分獨立判斷
                fair_t = h_p + a_p
                t_edge = abs(fair_t - mkt_t)
                t_desc = f"{'大分' if fair_t > mkt_t else '小分'}" if 4.5 < t_edge < self.total_trap_limit else "❌ NO BET"

                report.append({
                    "推薦比例": strength,
                    "對戰": f"{a_cn} @ {h_cn}",
                    "讓分建議": f"{pick} 過盤" if strength > 0 else pick,
                    "過盤機率": f"{round(prob*100, 1)}%",
                    "大小分建議": t_desc,
                    "預估分差": round(fair_s, 1),
                    "市場盤口": mkt_s,
                    "備註": risk_desc
                })
            except: continue
            
        if not report: return pd.DataFrame()
        return pd.DataFrame(report).sort_values(by="推薦比例", ascending=False)

# ==========================================
# 介面渲染 (按鈕區域)
# ==========================================
if st.button('🚀 啟動 V6.4 機率模型深度分析'):
    with st.spinner('正在抓取數據、計算正態分佈機率與執行防偏誤校驗...'):
        engine = NBASharpsEliteV6()
        df = engine.run()
        
        if not df.empty:
            # 顯示主要預測表
            st.dataframe(df, use_container_width=True)
            
            # 補充說明
            st.info("""
            **V6.4 模型說明：**
            1. **機率核心**：不再只看『預測分差』，而是計算『過盤機率 (Cover Probability)』。
            2. **解決受讓偏誤**：只有當機率顯著大於 53% 時才會給出建議，有效避免了點預測帶來的頻繁受讓陷阱。
            3. **動態風險**：標準差會隨比賽節奏 (Pace) 自動調整，節奏越快，過盤門檻越高。
            """)
        else:
            st.warning("⚠️ 目前暫無可用賽事數據，請檢查 API Key 或開賽時間。")

# 頁尾說明
st.divider()
st.caption("數據來源：NBA.com Advanced Stats & The Odds API | 建議僅供研究參考")
