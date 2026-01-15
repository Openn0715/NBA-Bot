import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# 1. 網頁配置與風格
st.set_page_config(page_title="NBA Sharps Pro", layout="wide")
st.title("🏀 NBA 頂級職業博弈量化報告")
st.markdown("""
**系統定位**：Sharps Level (職業級分析)  
**分析核心**：數據為輔，盤口行為優先。自動偵測誘盤(Trap)與反向走勢(RLM)。
""")

# 從 Secrets 獲取 API Key
try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

class NBA_Ultimate_Engine:
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

    def fetch_nba_stats(self):
        """獲取官網進階數據與 B2B 狀態"""
        raw_stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15)
        df = raw_stats.get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sb = scoreboardv2.ScoreboardV2(game_date=yesterday)
        b2b = list(sb.get_data_frames()[1]['TEAM_ABBREVIATION']) if not sb.get_data_frames()[1].empty else []
        return df, b2b

    def get_market_data(self):
        """獲取市場即時盤口"""
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        return requests.get(url).json()

    def analyze_behavior(self, model_line, current_line, home_team):
        """市場行為與誘盤判定邏輯"""
        edge = abs(model_line - current_line)
        
        # 判定標籤與意圖
        if edge > 6.0:
            return "🚨 疑似誘盤 (Trap)", "刻意吸注", "❌ NO BET", "數據優勢過大但盤口未跟進，極大機率存在誘盤風險"
        elif edge > 3.5:
            return "✅ 正常移動", "風險控制", "✅ 建議進場", "-"
        else:
            return "⚖️ 平衡盤口", "注額平衡", "✅ 觀望", "模型與市場達成共識"

    def run_analysis(self):
        try:
            df_stats, b2b_list = self.fetch_nba_stats()
            market_data = self.get_market_data()
        except Exception as e:
            st.error(f"數據掃描失敗: {e}")
            return pd.DataFrame()

        report = []
        for game in market_data:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                h_data = df_stats[df_stats['TEAM_NAME'] == h_en].iloc[0]
                a_data = df_stats[df_stats['TEAM_NAME'] == a_en].iloc[0]

                # 數據修正
                h_off, a_off = h_data['E_OFF_RATING'], a_data['E_OFF_RATING']
                f_log = "正常"
                if h_en in b2b_list: h_off -= self.b2b_penalty; f_log = "主B2B"
                if a_en in b2b_list: a_off -= self.b2b_penalty; f_log = "客B2B"

                # 預測比分運算
                pace = (h_data['E_PACE'] + a_data['E_PACE']) / 2
                h_p = round(((h_off + a_data['E_DEF_RATING']) / 2 + self.home_advantage) * pace / 100, 1)
                a_p = round(((a_off + h_data['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                # 公平盤 Fair Line (客減主)
                model_line = round(a_p - h_p, 1)
                mkt_spread = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_total = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']

                # 行為分析
                behavior, intent, action, risk_note = self.analyze_behavior(model_line, mkt_spread, h_cn)

                # 方向判定
                if action != "❌ NO BET":
                    # 讓分方向
                    if model_line < mkt_spread:
                        target = f"{h_cn} {'讓分' if mkt_spread < 0 else '受讓'}勝"
                    else:
                        target = f"{a_cn} {'受讓' if mkt_spread < 0 else '讓分'}勝"
                else:
                    target = "跳過"

                report.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "狀況": f_log,
                    "模型預測": f"{a_p}:{h_p}",
                    "公平盤/市場": f"{model_line}/{mkt_spread}",
                    "市場行為": behavior,
                    "分析建議": action,
                    "具體投注建議": target,
                    "風險說明": risk_note
                })
            except: continue
        return pd.DataFrame(report)

# 介面按鈕
if st.button('🚀 執行 Sharps Level 全自動量化掃描'):
    with st.spinner('正在分析莊家意圖與數據指標...'):
        engine = NBA_Ultimate_Engine()
        final_df = engine.run_analysis()
        
        if not final_df.empty:
            # 風格處理：將 NO BET 標紅
            def color_action(val):
                color = 'red' if val == '❌ NO BET' else ('green' if '✅' in val else 'white')
                return f'color: {color}'
            
            st.table(final_df.style.applymap(color_action, subset=['分析建議']))
            st.success("掃描完成。請記住：盤口異動優先於預測比分。")
        else:
            st.warning("暫無盤口數據，請確認 API 狀態或賽程時間。")
