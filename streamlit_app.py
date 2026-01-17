import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="籃球全聯盟市場分析 V14", layout="wide")

# 自動從 Secrets 讀取，若無則報錯
try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except Exception:
    st.error("❌ 請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

if 'league' not in st.session_state:
    st.session_state.league = None

def set_league(l): st.session_state.league = l

# 聯盟 API 對應表 (確認 key 與官方一致)
LEAGUE_MAP = {
    "NBA": "basketball_nba",
    "KBL": "basketball_kbl",
    "CBA": "basketball_cba",
    "B.League": "basketball_bleague"
}

# ==========================================
# 2. 逐場市場分析引擎 (嚴格職責分離)
# ==========================================
class MarketEngineV14:
    @staticmethod
    def analyze_game(game_data, league):
        home_team = game_data['home_team']
        away_team = game_data['away_team']
        
        try:
            # 抓取第一家博彩公司的盤口 (Spreads)
            bookmaker = game_data['bookmakers'][0]
            market = bookmaker['markets'][0]
            outcomes = market['outcomes']
            
            home_o = next(o for o in outcomes if o['name'] == home_team)
            spread = home_o['point']
            price = home_o['price']
            
            # --- 市場心理分析邏輯 ---
            # 1. 賠率壓力偵測 (熱門方賠率低於 -115)
            is_heavy_pressure = price < -118
            
            # 2. 信心指標
            confidence = 65
            if is_heavy_pressure: confidence += 15
            
            # 3. 推薦方向判定
            if spread < 0:
                direction = f"{home_team} 讓分 ({spread})"
                intent = "莊家防禦主隊大勝" if is_heavy_pressure else "標竿平衡盤"
            else:
                direction = f"{home_team} 受讓 (+{spread})"
                intent = "資金湧入受讓方" if is_heavy_pressure else "市場正常波動"

            return {
                "success": True,
                "summary": f"{away_team} @ {home_team}",
                "rec": direction,
                "conf": confidence,
                "intent": intent,
                "spread": spread,
                "price": price,
                "is_bait": abs(spread) < 3.0 and price < -110
            }
        except Exception:
            return {"success": False}

# ==========================================
# 3. 聯盟選擇入口
# ==========================================
if st.session_state.league is None:
    st.title("🏹 籃球全聯盟逐場市場掃描")
    st.subheader("請選擇今日分析聯盟：")
    cols = st.columns(4)
    for i, (k, v) in enumerate(LEAGUE_MAP.items()):
        with cols[i]:
            if st.button(f"進入 {k}", use_container_width=True):
                set_league(k)
                st.rerun()
    st.info("提示：NBA 以外的亞洲聯盟（CBA/KBL）通常在開賽前 4-6 小時才會釋出盤口數據。")
    st.stop()

# ==========================================
# 4. API 實時分析流程
# ==========================================
st.sidebar.title(f"🏀 {st.session_state.league}")
if st.sidebar.button("⬅️ 返回聯盟選擇"):
    st.session_state.league = None
    st.rerun()

league_key = LEAGUE_MAP[st.session_state.league]
url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"

st.header(f"🎯 {st.session_state.league} 逐場實時解析報告")

with st.spinner(f'正在同步 {st.session_state.league} 實時盤口...'):
    response = requests.get(url)
    raw_data = response.json()

    # 修正錯誤：檢查 API 回傳是否為列表
    if not isinstance(raw_data, list):
        st.error(f"⚠️ API 回傳異常：{raw_data.get('message', '未知錯誤')}")
        st.info("這通常代表目前該聯盟在 API 中暫無盤口數據，請稍後再試。")
    elif len(raw_data) == 0:
        st.warning(f"目前 {st.session_state.league} 暫無比賽或盤口尚未開出。")
    else:
        # 逐場進行 Loop 分析
        for game in raw_data:
            analysis = MarketEngineV14.analyze_game(game, st.session_state.league)
            
            if not analysis["success"]:
                continue
                
            with st.container():
                st.markdown(f"### 🏟️ {analysis['summary']}")
                c1, c2, c3 = st.columns([1, 1, 2])
                
                with c1:
                    st.write("**當前市場數據**")
                    st.metric("Spread", analysis['spread'])
                    st.write(f"賠率: {analysis['price']}")
                
                with c2:
                    st.metric("信心度", f"{analysis['conf']}%")
                    st.write(f"**意圖：** {analysis['intent']}")
                    
                with c3:
                    st.subheader(f"✅ 推薦下注：{analysis['rec']}")
                    if analysis['is_bait']:
                        st.error("🚨 誘盤警告：盤口異常友善，謹慎下注。")
                    else:
                        st.success("📝 市場分析：目前盤口移動與數據邏輯吻合。")
                st.divider()

st.caption(f"數據同步時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
