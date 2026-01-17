import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 系統環境配置
# ==========================================
st.set_page_config(page_title="NBA 數據獵殺 V18", layout="wide")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 找不到 API Key，請檢查 Secrets 設定。")
    st.stop()

# 核心映射表
NBA_TEAM_MAP = {
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

# ==========================================
# 2. 穩定的數據抓取 (帶有錯誤處理)
# ==========================================
@st.cache_data(ttl=600)
def get_safe_odds(market_type):
    """抓取盤口數據，增加超時處理"""
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets={market_type}&oddsFormat=american"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
        return []
    except:
        return []

# ==========================================
# 3. 分析引擎 (當連不上官方數據時使用動態加權)
# ==========================================
class NBASmartEngine:
    @staticmethod
    def get_analysis(game_s, game_t):
        try:
            home = game_s['home_team']
            away = game_s['away_team']
            
            # 取得讓分
            s_outcomes = game_s['bookmakers'][0]['markets'][0]['outcomes']
            h_s = next(o for o in s_outcomes if o['name'] == home)
            mkt_spread = h_s['point']
            mkt_s_price = h_s['price']
            
            # 取得大小分
            t_outcomes = game_t['bookmakers'][0]['markets'][0]['outcomes']
            mkt_total = t_outcomes[0]['point']
            mkt_t_price = t_outcomes[0]['price']

            # 模擬數據計算 (因應官方連線問題，改用市場變動與固定戰力偏差作為分析)
            # 讓分信心邏輯：賠率低於 -115 且 盤口落在關鍵分差
            s_conf = 60
            if mkt_s_price < -115: s_conf += 15
            if abs(mkt_spread) in [3, 7, 10]: s_conf += 10
            
            # 大小分信心邏輯：盤口相對於平均值 (225) 的背離程度
            t_conf = 65
            if mkt_total > 235 or mkt_total < 215: t_conf += 10

            return {
                "matchup": f"{NBA_TEAM_MAP.get(away, away)} @ {NBA_TEAM_MAP.get(home, home)}",
                "s_mkt": mkt_spread, "s_conf": s_conf, "s_rec": f"{NBA_TEAM_MAP.get(home) if mkt_s_price < -110 else NBA_TEAM_MAP.get(away)} 方向",
                "t_mkt": mkt_total, "t_conf": t_conf, "t_rec": "全場大分" if mkt_t_price < -112 else "全場小分"
            }
        except:
            return None

# ==========================================
# 4. 執行流程
# ==========================================
st.title("🏀 NBA 數據獵殺 V18.0 (穩定運作版)")
st.info("💡 系統已啟用快取與防斷線機制，確保即時輸出不跳轉。")

with st.spinner('同步最新市場數據中...'):
    spreads = get_safe_odds("spreads")
    totals = get_safe_odds("totals")

    if not spreads:
        st.warning("⚠️ 無法取得即時盤口，可能是 API 次數用盡或網路延遲。請稍後刷新。")
    else:
        for g_s in spreads:
            g_t = next((t for t in totals if t['id'] == g_s['id']), None)
            if not g_t: continue
            
            res = NBASmartEngine.get_analysis(g_s, g_t)
            if not res: continue

            with st.container():
                st.markdown(f"### 🏟️ {res['matchup']}")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("<div style='border:1px solid #444; padding:10px; border-radius:5px;'>", unsafe_allow_html=True)
                    st.write("**🎯 讓分 (Spread)**")
                    st.write(f"市場盤口: `{res['s_mkt']}`")
                    st.metric("讓分信心度", f"{res['s_conf']}%")
                    st.success(f"建議：{res['s_rec']}")
                    st.markdown("</div>", unsafe_allow_html=True)
                
                with c2:
                    st.markdown("<div style='border:1px solid #444; padding:10px; border-radius:5px;'>", unsafe_allow_html=True)
                    st.write("**📏 大小分 (Total)**")
                    st.write(f"市場盤口: `{res['t_mkt']}`")
                    st.metric("大小分信心度", f"{res['t_conf']}%")
                    st.error(f"建議：{res['t_rec']}")
                    st.markdown("</div>", unsafe_allow_html=True)
                st.divider()
