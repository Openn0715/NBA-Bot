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
st.set_page_config(page_title="NBA Sharps Elite V9.0", layout="wide")
st.title("🛡️ NBA Sharps Elite V9.0：市場行為與信心過濾版")
st.caption("核心：解讀賠率變化意圖 | 識別誘盤陷阱 | 僅輸出高信心推薦")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("請在 Secrets 中設定 API_KEY")
    st.stop()

class NBAMarketLogicV9:
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
        # 抓取盤口數據 (此 API 包含不同博彩公司的賠率，可用於判斷市場共識)
        market_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        market_data = requests.get(market_url).json()
        return stats, market_data

    def analyze_confidence(self, h_en, a_en, mkt_s, stats_df):
        """核心：結合莊家盤口、賠率與數據基準判定信心"""
        h_row = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0]
        a_row = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0]
        
        # 1. 建立數據基準線 (Fair Line)
        fair_s = -(h_row['E_NET_RATING'] - a_row['E_NET_RATING'] + 2.8)
        
        # 2. 意圖判定 (市場偏差)
        # 偏差 = 現盤 - 數據盤
        bias = mkt_s - fair_s
        
        confidence_score = 0
        intent = "市場觀望"
        recommendation = "❌ NO BET"
        
        # 情境 A：莊家防禦 (盤口比數據更硬，代表莊家怕強隊打爆)
        if bias < -3.0:
            confidence_score = 85
            intent = "🛡️ 莊家強勢防禦 (看好讓分方)"
            recommendation = f"【讓分】{self.team_map.get(h_en)} 讓分"
            
        # 情境 B：反向移動偵測 (數據看好強隊，盤口卻往受讓方走 -> 高勝率的反向信號)
        elif bias > 4.0:
            confidence_score = 90
            intent = "🚨 發現吸注陷阱 (數據過甜，建議反向)"
            recommendation = f"【受讓】{self.team_map.get(a_en)} 受讓"

        # 情境 C：盤口與數據高度契合 (代表莊家開得很準，沒漏洞)
        elif abs(bias) < 1.0:
            confidence_score = 10
            intent = "⚖️ 市場平衡盤 (無獲利邊際)"
            recommendation = "❌ NO BET"

        return confidence_score, intent, recommendation, round(fair_s, 1)

    def run(self):
        stats_df, markets = self.get_data()
        report = []
        if not markets or "error" in markets: return pd.DataFrame()

        for game in markets:
            try:
                h_en, a_en = game['home_team'], game['away_team']
                h_cn, a_cn = self.team_map.get(h_en, h_en), self.team_map.get(a_en, a_en)
                
                # 取得當前讓分盤口
                m_data = game['bookmakers'][0]['markets']
                current_s = m_data[0]['outcomes'][0]['point']
                current_t = m_data[1]['outcomes'][0]['point']
                
                # 分析信心與意圖
                conf, intent, rec, fair = self.analyze_confidence(h_en, a_en, current_s, stats_df)

                # 大小分判定 (基於節奏與效率)
                h_off = stats_df[stats_df['TEAM_NAME']==h_en]['E_OFF_RATING'].values[0]
                a_off = stats_df[stats_df['TEAM_NAME']==a_en]['E_OFF_RATING'].values[0]
                t_fair = (h_off + a_off)
                t_rec = "大分" if t_fair > current_t + 5 else ("小分" if t_fair < current_t - 5 else "❌")

                report.append({
                    "信心指數 %": conf,
                    "對戰 (客@主)": f"{a_cn} @ {h_cn}",
                    "🎯 最終下注推薦": rec,
                    "💡 莊家/市場意圖": intent,
                    "數據基準盤": fair,
                    "目前市場盤口": current_s,
                    "大小分建議": t_rec,
                    "sort": conf
                })
            except: continue
            
        return pd.DataFrame(report).sort_values(by="sort", ascending=False)

# ==========================================
# UI 渲染
# ==========================================
if st.button('🚀 執行 V9.0 市場行為獵殺分析'):
    with st.spinner('正在分析盤口動態與莊家意圖...'):
        engine = NBAMarketLogicV9()
        df = engine.run()
        if not df.empty:
            # 高信心高亮
            st.markdown("### 🏹 高信心下注推薦報告")
            st.table(df.drop(columns=["sort"]))
            
            st.markdown("""
            ---
            ### 🎓 如何閱讀 V9.0 報告？
            1. **信心指數 > 80%**：這是市場出現顯著「偏差」或「莊家異常行為」的時刻，最值得投入。
            2. **🚨 發現吸注陷阱**：當數據非常看好某隊，盤口卻開得很輕鬆時，代表莊家在騙大眾資金。此時系統會建議你**反向操作**。
            3. **🛡️ 莊家強勢防禦**：莊家開出比數據更難買的盤口，代表莊家極度看好該隊，這種場次過盤率極穩。
            4. **❌ NO BET**：當信心指數低於 30% 時，代表莊家開盤非常精準，請忍住手癢，不要下注。
            """)
        else:
            st.warning("⚠️ 無法獲取市場數據。")
