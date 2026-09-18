"""LocalMind - yerel RAG soru-cevap asistanı (Streamlit arayüzü).

ÇALIŞTIRMA
    streamlit run app.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import config

APP_NAME    = "LocalMind"
APP_VERSION = "v1.0"

st.set_page_config(
    page_title=f"{APP_NAME} — Yerel RAG Asistanı",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════
#  ORTAK CSS  (landing + chat ekranı için)
# ═══════════════════════════════════════════════════════════
CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

  :root {
    --acc:   #6366f1;
    --acc2:  #818cf8;
    --acc3:  #a5b4fc;
    --adim:  rgba(99,102,241,.13);
    --glow:  rgba(99,102,241,.30);
    --line:  rgba(255,255,255,.07);
    --line2: rgba(255,255,255,.12);
    --s1:    rgba(255,255,255,.025);
    --s2:    rgba(255,255,255,.05);
    --s3:    rgba(255,255,255,.09);
    --mu:    rgba(230,237,243,.42);
    --mu2:   rgba(230,237,243,.68);
    --ok:    #34d399;
    --okd:   rgba(52,211,153,.13);
    --warn:  #fbbf24;
    --warnd: rgba(251,191,36,.11);
    --tx:    #e6edf3;
    --bg:    #0b0e14;
    --r:     14px;
    --rs:    9px;
  }

  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
  }

  .block-container {
    padding-top: 0 !important;
    padding-bottom: 5rem;
    max-width: 1000px;
  }

  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
  [data-testid="stToolbar"]     { visibility: hidden !important; }
  [data-testid="stDecoration"]  { display: none !important; }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0f1320 0%,#0b0e14 100%) !important;
    border-right: 1px solid var(--line2) !important;
  }

  /* ═══════════════════════════════════
     LANDING EKRANI
  ═══════════════════════════════════ */
  /* Giriş sayfasında boş kalan sabit Streamlit başlığını kaldır. */
  body:has(.st-key-landing_page) [data-testid="stHeader"] {
    display: none !important;
  }
  body:has(.st-key-landing_page) [data-testid="stAppViewContainer"] > .main {
    padding-top: 0 !important;
  }
  .st-key-landing_page {
    min-height: 100vh;
    padding: 1.15rem 0 2.5rem;
    position: relative;
  }
  .st-key-landing_page::before {
    content: "";
    position: fixed; inset: 0; pointer-events: none;
    background:
      radial-gradient(circle at 8% 12%, rgba(99,102,241,.18), transparent 28%),
      radial-gradient(circle at 92% 78%, rgba(34,211,238,.10), transparent 26%),
      linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
    background-size: auto, auto, 48px 48px, 48px 48px;
    mask-image: linear-gradient(to bottom, black 0%, transparent 92%);
  }
  .land-nav {
    display:flex; align-items:center; justify-content:space-between;
    padding:.65rem .75rem; border:1px solid var(--line);
    border-radius:15px;
    background:rgba(14,18,28,.72);
    box-shadow:0 12px 34px rgba(0,0,0,.16), inset 0 1px rgba(255,255,255,.035);
    backdrop-filter:blur(14px);
    margin-bottom:3.1rem; position:relative; z-index:1;
  }
  .land-brand { display:flex; align-items:center; gap:.7rem; }
  .land-logo {
    width:38px; height:38px; border-radius:11px;
    display:flex; align-items:center; justify-content:center;
    background:linear-gradient(135deg,#818cf8,#4f46e5);
    color:#fff; font-size:1rem; font-weight:900;
    box-shadow:0 8px 24px rgba(79,70,229,.35);
  }
  .land-brand-copy strong { display:block; color:var(--tx); font-size:.95rem; letter-spacing:-.02em; }
  .land-brand-copy span { display:block; color:var(--mu); font-size:.67rem; margin-top:.05rem; }
  .land-local {
    display:inline-flex; align-items:center; gap:.42rem;
    color:var(--mu2); font-size:.72rem; font-weight:600;
    border:1px solid var(--line2); background:rgba(255,255,255,.035);
    border-radius:999px; padding:.38rem .72rem;
  }
  .land-local i {
    display:block; width:6px; height:6px; border-radius:50%;
    background:var(--ok); box-shadow:0 0 9px var(--ok);
  }
  .land-kicker {
    display:inline-flex; align-items:center; gap:.45rem;
    color:var(--acc3); font-size:.72rem; font-weight:700;
    text-transform:uppercase; letter-spacing:.12em;
    margin-bottom:1.15rem;
  }
  .land-kicker::before { content:""; width:22px; height:1px; background:var(--acc2); }
  .land-title {
    color:var(--tx); font-size:clamp(2.7rem,5vw,4.8rem); font-weight:800;
    line-height:1.02; letter-spacing:-.055em; max-width:650px;
    margin:0 0 1.25rem;
  }
  .land-title span {
    background:linear-gradient(120deg,#a5b4fc 10%,#67e8f9 90%);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-clip:text;
  }
  .land-sub {
    color:var(--mu2); font-size:1.03rem; line-height:1.75;
    max-width:560px; margin-bottom:1.35rem;
  }
  .land-points { display:flex; flex-wrap:wrap; gap:.55rem 1.1rem; margin:0 0 1.3rem; }
  .land-point { color:var(--mu2); font-size:.76rem; font-weight:550; }
  .land-point b { color:var(--ok); margin-right:.3rem; }
  .st-key-enter_chat button {
    min-height:3.25rem !important; border:0 !important; border-radius:13px !important;
    background:linear-gradient(135deg,#6d70f7,#4f46e5) !important;
    color:#fff !important; font-size:.96rem !important; font-weight:700 !important;
    box-shadow:0 12px 30px rgba(79,70,229,.32), inset 0 1px rgba(255,255,255,.18) !important;
    transition:transform .18s ease, box-shadow .18s ease !important;
  }
  .st-key-enter_chat button:hover {
    transform:translateY(-2px); box-shadow:0 16px 38px rgba(79,70,229,.45) !important;
  }
  .land-privacy { color:var(--mu); font-size:.68rem; margin-top:.65rem; }
  .land-preview {
    position:relative; padding:1rem; border-radius:24px;
    border:1px solid rgba(165,180,252,.18);
    background:linear-gradient(145deg,rgba(255,255,255,.07),rgba(255,255,255,.025));
    box-shadow:0 28px 80px rgba(0,0,0,.35), inset 0 1px rgba(255,255,255,.07);
    backdrop-filter:blur(18px); transform:rotate(1.2deg);
  }
  .land-preview::before {
    content:""; position:absolute; inset:-1px; border-radius:24px; pointer-events:none;
    background:linear-gradient(135deg,rgba(129,140,248,.22),transparent 42%);
    mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
    mask-composite:exclude; padding:1px;
  }
  .preview-head { display:flex; align-items:center; justify-content:space-between; padding:.25rem .2rem .9rem; }
  .preview-title { color:var(--tx); font-size:.78rem; font-weight:700; }
  .preview-status { color:var(--ok); font-size:.62rem; font-weight:650; }
  .preview-status::before { content:"●"; margin-right:.3rem; }
  .preview-body { border-radius:17px; background:rgba(5,8,15,.62); padding:1rem; min-height:330px; }
  .preview-user {
    width:78%; margin-left:auto; border-radius:15px 15px 4px 15px;
    background:linear-gradient(135deg,#5f63e9,#4540c5); color:#fff;
    padding:.75rem .9rem; font-size:.75rem; line-height:1.5;
  }
  .preview-ai { display:flex; gap:.55rem; margin-top:1rem; align-items:flex-start; }
  .preview-avatar {
    flex:none; width:26px; height:26px; border-radius:8px; display:flex;
    align-items:center; justify-content:center; background:var(--adim); color:var(--acc3);
    border:1px solid rgba(129,140,248,.22); font-size:.65rem;
  }
  .preview-answer {
    color:var(--mu2); border:1px solid var(--line); background:var(--s2);
    border-radius:4px 14px 14px 14px; padding:.75rem .85rem;
    font-size:.72rem; line-height:1.65;
  }
  .preview-answer strong { color:var(--tx); }
  .preview-source {
    display:flex; align-items:center; justify-content:space-between; margin-top:.75rem;
    border-top:1px solid var(--line); padding-top:.55rem; color:var(--mu); font-size:.61rem;
  }
  .preview-source b { color:var(--ok); font-weight:650; }
  .land-stats {
    display:grid; grid-template-columns:repeat(3,1fr); gap:.6rem;
    margin-top:1.35rem;
  }
  .land-stat {
    border:1px solid var(--line); background:rgba(255,255,255,.025);
    border-radius:12px; padding:.8rem .7rem;
  }
  .land-stat-n { color:var(--tx); font-size:1.15rem; font-weight:750; letter-spacing:-.03em; }
  .land-stat-l { color:var(--mu); font-size:.62rem; margin-top:.14rem; }
  .land-foot {
    text-align:center; color:var(--mu); font-size:.64rem;
    margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line);
  }
  @media (max-width: 760px) {
    .st-key-landing_page { padding-top:.65rem; }
    .land-nav { margin-bottom:2.2rem; }
    .land-title { font-size:2.65rem; }
    .land-preview { margin-top:1.6rem; transform:none; }
    .land-local { display:none; }
  }

  /* ═══════════════════════════════════
     CHAT EKRANI
  ═══════════════════════════════════ */

  /* Üst bar */
  .chat-topbar {
    display: flex; align-items: center;
    justify-content: space-between;
    padding: .55rem 0 .65rem;
    border-bottom: 1px solid var(--line2);
    margin-bottom: 1.2rem;
  }
  .chat-brand {
    display: flex; align-items: center; gap: .5rem;
  }
  .chat-brand-mark {
    width: 28px; height: 28px; border-radius: 8px;
    background: linear-gradient(135deg, var(--acc), #4338ca);
    display: flex; align-items: center; justify-content: center;
    font-size: .72rem; font-weight: 800; color: #fff;
    box-shadow: 0 2px 10px var(--glow);
  }
  .chat-brand-name {
    font-size: .9rem; font-weight: 700;
    color: var(--tx); letter-spacing: -.01em;
  }
  .chat-brand-ver {
    font-size: .65rem; color: var(--mu); margin-left: .1rem;
  }
  .chat-badges {
    display: flex; flex-wrap: wrap; align-items: center; gap: .3rem;
  }
  .cb {
    display: inline-flex; align-items: center; gap: .25rem;
    font-size: .68rem; font-weight: 500;
    padding: .18rem .52rem; border-radius: 99px;
    border: 1px solid var(--line2);
    background: var(--s2); color: var(--mu2);
    white-space: nowrap;
  }
  .cb.live {
    border-color: rgba(52,211,153,.32);
    background: var(--okd); color: var(--ok);
  }
  .cb.live::before {
    content: "";
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--ok); box-shadow: 0 0 5px var(--ok);
    display: inline-block;
    animation: pulse 2s ease-in-out infinite;
  }
  .cb.model {
    border-color: rgba(99,102,241,.35);
    background: var(--adim); color: var(--acc2);
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* Sohbet baloncukları */
  .lm-msg-user {
    display: flex; justify-content: flex-end; margin: 0 0 .9rem;
  }
  .lm-bubble-user {
    max-width: 72%;
    background: linear-gradient(135deg, #5a5eed, #3f3dca);
    color: #fff; border-radius: 20px 20px 5px 20px;
    padding: .75rem 1.1rem;
    font-size: .93rem; line-height: 1.65;
    box-shadow: 0 3px 16px rgba(99,102,241,.28);
    word-break: break-word;
  }
  .lm-msg-ai {
    display: flex; gap: .6rem; margin: 0 0 1rem; align-items: flex-start;
  }
  .lm-ava {
    flex: none; width: 28px; height: 28px; border-radius: 8px;
    background: linear-gradient(135deg, var(--acc), #4338ca);
    display: flex; align-items: center; justify-content: center;
    font-size: .65rem; font-weight: 800; color: #fff;
    box-shadow: 0 2px 8px var(--glow); margin-top: .15rem;
  }
  .lm-ai-body { flex: 1; min-width: 0; }
  .lm-ai-card {
    background: var(--s2); border: 1px solid var(--line2);
    border-radius: 5px 18px 18px 18px;
    padding: .8rem 1rem;
    box-shadow: 0 2px 10px rgba(0,0,0,.12);
  }
  .lm-answer {
    font-size: .94rem; line-height: 1.76; color: var(--tx);
    word-break: break-word;
  }
  .lm-answer.muted { color: var(--mu2); font-style: italic; }
  .lm-footer {
    display: flex; align-items: center; flex-wrap: wrap;
    gap: .38rem; margin-top: .42rem;
    font-size: .68rem; color: var(--mu);
  }
  .lm-dot { width:2px; height:2px; border-radius:50%; background:var(--mu); opacity:.45; }
  .lm-pill {
    font-size:.64rem; font-weight:600; letter-spacing:.03em;
    padding:.12rem .42rem; border-radius:4px;
  }
  .lm-pill.cached  { background:var(--warnd); color:var(--warn); border:1px solid rgba(251,191,36,.2); }
  .lm-pill.blocked { background:rgba(239,68,68,.09); color:#f87171; border:1px solid rgba(239,68,68,.18); }

  /* Yükleme animasyonu */
  .lm-thinking {
    display:flex; align-items:center; gap:.45rem;
    font-size:.82rem; color:var(--mu); padding:.2rem 0;
  }
  .lm-dots { display:flex; gap:3px; align-items:center; }
  .lm-dots span {
    width:5px; height:5px; border-radius:50%;
    background:var(--acc2); display:inline-block;
    animation:lm-dot .85s ease-in-out infinite;
  }
  .lm-dots span:nth-child(2){animation-delay:.17s}
  .lm-dots span:nth-child(3){animation-delay:.34s}
  @keyframes lm-dot{0%,80%,100%{transform:translateY(0);opacity:.3}40%{transform:translateY(-5px);opacity:1}}

  /* Boş ekran */
  .lm-empty {
    max-width:400px; margin:3rem auto 0; text-align:center;
    border:1px dashed rgba(99,102,241,.22); border-radius:18px;
    padding:2.5rem 1.6rem;
    background:radial-gradient(ellipse at 50% 0%,rgba(99,102,241,.05) 0%,transparent 65%);
  }
  .lm-empty-ico { font-size:1.8rem; display:block; margin-bottom:.8rem; }
  .lm-empty-t { font-size:.98rem; font-weight:650; color:var(--tx); margin-bottom:.42rem; }
  .lm-empty-b { font-size:.81rem; color:var(--mu); line-height:1.65; }

  /* Kaynak kartları */
  .src-lbl {
    font-size:.63rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:var(--mu); margin-bottom:.42rem;
  }
  .src-card {
    border:1px solid var(--line); border-radius:var(--rs);
    padding:.58rem .75rem; margin-bottom:.3rem; background:var(--s1);
  }
  .src-card.used { border-color:rgba(52,211,153,.22); background:rgba(52,211,153,.03); }
  .src-r1 { display:flex; justify-content:space-between; align-items:center; gap:.5rem; margin-bottom:.25rem; }
  .src-left { display:flex; align-items:center; gap:.42rem; min-width:0; }
  .src-rank {
    flex:none; width:16px; height:16px; border-radius:4px;
    background:var(--s3); display:flex; align-items:center; justify-content:center;
    font-size:.58rem; font-weight:700; color:var(--mu2);
  }
  .src-card.used .src-rank { background:rgba(52,211,153,.18); color:var(--ok); }
  .src-file { font-size:.76rem; font-weight:600; color:var(--tx); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .src-utag {
    flex:none; font-size:.59rem; font-weight:700;
    padding:.07rem .35rem; border-radius:4px;
    background:var(--okd); color:var(--ok); border:1px solid rgba(52,211,153,.18);
  }
  .src-score { font-size:.78rem; font-weight:700; font-family:ui-monospace,"SF Mono",Menlo,monospace; flex:none; }
  .src-score.hi  { color:var(--ok);   }
  .src-score.mid { color:var(--warn); }
  .src-score.lo  { color:var(--mu);   }
  .src-head { font-size:.7rem; color:var(--mu); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:.26rem; }
  .src-bar  { height:3px; border-radius:99px; background:rgba(255,255,255,.05); overflow:hidden; }
  .src-bar > i { display:block; height:100%; border-radius:99px; }
  .src-bar.hi  > i { background:linear-gradient(90deg,#34d399,#10b981); }
  .src-bar.mid > i { background:linear-gradient(90deg,#fbbf24,#f59e0b); }
  .src-bar.lo  > i { background:rgba(255,255,255,.14); }
  .src-sub { display:flex; gap:.7rem; margin-top:.24rem; font-size:.65rem; color:var(--mu); font-family:ui-monospace,"SF Mono",Menlo,monospace; }

  /* Sidebar */
  .sb-top {
    display:flex; align-items:center; gap:.58rem;
    padding:.85rem 0 .8rem; border-bottom:1px solid var(--line); margin-bottom:.9rem;
  }
  .sb-mark {
    width:26px; height:26px; border-radius:7px;
    background:linear-gradient(135deg,var(--acc),#4338ca);
    display:flex; align-items:center; justify-content:center;
    font-size:.68rem; font-weight:800; color:#fff;
    box-shadow:0 2px 8px var(--glow);
  }
  .sb-name { font-size:.9rem; font-weight:700; color:var(--tx); letter-spacing:-.01em; }
  .sb-ver  { font-size:.63rem; color:var(--mu); margin-top:.02rem; }
  .sb-sec  {
    font-size:.62rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
    color:var(--mu); margin:1rem 0 .48rem; padding-bottom:.26rem;
    border-bottom:1px solid var(--line);
  }
  .sb-row {
    display:flex; justify-content:space-between; align-items:center;
    font-size:.75rem; padding:.26rem 0;
    border-bottom:1px solid rgba(255,255,255,.03);
  }
  .sb-key { color:var(--mu2); }
  .sb-val { color:var(--tx); font-weight:500; font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:.71rem; }
  .sb-mc {
    border:1px solid var(--line2); border-radius:var(--rs);
    padding:.58rem .75rem; margin-bottom:.38rem; background:var(--s1);
  }
  .sb-mc.on { border-color:rgba(99,102,241,.38); background:var(--adim); }
  .sb-mc-n { font-size:.8rem; font-weight:650; color:var(--tx); margin-bottom:.13rem; }
  .sb-mc-d { font-size:.68rem; color:var(--mu); }
  .sb-mc-t {
    display:inline-flex; align-items:center; gap:.2rem;
    font-size:.64rem; font-weight:600;
    padding:.09rem .36rem; border-radius:4px; margin-top:.22rem;
  }
  .sb-mc-t.fast { background:var(--okd); color:var(--ok); border:1px solid rgba(52,211,153,.18); }
  .sb-mc-t.acc  { background:var(--adim); color:var(--acc2); border:1px solid rgba(99,102,241,.22); }
  .sb-src {
    display:flex; justify-content:space-between; align-items:center;
    font-size:.73rem; padding:.28rem 0;
    border-bottom:1px solid rgba(255,255,255,.03);
  }
  .sb-src-n { color:var(--mu2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:62%; }
  .sb-src-c {
    font-family:ui-monospace,Menlo,monospace; font-size:.69rem;
    color:var(--acc2); background:var(--adim);
    padding:.07rem .36rem; border-radius:4px; white-space:nowrap;
  }
  .sb-total { display:flex; justify-content:space-between; font-size:.76rem; font-weight:600; color:var(--tx); padding:.38rem 0 .1rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
#  CACHE
# ═══════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_pipeline(fast: bool):
    from src.pipeline import RagPipeline
    return RagPipeline.create(verbose=False, fast=fast)


@st.cache_data(show_spinner=False)
def db_stats():
    from src import database
    conn  = database.connect(config.DB_PATH)
    total = database.count_chunks(conn)
    rows  = [(r["source"], r["n"]) for r in database.stats_by_source(conn)]
    conn.close()
    return total, rows


# ═══════════════════════════════════════════════════════════
#  YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════

def score_cls(s: float) -> str:
    if s >= config.SIMILARITY_THRESHOLD:         return "hi"
    if s >= config.SIMILARITY_THRESHOLD * 0.72:  return "mid"
    return "lo"


def source_card(rank: int, s) -> str:
    used    = s.get("used_in_prompt")
    heading = (s.get("heading") or "başlıksız bölüm")[:78]
    pct     = max(3, min(100, round(s["score"] * 100)))
    cls     = score_cls(s["score"])
    badge   = '<span class="src-utag">✓ Kullanıldı</span>' if used else ""
    return (
        f'<div class="src-card {"used" if used else ""}">'
        f'  <div class="src-r1">'
        f'    <div class="src-left">'
        f'      <div class="src-rank">{rank}</div>'
        f'      <span class="src-file">{s["source"]}</span>'
        f'      {badge}'
        f'    </div>'
        f'    <span class="src-score {cls}">{s["score"]:.3f}</span>'
        f'  </div>'
        f'  <div class="src-head">{heading}</div>'
        f'  <div class="src-bar {cls}"><i style="width:{pct}%"></i></div>'
        f'  <div class="src-sub"><span>v {s["dense_score"]:.3f}</span><span>k {s["keyword_score"]:.3f}</span></div>'
        f'</div>'
    )


def render_sources(sources, container):
    used = [s for s in sources if s.get("used_in_prompt")]
    with container:
        if used:
            st.markdown(
                '<div class="src-lbl">Modele gönderilen kaynaklar</div>'
                + "".join(source_card(i, s) for i, s in enumerate(used, 1)),
                unsafe_allow_html=True,
            )


def footer_html(entry: dict) -> str:
    parts = []
    if entry.get("cached"):
        parts.append('<span class="lm-pill cached">Önbellekten</span>')
    elif not entry.get("found", True):
        parts.append('<span class="lm-pill blocked">Kapsam dışı</span>')
    if entry.get("elapsed"):
        parts.append(f'<span>{entry["elapsed"]:.1f} sn</span>')
    if not parts:
        return ""
    inner = '<span class="lm-dot"></span>'.join(parts)
    return f'<div class="lm-footer">{inner}</div>'


def msg_user(text: str) -> str:
    return (
        f'<div class="lm-msg-user">'
        f'<div class="lm-bubble-user">{text}</div>'
        f'</div>'
    )


def msg_ai(answer: str, found: bool = True, foot: str = "", cursor: bool = False) -> str:
    cur   = "▌" if cursor else ""
    muted = " muted" if not found else ""
    return (
        f'<div class="lm-msg-ai">'
        f'  <div class="lm-ava">◆</div>'
        f'  <div class="lm-ai-body">'
        f'    <div class="lm-ai-card">'
        f'      <div class="lm-answer{muted}">{answer}{cur}</div>'
        f'    </div>'
        f'    {foot}'
        f'  </div>'
        f'</div>'
    )


def thinking(label: str) -> str:
    return (
        f'<div class="lm-msg-ai">'
        f'  <div class="lm-ava">◆</div>'
        f'  <div class="lm-ai-body">'
        f'    <div class="lm-thinking">{label}'
        f'      <span class="lm-dots"><span></span><span></span><span></span></span>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def render_history(history, show_sources):
    for entry in history:
        st.markdown(msg_user(entry["question"]), unsafe_allow_html=True)
        st.markdown(
            msg_ai(entry["answer"], entry.get("found", True), footer_html(entry)),
            unsafe_allow_html=True,
        )
        if show_sources and entry.get("sources") and entry.get("found", True):
            with st.expander("Kaynaklar", expanded=False):
                render_sources(entry["sources"], st.container())


# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════

def sidebar_ui(total, per_source):
    with st.sidebar:
        st.markdown(
            '<div class="sb-top">'
            '  <div class="sb-mark">◆</div>'
            '  <div>'
            f'    <div class="sb-name">{APP_NAME}</div>'
            f'    <div class="sb-ver">{APP_VERSION} · Çevrim Dışı</div>'
            '  </div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sb-sec">Model</div>', unsafe_allow_html=True)
        quality = st.toggle(
            "Açıklamalı LLM yanıtı",
            value=False,
            help=("Açık: yerel LLM ile açıklamalı yanıt — daha yavaş\n"
                  "Kapalı: kaynaktaki en güçlü kanıt — hedef 1-3 sn"),
        )
        q_on = "" if quality else "on"
        p_on = "on" if quality else ""
        st.markdown(
            f'<div class="sb-mc {q_on}">'
            f'  <div class="sb-mc-n">Hızlı kaynak modu</div>'
            f'  <div class="sb-mc-d">LLM yok · doğrudan kanıt</div>'
            f'  <span class="sb-mc-t fast">⚡ ~15-35 sn/soru</span>'
            f'</div>'
            f'<div class="sb-mc {p_on}">'
            f'  <div class="sb-mc-n">phi-3.5-mini</div>'
            f'  <div class="sb-mc-d">3.8 B · daha kapsamlı cevap</div>'
            f'  <span class="sb-mc-t acc">◈ ~76 sn/soru</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sb-sec">Görünüm</div>', unsafe_allow_html=True)
        show_sources = st.toggle("Kaynak paneli", value=True)

        st.markdown('<div class="sb-sec">Bilgi Tabanı</div>', unsafe_allow_html=True)
        st.markdown(
            "".join(
                f'<div class="sb-src">'
                f'  <span class="sb-src-n">{n}</span>'
                f'  <span class="sb-src-c">{c}</span>'
                f'</div>'
                for n, c in per_source
            )
            + f'<div class="sb-total"><span>Toplam</span><span>{total} parça</span></div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sb-sec">Parametreler</div>', unsafe_allow_html=True)
        params = [
            ("Benzerlik eşiği", str(config.SIMILARITY_THRESHOLD)),
            ("Hibrit ağırlık",  f"v {config.HYBRID_ALPHA} / k {round(1-config.HYBRID_ALPHA,2)}"),
            ("Bağlam bütçesi",  f"{config.MAX_CONTEXT_CHARS} krk"),
            ("Aday sayısı",     str(config.TOP_K)),
        ]
        st.markdown(
            "".join(
                f'<div class="sb-row"><span class="sb-key">{k}</span>'
                f'<span class="sb-val">{v}</span></div>'
                for k, v in params
            ),
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        if st.button("🗑  Sohbeti temizle", use_container_width=True):
            st.session_state.history = []
            st.rerun()

        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if st.button("← Giriş ekranı", use_container_width=True):
            st.session_state.page = "landing"
            st.session_state.history = []
            st.rerun()

    return quality, show_sources


# ═══════════════════════════════════════════════════════════
#  LANDING EKRANI
# ═══════════════════════════════════════════════════════════

def page_landing(total, per_source):
    """Karşılama ekranı — ana eylem görünür ve tek tıkla sohbete geçer."""
    doc_count = len(per_source)

    with st.container(key="landing_page"):
        st.markdown(
            f"""
            <div class="land-nav">
              <div class="land-brand">
                <div class="land-logo">◆</div>
                <div class="land-brand-copy">
                  <strong>{APP_NAME}</strong>
                  <span>Yerel bilgi asistanı</span>
                </div>
              </div>
              <div class="land-local"><i></i> Sistem çevrim dışı çalışıyor</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        hero, preview = st.columns([1.12, .88], gap="large", vertical_alignment="center")

        with hero:
            st.markdown(
                """
                <div class="land-kicker">Notlarından doğru cevaba</div>
                <div class="land-title">Bilgin sende kalsın.<br><span>Cevabın saniyeler içinde gelsin.</span></div>
                <div class="land-sub">
                  Ders notlarını güvenli biçimde tarayan LocalMind, ilgili bölümleri bulur
                  ve yanıtını kaynaklarıyla birlikte üretir. İnternet gerekmez; verilerin
                  cihazından çıkmaz.
                </div>
                <div class="land-points">
                  <span class="land-point"><b>✓</b> Kaynaklı yanıtlar</span>
                  <span class="land-point"><b>✓</b> Yerel yapay zekâ</span>
                  <span class="land-point"><b>✓</b> Hibrit arama</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Sohbete başla  →",
                key="enter_chat",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.page = "chat"
                st.rerun()

            st.markdown(
                '<div class="land-privacy">🔒 Soruların ve belgelerin yalnızca bu cihazda işlenir.</div>',
                unsafe_allow_html=True,
            )

        with preview:
            st.markdown(
                f"""
                <div class="land-preview">
                  <div class="preview-head">
                    <span class="preview-title">Canlı yanıt önizlemesi</span>
                    <span class="preview-status">Bilgi tabanı hazır</span>
                  </div>
                  <div class="preview-body">
                    <div class="preview-user">Second-chance algoritmasının diğer adı nedir?</div>
                    <div class="preview-ai">
                      <div class="preview-avatar">◆</div>
                      <div class="preview-answer">
                        Second-chance algoritması, <strong>Clock (saat) algoritması</strong>
                        olarak da bilinir. Sayfalar dairesel bir listede tutulur ve referans
                        bitine göre ikinci bir şans verilir.
                        <div class="preview-source">
                          <span>işletimsistemi.txt</span><b>✓ Kaynak kullanıldı</b>
                        </div>
                      </div>
                    </div>
                    <div class="land-stats">
                      <div class="land-stat">
                        <div class="land-stat-n">{total}</div>
                        <div class="land-stat-l">İndeksli parça</div>
                      </div>
                      <div class="land-stat">
                        <div class="land-stat-n">{doc_count}</div>
                        <div class="land-stat-l">Kaynak belge</div>
                      </div>
                      <div class="land-stat">
                        <div class="land-stat-n">%100</div>
                        <div class="land-stat-l">Yerel çalışma</div>
                      </div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div class="land-foot">{APP_NAME} {APP_VERSION} · Microsoft Foundry Local ile çalışır</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════
#  CHAT EKRANI
# ═══════════════════════════════════════════════════════════

def page_chat(total, per_source):
    """Sohbet ekranı."""
    quality, show_sources = sidebar_ui(total, per_source)
    model_lbl = "phi-3.5-mini" if quality else "Hızlı kaynak"

    # ── Üst bar ──
    left_col, right_col = st.columns([5, 1])

    with left_col:
        st.markdown(
            f'<div class="chat-topbar">'
            f'  <div class="chat-badges">'
            f'    <span class="cb live"><b>{total}</b>&thinsp;parça</span>'
            f'    <span class="cb"><b>{len(per_source)}</b>&thinsp;belge</span>'
            f'    <span class="cb model">{model_lbl}</span>'
            f'    <span class="cb">🔒 Çevrim dışı</span>'
            f'    <span class="cb">🛡 Uydurma korumalı</span>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with right_col:
        st.markdown(
            '<div class="chat-topbar" style="justify-content:flex-end">'
            '  <div class="chat-brand">'
            '    <div class="chat-brand-mark">◆</div>'
            f'   <span class="chat-brand-name">{APP_NAME}</span>'
            f'   <span class="chat-brand-ver">{APP_VERSION}</span>'
            '  </div>'
            '</div>',
            unsafe_allow_html=True,
        )

    if total == 0:
        st.error("Bilgi tabanı boş. Terminalde `python main.py ingest` çalıştır.")
        return

    with st.spinner("Modeller yükleniyor…"):
        pipeline = load_pipeline(fast=not quality)

    if "history" not in st.session_state:
        st.session_state.history = []

    if not st.session_state.history:
        st.markdown(
            '<div class="lm-empty">'
            '  <span class="lm-empty-ico">◆</span>'
            '  <div class="lm-empty-t">Notlarına soru sor</div>'
            '  <div class="lm-empty-b">'
            "    Cevaplar yalnızca indekslenmiş ders notlarından üretilir.<br>"
            "    Kapsam dışı sorular nazikçe reddedilir."
            "  </div>"
            "</div>",
            unsafe_allow_html=True,
        )

    render_history(st.session_state.history, show_sources)

    question = st.chat_input("Notlarına bir soru sor…")
    if not question:
        return

    st.markdown(msg_user(question), unsafe_allow_html=True)

    status   = st.empty()
    src_area = st.container()
    ans_area = st.empty()

    status.markdown(thinking("Belgeler aranıyor"), unsafe_allow_html=True)

    started = time.perf_counter()
    pieces  = []

    def on_sources(sources):
        used_n = sum(1 for s in sources if s.get("used_in_prompt"))
        status.markdown(
            thinking(f"{used_n} kaynak seçildi · yazılıyor"),
            unsafe_allow_html=True,
        )
        if show_sources:
            render_sources(sources, src_area)

    def on_text(piece):
        pieces.append(piece)
        ans_area.markdown(
            msg_ai("".join(pieces), True, cursor=True),
            unsafe_allow_html=True,
        )

    try:
        result = pipeline.answer_query(question, on_text=on_text, on_sources=on_sources)
    except Exception as exc:
        status.empty()
        st.error(f"Cevap üretilemedi — {exc}\n\nSoruyu tekrar sormayı dene.")
        return

    status.empty()
    elapsed = time.perf_counter() - started
    entry = {
        "question": question,
        "answer":   result["answer"],
        "sources":  result["sources"],
        "found":    result["found"],
        "elapsed":  elapsed,
        "cached":   result.get("cached", False),
    }
    ans_area.markdown(
        msg_ai(result["answer"], result["found"], footer_html(entry)),
        unsafe_allow_html=True,
    )
    st.session_state.history.append(entry)


# ═══════════════════════════════════════════════════════════
#  ROUTER
# ═══════════════════════════════════════════════════════════

def main():
    if "page" not in st.session_state:
        st.session_state.page = "landing"

    total, per_source = db_stats()

    if st.session_state.page == "landing":
        page_landing(total, per_source)
    else:
        page_chat(total, per_source)


if __name__ == "__main__":
    main()
