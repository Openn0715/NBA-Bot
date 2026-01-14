import streamlit as st
import pandas as pd
import requests
import os
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# 設置網頁標題與風格
st.set_page_config(page_title="NBA 量化大師", layout="wide")

st.title("🏀 NBA 頂級職業量化分析報告")
st.caption("自動同步：近 15 場數據、B2B 疲勞修正、主場加成、+EV 方向判定")

# 獲取 API KEY (稍後會在部署平台上設定)
API_KEY = st.secrets["THE_ODDS_API_KEY"]

class NBA_Web_Analyzer:
    def __init__(self):
        self.home_advantage = 2.8
        self.b2b_penalty = 2.5
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

    def fetch_data(self):
        with st.spinner('⏳ 正在同步 NBA 官網數據...'):
            raw_stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15)
            df_stats = raw_stats.get_data_frames()[0]
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            sb = scoreboardv2.ScoreboardV2(game_date=yesterday)
            b2b_teams = list(sb.get_data_frames()[1]['TEAM_ABBREVIATION']) if not sb.get_data_frames()[1].empty else []
            return df_stats, b2b_teams

    def get_odds(self):
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        return requests.get(url).json()

    def run(self):
        df_stats, b2b_list = self.fetch_data()
        market_data = self.get_odds()
        
        results = []
        for game in market_data:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_row = df_stats[df_stats['TEAM_NAME'] == h_en]
                a_row = df_stats[df_stats['TEAM_NAME'] == a_en]
                if h_row.empty or a_row.empty: continue
                
                h_off, h_def, h_pace = h_row.iloc[0]['E_OFF_RATING'], h_row.iloc[0]['E_DEF_RATING'], h_row.iloc[0]['E_PACE']
                a_off, a_def, a_pace = a_row.iloc[0]['E_OFF_RATING'], a_row.iloc[0]['E_DEF_RATING'], a_row.iloc[0]['E_PACE']
                
                f_log = "正常"
                if h_en in b2b_list: h_off -= self.b2b_penalty; f_log = "主B2B"
                if a_en in b2b_list: a_off -= self.b2b_penalty; f_log = "客B2B"

                h_p = round((( (h_off + a_def) / 2 + self.home_advantage) * ((h_pace + a_pace) / 2)) / 100, 1)
                a_p = round((( (a_off + h_def) / 2) * ((h_pace + a_pace) / 2)) / 100, 1)
                
                m_spread = round(a_p - h_p, 1)
                m_total = round(h_p + a_p, 1)
                
                mkt_s = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
                
                s_edge, t_edge = abs(m_spread - mkt_s), abs(m_total - mkt_t)
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)

                # 方向判定
                s_pick = f"{h_cn if m_spread < mkt_s else a_cn} {'讓分' if mkt_s < 0 else '受讓'}勝"
                t_pick = "全場大分" if m_total > mkt_t else "全場小分"

                rec, target = "✅ 觀望", "-"
                if s_edge > t_edge:
                    if s_edge > 5.5: rec = "💰 職業重注"; target = s_pick
                    elif s_edge > 3.5: rec = "🔥 強烈推薦"; target = s_pick
                else:
                    if t_edge > 8.0: rec = "💰 職業重注"; target = t_pick
                    elif t_edge > 5.5: rec = "🏀 總分推薦"; target = t_pick

                results.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "狀況": f_log,
                    "預測比分": f"{a_p}:{h_p}",
                    "偏差(Edge)": max(round(s_edge,1), round(t_edge,1)),
                    "具體投注建議": target,
                    "分析建議": rec
                })
            except: continue
        return pd.DataFrame(results)

if st.button('🚀 立即掃描最新盤口'):
    data = NBA_Web_Analyzer().run()
    if not data.empty:
        st.table(data)
    else:
        st.warning("目前暫無足夠數據。")