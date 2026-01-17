import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 系統環境與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 頂級量化分析 V15", layout="wide")

# API Key 安全獲取
try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except Exception:
    st.error("❌ 錯誤：請在 Streamlit Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

# NBA 全球隊中文名稱映射表
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
# 2. NBA 核心分析引擎
# ==========================================
class NBAMarketSniper:
    @staticmethod
    def get_zh_name(en_name):
        return NBA_TEAM_MAP.get(en_name, en_name)

    @staticmethod
    def analyze_market(game):
        try:
            home_en = game['home_team']
            away_en = game['away_team']
            home_zh = NBA_TEAM_MAP.get(home_en, home_en)
            away_zh = NBA_TEAM_MAP.get(away_en, away_en)
            
            # 獲取賠率數據
            bookmaker = game['bookmakers'][0] # 使用標竿博彩公司
            market = bookmaker['markets'][0]
            outcomes = market['outcomes']
            
            home_o = next(o for o in outcomes if o['name'] == home_en)
            spread = home_o['point']
            price = home_o['price']
            
            # --- 核心邏輯 ---
            # 1. 信心指數計算
            conf = 70
            if price < -115: conf += 10 # 賠率壓力
            if abs(spread) in [3, 7, 10]: conf += 5 # 關鍵數字停留
            
            # 2. 意圖判定
            intent = "正常市場波動"
            if price < -120:
                intent = "🚨 莊家賠付預警：資金過度集中"
            elif abs(spread) < 2.5:
                intent = "⚖️ 均勢盤口：勝負取決於關鍵球"

            # 3. 推薦方向
            rec = f"{home_zh} {'讓分' if spread < 0 else '受讓'} ({spread})"
            
            return {
                "success": True,
                "matchup": f"{away_zh} @ {home_zh}",
                "spread": spread,
                "price": price,
                "conf": conf,
                "intent": intent,
                "rec": rec
            }
        except Exception:
            return {"success": False}

# ==========================================
# 3. UI 介面與實時抓取
# ==========================================
st.title("🏀 NBA 職業量化市場分析報告")
st.markdown("---")

# 側邊欄控制
st.sidebar.header("系統參數")
target_date = st.sidebar.date_input("選擇分析日期", datetime.now())

# API 請求
url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american"

with st.spinner('正在同步 NBA 最新實時盤口與賠率...'):
    response = requests.get(url)
    raw_json = response.json()

    # 嚴格檢查回傳格式
    if not isinstance(raw_json, list):
        st.error(f"API 異常：{raw_json.get('message', '未知錯誤')}")
    elif len(raw_json) == 0:
        st.warning("目前 API 中暫無當日 NBA 比賽數據。")
    else:
        # 逐場掃描分析
        sniper = NBAMarketSniper()
        
        for game in raw_json:
            analysis = sniper.analyze_market(game)
            
            if not analysis["success"]:
                continue
            
            # 每一場比賽獨立呈現一個 Card
            with st.container():
                st.subheader(f"🏟️ {analysis['matchup']}")
                c1, c2, c3 = st.columns([1, 1, 2])
                
                with c1:
                    st.metric("實時盤口", analysis['spread'])
                    st.write(f"當前賠率: {analysis['price']}")
                
                with c2:
                    st.metric("分析信心度", f"{analysis['conf']}%")
                    st.write(f"**意圖：** {analysis['intent']}")
                
                with c3:
                    st.markdown(f"### ✅ 建議：<span style='color:red'>{analysis['rec']}</span>", unsafe_allow_html=True)
                    if analysis['conf'] >= 80:
                        st.success("🔥 高價值推薦：市場信號極其強烈。")
                    else:
                        st.info("📝 穩健操作：建議控制倉位。")
                
                st.divider()

st.caption(f"數據自動更新於：{datetime.now().strftime('%H:%M:%S')}")
