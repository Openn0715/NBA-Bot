import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V6.2.1", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.2.1：穩定修正版")
st.caption("修正：KeyError 排序錯誤 | 強化：空數據保護機制")

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
        b2b_list = []
        try:
            sb_data = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()
            if len(sb_data) > 1 and not sb_data[1].empty:
                b2b_list = list(sb_data[1]['TEAM_ABBREVIATION'])
        except:
            pass
            
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    def apply_variance_expansion(self, fair_s, h_row, a_row, h_b2b, a_b2b):
        expansion_factor = 1.0
        net_rating_diff = abs(h_row['E_NET_RATING'] - a_row['E_NET_RATING'])
        if net_rating_diff > 8.0: expansion_factor += 0.15
        if h_b2b or a_b2b: expansion_factor += 0.1
        if max(h_row['E_PACE'], a_row['E_PACE']) > 102: expansion_factor += 0.05
        return round(fair_s * expansion_factor, 1)

    def calculate_bet_strength(self, edge, risk_msg, mkt_type="spread"):
        if "❌" in risk_msg or "⚠️" in risk_msg: return 0
        if mkt_type == "spread":
            if edge < 1.5: return 20
            if edge < 3.5: return 55
            if edge < 5.5: return 85
            return 30
        else:
            if edge < 4.5: return 20
            if edge < 8.0: return 65
            return 25

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []

        if not markets or "error" in markets:
            return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                if h_en not in stats['TEAM_NAME'].values or a_en not in stats['TEAM_NAME'].values:
                    continue

                h_row = stats[stats['TEAM_NAME'] == h_en].iloc[0]
                a_row = stats[stats['TEAM_NAME'] == a_en].iloc[0]
                h_b2b, a_b2b = h_en in b2b_list, a_en in b2b_list

                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_p = round(((h_row['E_OFF_RATING'] - (self.b2b_pen if h_b2b else 0) + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_p = round(((a_row['E_OFF_RATING'] - (self.b2b_pen if a_b2b else 0) + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                raw_fair_s = a_p - h_p
                fair_s = self.apply_variance_expansion(raw_fair_s, h_row, a_row, h_b2b, a_b2b)
                fair_t = round(h_p + a_p, 1)

                # 提取盤口
                mkt_s = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']

                edge_s = abs(fair_s - mkt_s)
                risk_s = "-"
                if abs(fair_s) < 2.0 and edge_s > 3.0: risk_s = "⚠️ 壓縮偏誤"
                if edge_s > self.spread_trap_limit: risk_s = "❌ 誘盤風險"

                s_strength = self.calculate_bet_strength(edge_s, risk_s, "spread")
                t_strength = self.calculate_bet_strength(abs(fair_t - mkt_t), "-", "total")

                report.append({
                    "對戰": f"{a_cn} @ {h_cn}",
                    "推薦比例": s_strength,
                    "預估比分": f"{a_p}:{h_p}",
                    "讓分建議": f"{h_cn if fair_s < mkt_s else a_cn} 過盤",
                    "讓分風險": risk_s,
                    "大小分建議": f"{'大分' if fair_t > mkt_t else '小分'}" if t_strength > 0 else "-",
                    "大小分比例": t_strength,
                    "ML參考": h_cn if h_p > a_p else a_cn
                })
            except:
                continue
            
        if not report:
            return pd.DataFrame()
            
        df = pd.DataFrame(report).sort_values(by="推薦比例", ascending=False)
        return df

# --- UI 渲染 ---
if st.button('🚀 執行 V6.2.1 穩定版分析'):
    with st.spinner('掃描賽程並執行變異擴張分析...'):
        engine = NBASharpsEliteV6()
        df = engine.run()
        if not df.empty:
            st.table(df.style.background_gradient(subset=['推薦比例'], cmap='Greens'))
        else:
            st.warning("⚠️ 目前暫無可用賽事數據，或 API 已達本日上限。")
