import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from nba_api.stats.endpoints import leaguedashteamstats

# ==========================================
# 1. 系統環境配置
# ==========================================
st.set_page_config(page_title="NBA 全能獵殺 V22", layout="wide")

try:
    API_KEY = st.secrets["THE_ODDS_API_KEY"]
except:
    st.error("❌ 找不到 API Key，請在 Secrets 中設定 THE_ODDS_API_KEY")
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
# 2. 數據抓取
# ==========================================
@st.cache_data(ttl=3600)
def get_advanced_nba_stats():
    try:
        headers = {'Host': 'stats.nba.com', 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://stats.nba.com/'}
        stats = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense='Advanced', last_n_games=15, headers=headers, timeout=20
        ).get_data_frames()[0]
        return stats
    except: return None

@st.cache_data(ttl=300)
def get_odds_data(m_type):
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={API_KEY}&regions=us&markets={m_type}&oddsFormat=american"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except: return []

# ==========================================
# 3. 核心量化引擎 (信心度 0-100% 動態波動)
# ==========================================
def calculate_dynamic_confidence(base_conf, diff, threshold):
    """
    base_conf: 基準起始值 (60 或 62)
    diff: 數據與市場的偏差值
    threshold: 觸發大幅波動的閾值
    """
    # 偏差值越大，信心度增加越快
    bonus = (diff / threshold) * 15 
    final_conf = base_conf + bonus
    
    # 限制在 0-100 之間
    return int(max(0, min(100, final_conf)))

def analyze_nba_game(gs, gt, stats_df):
    try:
        h_en, a_en = gs['home_team'], gs['away_team']
        h_zh, a_zh = NBA_TEAM_MAP.get(h_en, h_en), NBA_TEAM_MAP.get(a_en, a_en)
        
        has_stats = stats_df is not None
        h_stats = stats_df[stats_df['TEAM_NAME'] == h_en].iloc[0] if has_stats else None
        a_stats = stats_df[stats_df['TEAM_NAME'] == a_en].iloc[0] if has_stats else None

        # --- A. 讓分分析 (從 60% 開始波動) ---
        mkt_s_data = gs['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_spread = mkt_s_data['point']
        
        if has_stats:
            fair_s = -((h_stats['E_NET_RATING'] - a_stats['E_NET_RATING']) + 2.5)
            s_diff = abs(fair_s - curr_spread)
            s_conf = calculate_dynamic_confidence(60, s_diff, 2.5) # 每 2.5 分偏差增加 15% 信心
            s_rec = f"{h_zh} 方向" if fair_s < curr_spread else f"{a_zh} 方向"
        else:
            fair_s, s_conf, s_rec = 0, 60, "數據連線中"

        # --- B. 大小分分析 (從 62% 開始波動) ---
        mkt_t_data = gt['bookmakers'][0]['markets'][0]['outcomes'][0]
        curr_total = mkt_t_data['point']
        
        if has_stats:
            fair_t = ((h_stats['E_OFF_RATING'] + a_stats['E_OFF_RATING'])/2 * (h_stats['E_PACE'] + a_stats['E_PACE'])/2 / 50)
            t_diff = abs(fair_t - curr_total)
            t_conf = calculate_dynamic_confidence(62, t_diff, 4.0) # 每 4 分偏差增加 15% 信心
            t_rec = "全場大分" if fair_t > curr_total else "全場小分"
        else:
            fair_t, t_conf, t_rec = 0, 62, "數據連線中"

        return {
            "matchup": f"{a_zh} @ {h_zh}",
            "s_mkt": curr_spread, "s_fair": fair_s, "s_conf": s_conf, "s_rec": s_rec,
            "t_mkt": curr_total, "t_fair": fair_t, "t_conf": t_conf, "t_rec": t_rec
        }
    except: return None

# ==========================================
# 4. 介面呈現
# ==========================================
st.title("🏀 NBA 數據獵殺 V22 (全動態推薦版)")
st.info("💡 信心指數從 0-100% 隨數據偏差值與推薦強度動態波動。")

with st.spinner('計算動態信心指數中...'):
    stats_df = get_advanced_nba_stats()
    spreads = get_odds_data("spreads")
    totals = get_odds_data("totals")

    if spreads:
        for gs in spreads:
            gt = next((t for t in totals if t['id'] == gs['id']), None)
            if not gt: continue
            res = analyze_nba_game(gs, gt, stats_df)
            if not res: continue

            with st.container():
                st.markdown(f"### 🏟️ {res['matchup']}")
                c1, c2 = st.columns(2)
                
                with c1:
                    st.markdown("#### 🎯 讓分 (Spread)")
                    st.metric("讓分信心度", f"{res['s_conf']}%", delta=f"{res['s_conf']-60}%")
                    st.progress(res['s_conf'] / 100)
                    st.write(f"數據基準: `{round(res['s_fair'], 1)}` | 建議: **{res['s_rec']}**")
                
                with c2:
                    st.markdown("#### 📏 大小分 (Total)")
                    st.metric("大小分信心度", f"{res['t_conf']}%", delta=f"{res['t_conf']-62}%")
                    st.progress(res['t_conf'] / 100)
                    st.write(f"數據基準: `{round(res['t_fair'], 1)}` | 建議: **{res['t_rec']}**")
                st.divider()
