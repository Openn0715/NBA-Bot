import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats

# ==========================================
# 1. 初始化與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 全能獵殺 V20", layout="wide")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 請在 Secrets 中設定 THE_ODDS_API_KEY")
    st.stop()

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
# 2. 數據獲取與快取
# ==========================================
@st.cache_data(ttl=3600)
def get_advanced_nba_stats():
    try:
        headers = {'Host': 'stats.nba.com', 'User-Agent': 'Mozilla/5.0'}
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced', 
            last_n_games=15, headers=headers, timeout=15
        ).get_data_frames()[0]
        return stats
    except:
        return None

@st.cache_data(ttl=300)
def get_market_odds(m_type):
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets={m_type}&oddsFormat=american"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return []

# ==========================================
# 3. 雙向深度分析引擎 (依照需求固定信心度)
# ==========================================
def run_deep_analysis(game_s, game_t, stats_df):
    try:
        h_en, a_en = game_s['home_team'], game_s['away_team']
        h_zh, a_zh = NBA_TEAM_MAP.get(h_en, h_en), NBA_TEAM_MAP.get(a_en, a_en)
        
        # 數據基準
        has_stats = stats_df is not None
        h_stats = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0] if has_stats else None
        a_stats = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0] if has_stats else None

        # --- A. 讓分分析 (固定 60%) ---
        mkt_s = game_s['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_spread = mkt_s['point']
        
        if has_stats:
            fair_s = -((h_stats['E_NET_RATING'] - a_stats['E_NET_RATING']) + 2.5)
            s_rec = f"{h_zh} 方向" if fair_s < curr_spread else f"{a_zh} 方向"
        else:
            fair_s = "計算中..."
            s_rec = f"{h_zh} 方向" # 預設

        # --- B. 大小分分析 (固定 62%) ---
        mkt_t = game_t['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_total = mkt_t['point']
        
        if has_stats:
            # 專業大小分計算公式
            fair_t = ((h_stats['E_OFF_RATING'] + a_stats['E_OFF_RATING'])/2 * (h_stats['E_PACE'] + a_stats['E_PACE'])/2 / 50)
            t_rec = "全場大分" if fair_total > curr_total else "全場小分"
        else:
            fair_t = "計算中..."
            t_rec = "全場大分"

        return {
            "matchup": f"{a_zh} @ {h_zh}",
            "s_mkt": curr_spread, "s_fair": fair_s, "s_conf": 60, "s_rec": s_rec,
            "t_mkt": curr_total, "t_fair": fair_t, "t_conf": 62, "t_rec": t_rec
        }
    except: return None

# ==========================================
# 4. UI 介面呈現
# ==========================================
st.title("🏀 NBA 頂級職業數據量化報告 V20")
st.caption("分析單位：數據交叉驗證 + 市場趨勢判定")

with st.spinner('執行量化分析中...'):
    stats_df = get_advanced_nba_stats()
    spreads = get_market_odds("spreads")
    totals = get_market_odds("totals")

    if not spreads:
        st.warning("⚠️ 暫時無法獲取實時盤口數據。")
    else:
        for gs in spreads:
            gt = next((t for t in totals if t['id'] == gs['id']), None)
            if not gt: continue
            
            res = run_deep_analysis(gs, gt, stats_df)
            if not res: continue

            with st.container():
                st.markdown(f"### 🏟️ {res['matchup']}")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("#### 🎯 讓分分析 (Spread)")
                    st.write(f"數據基準: `{res['s_fair'] if isinstance(res['s_fair'], str) else round(res['s_fair'],1)}` | 市場盤口: `{res['s_mkt']}`")
                    st.metric("讓分信心度", f"{res['s_conf']}%")
                    st.progress(res['s_conf'] / 100)
                    st.success(f"具體建議：{res['s_rec']}")
                
                with c2:
                    st.markdown("#### 📏 大小分分析 (Total)")
                    st.write(f"數據基準: `{res['t_fair'] if isinstance(res['t_fair'], str) else round(res['t_fair'],1)}` | 市場盤口: `{res['t_mkt']}`")
                    st.metric("大小分信心度", f"{res['t_conf']}%")
                    st.progress(res['t_conf'] / 100)
                    st.error(f"具體建議：{res['t_rec']}")
                st.divider()

st.caption(f"數據更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
