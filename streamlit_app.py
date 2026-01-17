import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats

# ==========================================
# 1. 初始化與 API 配置
# ==========================================
st.set_page_config(page_title="NBA 全能獵殺 V19", layout="wide")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 請設定 THE_ODDS_API_KEY")
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
# 2. 數據獲取與快取 (防白屏)
# ==========================================
@st.cache_data(ttl=3600)
def get_advanced_nba_stats():
    """抓取 NBA 進階數據，用於計算 Fair Line"""
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
# 3. 雙向深度分析引擎
# ==========================================
def run_deep_analysis(game_s, game_t, stats_df):
    try:
        h_en, a_en = game_s['home_team'], game_s['away_team']
        h_zh, a_zh = NBA_TEAM_MAP.get(h_en, h_en), NBA_TEAM_MAP.get(a_en, a_en)
        
        # --- 基礎數據獲取 ---
        has_stats = stats_df is not None
        h_stats = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0] if has_stats else None
        a_stats = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0] if has_stats else None

        # --- A. 讓分深度分析 (數據+市場) ---
        mkt_s = game_s['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_spread = mkt_s['point']
        s_price = mkt_s['price']
        
        # 數據基準計算 (Fair Spread)
        if has_stats:
            fair_s = -((h_stats['E_NET_RATING'] - a_stats['E_NET_RATING']) + 2.5)
            s_diff = abs(fair_s - curr_spread)
            s_conf = min(60 + (s_diff * 10), 95)
            s_rec = f"{h_zh} 方向" if fair_s < curr_spread else f"{a_zh} 方向"
        else:
            fair_s = "連線中..."
            s_conf = 65 if s_price < -115 else 60
            s_rec = f"{h_zh} (市場強勢)" if s_price < -115 else f"{a_zh} (市場強勢)"

        # --- B. 大小分深度分析 (數據+市場) ---
        mkt_t = game_t['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_total = mkt_t['point']
        t_price = mkt_t['price']
        
        if has_stats:
            fair_t = ((h_stats['E_OFF_RATING'] + a_stats['E_OFF_RATING'])/2 * (h_stats['E_PACE'] + a_stats['E_PACE'])/2 / 50)
            t_diff = abs(fair_t - curr_total)
            t_conf = min(60 + (t_diff * 8), 95)
            t_rec = "全場大分" if fair_t > curr_total else "全場小分"
        else:
            fair_t = "連線中..."
            t_conf = 62
            t_rec = "全場大分" if t_price < -112 else "全場小分"

        return {
            "matchup": f"{a_zh} @ {h_zh}",
            "s_mkt": curr_spread, "s_fair": fair_s, "s_conf": int(s_conf), "s_rec": s_rec,
            "t_mkt": curr_total, "t_fair": fair_t, "t_conf": int(t_conf), "t_rec": t_rec
        }
    except: return None

# ==========================================
# 4. UI 顯示
# ==========================================
st.title("🏀 NBA 頂級職業數據量化報告 V19")
st.caption("同步內容：近 15 場進階數據、實時盤口、賠率貼水分析")

with st.spinner('正在執行交叉驗證...'):
    stats_df = get_advanced_nba_stats()
    spreads = get_market_odds("spreads")
    totals = get_market_odds("totals")

    if not spreads:
        st.warning("目前暫無 NBA 盤口數據。")
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
                    st.write(f"數據基準: `{res['s_fair']}` | 市場盤口: `{res['s_mkt']}`")
                    st.progress(res['s_conf'] / 100)
                    st.metric("信心度", f"{res['s_conf']}%")
                    st.success(f"具體建議：{res['s_rec']}")
                
                with c2:
                    st.markdown("#### 📏 大小分分析 (Total)")
                    st.write(f"數據基準: `{res['t_fair']}` | 市場盤口: `{res['t_mkt']}`")
                    st.progress(res['t_conf'] / 100)
                    st.metric("信心度", f"{res['t_conf']}%")
                    st.error(f"具體建議：{res['t_rec']}")
                st.divider()

st.caption(f"數據最後同步：{datetime.now().strftime('%H:%M:%S')}")
