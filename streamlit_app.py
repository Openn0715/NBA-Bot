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
st.set_page_config(page_title="NBA Sharps Elite V8.2", layout="wide")
st.title("🛡️ NBA Sharps Elite V8.2：陷阱偵測與意圖獵殺")
st.caption("職責分離：讓分盤(市場心理) | 大小分(數據戰力) | 新增盤口合理性濾網")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBAMarketSniperV82:
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

    def analyze_market_logic(self, h_en, a_en, current_s, stats_df):
        """核心：判讀盤口合理性與莊家陷阱"""
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        
        # 理論戰力盤 (Fair Line)
        fair_s = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.8)
        
        # 1. 偵測『太甜』的盤口 (吸注陷阱)
        # 如果數據看好 A 贏 8 分，莊家只開 3 分 -> 誘買 A
        diff = current_s - fair_s
        trap_status = "✅ 盤口邏輯正常"
        if diff > 4.5:
            trap_status = "⚠️ 誘盤警告：強隊太便宜 (吸注)"
        elif diff < -4.5:
            trap_status = "🛡️ 莊家防禦：強隊門檻極高"

        # 2. 關鍵數字停留分析
        is_key_num = "是" if current_s in [-3, -7, -10, 3, 7, 10] else "否"
        
        return trap_status, round(fair_s, 1), is_key_num

    def run(self):
        stats_df, markets = self.get_data()
        report = []
        if not markets or "error" in markets: return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                # 讓分盤數據
                outcomes = game['bookmakers'][0]['markets'][0]['outcomes']
                current_s = next(o['point'] for o in outcomes if o['name'] == h_en)
                
                # 市場邏輯與陷阱分析
                trap_info, fair_s, is_key = self.analyze_market_logic(h_en, a_en, current_s, stats_df)
                
                # 決定推薦方向 (結合意圖)
                rec_direction = "❌ NO BET"
                signal_strength = 0
                
                if "誘盤" in trap_info:
                    rec_direction = f"{self.team_map.get(a_en)} 受讓"
                    signal_strength = 85
                elif "防禦" in trap_info:
                    rec_direction = f"{self.team_map.get(h_en)} 讓分"
                    signal_strength = 75
                elif is_key == "是":
                    rec_direction = "跟隨關鍵數字移動"
                    signal_strength = 50

                # 大小分分析 (職責分離)
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2 if 'h_row' in locals() else 100
                # (簡化計算示意)
                fair_t = (stats_df[stats_df['TEAM_NAME']==h_en]['E_OFF_RATING'].values[0] + stats_df[stats_df['TEAM_NAME']==a_en]['E_OFF_RATING'].values[0])
                t_rec = "Over" if fair_t > mkt_t + 5 else ("Under" if fair_t < mkt_t - 5 else "NO BET")

                report.append({
                    "市場信號強度": f"{signal_strength}%",
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "讓分推薦方向": rec_direction,
                    "莊家意圖/陷阱": trap_info,
                    "數據基準盤": fair_s,
                    "目前盤口": current_s,
                    "大小分建議": t_rec,
                    "關鍵數字": is_key,
                    "sort": signal_strength
                })
            except: continue
        
        return pd.DataFrame(report).sort_values(by="sort", ascending=False)

# ==========================================
# UI 渲染
# ==========================================
if st.button('🚀 啟動 V8.2 意圖與陷阱深度掃描'):
    with st.spinner('偵測莊家佈局與資金陷阱中...'):
        engine = NBAMarketSniperV82()
        df = engine.run()
        if not df.empty:
            st.markdown("### 🏹 莊家行為解讀與獵殺報告")
            st.table(df.drop(columns=["sort"]))
            
            st.markdown("""
            ---
            ### 🎓 如何利用 V8.2 提高勝率？
            1. **獵殺『誘盤』**：當莊家開出一個比數據基準「便宜很多」的盤口時，通常代表莊家在引誘大眾買強隊。此時**反向買受讓**的勝率極高。
            2. **跟隨『防禦』**：若盤口開得比數據還深，代表莊家寧可少賠也不想讓你贏，這通常是強隊會大勝的信號。
            3. **避開平衡盤**：當數據基準與盤口完全一致時，代表無利可圖，請果斷執行 **NO BET**。
            """)
        else:
            st.warning("⚠️ 數據抓取失敗，請確認 API 狀態。")
