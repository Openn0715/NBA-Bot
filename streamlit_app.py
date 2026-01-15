import streamlit as st
import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2
from datetime import datetime, timedelta

# ==========================================
# 系統配置
# ==========================================
st.set_page_config(page_title="NBA Sharps Elite V6.1", layout="wide")
st.title("🛡️ NBA Sharps Elite V6.1：邏輯校驗修正版")
st.caption("修正：決策一致性衝突 (Consistent Decision Bug) | 強化：過盤邏輯校驗")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

# ==========================================
# 核心引擎 (含修正後的決策層)
# ==========================================
class NBASharpsUnifiedElite:
    def __init__(self):
        self.home_adv = 2.8
        self.b2b_pen = 2.5
        self.spread_trap_limit = 6.5
        self.total_trap_limit = 10.0
        self.min_edge_spread = 1.5
        self.min_edge_total = 4.5
        self.team_map = { # 略，保持原狀 }

    def get_data(self):
        stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15).get_data_frames()[0]
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        sb = scoreboardv2.ScoreboardV2(game_date=yesterday).get_data_frames()[1]
        b2b_list = list(sb['TEAM_ABBREVIATION']) if not sb.empty else []
        market_data = requests.get(f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american").json()
        return stats, b2b_list, market_data

    # --- 修正後的過濾與一致性引擎 ---
    def unified_decision_logic(self, fair_s, mkt_s, h_p, a_p):
        edge = abs(fair_s - mkt_s)
        ml_winner = "H" if h_p > a_p else "A"
        
        # 1. 基礎誘盤偵測
        if edge > self.spread_trap_limit:
            return "❌ NO BET", "🚨 誘盤風險", "數據極端偏移", "避讓"

        # 2. 一致性校驗層 (Consistency Check)
        # 如果模型預測 A 隊贏球 (ml_winner)，但建議方向卻是買 B 隊「讓分過盤」
        # 這只有在 B 隊是受讓方且預測輸分小於受讓分時才合理。
        # 錯誤 Bug 修復點：檢查方向是否背離預測勝負
        if fair_s < mkt_s: # 建議主隊
            recom_winner = "H"
        else: # 建議客隊
            recom_winner = "A"
            
        # 衝突判定：建議「讓分方」過盤，但模型卻預測該隊「輸球」
        # 如果 mkt_s < 0 代表主讓，mkt_s > 0 代表客讓
        is_h_fav = mkt_s < 0
        is_conflict = False
        
        if recom_winner == "H" and not is_h_fav and ml_winner == "A":
            # 這是主隊「受讓過盤」，模型預測主隊輸球但輸不多，合理。
            pass
        elif recom_winner == "H" and is_h_fav and ml_winner == "A":
            # 這是主隊「讓分過盤」，但模型預測主隊「直接輸球」，嚴重衝突！
            is_conflict = True
        elif recom_winner == "A" and is_h_fav and ml_winner == "H":
            # 這是客隊「受讓過盤」，合理。
            pass
        elif recom_winner == "A" and not is_h_fav and ml_winner == "H":
            # 這是客隊「讓分過盤」，但模型預測客隊「直接輸球」，嚴重衝突！
            is_conflict = True

        if is_conflict:
            return "❌ NO BET", "⚠️ 邏輯衝突", "模型預測勝負與讓分方向背離", "跳過"

        # 3. CLV 空間檢查
        if edge < self.min_edge_spread:
            return "⚖️ 觀望", "無優勢", "盤口精準", "無空間"

        return "✅ 建議", "低", "-", recom_winner

    def run(self):
        stats, b2b_list, markets = self.get_data()
        report = []

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                h_row, a_row = stats[stats['TEAM_NAME'] == h_en].iloc[0], stats[stats['TEAM_NAME'] == a_en].iloc[0]

                # 計算 Fair Line
                pace = (h_row['E_PACE'] + a_row['E_PACE']) / 2
                h_off = h_row['E_OFF_RATING'] - (self.b2b_pen if h_en in b2b_list else 0)
                a_off = a_row['E_OFF_RATING'] - (self.b2b_pen if a_en in b2b_list else 0)
                h_p = round(((h_off + a_row['E_DEF_RATING']) / 2 + self.home_adv) * pace / 100, 1)
                a_p = round(((a_off + h_row['E_DEF_RATING']) / 2) * pace / 100, 1)
                
                fair_s = round(a_p - h_p, 1)
                mkt_s = game['bookmakers'][0]['markets'][0]['outcomes'][0]['point']
                mkt_t = game['bookmakers'][0]['markets'][1]['outcomes'][0]['point']
                fair_t = round(h_p + a_p, 1)

                # --- 執行一致性校驗 ---
                s_status, s_risk, s_reason, s_winner_code = self.unified_decision_logic(fair_s, mkt_s, h_p, a_p)
                
                # 大小分處理 (保留原有邏輯)
                t_edge = abs(fair_t - mkt_t)
                if t_edge > self.total_trap_limit:
                    t_status, t_pick = "❌ NO BET", "-"
                elif t_edge < self.min_edge_total:
                    t_status, t_pick = "⚖️ 觀望", "-"
                else:
                    t_status, t_pick = "✅ 建議", ("大分" if fair_t > mkt_t else "小分")

                # ML 降級校驗
                ml_recom = (h_cn if h_p > a_p else a_cn)
                if s_status == "❌ NO BET" and s_risk == "⚠️ 邏輯衝突":
                    ml_recom = f"僅供參考: {ml_recom}"

                report.append({
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "預估比分": f"{a_p}:{h_p}",
                    "讓分盤推薦": f"{h_cn if s_winner_code=='H' else a_cn} ({'讓分' if (s_winner_code=='H' and mkt_s<0) or (s_winner_code=='A' and mkt_s>0) else '受讓'})過盤" if s_status=="✅ 建議" else "-",
                    "讓分狀態": s_status,
                    "讓分風險": s_risk if s_status != "✅ 建議" else s_reason,
                    "大小分建議": t_pick if t_status == "✅ 建議" else "-",
                    "大小分狀態": t_status,
                    "獨贏參考": ml_recom
                })
            except: continue
        return pd.DataFrame(report)

# ==========================================
# 介面渲染
# ==========================================
if st.button('🚀 執行校驗整合分析'):
    engine = NBASharpsUnifiedElite()
    df = engine.run()
    if not df.empty:
        st.table(df)
    else:
        st.warning("暫無盤口。")
