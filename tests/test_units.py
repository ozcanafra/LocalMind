"""Birim testleri: model YÜKLEMEDEN çalışan saf Python mantığını doğrular.

Neden ayrı bir dosya? test_rag.py yerel LLM'i çalıştırdığı için soru başına
~40 saniye sürüyor ve bellek sıkışıklığında düşebiliyor. Buradaki testler
saniyeler içinde biter ve her değişiklikten sonra koşulabilir.

Kapsam:
  - text_utils : gürültü temizleme
  - chunker    : başlık sınıflandırma ve parçalama
  - retriever  : Türkçe tokenizasyon, IDF skorlama, kosinüs benzerliği
  - generator  : bağlam biçimlendirme, karakter bütçesi, çıktı temizleme

KULLANIM
    python tests/test_units.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src import generator as gen
from src import text_utils as tu
from src.chunker import chunk_document, classify_line
from src.retriever import KeywordIndex, cosine_similarities, tokenize

_passed = 0
_failed = []


def check(name, got, expected):
    global _passed
    if got == expected:
        _passed += 1
        print(f"  [GECTI] {name}")
    else:
        _failed.append((name, got, expected))
        print(f"  [KALDI] {name}\n          beklenen: {expected!r}\n          gelen   : {got!r}")


def check_true(name, condition, detail=""):
    check(name if not detail else f"{name} ({detail})", bool(condition), True)


# --- text_utils -------------------------------------------------------------

def test_text_utils():
    print("\ntext_utils")

    # PDF'ten gelen Wingdings madde işaretleri (U+F0A7) yıldıza dönmeli
    check("PUA sembolleri temizlenir",
          tu.normalize_chars(" test  bir"), "* test * bir")

    # Akıllı tırnaklar düz karşılıklarına dönmeli
    check("akilli tirnak duzlestirilir",
          tu.normalize_chars("FIFO’ya göre"), "FIFO'ya göre")

    # 4+ kez tekrar eden ve 4+ kelimelik satırlar footer sayılır
    lines = ["Operating System Concepts - 9th Edition"] * 5 + ["Second-chance Algorithm"] * 5
    boilerplate = tu.find_boilerplate(lines)
    check_true("uzun tekrar eden satir footer sayilir",
               "Operating System Concepts - 9th Edition" in boilerplate)
    # Kısa başlıklar sık tekrar etse de korunmalı
    check_true("kisa baslik footer sayilmaz",
               "Second-chance Algorithm" not in boilerplate)

    # Slayt numaraları atılmalı, yerine boş satır (sınır) kalmalı
    cleaned = tu.clean_document("Baslik\n9.2\nIcerik")
    check_true("slayt numarasi atilir", "9.2" not in cleaned)


# --- chunker ----------------------------------------------------------------

def test_chunker():
    print("\nchunker")

    check("numarali baslik", classify_line("2. IP PROTOKOLU VE DATAGRAM"), "section")
    check("slayt basligi", classify_line("Second-chance Algorithm"), "subsection")
    # Tamamı büyük harfli kısa etiketler gövdede kalmalı, başlık olmamalı
    check("BUYUK HARF etiket govdede kalir", classify_line("TANIM"), "body")
    # Tablo satırları ";" veya ":" içerir -> başlık değil
    check("tablo satiri govde", classify_line("Options Degisken Opsiyonel; nadiren"), "body")
    check("madde isareti govde", classify_line("* bir madde"), "body")

    # RAKAMLA BASLAYAN TABLO HUCRELERI baslik olmamali.
    # Gercek hata: "4 (En kotu)" baslik sayilinca model, dogru cevap
    # baglamda olmasina ragmen bu basligi cevap olarak kopyaladi.
    check("tablo hucresi '4 (En kotu)' govde", classify_line("4 (En kötü)"), "body")
    check("tablo satiri '4 Process sonlandi' govde",
          classify_line("4 Process sonlandı Nonpreemptive"), "body")
    # Ama gercek numarali basliklar korunmali
    check("'1) Temel Kavramlar' baslik", classify_line("1) Temel Kavramlar"), "subsection")
    check("'2. IP PROTOKOLU' baslik", classify_line("2. IP PROTOKOLU VE DATAGRAM"), "section")

    # HICBIR SATIR KAYBOLMAZ GUVENCESI
    # Art arda gelen "baslik gibi gorunen" satirlar aslinda tablo
    # satirlariydi ve indekse HIC GIRMIYORDU - bilgi kayboluyordu.
    tablo = (
        "3. ANAHTARLAMA TEKNIKLERI\n"
        "Devre\n"
        "Verimsiz kullanim, pahali, uzun kurulum suresi\n"
        "Mesaj\n"
        "Sakla-ve-gonder yontemi kullanilir\n"
    )
    uretilen = chunk_document(tablo, chunk_size=120, overlap=30, min_words=1)
    tum_metin = " ".join(c["text"] for c in uretilen)
    check_true("tablo satiri kaybolmuyor (Verimsiz)", "Verimsiz kullanim" in tum_metin)
    check_true("tablo satiri kaybolmuyor (Sakla-ve-gonder)",
               "Sakla-ve-gonder" in tum_metin)

    # 6 kelimelik icerik satirlari artik baslik sayilmamali
    check("6 kelimelik tablo satiri govde",
          classify_line("Verimsiz kullanim, pahali, uzun kurulum suresi"), "body")
    check("LRU tablo satiri govde",
          classify_line("LRU En uzun sure kullanilmayan cikar"), "body")

    # BOSLUK DOLDURMA alistirmalari bilgi tasimaz, elenmeli
    from src.chunker import is_low_information
    check_true("bosluk doldurma elenir", is_low_information(
        "1. Second-chance algoritması _____________ algoritması olarak da bilinir.\n"
        "2. Referans biti 1 olan page'e _______ verilir ve biti _______ yapılır."))
    # Cevap anahtarlari KORUNMALI (alt cizgi yok)
    check_true("cevap anahtari korunur", not is_low_information(
        "1. Clock 2. ikinci şans / 0\n3. (0,0) - ne kullanılmış ne değiştirilmiş"))
    check_true("normal metin korunur", not is_low_information(
        "Second-chance algoritması FIFO tabanlıdır ve referans bitine bakar."))

    text = (
        "1. AG KATMANI\n"
        "Ag katmani paket bazinda haberlesmeyi saglar ve yonlendirme yapar.\n"
        "2. IP PROTOKOLU\n"
        "TTL 8 bit datagramin agda kalabilecegi sureyi belirtir.\n"
    )
    chunks = chunk_document(text, chunk_size=120, overlap=30, min_words=3)
    check_true("baslik degisince yeni chunk", len(chunks) == 2, f"{len(chunks)} chunk")
    check_true("baslik chunk metnine gomulur",
               chunks[1]["text"].startswith("[2. IP PROTOKOLU]"))


# --- retriever --------------------------------------------------------------

def test_retriever():
    print("\nretriever")

    tokens = tokenize("Yönlendirmenin IHL alanı ve TTL değeri nedir?")
    check_true("durak kelimeler atilir", "ve" not in tokens and "nedir" not in tokens)
    check_true("terimler korunur", "ihl" in tokens and "ttl" in tokens)

    # Türkçe I/İ sorunu: 'IHL'.lower() dogru calismali
    check_true("turkce buyuk harf normalize", "ihl" in tokenize("IHL"))

    texts = [
        "TTL 8 bit datagram suresi",
        "Sanal devre ATM ve X.25 kullanir",
        "Bagimsiz bir metin parcasi",
    ]
    index = KeywordIndex(texts)
    check_true("TTL sorgusu 1. chunk'i bulur",
               int(np.argmax(index.score("TTL kac bit"))) == 0)
    check_true("ATM sorgusu 2. chunk'i bulur",
               int(np.argmax(index.score("ATM X.25 sanal devre"))) == 1)
    check_true("alakasiz sorgu dusuk skor",
               float(index.score("basketbol futbol").max()) < 0.2)

    # Türkçe eklemeli yapı: "yönlendirme" ile "yönlendirmenin" eşleşmeli
    index_tr = KeywordIndex(["Yonlendirmenin temel gorevi paketleri iletmektir"])
    check_true("on-ek eslesmesi (yonlendirme <-> yonlendirmenin)",
               float(index_tr.score("yonlendirme nedir")[0]) > 0.0)

    matrix = np.array([[1, 0, 0], [0, 1, 0], [0.7, 0.7, 0]], dtype=np.float32)
    sims = cosine_similarities([1, 0, 0], matrix)
    check_true("kosinus: ayni vektor 1.0", abs(sims[0] - 1.0) < 1e-5)
    check_true("kosinus: dik vektor 0.0", abs(sims[1]) < 1e-5)
    check_true("bos matris cokmez", len(cosine_similarities([1, 0], np.zeros((0, 0)))) == 0)


# --- generator --------------------------------------------------------------

FAKE = [
    {"id": 1, "source": "a.txt", "chunk_index": 0, "heading": "2. IP > Alanlar",
     "text": "[2. IP > Alanlar]\nTTL 8 bit datagram suresi", "word_count": 6},
    {"id": 2, "source": "a.txt", "chunk_index": 1, "heading": "3. Anahtarlama",
     "text": "[3. Anahtarlama]\nSanal devre ATM ve X.25 kullanir", "word_count": 7},
    {"id": 3, "source": "b.txt", "chunk_index": 0, "heading": None,
     "text": "Baslikliz bir chunk metni burada", "word_count": 5},
]


def test_generator():
    print("\ngenerator")

    context = gen.format_context(FAKE)
    check_true("kaynaklar numaralanir", "[1] Kaynak:" in context and "[3] Kaynak:" in context)
    check_true("govdedeki tekrar baslik silinir", "[2. IP > Alanlar]\n" not in context)
    check_true("baslik etikete tasinir", "a.txt - 2. IP > Alanlar" in context)

    check_true("butcesiz tum chunklar", len(gen.select_within_budget(FAKE, None)) == 3)
    check_true("dar butce kirpar", len(gen.select_within_budget(FAKE, 60)) == 1)
    check_true("cok dar butcede bile en az 1 chunk",
               len(gen.select_within_budget(FAKE, 5)) == 1)

    # Tekrar eleme: chunk overlap yuzunden komsu chunk'lar ortak metin tasir.
    # Ikisi birden secilirse butcenin buyuk kismi tekrara gider.
    shared = "Bulut hesabi veya harici bir GPU gerektirmez, CPU ile calisir."
    dupes = [
        {"id": 10, "source": "d.txt", "chunk_index": 0, "heading": None,
         "text": f"Foundry Local yerel bir yapay zeka cozumudur.\n{shared}", "word_count": 15},
        {"id": 11, "source": "d.txt", "chunk_index": 1, "heading": None,
         "text": f"{shared}\nRAG mimarisi belgelerden bilgi getirir.", "word_count": 15},
        {"id": 12, "source": "d.txt", "chunk_index": 2, "heading": None,
         "text": "Tamamen farkli bir konu: SQLite yerel veri tabanidir.", "word_count": 8},
    ]
    picked = gen.select_within_budget(dupes, 10000)
    check_true("tekrar eden chunk elenir", [p["id"] for p in picked] == [10, 12],
               f"secilen: {[p['id'] for p in picked]}")
    check_true("farkli icerik korunur", any(p["id"] == 12 for p in picked))

    check("CEVAP: etiketi silinir", gen.clean_answer("CEVAP: 8 bittir."), "8 bittir.")
    check("tekrarli etiket silinir",
          gen.clean_answer("**CEVAP:** CEVAP: Adresleme [1]"), "Adresleme [1]")
    check("bosluklu etiket silinir", gen.clean_answer("** CEVAP : Dijkstra"), "Dijkstra")
    # Model gercekten "ÇEVAP:" yazdi (C yerine Ç). Turkce metinle egitilmis
    # modellerde bu harf kaymasi oluyor, varyanti da yakaliyoruz.
    check("Ç ile yazilan etiket silinir",
          gen.clean_answer("ÇEVAP: Cok fazla context switch olur."),
          "Cok fazla context switch olur.")
    check("kaynak basligi kirpilir, numara kalir",
          gen.clean_answer("[2] Kaynak: a.txt - 3. ANAHTARLAMA\nATM ve X.25"),
          "[2]\nATM ve X.25")
    check("ciplak kaynak satiri silinir",
          gen.clean_answer("bilgisayaragları.txt - 3. ANAHTARLAMA > Sanal D"), "")
    check("soru tekrari silinir",
          gen.clean_answer("- **Second-chance diger adi nedir**\nClock",
                           "Second-chance diger adi nedir?"), "Clock")

    # KRITIK REGRESYON TESTI - bu davranis bir kez BOZULDU.
    # Model soruyu yeniden ifade ederek cevaplarsa cevap SILINMEMELI.
    # Gercek vaka: model "...starvation sorunu Aging ile cozulur" dedi,
    # eski kod bunu "soru tekrari" sanip sildi ve dogru cevap cope gitti.
    restated = gen.clean_answer(
        "Priority scheduling'de starvation sorunu Aging ile cozulur.\n"
        "Cevabin numarasi: [1]",
        "Priority scheduling'de starvation sorunu nasil cozulur?",
    )
    check_true("soruyu tekrarlayip CEVAPLAYAN satir korunur",
               "Aging" in restated, f"gelen: {restated!r}")
    check("sondaki kaynak blogu silinir",
          gen.clean_answer("Dijkstra kullanir.\n**Kaynak:** a.txt bolum 5"),
          "Dijkstra kullanir.")
    check("normal cevap bozulmaz",
          gen.clean_answer("Normal bir cevap, silinmemeli.", "soru nedir?"),
          "Normal bir cevap, silinmemeli.")

    # YİNELEME DÖNGÜSÜ - bu metin UYDURMA DEĞİL, qwen2.5-1.5b'nin
    # "Thrashing nedir?" sorusuna verdiği GERÇEK cevaptır. Aynı ifadeler
    # üst üste tekrarlanıp cevabı okunamaz hâle getiriyor.
    loop = (
        "Thrashing, bir sistem üzerindeki çoklu süreçlerin birbirleriyle "
        "birbirine sahip olması nedeniyle, bu süreçlerin birbirleriyle "
        "birbirine sahip olması nedeniyle, sistem tarafından hafızda "
        "saklanmaya çalışılan belirli bir sayının aşılması nedeniyle oluşan "
        "bir durumdur. Bu durum, bir sistem üzerinde çoklu süreçlerin "
        "birbirleriyle birbirine sahip olması nedeni ile, bu süreçlerin "
        "birbirleriyle birbirine sahip olması nedeniyle, sistem tarafından "
        "hafızda saklanmaya çalışılan belirli bir sayının aşılması nedeniyle "
        "oluşur. Thrashing, bir sistem üzerinde çoklu süreçlerin "
        "birbirleriyle birbirine sahip olması nedeni ile, bu süreçlerin "
        "birbirleriyle birbirine sahip olması nedeniyle oluşur."
    )
    trimmed = gen.trim_repetition(loop)
    check_true("dongu kesilir", len(trimmed) < len(loop),
               f"{len(loop)} -> {len(trimmed)} karakter")

    # Terim tekrari SERBEST kalmali: RAG'de model kaynaktaki terimleri
    # (TTL, Dijkstra) tekrar tekrar kullanabilmeli.
    terms = ("TTL alani 8 bittir. TTL, datagramin agda kalabilecegi sureyi "
             "belirtir. TTL sifira ulasinca paket yok edilir.")
    check("terim tekrari bozulmaz", gen.trim_repetition(terms), terms)

    messages = gen.build_messages("TTL kac bit?", FAKE, "Bilmiyorum.")
    check_true("iki mesaj uretilir", len(messages) == 2)
    check_true("sistem mesajinda fallback var", "Bilmiyorum." in messages[0]["content"])
    check_true("soru en sonda", messages[1]["content"].rstrip().endswith("CEVAP:"))


class _FakeStreamModel:
    """Belirlenen metni parça parça veren sahte model (LLM yüklemeden test)."""

    def __init__(self, text, piece_size=7):
        self.text = text
        self.piece_size = piece_size

    def stream_chat(self, messages):
        for i in range(0, len(self.text), self.piece_size):
            yield self.text[i:i + self.piece_size]


def test_streaming():
    print("\ngenerator - akis (streaming)")

    # KRİTİK KURAL: ekrana akan metin ile döndürülen temiz metin AYNI olmalı.
    # Farklı olursa kullanıcı ekranda bir şey görüp kayıtta başkasını bulur.
    scenarios = [
        ("temiz kisa cevap", "TTL alani 8 bittir. [1]"),
        ("bastaki CEVAP: etiketi",
         "CEVAP: TTL alani 8 bittir ve datagramin agda kalabilecegi sureyi belirtir. [1]"),
        ("sondaki kaynak kuyrugu",
         "TTL alani 8 bittir ve datagramin agda kalma suresini belirtir.\n"
         "**Kaynak:** a.txt bolum 2"),
        ("cok kisa cevap", "8 bit"),
    ]

    for name, raw in scenarios:
        pieces = []
        final = gen.stream_answer(
            _FakeStreamModel(raw), "TTL kac bittir?", FAKE, "Bilmiyorum.", pieces.append
        )
        streamed = "".join(pieces)
        check(f"akis == sonuc ({name})", streamed, final)

    # Baştaki etiket akışta da temizlenmeli
    pieces = []
    gen.stream_answer(_FakeStreamModel("CEVAP: Dijkstra algoritmasi kullanilir ve en kisa yolu bulur."),
                      "soru nedir?", FAKE, "Bilmiyorum.", pieces.append)
    check_true("akiste CEVAP: etiketi silinir", not "".join(pieces).startswith("CEVAP"))

    # Sondaki kaynak kuyruğu akışta da atılmalı
    pieces = []
    gen.stream_answer(_FakeStreamModel("Dijkstra kullanilir ve en kisa yol hesaplanir.\n**Kaynak:** a.txt"),
                      "soru nedir?", FAKE, "Bilmiyorum.", pieces.append)
    check_true("akiste kaynak kuyrugu silinir", "**Kaynak:**" not in "".join(pieces))


def main() -> int:
    print("=" * 70)
    print("BIRIM TESTLERI (model yuklenmez)")
    print("=" * 70)

    test_text_utils()
    test_chunker()
    test_retriever()
    test_generator()
    test_streaming()

    total = _passed + len(_failed)
    print("\n" + "=" * 70)
    print(f"SONUC: {_passed}/{total}")
    if _failed:
        print("\nBASARISIZ:")
        for name, got, expected in _failed:
            print(f"  - {name}\n      beklenen: {expected!r}\n      gelen   : {got!r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
