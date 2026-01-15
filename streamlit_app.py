import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置與標頭
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V6", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.0：整合型量化決策系統")
st.caption("版本：整合重構版 | 邏輯：三線分流、市場行為優先、NO BET 避震")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

# ==========================================
# 核心分析引擎
# ==========================================
class NBASharpsUnifiedEngine:
    def __init__(self):
        # 基礎參數（保留所有既有權重）
        self.home_adv = 2.8
        self.b2b_pen = 2.5
        
        # 閾值設定（保留所有避震器邏輯）
        self.spread_trap_limit = 6.5   # 讓分誘盤門檻
        self.total_trap_limit = 10.0   # 大小分誘盤門檻
        self.min_edge_spread = 1.5     # CLV 最小空間 (讓分)
        self.min_edge_total = 4.5      # CLV 最小空間 (大小分)
        
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

    # --- 模組 1: 資料整合層 ---
    def get_raw_data(self):
        # 抓取官網進階數據 (近15場)
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        # 判定 B2B 狀態
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sb = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()[1]
        b2b_list = list(sb['TEAM_ABBREVIATION']) if not sb.empty else []
        # 抓取市場盤口
        market_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        market_data = requests.get(market_url).json()
        return stats, b2b_list, market_data

    # --- 模組 2: 市場行為與過濾引擎 (核心整合邏輯) ---
    def filter_engine(self, fair, mkt, mkt_type="spread"):
        edge = abs(fair - mkt)
        status, risk, reason = "✅ 建議", "低", "-"
        
        # 1. 誘盤偵測 (Trap Line)
        limit = self.spread_trap_limit if mkt_type == "spread" else self.total_trap_limit
        if edge > limit:
            return "❌ NO BET", "🚨 誘盤風險", "數據偏差過大，疑似陷阱"
        
        # 2. CLV 與 空間判斷
        min_e = self.min_edge_spread if mkt_type == "spread" else self.min_edge_total
        if edge < min_e:
            return "⚖️ 觀望", "無優勢", "盤口精準，無套利空間"

        return status, risk, reason

    # --- 模組 3: 最終計算與輸出層 ---
    def run(self):
        stats, b2b_list, markets = self.get_raw_data()
        final_report = []

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                h_row = stats[stats['TEAM_NAME'] == h_en].iloc[0]
                a_row = stats[stats['TEAM_NAME'] == a_en].iloc[0]

                # 基礎變量運算 (保留 Pace Factor 與效率修正)
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_off = h_row['E_OFF_RATING'] - (self.b2b_pen if h_en in b2b_list else 0)
                a_off = a_row['E_OFF_RATING'] - (self.b2b_pen if a_en in b2b_list else 0)

                # A. 獨立預測模組 (獨立 Fair Line 計算)
                h_pred = round(((h_off + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_pred = round(((a_off + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                fair_spread = round(a_pred - h_pred, 1)
                fair_total = round(h_pred + a_pred, 1)

                # B. 市場盤口對比
                mkt_spread = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_total = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']

                # C. 呼叫過濾引擎 (整合後的分析位置)
                s_status, s_risk, s_reason = self.filter_engine(fair_spread, mkt_spread, "spread")
                t_status, t_risk, t_reason = self.filter_engine(fair_total, mkt_total, "total")

                # D. 判定具體過盤方向 (Cover 邏輯整合)
                s_pick = f"{h_cn if fair_spread < mkt_spread else a_cn} 過盤" if s_status == "✅ 建議" else "-"
                t_pick = f"{'大分' if fair_total > mkt_total else '小分'}" if t_status == "✅ 建議" else "-"

                final_report.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "型態": "快節奏" if pace > 102 else ("防守戰" if pace < 97 else "標準"),
                    "預估比分": f"{a_pred}:{h_pred}",
                    "讓分盤建議": s_pick,
                    "讓分狀態": s_status,
                    "讓分風險": s_risk if s_status != "✅ 建議" else s_reason,
                    "大小分建議": t_pick,
                    "大小分狀態": t_status,
                    "大小分風險": t_risk if t_status != "✅ 建議" else t_reason,
                    "ML參考": h_cn if h_pred > a_pred else a_cn
                })
            except Exception: continue
        return pd.DataFrame(final_report)

# ==========================================
# 執行與介面渲染
# ==========================================
if st.button('🚀 執行全系統整合量化分析'):
    with st.spinner('同步 NBA 數據、計算三線分流模型、執行避震器...'):
        engine = NBASharpsUnifiedEngine()
        df = engine.run()
        if not df.empty:
            def highlight_status(val):
                if val == '✅ 建議': return 'background-color: #004d00; color: white'
                if val == '❌ NO BET': return 'background-color: #4d0000; color: white'
                return ''
            
            st.table(df.style.applymap(highlight_status, subset=['讓分狀態', '大小分狀態']))
            st.success("整合分析完成。請優先參考「✅ 建議」且無風險提示之盤口。")
        else:
            st.warning("目前暫無足夠盤口數據。")
