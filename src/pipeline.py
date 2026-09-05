"""RAG boru hattı: getirme + üretim adımlarını birleştirir.

Bu dosya PDF planındaki 4. Hafta hedefi olan answer_query() fonksiyonunu
barındırır. Akış:

    soru
      -> Retriever.search()      hibrit arama, en iyi K chunk
      -> eşik kontrolü           hiçbiri yeterince alakalı değilse "bilmiyorum"
      -> order_for_context()     chunk'ları belge sırasına diz
      -> generate_answer()       yerel LLM cevabı yazar
      -> sonuç sözlüğü

EŞİK KONTROLÜ NEDEN MODELDEN ÖNCE?
Alakasız bir soru geldiğinde modele hiç gitmeden geri dönüyoruz. İki faydası:
  - Hız: gereksiz LLM çağrısı yapılmıyor (CPU'da bu 2-5 saniye).
  - Güvenlik: model alakasız bağlam görünce uydurmaya meyilli. Hiç görmesin.
"""

import time

import config
from src import database, foundry_client, generator
from src.retriever import Retriever, order_for_context


class RagPipeline:
    """Yüklenmiş modelleri ve indeksi tutan çalışan asistan."""

    def __init__(self, conn, retriever, chat_model, embedding_model, low_memory=False):
        self.conn = conn
        self.retriever = retriever
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.low_memory = low_memory

        # Aynı soru tekrar sorulunca cevabı yeniden ÜRETME.
        # Üretim bu makinede 90 saniye; önbellekten dönüş anlık.
        # Sunumda/demoda aynı soruyu tekrar sormak çok yaygın.
        # Oturum içi (bellekte) tutulur, program kapanınca silinir.
        self._answer_cache = {}

    # -- kurulum -------------------------------------------------------------

    @classmethod
    def create(cls, verbose: bool = True, fast: bool = False):
        """Veri tabanını açar, modelleri yükler, hazır bir pipeline döndürür.

        fast=True  -> küçük/hızlı modeli tercih et (kaliteden verir).
                      Ölçüm: phi-3.5-mini ~90 sn ve 4/5 doğruluk,
                             qwen2.5-1.5b  ~35 sn ve 3/5 doğruluk.
                      Demo/sunum sırasında bekleme kısalsın diye.
        """
        conn = database.connect(config.DB_PATH)

        n = database.count_chunks(conn)
        if n == 0:
            raise RuntimeError(
                "Veri tabanı boş.\nÖnce şunu çalıştır:  python main.py ingest"
            )

        # İndeksin hangi embedding modeliyle üretildiğini doğrula.
        # Uyuşmazsa vektörler karşılaştırılamaz ve cevaplar sessizce bozulur.
        indexed_model = database.get_meta(conn, "embedding_model")
        if indexed_model and indexed_model != config.EMBEDDING_MODEL:
            raise RuntimeError(
                f"Veri tabanı '{indexed_model}' ile indekslenmiş ama config "
                f"'{config.EMBEDDING_MODEL}' diyor.\n"
                f"Çözüm: 'python main.py ingest' ile yeniden indeksle."
            )

        manager = foundry_client.get_manager(config.APP_NAME, config.CACHE_DIR)

        # Düşük bellek modu kararı: config'te açıkça belirtilmemişse
        # boş RAM'e bakarak otomatik ver.
        low_memory = config.LOW_MEMORY_MODE
        free_gb = foundry_client.free_memory_gb()
        if low_memory is None:
            low_memory = free_gb is not None and free_gb < config.LOW_MEMORY_THRESHOLD_GB

        if verbose:
            if free_gb is not None:
                print(f"Boş RAM: {free_gb:.1f} GB")
            if low_memory:
                print(
                    "Düşük bellek modu AÇIK: sohbet modeli her cevaptan sonra "
                    "bellekten atılacak (soru başına ~3 sn ek süre)."
                )

        if verbose:
            print(f"Embedding modeli: {config.EMBEDDING_MODEL}")
        embedding_model = foundry_client.EmbeddingModel(
            manager, config.EMBEDDING_MODEL, config.DEVICE_PREFERENCE, verbose
        )

        # Sohbet modeli: aday listesi sırayla denenir, ilk yüklenebilen kullanılır.
        # Hız modunda listeyi ters çevirip küçük modeli başa alıyoruz.
        candidates = (
            list(reversed(config.CHAT_MODEL_CANDIDATES))
            if fast else config.CHAT_MODEL_CANDIDATES
        )
        if verbose and fast:
            print("Hız modu AÇIK: küçük model tercih ediliyor (kalite biraz düşer).")

        chat_model = foundry_client.ChatModel(
            manager,
            candidates,
            config.DEVICE_PREFERENCE,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
            top_p=config.TOP_P,
            keep_loaded=not low_memory,
            verbose=verbose,
        )

        # Hangi sohbet modelinin çalıştığını ŞİMDİ belirle. Tembel yükleme
        # yapılırsa "Sohbet modeli: ..." mesajı akan cevabın ortasına giriyor.
        chat_model.warm_up()

        retriever = Retriever.from_database(
            conn, embedding_model, config.QUERY_INSTRUCTION
        )

        if verbose:
            print(f"{n} chunk yüklendi.\n")

        return cls(conn, retriever, chat_model, embedding_model, low_memory)

    # -- ana işlev -----------------------------------------------------------

    def answer_query(self, question: str, top_k=None, alpha=None, threshold=None,
                     on_text=None, on_sources=None):
        """Bir soruyu cevaplar.

        on_text    : verilirse cevap AKIŞ hâlinde üretilir ve her yeni metin
                     parçası bu fonksiyona gönderilir. Toplam süre değişmez
                     ama kullanıcı beklemek yerine yazının aktığını görür.
        on_sources : verilirse, üretim BAŞLAMADAN önce bulunan kaynaklarla
                     çağrılır. Arayüz kaynakları hemen gösterebilsin diye:
                     arama ~2 sn sürer, üretim ~90 sn. Kullanıcı ilk 2
                     saniyede neyin bulunduğunu görür.

        Döner:
            {
              "question":  soru metni,
              "answer":    cevap metni,
              "found":     bağlam bulundu mu (bool),
              "sources":   kullanılan chunk'lar (skorlarıyla),
              "elapsed":   toplam süre (saniye),
            }
        """
        top_k = top_k if top_k is not None else config.TOP_K
        alpha = alpha if alpha is not None else config.HYBRID_ALPHA
        threshold = threshold if threshold is not None else config.SIMILARITY_THRESHOLD

        started = time.perf_counter()

        question = (question or "").strip()
        if not question:
            return {
                "question": question,
                "answer": "Lütfen bir soru yaz.",
                "found": False,
                "sources": [],
                "elapsed": 0.0,
            }

        # Önbellekte varsa üretimi tamamen atla (90 sn -> anlık).
        # Akış isteniyorsa cevabı tek parça hâlinde geri veriyoruz;
        # arayüz açısından davranış aynı kalıyor.
        cache_key = question.lower()
        cached = self._answer_cache.get(cache_key)
        if cached is not None:
            if on_sources is not None:
                on_sources(cached["sources"])
            if on_text is not None:
                on_text(cached["answer"])
            return {**cached, "elapsed": time.perf_counter() - started, "cached": True}

        results = self.retriever.search(question, top_k=top_k, alpha=alpha)
        best_score = results[0]["score"] if results else 0.0

        # Eşiğin altındaysa modeli hiç çağırma
        if best_score < threshold:
            return {
                "question": question,
                "answer": config.FALLBACK_ANSWER,
                "found": False,
                "sources": results,
                "elapsed": time.perf_counter() - started,
            }

        # 1) Bütçeye sığanları SKOR sırasına göre seç (en alakalı mutlaka girsin)
        selected = generator.select_within_budget(results, config.MAX_CONTEXT_CHARS)
        # 2) Seçilenleri BELGE sırasına diz (model metni akış hâlinde okusun)
        ordered = order_for_context(selected)

        selected_ids = {s["id"] for s in selected}
        for r in results:
            r["used_in_prompt"] = r["id"] in selected_ids

        # Kaynakları üretim başlamadan bildir: arama ~2 sn, üretim ~90 sn.
        # Kullanıcı ilk saniyelerde neyin bulunduğunu görsün.
        if on_sources is not None:
            on_sources(results)

        # 3) Düşük bellek modunda embedding modelini boşalt: sohbet modeli
        #    uzun prompt'u ancak o zaman işleyebiliyor. Sonraki soruda
        #    otomatik geri yüklenir (~3.5 sn).
        if self.low_memory:
            self.embedding_model.release()

        if on_text is not None:
            answer = generator.stream_answer(
                self.chat_model, question, ordered, config.FALLBACK_ANSWER, on_text
            )
        else:
            answer = generator.generate_answer(
                self.chat_model, question, ordered, config.FALLBACK_ANSWER
            )

        result = {
            "question": question,
            "answer": answer or config.FALLBACK_ANSWER,
            "found": True,
            "sources": results,
            "elapsed": time.perf_counter() - started,
            "cached": False,
        }
        self._answer_cache[cache_key] = result
        return result

    def close(self):
        self.chat_model.close()
        self.embedding_model.close()
        self.conn.close()
