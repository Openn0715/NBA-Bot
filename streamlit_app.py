import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="籃球 API 實戰獵殺 V13", layout="wide")

# 請在此輸入您的 API Key
API_KEY = st.secrets.get("THE_ODDS_API_KEY", "YOUR_API_KEY_HERE")

if 'league' not in st.session_state:
    st.session_state.league = None

def set_league(l): st.session_state.league = l

# 聯盟 API 對應表
LEAGUE_MAP = {
    "NBA": "basketball_nba",
    "KBL": "basketball_kbl",
    "CBA": "basketball_cba",
    "B_LEAGUE": "basketball_bleague"
}

# ==========================================
# 2. 核心分析邏輯引擎
# ==========================================
class MarketEngine:
    @staticmethod
    def analyze(home_team, away_team, spread, price):
        # 盤口與賠率分析邏輯
        # 1. 偵測賠率壓力 (如果賠率低於 -115，代表莊家在該方向有賠付壓力)
        is_pressure = price < -115
        
        # 2. 判斷信心與意圖
        confidence = 60
        if is_pressure: confidence += 15
        
        # 3. 推薦方向判斷
        if spread < 0:
            rec = f"{home_team} 讓分 ({spread})"
        else:
            rec = f"{home_team} 受讓 ({spread})"
            
        return {
            "rec": rec,
            "conf": confidence,
            "intent": "莊家賠付防禦" if is_pressure else "市場平衡盤",
            "is_trap": abs(spread) < 2.5 and price < -110
        }

# ==========================================
# 3. 聯盟選擇入口
# ==========================================
if st.session_state.league is None:
    st.title("🏹 籃球實時盤口分析系統 (V13 API 版)")
    st.subheader("請選擇要分析的聯盟：")
    cols = st.columns(4)
    for i, (k, v) in enumerate(LEAGUE_MAP.items()):
        with cols[i]:
            if st.button(f"進入 {k}", use_container_width=True):
                set_league(k)
                st.rerun()
    st.stop()

# ==========================================
# 4. API 數據抓取與逐場分析流程
# ==========================================
st.sidebar.title(f"🏀 當前聯盟：{st.session_state.league}")
if st.sidebar.button("返回選擇"):
    st.session_state.league = None
    st.rerun()

# 呼叫 API
sport_key = LEAGUE_MAP[st.session_state.league]
url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"

st.header(f"🎯 {st.session_state.league} 逐場實時掃描報告")

with st.spinner('正在從 API 抓取最新盤口數據...'):
    try:
        response = requests.get(url)
        data = response.json()

        if not data:
            st.warning("⚠️ 目前 API 中暫無該聯盟今日比賽數據。")
        else:
            # --- 逐場分析 Loop 開始 ---
            for game in data:
                home_team = game['home_team']
                away_team = game['away_team']
                
                # 抓取第一家博彩公司 (通常是 DraftKings 或 FanDuel) 的數據
                try:
                    bookmaker = game['bookmakers'][0]
                    market = bookmaker['markets'][0]
                    outcomes = market['outcomes']
                    
                    # 提取主隊盤口資訊
                    home_outcome = next(o for o in outcomes if o['name'] == home_team)
                    curr_spread = home_outcome['point']
                    curr_price = home_outcome['price']
                    
                    # 執行分析
                    res = MarketEngine.analyze(home_team, away_team, curr_spread, curr_price)
                    
                    # UI 顯示 Card
                    with st.container():
                        st.markdown(f"### 🏟️ {away_team} @ {home_team}")
                        c1, c2, c3 = st.columns([1, 1, 2])
                        
                        with c1:
                            st.write("**當前 API 盤口**")
                            st.latex(f"Spread: {curr_spread}")
                            st.write(f"賠率: {curr_price}")
                        
                        with c2:
                            st.metric("信心程度", f"{res['conf']}%")
                            st.write(f"**意圖：** {res['intent']}")
                            
                        with c3:
                            st.subheader(f"✅ 推薦：{res['rec']}")
                            if res['is_trap']:
                                st.error("🚨 警告：此盤口極度疑似誘騙陷阱 (Bait Line)")
                            else:
                                st.success("📝 市場邏輯：建議根據賠率變動跟注")
                        st.divider()
                except (IndexError, StopIteration):
                    continue
            # --- 逐場分析 Loop 結束 ---

    except Exception as e:
        st.error(f"❌ API 抓取失敗: {str(e)}")

st.caption(f"API 最後同步時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
