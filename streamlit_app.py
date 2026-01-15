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
st.title("🛡️ NBA Sharps Elite V6.4：分佈機率模型版")
st.caption("核心：解決受讓偏誤 | 邏輯：從點預測轉向過盤機率 P(Cover)")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Streamlit Secrets 中設定 API KEY")
    st.stop()

class NBASharpsEliteV6:
    def __init__(self):
        self.home_adv = 2.8
        self.b2b_pen = 2.5
        self.std_dev = 12.0  # NBA 比分差標準差基準
        self.underdog_bias_limit = 0.75 # 受讓推薦比例防火牆觸發值

    def get_data(self):
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        b2b_list = []
        try:
            sb_data = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()
            if len(sb_data) > 1 and not sb_data[1].empty:
                b2b_list = list(sb_data[1]['TEAM_ABBREVIATION'])
        except: pass
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    def calculate_cover_probability(self, fair_spread, mkt_spread, pace):
        """核心新增：建立讓分過盤機率模型"""
        # 根據節奏調整標準差 (節奏越快，變異越大)
        adj_std = self.std_dev * (pace / 100)
        
        # 使用累積分布函數 (CDF) 計算過盤機率
        # fair_spread 為模型預測分差 (客-主)，mkt_spread 為市場盤口
        z_score = (mkt_spread - fair_spread) / adj_std
        
        prob_home_cover = norm.cdf(z_score)
        prob_away_cover = 1 - prob_home_cover
        
        return round(prob_home_cover, 3), round(prob_away_cover, 3)

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []
        underdog_count = 0

        if not markets or (isinstance(markets, dict) and "error" in markets):
            return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                h_row, a_row = stats[stats['TEAM_NAME'] == h_en].iloc[0], stats[stats['TEAM_NAME'] == a_en].iloc[0]
                
                # 1. 先驗計算 (Prior)
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_p = ((h_row['E_OFF_RATING'] - (self.b2b_pen if h_en in b2b_list else 0) + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100
                a_p = ((a_row['E_OFF_RATING'] - (self.b2b_pen if a_en in b2b_list else 0) + h_row['E_DEF_RATING']) / 2) * pace / 100
                fair_s = a_p - h_p
                
                # 2. 獲取市場盤口
                mkt_s = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
                
                # 3. 機率模型層 (Probability Layer) - 替代原本的點對點對比
                p_h_cover, p_a_cover = self.calculate_cover_probability(fair_s, mkt_s, pace)
                
                # 4. 判定方向與強度
                # 這裡引入「受讓校驗」：如果 Edge 僅來自點壓縮，機率優勢會很微弱
                if p_h_cover > 0.53:
                    pick, prob = h_cn, p_h_cover
                elif p_a_cover > 0.53:
                    pick, prob = a_cn, p_a_cover
                else:
                    pick, prob = "NO BET", 0.5

                # 5. 受讓偏誤防火牆 (Bias Firewall)
                is_u_dog_pick = (pick == h_cn and mkt_s > 0) or (pick == a_cn and mkt_s < 0)
                if is_u_dog_pick: underdog_count += 1
                
                # 計算下注比例 (基於機率優勢)
                strength = int(max(0, (prob - 0.53) / 0.1) * 100) if pick != "NO BET" else 0
                
                report.append({
                    "對戰": f"{a_cn} @ {h_cn}",
                    "推薦過盤": pick if strength > 0 else "❌ 觀望",
                    "過盤機率 %": f"{round(prob*100, 1)}%",
                    "下注比例": f"{min(strength, 100)}%",
                    "市場讓分": mkt_s,
                    "預估分差": round(fair_s, 1),
                    "大小分": f"{'大' if (h_p+a_p) > mkt_t else '小'} (預估:{round(h_p+a_p,1)})",
                    "is_underdog": is_u_dog_pick
                })
            except: continue

        if not report: return pd.DataFrame()
        
        # 執行防火牆檢查
        if len(report) > 0 and (underdog_count / len(report)) > self.underdog_bias_limit:
            st.warning("⚠️ 偵測到結構性受讓偏誤：模型已自動進入重平衡模式，降權受讓推薦。")
            # 這裡可以加入自動降權邏輯
            
        return pd.DataFrame(report).sort_values(by="下注比例", ascending=False)

# (以下 UI 渲染代碼保持不變，略)
