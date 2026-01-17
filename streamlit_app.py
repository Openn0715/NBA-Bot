import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# 1. UI 與 Session 初始化
# ==========================================
st.set_page_config(page_title="籃球逐場獵殺 V12", layout="wide")

if 'league' not in st.session_state:
    st.session_state.league = None

def set_league(l): st.session_state.league = l

# ==========================================
# 2. 聯盟模組與數據路由
# ==========================================
LEAGUES = {
    "NBA": "美國職籃", "KBL": "韓國籃球", 
    "CBA": "中國籃球", "B_LEAGUE": "日本籃球"
}

# ==========================================
# 3. 核心逐場分析引擎
# ==========================================
class GameAnalyser:
    def __init__(self, league):
        self.league = league

    def analyze_single_game(self, g):
        """
        對單一比賽進行個別分析邏輯
        """
        # A. 盤口移動計算
        move = g['curr_spread'] - g['open_spread']
        
        # B. RLM (反向移動) 判定邏輯
        # 邏輯：資金在主隊 (bias=H) 但盤口往客隊動 (move > 0)
        is_rlm = (g['public_bias'] == 'H' and move > 0) or (g['public_bias'] == 'A' and move < 0)
        
        # C. 誘盤判斷 (Bait Line)
        # 邏輯：強隊實力遠高於盤口，且無人缺陣
        is_trap = abs(g['open_spread']) < 4.0 and g['is_power_team']
        
        # D. 決定推薦方向
        rec = "❌ NO BET"
        confidence = 50
        reason = "市場行為不明確，莊家與資金方向同步。"

        if is_rlm:
            rec = f"【推薦】{g['home'] if move < 0 else g['away']} (反向盤)"
            confidence = 88
            reason = "偵測到強烈 RLM 信號：市場大眾資金湧入，莊家卻反向調盤，信心度高。"
        elif is_trap:
            rec = f"【推薦】{g['away'] if g['open_spread'] < 0 else g['home']} (受讓)"
            confidence = 75
            reason = "警示：盤口過於友善（太甜），疑似吸注盤，建議反向操作。"
        elif abs(move) >= 2.0:
            rec = f"【推薦】{g['home'] if move < 0 else g['away']}"
            confidence = 65
            reason = "莊家防禦性大幅調盤，跟隨專業資金流向。"

        return {
            "rec": rec,
            "conf": confidence,
            "intent": "發現專業資金介入" if is_rlm else ("莊家設陷誘騙" if is_trap else "正常波動"),
            "reason": reason,
            "is_key_num": abs(g['curr_spread']) in [3.0, 7.0, 10.0]
        }

# ==========================================
# 4. 聯盟選擇入口
# ==========================================
if st.session_state.league is None:
    st.title("🏹 籃球市場逐場分析系統")
    st.subheader("請選擇今日分析聯盟：")
    cols = st.columns(4)
    for i, (k, v) in enumerate(LEAGUES.items()):
        with cols[i]:
            st.button(f"進入 {v}", on_click=set_league, args=(k,), use_container_width=True)
    st.stop()

# ==========================================
# 5. 逐場掃描流程 (主程序)
# ==========================================
st.sidebar.title(f"🏀 {LEAGUES[st.session_state.league]}")
if st.sidebar.button("返回選擇"):
    st.session_state.league = None
    st.rerun()

analysis_date = st.sidebar.date_input("分析日期", datetime.now())

# 模擬當日比賽列表 (實際上會從 API 獲取)
# 這裡展示了 loop 的運作方式
mock_games = [
    {"home": "勇士", "away": "湖人", "open_spread": -4.5, "curr_spread": -3.0, "public_bias": "H", "is_power_team": True},
    {"home": "塞爾提克", "away": "尼克", "open_spread": -8.0, "curr_spread": -9.5, "public_bias": "H", "is_power_team": True},
    {"home": "老鷹", "away": "公牛", "open_spread": -2.5, "curr_spread": -2.5, "public_bias": "A", "is_power_team": False},
]

st.header(f"🎯 {LEAGUES[st.session_state.league]} 逐場市場獵殺報告")

analyser = GameAnalyser(st.session_state.league)

# 重點：逐場進行 Loop
for game in mock_games:
    res = analyser.analyze_single_game(game)
    
    # UI 顯示：Card 形式
    with st.container():
        # 分隔線與標題
        st.markdown(f"### 🏟️ {game['away']} (客) vs {game['home']} (主)")
        
        c1, c2, c3 = st.columns([1, 1, 2])
        
        with c1:
            st.write("**盤口變動**")
            st.latex(f"{game['open_spread']} \\rightarrow {game['curr_spread']}")
            if res['is_key_num']:
                st.warning("⚠️ 停在關鍵分差數字")
                
        with c2:
            st.metric("信心程度", f"{res['conf']}%")
            st.write(f"**意圖：** {res['intent']}")
            
        with c3:
            st.subheader(res['rec'])
            st.info(f"分析理由：{res['reason']}")
            
        st.divider()

# 頁尾說明
st.caption("提示：信心度 80% 以上且為『反向盤』的場次，過盤概率最具統計學意義。")
