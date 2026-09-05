"""Getirme (retrieval) katmanı: soruya en uygun chunk'ları bulur.

NEDEN HİBRİT ARAMA?

Salt vektör (dense) araması anlamsal çalışır: "işletim sistemi bellek yönetimi"
ile "sanal bellek sayfalama" birbirine yakın çıkar. Güzel, ama kesin terimleri
kaçırır. "TTL alanı kaç bit?" sorusunda asıl sinyal 'TTL' kelimesinin metinde
AYNEN geçmesidir; anlamsal benzerlik burada zayıf kalır.

Salt anahtar kelime araması ise tersini yapar: kelimeyi bulur ama "sayfa
değiştirme algoritması nedir" gibi yeniden ifade edilmiş soruları kaçırır.

Çözüm: ikisini ağırlıklı topla.
    skor = ALPHA * kosinus_benzerligi + (1 - ALPHA) * anahtar_kelime_skoru

TÜRKÇE İÇİN ÖZEL NOT
Türkçe eklemeli bir dildir: soruda "yönlendirme", belgede "yönlendirmenin".
Tam kelime eşleşmesi bunu kaçırır. Bu yüzden ilk N harfe göre ön-ek eşleşmesi
kullanıyoruz - basit ama Türkçede şaşırtıcı derecede etkili bir gövdeleme.
"""

import math
import re
from collections import Counter

import numpy as np

# --- Türkçe metin işleme ----------------------------------------------------

# Python'un .lower() metodu Türkçe I/İ ayrımını yanlış yapar.
# 'I'.lower() -> 'i' olmalı ki 'ı', 'İ'.lower() -> 'i' olsun.
_TR_LOWER_MAP = str.maketrans("IİĞÜŞÖÇ", "iiğüşöç")

_TOKEN_PATTERN = re.compile(r"[0-9a-zçğıöşü]+", re.IGNORECASE)

# Türkçe/İngilizce durak kelimeleri: her metinde geçtikleri için ayırt edici
# değiller. Skorlamada gürültü yaratmasınlar diye ayıklıyoruz.
STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "için", "olan", "olarak", "gibi",
    "daha", "çok", "en", "ne", "nedir", "nasıl", "kaç", "hangi", "mi", "mı",
    "mu", "mü", "the", "of", "a", "an", "is", "are", "to", "in", "on", "and",
    "or", "ise", "eğer", "her", "tüm", "var", "yok", "olur", "yapar", "eder",
}

# Kısmi eşleşme cezası (üs). 1.0 = ceza yok.
#
# 2.0 DENENDİ VE GERİ ALINDI - ölçüm sonucu:
#   üs 1.0 : cevaplanabilir min 0.528 | "sanal bellek" tuzağı 0.498 | boşluk 0.030
#   üs 2.0 : cevaplanabilir min 0.460 | "sanal bellek" tuzağı 0.431 | boşluk 0.029
#
# Ceza tuzağı düşürdü ama iyi soruları da AYNI ORANDA düşürdü. Ayrım
# boşluğu değişmedi; sadece bütün skorlar aşağı kaydı. Fazladan parametre
# taşımanın karşılığı yok, o yüzden 1.0'da bırakıldı.
#
# Ders: bir düzeltmenin hedefi düşürmesi yetmez, HEDEFİ DİĞERLERİNDEN
# DAHA ÇOK düşürmesi gerekir. Mutlak değil, göreli iyileşmeye bakılmalı.
COVERAGE_EXPONENT = 1.0

# Ön-ek eşleşmesinde karşılaştırılacak harf sayısı.
# 6 iyi bir denge: "yönlend|irme" ve "yönlend|irmenin" eşleşir,
# ama "paket" ile "paralel" eşleşmez.
PREFIX_LEN = 6
# Bu uzunluktan kısa kelimelerde ön-ek yerine tam eşleşme aranır.
MIN_PREFIX_TOKEN = 5


def tokenize(text: str):
    """Metni normalleştirilmiş kelime listesine çevirir."""
    lowered = text.translate(_TR_LOWER_MAP).lower()
    return [
        t for t in _TOKEN_PATTERN.findall(lowered)
        if len(t) > 1 and t not in STOPWORDS
    ]


def _stem(token: str) -> str:
    """Kaba gövdeleme: kelimenin ilk PREFIX_LEN harfi."""
    return token[:PREFIX_LEN] if len(token) >= MIN_PREFIX_TOKEN else token


# --- Anahtar kelime indeksi -------------------------------------------------


class KeywordIndex:
    """Basit IDF ağırlıklı anahtar kelime indeksi.

    IDF (Inverse Document Frequency) = ters belge sıklığı.
    Fikir: 'TTL' sadece 2 chunk'ta geçiyorsa çok ayırt edicidir, yüksek ağırlık
    alır. 'sistem' 40 chunk'ta geçiyorsa ayırt edici değildir, düşük ağırlık.
    Böylece nadir ve kritik terimler skoru domine eder.
    """

    def __init__(self, texts):
        self.doc_stems = [set(_stem(t) for t in tokenize(text)) for text in texts]
        n_docs = max(len(texts), 1)

        # Her gövde kaç chunk'ta geçiyor?
        df = Counter()
        for stems in self.doc_stems:
            df.update(stems)

        # IDF = log(1 + N / df).  df büyüdükçe ağırlık küçülür.
        self.idf = {
            stem: math.log(1.0 + n_docs / count) for stem, count in df.items()
        }
        self._default_idf = math.log(1.0 + n_docs)

    def score(self, question: str) -> np.ndarray:
        """Her chunk için 0..1 arası anahtar kelime skoru döndürür.

        Ham skor = (chunk'ta bulunan sorgu terimlerinin IDF toplamı)
                   / (tüm sorgu terimlerinin IDF toplamı)
        yani "sorunun ayırt edici terimlerinin yüzde kaçı bu chunk'ta var?"

        KISMİ EŞLEŞME CEZASI (üs alma) NEDEN VAR?

        Ham oran, terimlerin YARISINI içeren bir chunk'a 0.50 veriyor. Bu
        fazla cömert ve gerçek bir hataya yol açtı:

            Soru : "sanal bellek nedir"        (anlamlı terimler: sanal, bellek)
            Chunk: "3. ANAHTARLAMA TEKNİKLERİ > Sanal Devre"   (AĞ belgesi!)

        Chunk sadece "sanal" terimini içeriyordu, "bellek" yoktu. Yine de
        0.50 kelime skoru aldı, hibrit skoru eşiğin üstüne taşıdı ve model
        ağ konusuyla bellek konusunu karıştıran anlamsız bir cevap üretti.

        Üs alınca kısmi eşleşme hak ettiği yere düşüyor:
            oran 1.00 (tüm terimler) -> 1.00   değişmez
            oran 0.50 (yarısı)       -> 0.25   yarı yarıya düşer
            oran 0.33 (üçte biri)    -> 0.11
        Tam eşleşme cezalandırılmıyor, sadece kısmi eşleşmenin ağırlığı
        gerçekçi hâle geliyor.
        """
        q_stems = {_stem(t) for t in tokenize(question)}
        if not q_stems:
            return np.zeros(len(self.doc_stems), dtype=np.float32)

        weights = {s: self.idf.get(s, self._default_idf) for s in q_stems}
        total = sum(weights.values()) or 1.0

        scores = np.zeros(len(self.doc_stems), dtype=np.float32)
        for i, stems in enumerate(self.doc_stems):
            matched = sum(w for s, w in weights.items() if s in stems)
            scores[i] = (matched / total) ** COVERAGE_EXPONENT
        return scores


# --- Vektör araması ---------------------------------------------------------


def cosine_similarities(query_vector, matrix) -> np.ndarray:
    """Sorgu vektörü ile tüm chunk vektörleri arasındaki kosinüs benzerliği.

    Eski kod bunu chunk başına bir Python döngüsüyle yapıyordu. Burada tek
    matris çarpımı kullanıyoruz: hem çok daha hızlı hem daha az kod.

    Kosinüs benzerliği = (a . b) / (|a| * |b|)
    Vektörleri önce birim uzunluğa normalize edersek sadece nokta çarpımı kalır.
    """
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)

    q = np.asarray(query_vector, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return np.zeros(matrix.shape[0], dtype=np.float32)
    q = q / q_norm

    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0  # sıfıra bölmeyi engelle
    normalized = matrix / norms[:, None]

    return normalized @ q


# --- Ana getirme sınıfı -----------------------------------------------------


class Retriever:
    """Chunk'ları bellekte tutar ve hibrit arama yapar.

    Veri tabanı bir kez okunur, sonraki tüm sorgular bellekten yanıtlanır.
    Belge sayımız küçük (57 chunk) olduğu için bu yeterli; PDF planında da
    belirtildiği gibi büyük N için gerçek bir vektör veri tabanı gerekir.
    """

    # Aynı soru tekrar sorulunca embedding'i yeniden hesaplama.
    # Düşük bellek modunda embedding modeli her soruda yeniden yükleniyor
    # (~3.5 sn); önbellek bunu tamamen atlatıyor. Sunumda aynı soruyu
    # tekrar sormak yaygın olduğu için gerçek bir kazanç.
    _QUERY_CACHE_LIMIT = 128

    def __init__(self, records, matrix, embedding_client, query_instruction=""):
        self.records = records
        self.matrix = matrix
        self.embedding_client = embedding_client
        self.query_instruction = query_instruction
        self.keyword_index = KeywordIndex([r["text"] for r in records])
        self._query_cache = {}

    @classmethod
    def from_database(cls, conn, embedding_client, query_instruction=""):
        from src import database

        records, matrix = database.load_chunks(conn)
        if not records:
            raise RuntimeError(
                "Veri tabanı boş. Önce 'python main.py ingest' çalıştır."
            )
        return cls(records, matrix, embedding_client, query_instruction)

    def embed_question(self, question: str):
        """Soruyu vektöre çevirir.

        KRİTİK: qwen3-embedding modeli ASİMETRİK arama için eğitildi.
        Belgeler ham hâlde gömülür, ama sorgular şu formatta gömülmelidir:
            "Instruct: <görev tarifi>\\nQuery: <soru>"
        Eski kod bu öneki kullanmıyordu; model soruyu "bir belge parçası"
        sanıyor ve isabet oranı düşüyordu.
        """
        key = question.strip().lower()
        cached = self._query_cache.get(key)
        if cached is not None:
            return cached

        text = f"{self.query_instruction}{question}"
        response = self.embedding_client.generate_embedding(text)
        vector = response.data[0].embedding

        if len(self._query_cache) >= self._QUERY_CACHE_LIMIT:
            self._query_cache.clear()  # basit taşma kontrolü
        self._query_cache[key] = vector
        return vector

    def search(self, question: str, top_k: int = 5, alpha: float = 0.7):
        """Soruya en uygun chunk'ları skorlarıyla birlikte döndürür.

        Dönen her eleman: kayıt sözlüğü + score / dense_score / keyword_score
        """
        q_vector = self.embed_question(question)

        dense = cosine_similarities(q_vector, self.matrix)
        keyword = self.keyword_index.score(question)
        combined = alpha * dense + (1.0 - alpha) * keyword

        # En yüksek skorlu top_k indeksi bul (tam sıralamaya gerek yok)
        k = min(top_k, len(combined))
        top_idx = np.argpartition(-combined, k - 1)[:k]
        top_idx = top_idx[np.argsort(-combined[top_idx])]

        results = []
        for i in top_idx:
            record = dict(self.records[i])
            record["score"] = float(combined[i])
            record["dense_score"] = float(dense[i])
            record["keyword_score"] = float(keyword[i])
            results.append(record)
        return results


def order_for_context(results):
    """Chunk'ları belgedeki orijinal sırasına göre dizer.

    Model bağlamı okurken belge akışını takip edebilsin diye skora göre değil,
    (kaynak, sıra) göre diziyoruz. Aynı bölümden gelen ardışık parçalar yan
    yana gelince model bilgiyi daha doğru birleştiriyor.
    """
    return sorted(results, key=lambda r: (r["source"], r["chunk_index"]))
