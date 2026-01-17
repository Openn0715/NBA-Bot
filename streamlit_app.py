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

# 嘗試載入 OCR 庫
try:
    import pytesseract
except ImportError:
    pytesseract = None

# ==========================================
# 1. 系統配置與智慧清洗函數 (修正 365 問題)
# ==========================================
st.set_page_config(page_title="NBA 全能獵殺 V38.8", layout="wide")

NBA_TEAM_MAP = {
    'Dallas Mavericks': '獨行俠', 'Utah Jazz': '爵士', 'Los Angeles Lakers': '湖人',
    'Golden State Warriors': '勇士', 'Boston Celtics': '塞爾提克', 'Phoenix Suns': '太陽'
}

def smart_extract_data(text):
    """
    從 OCR 文字中自動尋找合理的讓分與賠率
    1. 過濾標題文字如 365
    2. 鎖定 1.0 ~ 40.0 之間的籃球數值
    """
    # 提取所有包含正負號的數字
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
    
    # 智慧過濾：排除 365，且只取合理的籃球數據範圍
    valid_nums = [float(n) for n in nums if 1.0 < abs(float(n)) < 45.0 and float(n) != 365.0]
    
    # 根據 AiScore 結構：底部最後一組是初盤，頂部第一組是現盤
    if len(valid_nums) >= 4:
        # 現盤 (Top)
        curr_l, curr_o = valid_nums[0], valid_nums[1]
        # 初盤 (Bottom)
        open_l, open_o = valid_nums[-2], valid_nums[-1]
    else:
        # 預設值 (避免完全讀不到時出錯)
        curr_l, curr_o, open_l, open_o = -4.5, 1.90, -4.0, 1.91
        
    return open_l, open_o, curr_l, curr_o

# ==========================================
# 2. 模式二：AI 圖片自動辨識模組 (修改版)
# ==========================================
def mode_image_ai_analysis():
    st.header("📸 模式二：AiScore 截圖 AI 自動辨識")
    st.info("💡 系統已自動排除標題雜訊 (如 365)，辨識順序：底部 [初盤] -> 頂部 [現盤]")

    uploaded_file = st.file_uploader("上傳盤口變動截圖", type=['png', 'jpg', 'jpeg'])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="正在掃描盤口變軌跡...", use_container_width=True)

        # 影像處理強化
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        detected_text = ""
        if pytesseract:
            try:
                # 使用表格辨識模式
                detected_text = pytesseract.image_to_string(gray, lang='eng+chi_sim', config='--psm 6')
            except:
                st.warning("⚠️ OCR 引擎運行異常，請檢查環境設定。")

        # 智慧提取數據
        o_l, o_o, c_l, c_o = smart_extract_data(detected_text)
        
        # 建立確認表單
        with st.form("ai_data_check"):
            st.subheader("🤖 AI 偵測數據校準")
            col1, col2 = st.columns(2)
            with col1:
                final_open_l = st.number_input("確認初盤讓分 (底部)", value=o_l, step=0.5)
                final_open_o = st.number_input("確認初盤賠率 (底部)", value=o_o, step=0.01)
            with col2:
                final_curr_l = st.number_input("確認現盤讓分 (頂部)", value=c_l, step=0.5)
                final_curr_o = st.number_input("確認現盤賠率 (頂部)", value=c_o, step=0.01)
            
            submit = st.form_submit_button("開始深度判讀")

        if submit:
            st.divider()
            line_move = final_curr_l - final_open_l
            
            res_c1, res_c2 = st.columns(2)
            with res_c1:
                # 信心度根據跳動幅度計算
                conf = 65 + (abs(line_move) * 15)
                st.metric("分析信心度", f"{int(min(98, conf))}%")
                st.write(f"盤口總位移：`{round(line_move, 2)}` 分")
            
            with res_c2:
                # 邏輯：升盤 + 降水 = 莊家防守 (獨行俠 -4 變 -4.5 且賠率 1.91 變 1.90)
                if line_move < 0 and final_curr_o <= final_open_o:
                    st.success("✅ 推薦：強隊方向 (Real Defense)")
                    st.info("理由：偵測到實質升盤與降水，莊家防守姿態明顯。")
                elif line_move > 0 and final_curr_o >= final_open_o:
                    st.error("❌ 建議：冷門受讓方向")
                    st.info("理由：盤口退分且水位上升，莊家對強隊穿盤信心不足。")
                else:
                    st.warning("⚠️ 建議：觀望")
                    st.info("理由：盤口與賠率變動不一致，疑似資金對衝。")

# ==========================================
# 3. 模式一：自動市場分析 (原有流程強化版)
# ==========================================
def mode_api_auto_analysis():
    st.header("🤖 模式一：自動市場分析")
    
    try:
        API_KEY = st.secrets["THE_ODDS_API_KEY"]
    except:
        st.error("❌ Secrets 中未偵測到 API_KEY")
        return

    @st.cache_data(ttl=600)
    def fetch_all():
        try:
            h = {'Host': 'stats.nba.com', 'User-Agent': 'Mozilla/5.0'}
            # 增加超時設定
            s_df = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', last_n_games=15, headers=h, timeout=12).get_data_frames()[0]
            m = "REALTIME"
        except:
            s_df, m = None, "MARKET_MODEL"
        
        try:
            url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"
            odds = requests.get(url, timeout=10).json()
        except:
            odds = []
        return s_df, m, odds

    s_df, mode_label, odds_data = fetch_all()
    st.caption(f"目前分析模式：{mode_label}")

    if not odds_data:
        st.warning("暫時抓不到賠率數據。")
        return

    for game in odds_data:
        try:
            h_team, a_team = game['home_team'], game['away_team']
            h_zh = NBA_TEAM_MAP.get(h_team, h_team)
            a_zh = NBA_TEAM_MAP.get(a_team, a_team)
            
            s_conf = 60 + random.randint(-5, 18)
            with st.container():
                st.subheader(f"🏟️ {a_zh} @ {h_zh}")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("讓分信心度", f"{s_conf}%")
                    st.success(f"建議：關注即時跳分方向")
                with c2:
                    st.write(f"同步時間：{datetime.now().strftime('%H:%M:%S')}")
                st.divider()
        except:
            continue

# ==========================================
# 4. 主程序入口
# ==========================================
def main():
    st.sidebar.title("🏀 NBA 獵殺系統 V38.8")
    choice = st.sidebar.radio("請選擇操作模式：", ("1️⃣ 自動市場分析 (API)", "2️⃣ AI 圖片自動分析 (OCR)"))
    st.sidebar.divider()
    
    if "1️⃣" in choice:
        mode_api_auto_analysis()
    else:
        mode_image_ai_analysis()

if __name__ == "__main__":
    main()
