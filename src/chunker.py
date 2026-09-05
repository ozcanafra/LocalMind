"""Belgeyi arama için uygun parçalara (chunk) ayırır.

ESKİ YAKLAŞIM (sorunluydu):
    Metni 300 kelimede bir körlemesine kes.
    -> Tek chunk 4 farklı konuyu birden kapsıyordu, tablo satırları ortadan
       bölünüyordu, arama isabeti düşüktü. 3 belgeden toplam 18 chunk çıkmıştı.

YENİ YAKLAŞIM:
    1. Metni "birim"lere ayır (paragraf satırı veya cümle).
    2. Başlıkları tespit et; başlık değişince ZORUNLU yeni chunk başlat.
    3. Birimleri CHUNK_SIZE kelimeye kadar paketle, aralarında overlap bırak.
    4. Her chunk'ın başına ait olduğu BAŞLIĞI yaz.

4. madde kritik: "TTL 8 bit Datagramın ağda kalabileceği süre" satırı tek
başına "IP" kelimesini içermez. Başlığı ekleyince chunk şöyle olur:
    [2. IP PROTOKOLÜ VE DATAGRAM YAPISI]
    TTL 8 bit Datagramın ağda kalabileceği süre...
Artık "IP başlığındaki TTL alanı nedir?" sorusu bu chunk'la eşleşir.
"""

import re

# "1. AĞ KATMANI NEDİR?" / "6. DİNAMİK YÖNLENDİRME ALGORİTMALARI"
_NUMBERED_HEADING = re.compile(r"^\d{1,2}\.\s*[A-ZÇĞİÖŞÜ]")

# Numaralı madde/başlık: "1) Temel Kavramlar", "3. Deadlock Avoidance"
# Rakamdan hemen sonra nokta veya parantez gelmeli. Bu kalıba uymayan,
# rakamla başlayan satırlar tablo hücresidir ("4 (En kötü)").
_NUMBERED_ITEM = re.compile(r"^\d{1,2}[.)]\s+\S")

# Bir ara başlık en fazla bu kadar kelime olabilir (bkz. classify_line).
_MAX_HEADING_WORDS = 4

# Cümle sonu: nokta/soru/ünlem + boşluk + büyük harf ile başlayan yeni cümle
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9])")

# Madde işareti ile başlayan satırlar
_BULLET_START = ("*", "-", "•", "o ")

# Türkçe büyük harfler (İ ve I ayrımı için gerekli)
_TR_UPPER = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÇĞİÖŞÜ")


def classify_line(line: str) -> str:
    """Satırı sınıflandırır: "section" | "subsection" | "body".

    İki seviyeli başlık hiyerarşisi tutuyoruz, çünkü tek seviye yetmiyordu:
    "2. IP PROTOKOLÜ VE DATAGRAM YAPISI" (section) altında
    "Alan Boyut Açıklama" (subsection) gibi ara başlıklar var. Tek değişken
    kullanınca ara başlık gerçek bölüm başlığını eziyordu.

    DİKKAT: "TANIM", "EZBER", "DİKKAT", "SINAVDA" gibi tamamı büyük harfli
    kısa etiketler başlık DEĞİL, gövdenin parçasıdır. Onları başlık sayınca
    hem gerçek başlık kayboluyor hem de gövdeden bilgi siliniyordu.
    """
    s = line.strip()
    if not s or s.startswith(_BULLET_START):
        return "body"

    words = s.split()

    # a) "1. BÖLÜM ADI" -> ana bölüm başlığı
    if _NUMBERED_HEADING.match(s) and len(words) <= 10:
        return "section"

    # Ara başlıklar KISADIR. Bu sınır 6'dan 4'e indirildi çünkü 6 kelimelik
    # tablo satırları başlık sanılıp GÖVDEDEN SİLİNİYORDU:
    #     "Verimsiz kullanım, pahalı, uzun kurulum süresi"   (6 kelime)
    #     "LRU En uzun süre kullanılmayan çıkar"             (6 kelime)
    # Bu iki bilgi indekste hiç yer almıyordu.
    #
    # Gerçek başlıklar kısa: "Second-chance Algorithm" (2),
    # "Alan Boyut Açıklama" (3), "Non-Uniform Memory Access" (3).
    #
    # Güvenlik asimetrisi: bir başlığı yanlışlıkla gövde saymak ZARARSIZ
    # (metin korunur), gövdeyi yanlışlıkla başlık saymak BİLGİ KAYBETTİRİR.
    # Şüphede kalınca gövde tarafını seçiyoruz.
    if len(words) > _MAX_HEADING_WORDS:
        return "body"

    letters = [c for c in s if c.isalpha()]
    if not letters:
        return "body"

    # b) Tamamı büyük harf kısa satır -> etiket, gövdede kalsın
    if all(c in _TR_UPPER for c in letters):
        return "body"

    # Tablo satırları ";", ":" veya "=" içerir ("Options Değişken Opsiyonel;
    # nadiren kullanılır"). Gerçek başlıklar içermez. Bu ayrım tablo
    # satırlarının yanlışlıkla başlık sayılıp gövdeden silinmesini önler.
    if any(ch in s for ch in ";:=•*"):
        return "body"

    # RAKAMLA BAŞLAYAN TABLO HÜCRELERİ
    # "4 (En kötü)" ve "4 Process sonlandı Nonpreemptive" gibi satırlar
    # tablo hücresidir, başlık değil. Ama "1) Temel Kavramlar" ve
    # "2. IP PROTOKOLÜ" gerçek başlıktır. Fark: gerçek başlıkta rakamdan
    # hemen sonra nokta veya parantez gelir.
    #
    # NEDEN ÖNEMLİ? Bu yanlış sınıflandırma somut bir hataya yol açtı:
    # bir chunk'ın başlığı "... > 4 (En kötü)" olarak kaydedildi ve model
    # "en kolay değiştirilen sınıf hangisidir?" sorusuna, doğru cevap
    # (Sınıf 1) bağlamda olmasına rağmen "4 (En kötü)" dedi - yani
    # cevabı değil, komşu chunk'ın BAŞLIĞINI kopyaladı.
    if s[0].isdigit() and not _NUMBERED_ITEM.match(s):
        return "body"

    # c) Kısa, madde işaretsiz, noktalama ile bitmeyen satır -> ara başlık
    #    ("Second-chance Algorithm", "Alan Boyut Açıklama" gibi)
    if not s.endswith((".", ",", ":", ";", "?", "!")):
        return "subsection"

    return "body"


def _label(section, subsection) -> str | None:
    """Bölüm ve alt bölümü tek bir başlık etiketinde birleştirir."""
    parts = [p for p in (section, subsection) if p]
    return " > ".join(parts) if parts else None


def split_units(text: str):
    """Metni (başlık_etiketi, birim_metni) çiftlerine ayırır.

    "Birim" = bir paragraf satırı ya da (satır çok uzunsa) bir cümle.

    HİÇBİR SATIR KAYBOLMAZ GÜVENCESİ
    Başlık olarak sınıflandırılan satırlar gövdeye eklenmez; sadece sonraki
    chunk'ların etiketi olurlar. Peki o başlığın altına hiç gövde satırı
    gelmezse? O satır indekste HİÇ YER ALMAZ - bilgi kaybolur.

    Gerçekten yaşandı: karşılaştırma tablolarındaki
        "Verimsiz kullanım, pahalı, uzun kurulum süresi"
        "LRU En uzun süre kullanılmayan çıkar"
    satırları art arda "başlık" sanıldı, hiçbirine gövde bağlanmadı ve
    ikisi de veri tabanına hiç girmedi.

    Çözüm: bir ara başlık kullanılmadan yerine yenisi gelirse, eskisi
    aslında gövde metniydi demektir - onu birim olarak geri ekliyoruz.
    """
    section = None
    subsection = None
    pending_subsection = None  # atandı ama henüz hiçbir gövde satırı gelmedi
    units = []

    def rescue_unused():
        """Kullanılmamış ara başlığı gövde metni olarak kurtarır."""
        nonlocal pending_subsection
        if pending_subsection is not None:
            units.append((_label(section, None), pending_subsection))
            pending_subsection = None

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        kind = classify_line(line)
        if kind == "section":
            rescue_unused()
            section = line
            subsection = None  # yeni bölüm -> alt başlığı sıfırla
            continue
        if kind == "subsection":
            rescue_unused()
            subsection = line
            pending_subsection = line
            continue

        pending_subsection = None  # bu ara başlık gerçekten kullanıldı
        heading = _label(section, subsection)

        # Satır çok uzunsa (ör. llmprojesi.txt tek satırlık dev metin)
        # cümlelere ayır ki paketleme mantıklı yerlerden bölsün.
        if len(line.split()) > 60:
            for sentence in _SENTENCE_SPLIT.split(line):
                sentence = sentence.strip()
                if sentence:
                    units.append((heading, sentence))
        else:
            units.append((heading, line))

    rescue_unused()  # dosya sonundaki kullanılmamış başlık da kurtarılsın
    return units


# Boşluk doldurma alıştırması: "Second-chance algoritması _______ olarak da
# bilinir." Ders notlarında sınav provası bölümleri böyle.
_BLANK_LINE = re.compile(r"_{3,}")

# Satırlarının bu oranı boşluk içeriyorsa chunk bilgi taşımıyor demektir.
_LOW_INFO_BLANK_RATIO = 0.5


def is_low_information(text: str) -> bool:
    """Chunk bilgi taşımayan bir alıştırma mı?

    NEDEN ELENMELİ?
    Ders notlarındaki "Boşluk Doldurma Provası" bölümleri şöyle:
        "1. Second-chance algoritması ___________ algoritması olarak da bilinir."
    Bu satır sorunun kendisini içeriyor ama CEVABI içermiyor. Arama bu
    chunk'ı çok alakalı buluyor (soruyla neredeyse birebir aynı kelimeler)
    ve bağlamın değerli yerini işgal ediyor. Model de boşluğu cevap sanıp
    kafası karışabiliyor.

    DİKKAT: cevap anahtarları ELENMEZ. "1. Clock 2. ikinci şans / 0"
    satırlarında alt çizgi yok, dolayısıyla bu filtre onlara dokunmaz -
    ki onlar gerçekten değerli bilgi taşıyor.
    """
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return True
    blanks = sum(1 for line in lines if _BLANK_LINE.search(line))
    return blanks / len(lines) >= _LOW_INFO_BLANK_RATIO


def chunk_document(
    text: str,
    chunk_size: int = 120,
    overlap: int = 30,
    min_words: int = 15,
):
    """Temizlenmiş belge metnini chunk listesine çevirir.

    Dönen her eleman: {"heading": str|None, "text": str, "word_count": int}
    """
    units = split_units(text)
    chunks = []
    buffer = []          # şu anki chunk'ın birimleri
    buffer_words = 0
    buffer_heading = None

    def flush():
        """Tampondaki birimleri bir chunk'a çevirip listeye ekler."""
        nonlocal buffer, buffer_words
        if not buffer:
            return
        body = "\n".join(buffer)
        # Başlığı chunk metnine göm -> arama sırasında bağlam kazanır
        full = f"[{buffer_heading}]\n{body}" if buffer_heading else body
        chunks.append(
            {
                "heading": buffer_heading,
                "text": full,
                "word_count": buffer_words,
            }
        )
        # Overlap: son birkaç birimi bir sonraki chunk'a devret ki
        # sınırda kesilen bilgi iki chunk'ta da bulunsun.
        carried, carried_words = [], 0
        for unit in reversed(buffer):
            n = len(unit.split())
            if carried_words + n > overlap:
                break
            carried.insert(0, unit)
            carried_words += n
        buffer = carried
        buffer_words = carried_words

    for heading, unit in units:
        n_words = len(unit.split())

        # Başlık değiştiyse mevcut chunk'ı kapat (konu sınırı)
        if heading != buffer_heading:
            flush()
            buffer, buffer_words = [], 0  # başlık değişince overlap taşıma
            buffer_heading = heading

        # Tampon dolduysa kapat
        if buffer_words + n_words > chunk_size and buffer_words > 0:
            flush()

        buffer.append(unit)
        buffer_words += n_words

    flush()

    # Çok kısa artıkları bir öncekine yapıştır (tek başına anlamsızlar)
    merged = []
    for ch in chunks:
        if merged and ch["word_count"] < min_words:
            prev = merged[-1]
            prev["text"] += "\n" + ch["text"].split("\n", 1)[-1]
            prev["word_count"] += ch["word_count"]
        else:
            merged.append(ch)

    # Bilgi taşımayan alıştırma chunk'larını ele
    return [ch for ch in merged if not is_low_information(ch["text"])]
