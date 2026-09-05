"""Ham belge metnini temizleme yardımcıları.

Belgelerimiz PDF/slayttan kopyalandığı için üç tür gürültü içeriyor:
  1. Bozuk sembol karakterleri (Wingdings madde işaretleri -> U+F0A7 gibi)
  2. Her slaytta tekrar eden alt bilgi (footer) satırları
  3. Slayt numaraları (9.2, 9.3, ...)

Bu gürültü embedding vektörünü bozar: alakasız iki chunk, ikisi de aynı
footer'ı içerdiği için birbirine "benzer" görünür. Aramadan önce temizliyoruz.

NOT: Aşağıdaki karakter sabitleri bilerek \\u kaçış kodu ile yazıldı.
Doğrudan yapıştırılan özel karakterler dosya kodlamasında bozulabiliyor.
"""

import re
import unicodedata
from collections import Counter

# Wingdings/Symbol fontlarından gelen "Private Use Area" karakterleri.
# PDF'ten kopyalanınca madde işaretleri bu aralığa düşer (U+E000-U+F8FF).
# Bizim belgede U+F0A7 (65 adet) ve U+F034 (5 adet) çıkıyor.
_PUA_PATTERN = re.compile("[-]")

# Slayt numarası: "9.2", "12.15", "3" gibi tek başına duran satırlar
_SLIDE_NUMBER_PATTERN = re.compile(r"^\s*\d{1,3}([.\-]\d{1,3})?\s*$")

# Tipografik karakterleri düz ASCII karşılıklarıyla değiştir.
_CHAR_REPLACEMENTS = {
    "’": "'",  # sağ tek tırnak
    "‘": "'",  # sol tek tırnak
    "“": '"',  # sol çift tırnak
    "”": '"',  # sağ çift tırnak
    "–": "-",  # en dash
    "—": "-",  # em dash
    " ": " ",  # kırılmaz boşluk
    "•": "*",  # madde işareti -> düz yıldız
}

# Bir satırın "tekrar eden footer" sayılması için gereken minimum tekrar sayısı.
BOILERPLATE_MIN_REPEATS = 4
# ...ve minimum kelime sayısı. Bu ikinci koşul kritik: "Second-chance Algorithm"
# gibi kısa slayt başlıkları 15 kez tekrar ediyor ama anlamlı, silinmemeli.
# Footer'lar uzundur ("Operating System Concepts - 9th Edition" = 6 kelime),
# başlıklar kısadır (2-3 kelime). Bu ayrım ikisini birbirinden ayırıyor.
BOILERPLATE_MIN_WORDS = 4


def normalize_chars(text: str) -> str:
    """Bozuk sembolleri ve tipografik karakterleri sadeleştirir."""
    text = unicodedata.normalize("NFC", text)
    for bad, good in _CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)
    # Özel kullanım alanı karakterlerini düz madde işaretine çevir
    text = _PUA_PATTERN.sub("*", text)
    return text


def find_boilerplate(lines):
    """Belgede tekrar eden alt bilgi (footer) satırlarını bulur.

    Kural: >= BOILERPLATE_MIN_REPEATS kez tekrar eden VE
           >= BOILERPLATE_MIN_WORDS kelimeden oluşan satırlar footer'dır.
    """
    counts = Counter(line.strip() for line in lines if line.strip())
    return {
        line
        for line, n in counts.items()
        if n >= BOILERPLATE_MIN_REPEATS and len(line.split()) >= BOILERPLATE_MIN_WORDS
    }


# Madde işareti ile başlayan satırlar (birleştirilmemeli)
_BULLET_START = ("*", "-", "•", "o ", "–")

# "1)" / "3." gibi numaralı madde başlangıçları
_NUMBERED_START = re.compile(r"^\s*\d{1,2}[).]\s")

# Türkçe büyük harfler
_TR_UPPER = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÇĞİÖŞÜ")


def _is_all_caps(line: str) -> bool:
    """Satır tamamen büyük harf mi? ("TANIM", "SINAVDA" gibi etiketler)"""
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c in _TR_UPPER for c in letters)


def _starts_new_block(line: str) -> bool:
    """Bu satır yeni bir madde/başlık mı başlatıyor? (birleştirme yasak)"""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(_BULLET_START):
        return True
    if _NUMBERED_START.match(stripped):
        return True
    return _is_all_caps(stripped)


def join_wrapped_lines(text: str) -> str:
    """PDF/slayttan gelen, cümle ORTASINDAN kırılmış satırları birleştirir.

    SORUN
    Belgeler slayttan kopyalandığı için satırlar sabit genişlikte kırılmış:
        "İşletim sistemlerinin en önemli özelliklerinden biri birden çok"
        "programı aynı anda çalıştırabilmeleridir."
    Bu iki satır tek bir cümle. Ayrı kalınca iki sorun çıkıyor:
      1. chunker bu kırıntıları BAŞLIK sanabiliyor. Gerçekten oldu: bir
         chunk'ın başlığı "page'in değiştirilmesi sırasında ikinci bir"
         olarak kaydedilmişti - bu bir başlık değil, yarım cümle.
      2. Modele giden bağlam kırık kırık okunuyor.

    KURAL
    İki satır birleştirilir eğer:
      - önceki satır cümle sonu noktalaması ile BİTMİYORSA (. ! ? : ;)
      - sonraki satır yeni bir madde/başlık BAŞLATMIYORSA
      - VE (sonraki satır küçük harfle başlıyorsa  VEYA
            önceki satır virgülle bitiyorsa)

    Son koşul TABLO SATIRLARINI korur. Örnek tablo:
        "IHL 4 bit Başlık uzunluğu: min 20, max 60 oktet"
        "ToS (Hizmet Türü) 8 bit Öncelik, gecikme, güvenilirlik bilgisi"
    İkinci satır BÜYÜK harfle başlıyor ve birincisi virgülle bitmiyor
    -> birleştirilmez, tablo bozulmaz. Buna karşılık gerçek cümle kırığı:
        "...birden çok programı aynı anda"
        "çalıştırabilmeleridir."
    ikinci satır küçük harfle başlıyor -> birleştirilir.
    """
    lines = text.split("\n")
    out = []

    for line in lines:
        stripped = line.strip()

        if not out or not stripped:
            out.append(stripped)
            continue

        previous = out[-1]
        if not previous or previous.endswith((".", "!", "?", ":", ";")):
            out.append(stripped)
            continue

        if _starts_new_block(stripped):
            out.append(stripped)
            continue

        first_char = stripped[0]
        continues = first_char.islower() or previous.endswith(",")
        if continues:
            out[-1] = f"{previous} {stripped}"
        else:
            out.append(stripped)

    return "\n".join(out)


def clean_document(raw: str, verbose: bool = False) -> str:
    """Ham belge metnini temizler.

    Silinen footer/slayt-numarası satırlarının yerine BOŞ SATIR bırakırız.
    Bu kasıtlı: boş satır, chunker için doğal bir "burada konu değişiyor"
    sınırıdır. Yani gürültüyü temizlerken bedava bölme noktası kazanıyoruz.
    """
    text = normalize_chars(raw)
    lines = text.split("\n")

    boilerplate = find_boilerplate(lines)
    if verbose and boilerplate:
        print(f"    Tekrar eden footer temizlendi ({len(boilerplate)} kalip):")
        for b in sorted(boilerplate):
            print(f"      - {b[:70]}")

    cleaned = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if stripped and (
            stripped in boilerplate or _SLIDE_NUMBER_PATTERN.match(stripped)
        ):
            cleaned.append("")  # sınır işareti olarak boş satır bırak
            removed += 1
            continue
        # Satır içindeki fazla boşlukları tekille
        cleaned.append(re.sub(r"[ \t]+", " ", stripped))

    if verbose:
        print(f"    {removed} gurultu satiri atildi (toplam {len(lines)} satirdan)")

    out = "\n".join(cleaned)
    # Cümle ortasından kırılmış satırları birleştir (slayt/PDF kaynaklı)
    out = join_wrapped_lines(out)
    # 3+ ardışık boş satırı 2'ye indir
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
