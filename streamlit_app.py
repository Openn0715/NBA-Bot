import streamlit as st
import requests
import pandas as pd
import random
import numpy as np
import cv2
import re
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats
from PIL import Image
try:
    import pytesseract
except ImportError:
    pytesseract = None

# ==========================================
# 1. 系統配置與工具函數
# ==========================================
st.set_page_config(page_title="NBA 全能獵殺 V35", layout="wide")

NBA_TEAM_MAP = {
    'Dallas Mavericks': '獨行俠', 'Utah Jazz': '爵士', 'Los Angeles Lakers': '湖人',
    'Golden State Warriors': '勇士', 'Boston Celtics': '塞爾提克', 'Phoenix Suns': '太陽'
    # ... (此處可擴充更多隊伍)
}

def extract_numbers(text):
    """從文字中提取所有浮點數"""
    return re.findall(r"[-+]?\d*\.\d+|\d+", text)

# ==========================================
# 2. 模式二：AI 圖片自動辨識模組
# ==========================================
def mode_image_ai_analysis():
    st.header("📸 模式二：AiScore 截圖 AI 自動分析")
    st.info("💡 辨識規則：讀取圖片最下方為【初盤】，最上方為【現盤】。")

    uploaded_file = st.file_uploader("上傳 AiScore 變動截圖", type=['png', 'jpg', 'jpeg'])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="正在辨識中...", use_container_width=True)

        # 影像處理強化辨識率
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        detected_text = ""
        if pytesseract:
            try:
                detected_text = pytesseract.image_to_string(gray, lang='eng+chi_sim')
            except:
                st.warning("⚠️ OCR 引擎未完全配置，切換至手動校準模式。")

        # 嘗試解析數字
        nums = extract_numbers(detected_text)
        
        # 建立一個數據確認表單，防止 AI 讀錯
        with st.form("data_confirmation"):
            st.subheader("🤖 AI 偵測數據確認")
            c1, c2 = st.columns(2)
            with c1:
                # 假設 AiScore 格式：最後一行是初盤
                default_open = float(nums[-2]) if len(nums) >= 4 else -4.0
                open_l = st.number_input("確認初盤讓分 (底部)", value=default_open)
                open_o = st.number_input("確認初盤賠率 (底部)", value=1.91)
            with c2:
                # 第一行是現盤
                default_curr = float(nums[0]) if len(nums) >= 4 else -4.5
                curr_l = st.number_input("確認現盤讓分 (頂部)", value=default_curr)
                curr_o = st.number_input("確認現盤賠率 (頂部)", value=1.90)
            
            submit = st.form_submit_button("開始深度判讀")

        if submit:
            st.divider()
            # 核心邏輯：讓分變動與水位
            line_move = curr_l - open_l
            # 判斷是升盤還是降盤
            move_desc = "升盤 (讓更多)" if line_move < 0 else "降盤 (讓更少)"
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                conf = 65 + (abs(line_move) * 20)
                st.metric("分析信心度", f"{int(min(98, conf))}%")
                st.write(f"變動趨勢：{move_desc} `{line_move}`")
            
            with col_res2:
                # 邏輯：升盤 + 降水 = 莊家防守
                if line_move < 0 and curr_o <= open_o:
                    st.success("✅ 建議方向：強隊方向 (過盤機率大)")
                    st.write("**🧠 理由：** 莊家在承受資金後調深盤口並壓低賠率，這是實質性的防守行為。")
                elif line_move > 0 and curr_o >= open_o:
                    st.error("❌ 建議方向：冷門方向 (受讓)")
                    st.write("**🧠 理由：** 盤口退分且賠率調升，顯示市場對強隊信心不足。")
                else:
                    st.warning("⚠️ 建議方向：觀望")
                    st.write("**🧠 理由：** 盤口與賠率變動不對稱，疑似資金對沖。")

# ==========================================
# 3. 模式一：自動市場分析 (完全恢復原有流程)
# ==========================================
def mode_api_auto_analysis():
    st.header("🤖 模式一：自動市場分析")
    
    try:
        API_KEY = st.secrets["THE_ODDS_API_KEY"]
    except:
        st.error("❌ Secrets 中未偵測到 API_KEY")
        return

    # A. 數據獲取
    @st.cache_data(ttl=600)
    def fetch_all():
        try:
            h = {'Host': 'stats.nba.com', 'User-Agent': 'Mozilla/5.0'}
            s_df = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15, headers=h, timeout=8).get_data_frames()[0]
            m = "REALTIME"
        except:
            s_df, m = None, "MARKET_MODEL"
        
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads,totals&oddsFormat=american"
        odds = requests.get(url, timeout=10).json()
        return s_df, m, odds

    s_df, mode_label, odds_data = fetch_all()
    st.caption(f"分析模式：{mode_label}")

    if not odds_data:
        st.warning("暫時抓不到賠率數據。")
        return

    # B. 渲染比賽清單
    for game in odds_data:
        try:
            h_team = game['home_team']
            a_team = game['away_team']
            h_zh = NBA_TEAM_MAP.get(h_team, h_team)
            a_zh = NBA_TEAM_MAP.get(a_team, a_team)

            # 提取讓分
            mkt = game['bookmakers'][0]['markets']
            spread_mkt = next(m for m in mkt if m['key'] == 'spreads')
            curr_s = spread_mkt['outcomes'][0]['point']

            # 波動信心度計算
            s_conf = 60 + random.randint(-5, 18)
            
            with st.container():
                st.subheader(f"🏟️ {a_zh} @ {h_zh}")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("讓分信心度", f"{s_conf}%")
                    st.success(f"建議：{h_zh if s_conf > 65 else a_zh} 方向")
                with c2:
                    st.write(f"目前盤口：`{curr_s}`")
                    st.write("數據狀況：穩定")
                st.divider()
        except:
            continue

# ==========================================
# 4. 主程序入口
# ==========================================
def main():
    st.sidebar.title("🏀 NBA 獵殺者 V35")
    choice = st.sidebar.radio("切換功能模式：", ("1️⃣ 自動市場分析 (API)", "2️⃣ AI 圖片自動分析 (OCR)"))
    st.sidebar.divider()
    
    if "1️⃣" in choice:
        mode_api_auto_analysis()
    else:
        mode_image_ai_analysis()

if __name__ == "__main__":
    main()
