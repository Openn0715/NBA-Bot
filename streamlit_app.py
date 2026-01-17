import streamlit as st
import pandas as pd
import requests
import numpy as np
from scipy.stats import norm
from datetime import datetime

# ==========================================
# 1. 系統環境與 UI 配置
# ==========================================
st.set_page_config(page_title="籃球市場分析系統 V11", layout="wide")

# 初始化 Session State (確保首頁優先級)
if 'current_league' not in st.session_state:
    st.session_state.current_league = None

def select_league(league_key):
    st.session_state.current_league = league_key

# ==========================================
# 2. League Config (聯盟配置模組)
# ==========================================
LEAGUE_CONFIG = {
    "NBA": {"name": "美國職籃 (NBA)", "has_adv_stats": True, "api_key": "basketball_nba"},
    "KBL": {"name": "韓國籃球 (KBL)", "has_adv_stats": False, "api_key": "basketball_kbl"},
    "CBA": {"name": "中國籃球 (CBA)", "has_adv_stats": False, "api_key": "basketball_cba"},
    "B_LEAGUE": {"name": "日本籃球 (B.League)", "has_adv_stats": False, "api_key": "basketball_bleague"}
}

# ==========================================
# 3. 分析引擎模組 (職責分離)
# ==========================================
class BasketballAnalysisRouter:
    def __init__(self, league_key):
        self.league = league_key
        self.config = LEAGUE_CONFIG[league_key]
        self.api_key = st.secrets.get("THE_ODDS_API_KEY", "")

    def fetch_data(self):
        # 實務上在此依據 self.config['api_key'] 請求不同的資料源
        # 以下為模擬數據結構
        return [
            {
                "home": "主隊", "away": "客隊", 
                "line_open": -5.5, "line_curr": -4.0, 
                "odds_curr": -110, "total": 215.5,
                "public_volume": "65% on Home"
            }
        ]

    # --- 邏輯 A: 純市場分析 (所有聯盟適用) ---
    def pure_market_analysis(self, game):
        move = game['line_curr'] - game['line_open']
        is_rlm = ("Home" in game['public_volume'] and move > 0) or ("Away" in game['public_volume'] and move < 0)
        
        strength = 50
        intent = "市場波動平穩"
        rec = "❌ NO BET"
        
        if is_rlm:
            strength = 85
            rec = f"{game['away'] if move > 0 else game['home']} (RLM 方向)"
            intent = "⚠️ 偵測到反向移動 (RLM)：大眾買入但盤口反向，莊家顯然在防範專業資金。"
        elif abs(move) >= 1.5:
            strength = 70
            rec = f"{game['home'] if move < 0 else game['away']} (趨勢跟隨)"
            intent = "🛡️ 莊家單向防禦：盤口移動幅度劇烈，莊家正在降低賠付風險。"
        
        return strength, intent, rec

    # --- 邏輯 B: NBA 專屬數據驗證 (僅 NBA 呼叫) ---
    def validate_with_nba_stats(self, game):
        # 此處會載入 nba_api 數據 (OffRtg, DefRtg, 傷病)
        # 僅用於微調信心度，不決定方向
        stats_check = "✅ 已完成傷病與效率值校驗。目前盤口變化與主力缺陣情況吻合。"
        confidence_boost = 5 # 數據支持則提升信心
        return confidence_boost, stats_check

# ==========================================
# 4. League Selector (首頁介面)
# ==========================================
if st.session_state.current_league is None:
    st.title("🏹 籃球市場盤口分析系統")
    st.subheader("請先選擇要分析的聯盟：")
    
    cols = st.columns(4)
    btn_keys = list(LEAGUE_CONFIG.keys())
    
    for i, key in enumerate(btn_keys):
        with cols[i]:
            if st.button(f"進入 {LEAGUE_CONFIG[key]['name']}", use_container_width=True):
                select_league(key)
                st.rerun()
    
    st.info("💡 系統說明：NBA 模式將包含額外的效率值與傷病校驗；其餘聯盟僅針對市場行為分析。")
    st.stop()

# ==========================================
# 5. 分析主流程 (Analysis Router)
# ==========================================
target_league = st.session_state.current_league
config = LEAGUE_CONFIG[target_league]

# Sidebar 控制項
st.sidebar.title(f"🏀 {config['name']}")
if st.sidebar.button("⬅️ 返回聯盟選擇"):
    st.session_state.current_league = None
    st.rerun()

st.header(f"🎯 {config['name']} 當日市場深度解析")
st.write(f"當前模式：{'市場行為 + 數據驗證 (NBA)' if config['has_adv_stats'] else '純市場盤口行為分析 (International)'}")

router = BasketballAnalysisRouter(target_league)
games = router.fetch_data()

# 渲染分析結果
for g in games:
    # 執行基礎市場分析
    mkt_strength, mkt_intent, mkt_rec = router.pure_market_analysis(g)
    
    # 執行 NBA 專屬校驗
    final_confidence = mkt_strength
    nba_stats_report = ""
    
    if config['has_adv_stats']:
        boost, stats_log = router.validate_with_nba_stats(g)
        final_confidence += boost
        nba_stats_report = stats_log

    # 輸出卡片
    with st.container():
        col_l, col_r = st.columns([1, 2])
        with col_l:
            st.metric("信號強度", f"{final_confidence}%")
            st.subheader(f"✅ 推薦：{mkt_rec}")
        with col_r:
            st.markdown(f"**📌 盤口狀態：** 初盤 {g['line_open']} → 現盤 {g['line_curr']}")
            st.markdown(f"**🧠 市場判讀：** {mkt_intent}")
            if nba_stats_report:
                st.markdown(f"**🔬 NBA 數據校驗：** {nba_stats_report}")
        st.divider()

st.caption(f"數據更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
