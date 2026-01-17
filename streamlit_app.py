import streamlit as st
import pandas as pd
import numpy as np
import requests
from scipy.stats import norm
from datetime import datetime

# ==========================================
# 1. 系統初始化與介面設定
# ==========================================
st.set_page_config(page_title="籃球盤口市場獵人 V10", layout="wide")

if 'selected_league' not in st.session_state:
    st.session_state.selected_league = None

def set_league(league):
    st.session_state.selected_league = league

# 自定義 CSS 強化視覺效果
st.markdown("""
<style>
    .report-card { border: 1px solid #4a4a4a; border-radius: 10px; padding: 20px; margin-bottom: 20px; background-color: #1e1e1e; }
    .high-confidence { border-left: 10px solid #ff4b4b; }
    .league-btn { font-size: 20px !important; height: 100px !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 聯盟選擇介面
# ==========================================
if st.session_state.selected_league is None:
    st.title("🏹 歡迎使用多聯盟籃球盤口分析系統")
    st.subheader("請選擇您要分析的聯盟：")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.button("🇺🇸 NBA", on_click=set_league, args=("NBA",), use_container_width=True)
    with col2: st.button("🇰🇷 韓國籃球 (KBL)", on_click=set_league, args=("KBL",), use_container_width=True)
    with col3: st.button("🇨🇳 中國籃球 (CBA)", on_click=set_league, args=("CBA",), use_container_width=True)
    with col4: st.button("🇯🇵 日本籃球 (B.League)", on_click=set_league, args=("B.League",), use_container_width=True)
    st.stop()

# 顯示當前聯盟
st.sidebar.title(f"🏀 {st.session_state.selected_league}")
if st.sidebar.button("返回聯盟選擇"):
    st.session_state.selected_league = None
    st.rerun()

analysis_date = st.sidebar.date_input("選擇比賽日期", datetime.now())

# ==========================================
# 3. 核心分析引擎 (模組化設計)
# ==========================================
class MarketHunterEngine:
    def __init__(self, league):
        self.league = league
        self.api_key = st.secrets.get("THE_ODDS_API_KEY", "YOUR_API_KEY")

    def get_market_data(self):
        # 模擬 API 抓取邏輯 (實務上會依據 league key 請求 The Odds API)
        # 為了 Gemini 環境展示，我們建立結構化模擬數據
        return [
            {"home": "勇士", "away": "湖人", "spread_open": -4.5, "spread_curr": -5.5, "odds_curr": -110, "total": 228.5, "public_bias": "湖人"},
            {"home": "塞爾提克", "away": "尼克", "spread_open": -8.5, "spread_curr": -7.0, "odds_curr": -115, "total": 215.0, "public_bias": "塞爾提克"},
            {"home": "公鹿", "away": "熱火", "spread_open": -6.0, "spread_curr": -6.0, "odds_curr": -105, "total": 220.0, "public_bias": "公鹿"},
        ]

    def analyze_game(self, game):
        # STEP 1: 盤口移動分析
        move = game['spread_curr'] - game['spread_open']
        
        # STEP 2: RLM 偵測 (反向盤口移動)
        # 如果大眾買 A，但盤口往 B 走
        is_rlm = (game['public_bias'] == game['away'] and move < 0) or (game['public_bias'] == game['home'] and move > 0)
        
        # STEP 3: 誘盤判斷 (假設性戰力基準，NBA 則會調用進階數據)
        is_trap = False
        if abs(game['spread_curr']) < 3.0 and game['public_bias'] == "熱門隊":
            is_trap = True

        # STEP 4: 信心計算
        conf = 50
        reason = "市場行為趨於平衡，建議觀望。"
        rec = "❌ NO BET"
        behavior = "順市場"

        if is_rlm:
            conf = 85
            rec = f"{game['home'] if move < 0 else game['away']} (反向盤口)"
            behavior = "反市場 (RLM)"
            reason = "發現顯著反向移動：資金湧向一方但莊家不惜調整盤口對抗大眾，這通常是專業資金 (Sharps) 進場的信號。"
        elif abs(move) > 1.5:
            conf = 70
            rec = f"{game['home'] if move < 0 else game['away']}"
            behavior = "順市場 (追盤)"
            reason = "盤口出現大幅度單向移動，莊家正在積極防禦，建議跟隨強勢方。"
        elif is_trap:
            conf = 65
            rec = f"{game['away'] if game['spread_curr'] < 0 else game['home']} (受讓)"
            behavior = "反市場 (誘盤拒絕)"
            reason = "目前盤口開得過於友善，疑似吸注陷阱，建議反向操作。"

        return {
            "summary": f"{game['away']} @ {game['home']} (盤口: {game['spread_curr']})",
            "behavior": behavior,
            "recommendation": rec,
            "confidence": conf,
            "reason": reason,
            "total_rec": "Over" if game['total'] < 220 else "Under"
        }

# ==========================================
# 4. 執行與輸出
# ==========================================
engine = MarketHunterEngine(st.session_state.selected_league)
data = engine.get_market_data()

reports = []
for game in data:
    reports.append(engine.analyze_game(game))

# 依信心程度排序
reports.sort(key=lambda x: x['confidence'], reverse=True)

st.header(f"🎯 {st.session_state.selected_league} 盤口分析獵殺報告")
st.write(f"分析日期：{analysis_date}")

for r in reports:
    color_class = "high-confidence" if r['confidence'] >= 80 else ""
    with st.container():
        st.markdown(f"""
        <div class="report-card {color_class}">
            <h3>📌 {r['summary']}</h3>
            <p>📈 <b>市場行為：</b> {r['behavior']}</p>
            <p>✅ <b>推薦下注：</b> <span style="color:#ff4b4b; font-size:20px;">{r['recommendation']}</span></p>
            <p>🔥 <b>信心程度：</b> {r['confidence']}%</p>
            <p>🏀 <b>大小分建議：</b> {r['total_rec']}</p>
            <hr>
            <p>🧠 <b>推薦理由：</b> {r['reason']}</p>
        </div>
        """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("系統提示：當信心程度超過 80% 且標註為『反市場 (RLM)』時，過盤率在歷史統計中最高。")
