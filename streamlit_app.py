import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# 1. 系統配置
st.set_page_config(page_title="NBA Sharps Elite V4", layout="wide")
st.title("🛡️ NBA Sharps Elite：實戰準度過濾系統")
st.markdown("""
**核心哲學：** 寧可錯過，也不落入誘盤。
**監控指標：** 擊敗收盤線 (CLV)、模型自我否定 (Model Humility)、假象優勢過濾。
""")

# 2. 安全獲取 API Key
try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBASharpsElite:
    def __init__(self):
        self.home_adv = 2.8
        self.b2b_penalty = 2.5
        self.false_edge_threshold = 7.5  # 超過此值視為誘盤風險
        self.clv_min_edge = 1.5         # 低於此值無博弈價值
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
        """同步 NBA 官網進階數據"""
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sb = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()[1]
        b2b_list = list(sb['TEAM_ABBREVIATION']) if not sb.empty else []
        return stats, b2b_list

    def get_odds(self):
        """獲取即時盤口數據"""
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"
        return requests.get(url).json()

    def run_analysis(self):
        try:
            df_stats, b2b_list = self.fetch_data()
            market_data = self.get_odds()
        except Exception as e:
            st.error(f"數據同步失敗: {e}")
            return pd.DataFrame()

        results = []
        for game in market_data:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                h_row = df_stats[df_stats['TEAM_NAME'] == h_en].iloc[0]
                a_row = df_stats[df_stats['TEAM_NAME'] == a_en].iloc[0]

                # 基礎模型運算 (Pace & Efficiency)
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_off = h_row['E_OFF_RATING'] - (self.b2b_penalty if h_en in b2b_list else 0)
                a_off = a_row['E_OFF_RATING'] - (self.b2b_penalty if a_en in b2b_list else 0)
                
                h_pred = round(((h_off + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_pred = round(((a_off + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                fair_line = round(a_pred - h_pred, 1)
                curr_line = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                
                # --- 實戰過濾核心邏輯 ---
                edge = abs(fair_line - curr_line)
                action = "✅ 建議進場"
                risk_msg = "風險受控"
                
                # 1. 假象優勢過濾 (False Edge Filter)
                if edge > self.false_edge_threshold:
                    action = "❌ NO BET"
                    risk_msg = "疑似誘盤 (False Edge)"
                
                # 2. 模型自我否定 (Model Humility)
                # 簡化模擬：若模型預測方向與大眾心理(讓分深度)極度背離且無數據支撐
                elif edge < self.clv_min_edge:
                    action = "✅ 觀望"
                    risk_msg = "缺乏 CLV 空間"

                # 3. 比賽型態分類 (Game Archetype)
                archetype = "標準節奏"
                if pace > 102: archetype = "快節奏亂戰"
                elif pace < 97: archetype = "半場防守戰"

                results.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "型態": archetype,
                    "模型比分": f"{a_pred}:{h_pred}",
                    "公平盤/市場": f"{fair_line} / {curr_line}",
                    "Edge": edge,
                    "分析建議": action,
                    "風險判定": risk_msg,
                    "具體方向": f"{h_cn if fair_line < curr_line else a_cn} 勝" if action == "✅ 建議進場" else "-"
                })
            except: continue
        return pd.DataFrame(results)

# 介面顯示
if st.button('🎯 執行 Elite 實戰量化分析'):
    with st.spinner('正在計算 CLV 潛力與過濾假象優勢...'):
        engine = NBASharpsElite()
        df = engine.run_analysis()
        
        if not df.empty:
            # 視覺化修飾
            def style_action(val):
                color = '#ff4b4b' if '❌' in val else ('#00cc66' if '✅ 建議' in val else '#ffffff')
                return f'color: {color}; font-weight: bold'
            
            st.table(df.style.applymap(style_action, subset=['分析建議']))
            
            st.info("""
            **💡 Sharps 提醒：**
            1. **NO BET** 代表數據優勢大到不自然，莊家可能掌握了你不知道的傷病或輪休。
            2. **觀望** 代表該盤口已非常精準，沒有超額獲利潛力。
            3. 優先選擇 **標綠色** 且 Edge 在 2.0~5.0 之間的場次。
            """)
        else:
            st.warning("目前非賽事時間或 API 額度已達上限。")
