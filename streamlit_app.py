import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V6.2", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.2：變異擴張與偏誤校正版")
st.caption("核心：修正比分壓縮、下注比例量化、優先級排序系統")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBASharpsEliteV6:
    def __init__(self):
        self.home_adv = 2.8
        self.b2b_pen = 2.5
        self.spread_trap_limit = 6.5
        self.total_trap_limit = 10.0
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
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sb_data = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()
        b2b_list = list(sb_data[1]['TEAM_ABBREVIATION']) if len(sb_data) > 1 else []
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    def apply_variance_expansion(self, fair_s, h_row, a_row, h_b2b, a_b2b):
        """新增：變異擴張層，拉開合理分差"""
        expansion_factor = 1.0
        
        # 1. Blowout 風險：實力斷層越大，變異擴張越強
        net_rating_diff = abs(h_row['E_NET_RATING'] - a_row['E_NET_RATING'])
        if net_rating_diff > 8.0: expansion_factor += 0.15
        
        # 2. 賽程疲勞與移動壓力
        if h_b2b or a_b2b: expansion_factor += 0.1
        
        # 3. 進攻節奏不對等 (節奏快的一方更容易拉開分差)
        if max(h_row['E_PACE'], a_row['E_PACE']) > 102: expansion_factor += 0.05
        
        expanded_s = fair_s * expansion_factor
        return round(expanded_s, 1)

    def calculate_bet_strength(self, edge, risk_msg, mkt_type="spread"):
        """新增：推薦下注比例 (0%-100%)"""
        if "❌" in risk_msg or "⚠️" in risk_msg: return 0
        
        base_strength = 0
        if mkt_type == "spread":
            # 讓分盤比例計算
            if edge < 1.5: base_strength = 20
            elif edge < 3.5: base_strength = 50
            elif edge < 5.5: base_strength = 85
            else: base_strength = 40 # Edge 太大進入誘盤觀察區，降權
        else:
            # 大小分比例計算
            if edge < 4.5: base_strength = 20
            elif edge < 8.0: base_strength = 60
            else: base_strength = 30
            
        return base_strength

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                h_row, a_row = stats[stats['TEAM_NAME'] == h_en].iloc[0], stats[stats['TEAM_NAME'] == a_en].iloc[0]
                h_b2b, a_b2b = h_en in b2b_list, a_en in b2b_list

                # 基礎 Fair Line 計算
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_p = round(((h_row['E_OFF_RATING'] - (self.b2b_pen if h_b2b else 0) + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_p = round(((a_row['E_OFF_RATING'] - (self.b2b_pen if a_b2b else 0) + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                raw_fair_s = a_p - h_p
                # --- 執行變異擴張 ---
                fair_s = self.apply_variance_expansion(raw_fair_s, h_row, a_row, h_b2b, a_b2b)
                
                mkt_s = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
                fair_t = round(h_p + a_p, 1)

                # --- 受讓偏誤校正 (Bias Correction) ---
                edge_s = abs(fair_s - mkt_s)
                risk_s = "-"
                # 若分差極小且長期指向受讓，判定為 False Edge
                if abs(fair_s) < 2.0 and edge_s > 3.0:
                    risk_s = "⚠️ 疑似壓縮偏誤"

                # 誘盤攔截 (保留既有功能)
                if edge_s > self.spread_trap_limit: risk_s = "❌ 誘盤風險"

                # 計算強度
                s_strength = self.calculate_bet_strength(edge_s, risk_s, "spread")
                t_strength = self.calculate_bet_strength(abs(fair_t - mkt_t), "-", "total")

                report.append({
                    "對戰": f"{a_cn} @ {h_cn}",
                    "推薦比例": s_strength,
                    "預估比分": f"{a_p}:{h_p}",
                    "讓分建議": f"{h_cn if fair_s < mkt_s else a_cn} 過盤",
                    "讓分風險": risk_s,
                    "大小分建議": f"{'大分' if fair_total > mkt_total else '小分'}" if t_strength > 0 else "-",
                    "大小分比例": t_strength,
                    "ML參考": h_cn if h_p > a_p else a_cn
                })
            except: continue
            
        # 依推薦下注比例由高到低排序
        df = pd.DataFrame(report).sort_values(by="推薦比例", ascending=False)
        return df

# --- UI 渲染 ---
if st.button('🚀 執行 V6.2 精英量化掃描'):
    with st.spinner('執行變異擴張、校正比分壓縮、計算下注比例...'):
        df = NBASharpsEliteV6().run()
        st.table(df.style.background_gradient(subset=['推薦比例'], cmap='Greens'))
