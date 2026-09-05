"""Fonksiyonel test koşucusu (PDF planı, Faz 3 / 5. Hafta).

İKİ MOD

  Hızlı mod (--retrieval):
      Sadece ARAMA katmanını test eder. Sohbet modeli hiç yüklenmez.
      Kontrol: doğru belge ilk sıralara geldi mi? Alakasız soru eşiğin
      altında kaldı mı? Soru başına ~2 saniye.

  Tam mod (varsayılan):
      Cevap üretimini de test eder. Kontrol: cevapta beklenen anahtar
      kelime geçiyor mu? Soru başına ~40 saniye (CPU'da yerel model).

Neden iki mod? Arama hatası ile üretim hatası farklı şeylerdir. Doğru chunk
bulunduğu hâlde model yanlış cevap veriyorsa sorun prompt'ta veya modelde;
doğru chunk hiç bulunamıyorsa sorun chunk'lama veya aramada. Ayrı ölçünce
hangisini düzelteceğini biliyorsun.

KULLANIM
    python tests/test_rag.py --retrieval     hızlı, sadece arama
    python tests/test_rag.py                 tam, cevap üretimi dahil
    python tests/test_rag.py --limit 3       ilk 3 soruyla dene
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from test_questions import ANSWERABLE, EDGE_CASES, UNANSWERABLE

PASS = "GECTI"
FAIL = "KALDI"


def normalize(text: str) -> str:
    """Karşılaştırma için metni sadeleştirir (küçük harf, aksan duyarsız)."""
    text = (text or "").translate(str.maketrans("IİĞÜŞÖÇ", "iiğüşöç")).lower()
    return unicodedata.normalize("NFC", text)


# Türkçe ek/yumuşama toleransı için karşılaştırılacak harf sayısı
_TR_STEM_LEN = 5


def contains_any(text: str, keywords) -> bool:
    """Metinde anahtar kelimelerden en az biri geçiyor mu?

    İKİ AYRI HATA BU FONKSİYONDA YAŞANDI, ikisi de burada çözülüyor:

    1) DÜZ ALT DİZGE ARAMASI YANLIŞ CEVABI DOĞRU SAYDI
           soru  : "TTL alanı kaç bittir?"   (doğru cevap: 8 bit)
           cevap : "128 oktettir."           (YANLIŞ)
           aranan: "8"
       "8" dizgisi "128" içinde geçtiği için test GEÇTİ sandı.
       -> Sayı içeren veya kısa anahtar kelimelerde \\b sınırı kullanıyoruz.

    2) KELİME SINIRI DOĞRU CEVABI YANLIŞ SAYDI
           cevap : "...kullanıcı programının BELLEĞE erişmesini KORUMAK için"
           aranan: "bellek", "koruma"
       Türkçe eklemeli ve ünsüz yumuşamalı bir dil:
           bellek -> belleğe   (k -> ğ)
           koruma -> korumak   (ek)
       \\b eşleşmesi ikisini de kaçırdı, cevap doğru olduğu hâlde test KALDI.
       -> Uzun ve harf içeren anahtar kelimelerde ilk 5 harfe göre
          ön-ek eşleşmesi yapıyoruz ("belle" hem "bellek" hem "belleğe"yi,
          "korum" hem "koruma" hem "korumak"ı yakalar).

    Aynı ön-ek mantığını retriever'da da kullanıyoruz (bkz. src/retriever.py).
    """
    haystack = normalize(text)
    for keyword in keywords:
        key = normalize(keyword)

        # Sayı içeren veya kısa anahtarlar: tam kelime eşleşmesi (katı)
        if any(ch.isdigit() for ch in key) or len(key) < _TR_STEM_LEN:
            if re.search(r"\b" + re.escape(key) + r"\b", haystack):
                return True
            continue

        # Uzun anahtarlar: kelime başından ilk 5 harf eşleşsin (Türkçe ekleri)
        stem = key[:_TR_STEM_LEN]
        if re.search(r"\b" + re.escape(stem), haystack):
            return True
    return False


class Results:
    """Test sonuçlarını toplar ve özet yazdırır."""

    def __init__(self):
        self.rows = []

    def add(self, category, question, ok, detail=""):
        self.rows.append((category, question, ok, detail))
        status = PASS if ok else FAIL
        print(f"  [{status}] {question[:58]:<58} {detail}")

    def summary(self) -> int:
        print("\n" + "=" * 78)
        print("OZET")
        print("=" * 78)
        total_ok = 0
        for category in dict.fromkeys(r[0] for r in self.rows):
            rows = [r for r in self.rows if r[0] == category]
            ok = sum(1 for r in rows if r[2])
            total_ok += ok
            print(f"  {category:<34} {ok}/{len(rows)}")
        total = len(self.rows)
        print(f"  {'TOPLAM':<34} {total_ok}/{total}")

        failed = [r for r in self.rows if not r[2]]
        if failed:
            print("\nBASARISIZ TESTLER:")
            for _, q, _, detail in failed:
                print(f"  - {q[:60]}\n      {detail}")
        return 0 if not failed else 1


# --- Hızlı mod: sadece arama -----------------------------------------------


def run_retrieval_tests(limit=None) -> int:
    from src import database, foundry_client, generator
    from src.retriever import Retriever

    print("=" * 78)
    print("ARAMA TESTLERI (sohbet modeli yuklenmez)")
    print("=" * 78)

    conn = database.connect(config.DB_PATH)
    manager = foundry_client.get_manager(config.APP_NAME, config.CACHE_DIR)
    embedding_model = foundry_client.EmbeddingModel(
        manager, config.EMBEDDING_MODEL, config.DEVICE_PREFERENCE, verbose=False
    )
    retriever = Retriever.from_database(
        conn, embedding_model, config.QUERY_INSTRUCTION
    )

    results = Results()

    print("\n1) Dogru BELGE bulunuyor mu?")
    for case in ANSWERABLE[:limit]:
        hits = retriever.search(case["question"], config.TOP_K, config.HYBRID_ALPHA)
        top = hits[0]
        sources = [h["source"] for h in hits]
        ok = case["expect_source"] in sources and top["score"] >= config.SIMILARITY_THRESHOLD
        rank = sources.index(case["expect_source"]) + 1 if case["expect_source"] in sources else 0
        detail = f"skor {top['score']:.3f}, dogru belge sira {rank or '-'}"
        results.add("Dogru belge", case["question"], ok, detail)

    # EN ONEMLI TEST BU.
    # "Dogru belge geldi mi" yetmiyor: dogru belgenin YANLIS PARCASI gelebiliyor,
    # ya da dogru parca bulunup karakter butcesinde elenebiliyor. Ikisinde de
    # model dogru cevap veremez cunku bilgi onune hic konmamis olur.
    # Bu testi eklemeden once 12/12 geciyorduk ama cevaplar yanlisti.
    print("\n2) Cevabin METNI baglama giriyor mu? (butce kirpmasindan SONRA)")
    for case in ANSWERABLE[:limit]:
        # expect_context bir LISTE: ayni bilgi belgede birden fazla ifadeyle
        # gecebilir, herhangi biri baglamda varsa yeterli.
        wanted = [normalize(w) for w in case["expect_context"]]
        hits = retriever.search(case["question"], config.TOP_K, config.HYBRID_ALPHA)
        selected = generator.select_within_budget(hits, config.MAX_CONTEXT_CHARS)

        in_results = any(w in normalize(h["text"]) for h in hits for w in wanted)
        in_context = any(w in normalize(s["text"]) for s in selected for w in wanted)

        if in_context:
            detail = f"{len(selected)} chunk secildi"
        elif in_results:
            detail = f"BULUNDU ama butcede ELENDI ({len(selected)} chunk secildi)"
        else:
            detail = f"ilk {config.TOP_K} sonucta HIC YOK"
        results.add("Baglam isabeti", case["question"], in_context, detail)

    print("\n3) Cevabi belgelerde OLMAYAN sorular - esigin ALTINDA kalmali")
    for case in UNANSWERABLE[:limit]:
        hits = retriever.search(case["question"], config.TOP_K, config.HYBRID_ALPHA)
        top_score = hits[0]["score"]
        ok = top_score < config.SIMILARITY_THRESHOLD
        detail = f"skor {top_score:.3f} (esik {config.SIMILARITY_THRESHOLD})"
        results.add("Esik korumasi", case["question"], ok, detail)

    embedding_model.close()
    conn.close()
    return results.summary()


# --- Tam mod: cevap üretimi dahil -------------------------------------------


def run_full_tests(limit=None, fast=False) -> int:
    from src.pipeline import RagPipeline

    print("=" * 78)
    print("TAM TESTLER (cevap uretimi dahil - yavas)")
    print("=" * 78)

    pipeline = RagPipeline.create(verbose=True, fast=fast)
    results = Results()

    def ask(question):
        """Soruyu sorar; hata olursa testi ÖLDÜRMEZ, hatayı sonuç olarak döner.

        NEDEN GEREKLİ?
        Foundry Local ara sıra geçici "Operation was cancelled" hatası
        veriyor. Önceden tek bir soru patlayınca tüm koşu çöküyordu ve
        30 DAKİKALIK test sonucu kayboluyordu. Artık o soru "KALDI"
        sayılıyor, diğerleri koşmaya devam ediyor.
        """
        try:
            return pipeline.answer_query(question), None
        except Exception as exc:
            return None, str(exc).splitlines()[0][:70]

    try:
        print("\n1) Cevabi belgelerde OLAN sorular - dogru cevap gelmeli")
        for case in ANSWERABLE[:limit]:
            out, error = ask(case["question"])
            if error:
                results.add("Tam: belgede olan", case["question"], False,
                            f"HATA: {error}")
                continue
            ok = out["found"] and contains_any(out["answer"], case["expect_keywords"])
            detail = f"{out['elapsed']:.0f}sn | {out['answer'][:60]}"
            results.add("Tam: belgede olan", case["question"], ok, detail)

        print("\n2) Cevabi belgelerde OLMAYAN sorular - 'bilmiyorum' demeli")
        for case in UNANSWERABLE[:limit]:
            out, error = ask(case["question"])
            if error:
                results.add("Tam: belgede olmayan", case["question"], False,
                            f"HATA: {error}")
                continue
            ok = not out["found"] or normalize(config.FALLBACK_ANSWER) in normalize(
                out["answer"]
            )
            detail = f"{out['elapsed']:.0f}sn | {out['answer'][:60]}"
            results.add("Tam: belgede olmayan", case["question"], ok, detail)

        print("\n3) Uc durumlar - cokmemeli")
        for case in EDGE_CASES:
            try:
                out = pipeline.answer_query(case["question"])
                ok = bool(out["answer"])
                detail = f"{case['note']}: {out['answer'][:50]}"
            except Exception as exc:
                ok = False
                detail = f"{case['note']}: ISTISNA {exc}"
            results.add("Uc durumlar", case["note"], ok, detail)
    finally:
        pipeline.close()

    return results.summary()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RAG asistani fonksiyonel testleri")
    parser.add_argument(
        "--retrieval", action="store_true",
        help="Sadece arama katmanini test et (hizli, sohbet modeli yuklenmez)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Ilk N soruyla sinirla")
    parser.add_argument(
        "--fast", action="store_true",
        help="Hizli model kullan (qwen2.5-1.5b, ~35 sn/soru yerine ~90 sn)",
    )
    args = parser.parse_args(argv)

    if args.retrieval:
        return run_retrieval_tests(args.limit)
    return run_full_tests(args.limit, fast=args.fast)


if __name__ == "__main__":
    sys.exit(main())
