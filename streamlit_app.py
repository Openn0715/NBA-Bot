import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V6.3", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.3：決策樹架構版")
st.caption("核心：Spread 主決策制 | 邏輯衝突自動熔斷 | 三線分流一致性校驗")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
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
        except: pass
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    def apply_variance_expansion(self, fair_s, h_row, a_row, h_b2b, a_b2b):
        expansion_factor = 1.0
        net_rating_diff = abs(h_row['E_NET_RATING'] - a_row['E_NET_RATING'])
        if net_rating_diff > 8.0: expansion_factor += 0.15
        if h_b2b or a_b2b: expansion_factor += 0.1
        if max(h_row['E_PACE'], a_row['E_PACE']) > 102: expansion_factor += 0.05
        return round(fair_s * expansion_factor, 1)

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []

        if not markets or (isinstance(markets, dict) and "error" in markets):
            return pd.DataFrame()

        for game in markets:
            try:
                # 1. 基礎數據準備
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                if h_en not in stats['TEAM_NAME'].values or a_en not in stats['TEAM_NAME'].values: continue
                h_row, a_row = stats[stats['TEAM_NAME'] == h_en].iloc[0], stats[stats['TEAM_NAME'] == a_en].iloc[0]
                h_b2b, a_b2b = h_en in b2b_list, a_en in b2b_list

                # 2. 模型核心計算
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_p = round(((h_row['E_OFF_RATING'] - (self.b2b_pen if h_b2b else 0) + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_p = round(((a_row['E_OFF_RATING'] - (self.b2b_pen if a_b2b else 0) + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                fair_s = self.apply_variance_expansion((a_p - h_p), h_row, a_row, h_b2b, a_b2b)
                fair_t = round(h_p + a_p, 1)

                # 3. 市場盤口提取
                m_data = game['bookmakers'][0]['markets']
                mkt_s = m_data[0]['outcomes'][0]['point']
                mkt_t = m_data[1]['outcomes'][0]['point']
                
                # 4. 決策樹決策層 (Decision Tree Logic)
                edge_s = abs(fair_s - mkt_s)
                s_pick = h_cn if fair_s < mkt_s else a_cn
                ml_pred_winner = h_cn if h_p > a_p else a_cn
                is_h_fav = mkt_s < 0 # 市場看好主隊
                
                # STEP 1: 判斷 Spread 是否具備基礎 Edge 與 誘盤過濾
                if edge_s < 1.5 or edge_s > self.spread_trap_limit:
                    s_status = "❌ NO BET"
                    s_desc = "無足夠優勢或誘盤風險"
                else:
                    # STEP 2: 強制一致性校驗
                    # 情況 A: 推薦「讓分方」過盤，但模型預估他會輸球 -> 衝突
                    # 情況 B: 推薦「受讓方」過盤，但模型預估他會大輸 -> 正常校驗
                    is_conflict = False
                    if (s_pick == h_cn and is_h_fav and ml_pred_winner == a_cn) or \
                       (s_pick == a_cn and not is_h_fav and ml_pred_winner == h_cn):
                        is_conflict = True
                    
                    if is_conflict:
                        s_status = "❌ NO BET"
                        s_desc = "邏輯衝突 (勝負與讓分方向背離)"
                    else:
                        s_status = "✅ 建議"
                        type_str = "讓分" if (s_pick == h_cn and is_h_fav) or (s_pick == a_cn and not is_h_fav) else "受讓"
                        s_desc = f"{s_pick} ({type_str}) 過盤"

                # STEP 3: Moneyline 輔助顯示 (依附於 Spread)
                ml_display = ml_pred_winner if s_status == "✅ 建議" else "停止推薦"

                # STEP 4: Total 獨立決策
                t_edge = abs(fair_t - mkt_t)
                if t_edge < 4.5 or t_edge > self.total_trap_limit:
                    t_desc = "❌ NO BET"
                else:
                    t_desc = f"{'大分' if fair_t > mkt_t else '小分'} (Edge:{round(t_edge,1)})"

                report.append({
                    "優先級": 1 if s_status == "✅ 建議" else 99,
                    "對戰": f"{a_cn} @ {h_cn}",
                    "【主要投注盤】讓分建議": s_desc,
                    "【輔助資訊】獨贏參考": ml_display,
                    "【獨立盤】大小分建議": t_desc,
                    "預估比分": f"{a_p}:{h_p}",
                    "讓分狀態": s_status
                })
            except: continue
            
        df = pd.DataFrame(report).sort_values(by=["優先級", "對戰"])
        return df

# --- UI 渲染 ---
if st.button('🎯 啟動決策樹架構分析'):
    with st.spinner('執行決策樹校驗...'):
        df = NBASharpsEliteV6().run()
        if not df.empty:
            # 移除優先級欄位顯示
            display_df = df.drop(columns=["優先級"])
            st.dataframe(display_df, use_container_width=True)
            st.info("💡 邏輯：Spread 為核心，任何方向衝突或 Edge 不足將全場關閉推薦。")
        else:
            st.warning("⚠️ 目前暫無可用賽事數據。")
