"""LocalMind - yerel RAG soru-cevap asistanı (Streamlit arayüzü).

ÇALIŞTIRMA
    streamlit run app.py

TASARIM KARARLARI

1. MODELLER BİR KEZ YÜKLENİR
   Streamlit her etkileşimde script'i baştan çalıştırır. Model yükleme
   8-15 saniye sürdüğü için @st.cache_resource ile önbelleğe alınır.

2. VARSAYILAN: HIZLI MODEL
   Ölçüm (60 soruluk test seti):
       phi-3.5-mini  -> medyan 76 sn
       qwen2.5-1.5b  -> medyan ~35 sn
   Etkileşimli kullanımda 76 saniye çok uzun. Arayüz hızlı modelle
   açılıyor; kalite gerektiğinde yan panelden "Yüksek doğruluk" açılabilir.

3. BEKLEME SÜRESİ GÖRÜNÜR OLMALI
   Üç aşamalı geri bildirim: aranıyor -> kaynaklar bulundu -> cevap akıyor.
   Arama ~2 saniye sürdüğü için kullanıcı ilk saniyelerde bir şey görür.

4. ŞEFFAFLIK GÖRSEL OLMALI
   Her kaynağın skoru renkli çubukla gösterilir; "model bunu nereden buldu?"
   sorusu tek bakışta cevaplanır.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

import config

APP_NAME = "LocalMind"
APP_TAGLINE = "Ders notlarınla konuşan, tamamen çevrim dışı asistan"

st.set_page_config(
    page_title=f"{APP_NAME} — Yerel RAG Asistanı",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Görsel stil ------------------------------------------------------------
# Koyu tema .streamlit/config.toml içinde temel alınıyor; buradaki CSS
# onun üzerine ince ayar yapıyor. Renkler tek bir vurgu tonu (indigo)
# etrafında toplandı, gri tonları yarı saydam katmanlarla üretiliyor.
CSS = """
<style>
  :root {
    --lm-accent: #7c83ff;
    --lm-accent-dim: rgba(124,131,255,.16);
    --lm-line: rgba(255,255,255,.09);
    --lm-surface: rgba(255,255,255,.032);
    --lm-surface-2: rgba(255,255,255,.055);
    --lm-muted: rgba(230,237,243,.55);
    --lm-ok: #3fb950;
    --lm-warn: #d29922;
  }

  /* Streamlit'in varsayılan üst boşluğunu daralt */
  .block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px; }
  #MainMenu, footer { visibility: hidden; }

  /* ---------- Uygulama başlığı ---------- */
  .lm-head {
    display: flex; align-items: center; gap: .85rem;
    padding-bottom: .9rem; margin-bottom: .3rem;
    border-bottom: 1px solid var(--lm-line);
  }
  .lm-mark {
    width: 38px; height: 38px; border-radius: 10px; flex: none;
    background: linear-gradient(135deg, var(--lm-accent), #4b53d6);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; font-weight: 700; color: #fff;
    box-shadow: 0 3px 14px rgba(124,131,255,.32);
  }
  .lm-title { font-size: 1.32rem; font-weight: 650; letter-spacing: -.015em; line-height: 1.2; }
  .lm-sub   { font-size: .84rem; color: var(--lm-muted); margin-top: .12rem; }

  /* ---------- Durum şeridi ---------- */
  .lm-status { display: flex; flex-wrap: wrap; gap: .4rem; margin: .85rem 0 1.5rem; }
  .lm-chip {
    font-size: .735rem; padding: .24rem .62rem; border-radius: 7px;
    background: var(--lm-surface); border: 1px solid var(--lm-line);
    color: var(--lm-muted); white-space: nowrap;
  }
  .lm-chip b { color: #e6edf3; font-weight: 600; }
  .lm-chip.live { border-color: rgba(63,185,80,.34); }
  .lm-chip.live::before {
    content: "●"; color: var(--lm-ok); margin-right: .35rem; font-size: .6rem;
    position: relative; top: -1px;
  }
  .lm-chip.model { border-color: rgba(124,131,255,.34); background: var(--lm-accent-dim); }

  /* ---------- Cevap ---------- */
  .lm-answer {
    font-size: 1.03rem; line-height: 1.72;
    padding: .1rem 0 .1rem 1rem;
    border-left: 2px solid var(--lm-accent);
  }
  .lm-meta {
    font-size: .755rem; color: var(--lm-muted);
    margin-top: .7rem; display: flex; gap: .5rem; align-items: center;
  }

  /* ---------- Kaynak kartları ---------- */
  .lm-src {
    border: 1px solid var(--lm-line); border-radius: 10px;
    padding: .6rem .72rem; margin-bottom: .45rem;
    background: var(--lm-surface);
  }
  .lm-src.used { border-color: rgba(63,185,80,.30); background: rgba(63,185,80,.055); }
  .lm-src-top {
    display: flex; justify-content: space-between; align-items: baseline; gap: .6rem;
  }
  .lm-src-name { font-size: .8rem; font-weight: 600; }
  .lm-src-num {
    display: inline-block; min-width: 1.15rem; text-align: center;
    font-size: .68rem; color: var(--lm-muted); margin-right: .35rem;
  }
  .lm-src-score {
    font-size: .78rem; font-variant-numeric: tabular-nums;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
  }
  .lm-src-head { font-size: .735rem; color: var(--lm-muted); margin: .3rem 0 .45rem; }
  .lm-bar { height: 5px; border-radius: 999px; background: rgba(255,255,255,.07); overflow: hidden; }
  .lm-bar > i { display: block; height: 100%; border-radius: 999px; }
  .lm-bar.hi  > i { background: linear-gradient(90deg,#3fb950,#2ea043); }
  .lm-bar.mid > i { background: linear-gradient(90deg,#d29922,#bb8009); }
  .lm-bar.lo  > i { background: rgba(255,255,255,.22); }
  .lm-sub {
    display: flex; gap: .85rem; margin-top: .38rem;
    font-size: .69rem; color: var(--lm-muted);
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
  }

  /* ---------- Yan panel ---------- */
  .lm-label {
    font-size: .68rem; text-transform: uppercase; letter-spacing: .09em;
    color: var(--lm-muted); margin: .2rem 0 .5rem;
  }
  .lm-row {
    display: flex; justify-content: space-between; font-size: .78rem;
    padding: .22rem 0; border-bottom: 1px solid rgba(255,255,255,.05);
  }
  .lm-row span:last-child {
    color: var(--lm-muted); font-variant-numeric: tabular-nums;
    font-family: ui-monospace, Menlo, monospace;
  }

  /* Boş durum */
  .lm-empty {
    border: 1px dashed var(--lm-line); border-radius: 12px;
    padding: 2.2rem 1.5rem; text-align: center; color: var(--lm-muted);
    font-size: .88rem; line-height: 1.7;
  }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_pipeline(fast: bool):
    """Boru hattını bir kez kurar ve önbelleğe alır."""
    from src.pipeline import RagPipeline

    return RagPipeline.create(verbose=False, fast=fast)


@st.cache_data(show_spinner=False)
def db_stats():
    """Veri tabanı istatistikleri."""
    from src import database

    conn = database.connect(config.DB_PATH)
    total = database.count_chunks(conn)
    rows = [(r["source"], r["n"]) for r in database.stats_by_source(conn)]
    conn.close()
    return total, rows


def score_class(score: float) -> str:
    """Skoru renk sınıfına çevirir: eşik üstü yeşil, yakını sarı, altı gri."""
    if score >= config.SIMILARITY_THRESHOLD:
        return "hi"
    if score >= config.SIMILARITY_THRESHOLD * 0.7:
        return "mid"
    return "lo"


def source_html(rank: int, s) -> str:
    """Tek kaynak kartı: sıra, dosya, skor çubuğu, alt skorlar."""
    used = s.get("used_in_prompt")
    heading = s.get("heading") or "başlıksız bölüm"
    if len(heading) > 88:
        heading = heading[:86] + "…"
    pct = max(3, min(100, round(s["score"] * 100)))
    return (
        f'<div class="lm-src {"used" if used else ""}">'
        f'  <div class="lm-src-top">'
        f'    <span class="lm-src-name"><span class="lm-src-num">{rank}</span>{s["source"]}</span>'
        f'    <span class="lm-src-score">{s["score"]:.3f}</span>'
        f"  </div>"
        f'  <div class="lm-src-head">{heading}</div>'
        f'  <div class="lm-bar {score_class(s["score"])}"><i style="width:{pct}%"></i></div>'
        f'  <div class="lm-sub"><span>vektör {s["dense_score"]:.3f}</span>'
        f'<span>kelime {s["keyword_score"]:.3f}</span></div>'
        f"</div>"
    )


def render_sources(sources, container):
    """Kaynakları 'gönderilen' ve 'diğer adaylar' diye ayırıp gösterir."""
    used = [s for s in sources if s.get("used_in_prompt")]
    other = [s for s in sources if not s.get("used_in_prompt")]

    with container:
        if used:
            st.markdown(
                f'<div class="lm-label">Modele gönderilen · {len(used)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                "".join(source_html(i, s) for i, s in enumerate(used, 1)),
                unsafe_allow_html=True,
            )
        if other:
            with st.expander(f"Bulunan diğer {len(other)} aday (bütçeye sığmadı)"):
                st.markdown(
                    "".join(
                        source_html(i, s)
                        for i, s in enumerate(other, len(used) + 1)
                    ),
                    unsafe_allow_html=True,
                )


def sidebar(total, per_source):
    """Yan panel: model seçimi, bilgi tabanı, ayarlar."""
    with st.sidebar:
        st.markdown('<div class="lm-label">Model</div>', unsafe_allow_html=True)
        quality = st.toggle(
            "Yüksek doğruluk",
            value=False,
            help="Açık: phi-3.5-mini (3.8B) — daha doğru, medyan ~76 sn.\n"
                 "Kapalı: qwen2.5-1.5b — hızlı, medyan ~15-35 sn, "
                 "ama bazı soruları yanlış cevaplıyor.",
        )
        if quality:
            st.caption("**phi-3.5-mini** · ~76 sn · daha doğru")
        else:
            st.caption("**qwen2.5-1.5b** · ~15-35 sn · doğruluk daha düşük")

        st.markdown('<div class="lm-label">Görünüm</div>', unsafe_allow_html=True)
        show_sources = st.toggle("Kaynakları göster", value=True)

        st.markdown(
            '<div class="lm-label" style="margin-top:1rem">Bilgi tabanı</div>',
            unsafe_allow_html=True,
        )
        rows = "".join(
            f'<div class="lm-row"><span>{n}</span><span>{c}</span></div>'
            for n, c in per_source
        )
        st.markdown(
            rows
            + f'<div class="lm-row" style="border:none;margin-top:.3rem">'
              f'<span><b>Toplam</b></span><span><b>{total}</b></span></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="lm-label" style="margin-top:1rem">Parametreler</div>',
            unsafe_allow_html=True,
        )
        params = [
            ("Parça boyutu", f"{config.CHUNK_SIZE} kelime"),
            ("Benzerlik eşiği", f"{config.SIMILARITY_THRESHOLD}"),
            ("Bağlam bütçesi", f"{config.MAX_CONTEXT_CHARS} krk"),
            ("Hibrit ağırlık", f"{config.HYBRID_ALPHA} / {round(1-config.HYBRID_ALPHA,2)}"),
            ("Aday sayısı", f"{config.TOP_K}"),
        ]
        st.markdown(
            "".join(
                f'<div class="lm-row"><span>{k}</span><span>{v}</span></div>'
                for k, v in params
            ),
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        if st.button("Sohbeti temizle", use_container_width=True):
            st.session_state.history = []
            st.rerun()

    return quality, show_sources


def main():
    total, per_source = db_stats()
    quality, show_sources = sidebar(total, per_source)

    st.markdown(
        f"""
        <div class="lm-head">
          <div class="lm-mark">◆</div>
          <div>
            <div class="lm-title">{APP_NAME}</div>
            <div class="lm-sub">{APP_TAGLINE}</div>
          </div>
        </div>
        <div class="lm-status">
          <span class="lm-chip live"><b>{total}</b>&nbsp;parça indeksli</span>
          <span class="lm-chip"><b>{len(per_source)}</b>&nbsp;belge</span>
          <span class="lm-chip model">{'phi-3.5-mini' if quality else 'qwen2.5-1.5b'}</span>
          <span class="lm-chip">çevrim dışı</span>
          <span class="lm-chip">kaynak gösterimli</span>
          <span class="lm-chip">uydurma koruması</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if total == 0:
        st.error("Bilgi tabanı boş. Terminalde `python main.py ingest` çalıştır.")
        return

    with st.spinner("Modeller belleğe yükleniyor…"):
        pipeline = load_pipeline(quality)

    if "history" not in st.session_state:
        st.session_state.history = []

    if not st.session_state.history:
        st.markdown(
            '<div class="lm-empty">Ders notlarına bir soru sor.<br>'
            "Cevap yalnızca indekslenmiş belgelerden üretilir; "
            "kaynak dışı sorular reddedilir.</div>",
            unsafe_allow_html=True,
        )

    for entry in st.session_state.history:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant"):
            st.markdown(
                f'<div class="lm-answer">{entry["answer"]}</div>'
                f'<div class="lm-meta">{entry["meta"]}</div>',
                unsafe_allow_html=True,
            )
            if show_sources and entry.get("sources"):
                with st.expander("Kaynaklar"):
                    render_sources(entry["sources"], st.container())

    question = st.chat_input("Sorunu yaz…")
    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        status = st.empty()
        sources_area = st.container()
        answer_area = st.empty()
        meta_area = st.empty()

        status.markdown(
            '<div class="lm-meta">Belgeler aranıyor…</div>', unsafe_allow_html=True
        )
        started = time.perf_counter()
        pieces = []

        def on_sources(sources):
            used = sum(1 for s in sources if s.get("used_in_prompt"))
            if show_sources:
                render_sources(sources, sources_area)
            status.markdown(
                f'<div class="lm-meta">{used} kaynak seçildi · cevap üretiliyor…</div>',
                unsafe_allow_html=True,
            )

        def on_text(piece):
            pieces.append(piece)
            answer_area.markdown(
                f'<div class="lm-answer">{"".join(pieces)}▌</div>',
                unsafe_allow_html=True,
            )

        try:
            result = pipeline.answer_query(
                question, on_text=on_text, on_sources=on_sources
            )
        except Exception as exc:
            status.empty()
            st.error(
                f"Cevap üretilemedi — {exc}\n\n"
                "Geçici bir hata olabilir, soruyu tekrar sormayı dene."
            )
            return

        status.empty()
        answer_area.markdown(
            f'<div class="lm-answer">{result["answer"]}</div>', unsafe_allow_html=True
        )

        elapsed = time.perf_counter() - started
        if result.get("cached"):
            meta = "Önbellekten — anında"
        elif not result["found"]:
            meta = f"Eşik koruması devrede — model çalıştırılmadı · {elapsed:.1f} sn"
        else:
            meta = f"{elapsed:.1f} saniye"
        meta_area.markdown(f'<div class="lm-meta">{meta}</div>', unsafe_allow_html=True)

    st.session_state.history.append(
        {
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "meta": meta,
        }
    )


if __name__ == "__main__":
    main()
