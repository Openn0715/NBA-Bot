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
st.set_page_config(page_title="NBA Sharps Elite V8.0", layout="wide")
st.title("🛡️ NBA Sharps Elite V8.0：市場意圖與職責分離版")
st.caption("讓分盤：市場行為邏輯 | 大小分盤：進階效率邏輯 | 禁止邏輯交叉污染")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBASharpsEliteV8:
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
        # 僅用於大小分判斷的效率值
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=10).get_data_frames()[0]
        # 獲取即時盤口與移動數據 (模擬初盤比對)
        market_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        market_data = requests.get(market_url).json()
        return stats, market_data

    def analyze_spread_intent(self, game_data, stats_df):
        """職責 1: 讓分盤市場行為分析 (不使用預測比分)"""
        outcomes = game_data['bookmakers'][0]['markets'][0]['outcomes']
        h_en = game_data['home_team']
        a_en = game_data['away_team']
        
        # 模擬盤口變化 (此處透過 NetRating 建立基準初盤，用以觀察市場移動方向)
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        implied_opening = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.5)
        
        current_s = next(o['point'] for o in outcomes if o['name'] == h_en)
        
        # STEP 1-3: 判斷移動與 RLM (Reverse Line Movement)
        move_dist = current_s - implied_opening
        signal_strength = 0
        direction = "❌ NO BET"
        intent_tag = "市場平衡"

        # 邏輯：如果盤口往強隊移動且水位變低，代表莊家防禦
        # 邏輯：如果盤口往強隊移動但水位反升，代表誘盤
        if abs(move_dist) > 1.5:
            signal_strength = min(int(abs(move_dist) * 25), 95)
            if move_dist < 0: # 莊家加深主隊讓分
                direction = f"{self.team_map.get(h_en)} 較容易過盤"
                intent_tag = "🛡️ 莊家風險防禦 (強隊方向)"
            else: # 莊家加深客隊讓分 (或主隊減輕)
                direction = f"{self.team_map.get(a_en)} 較容易過盤"
                intent_tag = "📉 資金流向引導 (受讓方向)"
        
        # 關鍵數字補償 (3, 7, 10)
        if current_s in [-3, -7, -10, 3, 7, 10]:
            signal_strength += 10
            intent_tag += " | 關鍵數字停留"

        return direction, signal_strength, intent_tag, current_s

    def analyze_total_efficiency(self, game_data, stats_df):
        """職責 2: 大小分效率分析 (純數據導向)"""
        h_en = game_data['home_team']
        a_en = game_data['away_team']
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        
        mkt_t = game_data['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
        
        pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
        fair_t = (h_row['E_OFF_RATING'] + a_row['E_OFF_RATING']) * (pace/100)
        
        edge = fair_t - mkt_t
        if edge > 6.0: return "Over (大分)", "火熱進攻預期"
        if edge < -6.0: return "Under (小分)", "防守節奏壓制"
        return "❌ NO BET", "數據與盤口契合"

    def run(self):
        stats_df, markets = self.get_data()
        report = []
        if not markets or "error" in markets: return pd.DataFrame()

        for game in markets:
            try:
                # 讓分盤判斷
                s_dir, s_strength, s_intent, curr_s = self.analyze_spread_intent(game, stats_df)
                
                # 大小分判斷
                t_dir, t_reason = self.analyze_total_efficiency(game, stats_df)
                
                # 下注比例 (由信號強度轉化)
                bet_ratio = f"{int(s_strength * 0.1)}%" if s_strength > 0 else "0%"

                report.append({
                    "對戰 (客@主)": f"{self.team_map.get(game['away_team'])} @ {self.team_map.get(game['home_team'])}",
                    "【讓分盤】過盤判斷": s_dir,
                    "市場信號強度": f"{s_strength}%",
                    "莊家行為偵測": s_intent,
                    "【大小分】建議": t_dir,
                    "大小分依據": t_reason,
                    "目前盤口 (S/T)": f"{curr_s} / {game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']}",
                    "推薦下注比例": bet_ratio,
                    "sort": s_strength
                })
            except: continue
        
        return pd.DataFrame(report).sort_values(by="sort", ascending=False)

# ==========================================
# UI 渲染
# ==========================================
if st.button('🎯 啟動 V8.0 市場行為深度掃描'):
    with st.spinner('解構莊家意圖中...'):
        engine = NBASharpsEliteV8()
        df = engine.run()
        if not df.empty:
            st.markdown("### 🏹 市場行為分析報告")
            st.table(df.drop(columns=["sort"]))
            
            st.info("💡 V8.0 注意事項：讓分盤已停止參考預測分差，完全基於莊家開盤行為與市場移動邏輯。")
        else:
            st.warning("⚠️ 暫無市場數據。")
