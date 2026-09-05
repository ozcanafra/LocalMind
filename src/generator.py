"""Üretim (generation) katmanı: bulunan chunk'lardan cevap yazdırır.

PROMPT TASARIMI

Eski prompt kısaydı ve kaynak numarası yoktu. Yeni prompt üç şey ekliyor:

1. NUMARALI KAYNAKLAR
   Her chunk [1], [2] diye numaralanıyor. Model cevabın sonunda hangi
   kaynaktan aldığını belirtebiliyor -> PDF planındaki "kaynak gösterme"
   hedefi karşılanıyor ve cevabı doğrulamak kolaylaşıyor.

2. KESİN KURALLAR
   "Kendi genel bilgini kullanma", "sayı uydurma", "kaynakta yoksa şu cümleyi
   yaz" gibi net ve sayılabilir talimatlar. Belirsiz talimatlar küçük
   modellerde işe yaramıyor.

3. SORU EN SONDA
   Bağlam önce, soru sonra geliyor. Küçük modellerde en son okunan talimat
   en güçlü etkiyi yapar (recency bias). Eski kodda da böyleydi, korundu.
"""

import re

# Kısa tutuldu, çünkü prompt'un her karakteri bellek bütçesinden yiyor
# (config.MAX_CONTEXT_CHARS açıklamasına bak).
#
# 3. VE 4. KURAL NEDEN VAR? (silmeden önce oku)
# İlk sürümde "kaynaklarda cevap yoksa 'bilmiyorum' de" kuralı tek başınaydı
# ve FAZLA BASKIN çıktı: model, cevap bağlamda açıkça dururken bile kaçış
# yolu olarak onu seçiyordu. Somut vaka: "Foundry Local GPU gerektirir mi?"
# sorusunda bağlamda "Bulut hesabı veya harici bir GPU gerektirmez" cümlesi
# İKİ KEZ geçmesine rağmen model "dokümanlarda yok" dedi.
#
# Kritik nokta: alakasız soruları zaten EŞİK KORUMASI engelliyor
# (pipeline.py, skor < 0.45 ise model hiç çağrılmıyor - testte 5/5).
# Yani prompt'taki kaçınma kuralı ikinci savunma hattı; gereğinden baskın
# olması faydadan çok zarar veriyordu.
#
# Ölçüm (5 soruluk hedefli set): yumuşatma qwen2.5-1.5b'yi 2/5 -> 3/5
# yaptı, phi-3.5-mini'de fark yaratmadı (4/5). Zararsız kazanç.
SYSTEM_PROMPT = """Sen bir ders notu asistanısın. SADECE sana verilen kaynaklara dayanarak Türkçe cevap ver.

KURALLAR:
1. Sadece kaynaklardaki bilgiyi kullan, kendi bilgini kullanma, uydurma.
2. Kaynaktaki terim ve sayıları AYNEN kullan.
3. Kaynaklarda soruyu destekleyen bir cümle varsa MUTLAKA cevapla, kaçınma.
4. Evet/hayır sorularında önce net cevabı ver, sonra kaynaktaki cümleyi aktar.
5. Cevabın sonuna kaynak numarasını yaz: [1]
6. Kaynaklarda konuyla ilgili hiçbir bilgi yoksa şunu yaz: "{fallback}"

Kısa ve net cevap ver."""
# NOT: Buraya bir zamanlar şu kural eklenmişti:
#   "Kaynaklar soruyla AYNI KONUDA görünüp de sorulan şeyin cevabını
#    içermiyorsa, benzer bilgiyle cevap UYDURMA"
# Amaç "Sanal bellek nedir?" gibi konu-örtüşmeli ama cevapsız soruları
# reddettirmekti. ÖLÇÜLDÜ, İŞE YARAMADI: model yine cevap uydurdu
# ("sanal bellek, bir sanal ağ üzerinde kullanılan bellek tipidir").
# Üstelik prompt uzadı ve başka cevaplar da bozuldu. Geri alındı.
#
# Bu sınırın gerçek çözümü prompt değil; bkz. README "Bilinen kısıtlar".


def _format_block(index: int, result) -> str:
    """Tek bir chunk'ı numaralı kaynak bloğuna çevirir."""
    heading = result.get("heading")
    title = f"{result['source']} - {heading}" if heading else result["source"]

    # Chunk metninin başında zaten [başlık] satırı var; başlığı yukarıdaki
    # etikete taşıdığımız için gövdeden çıkarıyoruz ki iki kez geçmesin.
    body = result["text"]
    if body.startswith("["):
        body = body.split("\n", 1)[-1]

    return f"[{index}] Kaynak: {title}\n{body.strip()}"


# Bloklar arasındaki "\n\n" ayırıcı
_BLOCK_SEPARATOR_LEN = 2

# Bir aday, seçilmiş bir chunk'la bu oranda örtüşüyorsa tekrar sayılır.
# Ölçüm SATIR SAYISI ile değil KARAKTER ile yapılır: uzun ortak cümleler
# bütçede kısa farklılıklardan çok daha fazla yer kaplar.
#
# 0.5 seçildi çünkü gerçek vakada örtüşme tam olarak buradaydı: "Foundry
# Local" sorusunda seçilen iki chunk 4'er satırdı ve 2 satır ortaktı, ama
# o 2 satır karakterlerin yarısından fazlasıydı.
_DUPLICATE_OVERLAP_RATIO = 0.5


def _content_lines(result):
    """Chunk'ın gövde satırlarını normalize edilmiş küme olarak döndürür."""
    body = result["text"]
    if body.startswith("["):
        body = body.split("\n", 1)[-1]
    return {line.strip().lower() for line in body.split("\n") if len(line.strip()) > 15}


def _is_duplicate(candidate, selected) -> bool:
    """Aday, seçilenlerden biriyle büyük ölçüde aynı metni mi taşıyor?

    NEDEN GEREKLİ?
    Chunk overlap (25 kelime) komşu chunk'ların bir kısmını ortak yapıyor.
    Bu kasıtlı: sınırda kesilen bilgi iki chunk'ta da bulunsun diye. Ama
    arama ikisini birden getirdiğinde bütçenin büyük kısmı TEKRARA gidiyor.

    Gerçek vaka - "Foundry Local GPU gerektirir mi?" sorusunda seçilen iki
    chunk'ın ikisi de şu iki cümleyi içeriyordu:
        "Bulut hesabı veya harici bir GPU gerektirmez; ..."
        "RAG (Retrieval-Augmented Generation): ..."
    Yani 1300 karakterlik bütçenin ~%40'ı aynı metnin ikinci kopyasıydı.
    O yer, farklı bilgi taşıyan başka bir chunk'a gidebilirdi.
    """
    candidate_lines = _content_lines(candidate)
    if not candidate_lines:
        return False

    total_chars = sum(len(line) for line in candidate_lines)
    if total_chars == 0:
        return False

    for chosen in selected:
        shared = candidate_lines & _content_lines(chosen)
        shared_chars = sum(len(line) for line in shared)
        if shared_chars / total_chars >= _DUPLICATE_OVERLAP_RATIO:
            return True
    return False


def select_within_budget(results, max_chars=None):
    """Karakter bütçesine sığan chunk'ları SKOR SIRASINA göre seçer.

    KARAKTER BÜTÇESİ NEDEN VAR?

    Bu makinede prompt uzunluğu sert bir bellek duvarına çarpıyor. Ölçüm
    (temiz süreçte, kademeli uzatarak):

        ~1700 karakter -> OK   (33 sn)
        ~2294 karakter -> OK   (41 sn)
        ~2494 karakter -> "bad allocation", çöküyor

    Sebep: ONNX Runtime, lm_head çıktısı için
    (token_sayısı x kelime_dağarcığı) boyutunda TEK PARÇA bellek ayırıyor.
    qwen2.5'in kelime dağarcığı 152.000; ~1100 token için bu ~690 MB
    BİTİŞİK bellek demek. Boş RAM toplamı yetse bile parçalanmış bellekte
    bu kadar bitişik blok bulunamıyor.

    BU FONKSİYON NEDEN AYRI DURUYOR?
    Bütçe kırpması SKOR sırasına göre yapılmalı (en alakalı chunk mutlaka
    girsin), ama prompt'a yazarken BELGE sırası kullanılmalı (model metni
    akış hâlinde okusun). İkisini tek adımda yaparsan, belge sırasına dizip
    sonra kırpınca en yüksek skorlu chunk bütçe dışında kalabiliyor.

    Bu gerçekten yaşandı: "Link-State en kısa yolu hangi algoritmayla
    hesaplar?" sorusunda doğru chunk (Dijkstra) elendi, model "Flooding"
    diye yanlış cevap verdi. Bu yüzden önce burada seçiyoruz, sonra
    pipeline tarafında belge sırasına diziyoruz.
    """
    if max_chars is None:
        return list(results)

    selected = []
    total = 0
    for r in results:  # skor sırasında geldiği varsayılır
        # Zaten bağlamda olan metni ikinci kez koyma; bütçeyi boşa harcar
        if _is_duplicate(r, selected):
            continue
        length = len(_format_block(len(selected) + 1, r)) + _BLOCK_SEPARATOR_LEN
        if selected and total + length > max_chars:
            continue  # sığmıyor; sonraki daha kısa olabilir, bakmaya devam et
        selected.append(r)
        total += length
    return selected


def format_context(results) -> str:
    """Chunk listesini numaralı kaynak bloğuna çevirir.

    Bütçe kontrolü BURADA YAPILMAZ; select_within_budget() ile önceden
    yapılmış olması beklenir. Tek sorumluluk, tek yer.
    """
    return "\n\n".join(
        _format_block(i, r) for i, r in enumerate(results, start=1)
    )


def build_messages(question: str, results, fallback: str):
    """Chat modeline gönderilecek mesaj listesini hazırlar."""
    context = format_context(results)
    user_message = (
        f"KAYNAKLAR:\n{context}\n\n"
        f"----\n"
        f"SORU: {question}\n"
        f"CEVAP:"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(fallback=fallback)},
        {"role": "user", "content": user_message},
    ]


# Modelin cevabın BAŞINA yapıştırdığı prompt etiketleri.
# Yıldızlar her yerde olabiliyor ("**CEVAP:**", "CEVAP :", "** CEVAP:"),
# bu yüzden \*{0,2} + \s* kalıbını her parçanın arasına koyuyoruz.
# Aksi hâlde "**CEVAP:** CEVAP: ..." girdisinde sadece ilki temizleniyordu.
#
# "ÇEVAP" varyantı da yakalanıyor: model gerçekten "ÇEVAP:" yazdı (Ç ile).
# Türkçe metinle eğitilmiş modellerde bu tür harf kaymaları oluyor.
_LEAD_LEAK = re.compile(
    r"^\s*\*{0,2}\s*([CÇ]EVAP|KAYNAK(LAR)?|SORU|Answer)\s*\*{0,2}\s*:\s*\*{0,2}\s*",
    re.IGNORECASE,
)

# Modelin kaynak başlığını olduğu gibi kopyalaması:
#   "[2] Kaynak: bilgisayarağları.txt - 5. YOL BELİRLEME..."  ->  "[2]"
# Kaynak numarasını korumak istiyoruz ama dosya adı + başlık kuyruğunu değil.
_SOURCE_ECHO = re.compile(
    r"(\[\d+\])\s*Kaynak\s*:[^\n]*", re.IGNORECASE
)

# Cevabın sonuna eklenen "**Kaynak:** ..." bloğu (numara içermeyen hâli)
_TRAILING_SOURCE = re.compile(
    r"\n?\s*(\*\*)?Kaynak(lar)?(\*\*)?\s*:\s*(?!\[)[^\n]*$", re.IGNORECASE
)


# Cevabın başındaki markdown gürültüsü: "**", "- ", "# ", "* "
_LEAD_MARKDOWN = re.compile(r"^\s*(\*\*|##?#?|[-*•])\s*")

# Modelin kaynak başlığını çıplak kopyalaması:
#   "bilgisayarağları.txt - 3. ANAHTARLAMA TEKNİKLERİ > Sanal Devre"
_BARE_SOURCE_LINE = re.compile(r"^\s*\S+\.txt\s*[-–>].*$", re.IGNORECASE | re.MULTILINE)


# Soru tekrarından sonra kalan bu kadar karakter "önemsiz kuyruk" sayılır.
_ECHO_TRAILING_SLACK = 15


def _strip_question_echo(answer: str, question: str) -> str:
    """Cevabın başındaki soru tekrarını siler.

    Küçük modeller sık sık soruyu markdown başlığı olarak yazıp sonra
    cevaplıyor:  "- **Second-chance algoritması hangi bit'e...**\\nReferans biti"
    Soru kısmını atınca geriye asıl cevap kalıyor.

    DİKKAT - BURADA BİR HATA YAPILDI VE DÜZELTİLDİ:
    İlk sürüm "satır, sorunun ilk 40 karakteriyle başlıyorsa sil" diyordu.
    Bu, DOĞRU CEVAPLARI yok etti. Gerçek vaka:

        Soru : "Priority scheduling'de starvation sorunu nasıl çözülür?"
        Cevap: "Priority scheduling'de starvation sorunu Aging ile çözülür"

    Model soruyu yeniden ifade ederek cevaplamış - Türkçede son derece
    doğal bir biçim. İlk 40 karakter aynı olduğu için satır silindi ve
    geriye sadece "Cevabın numarası: [1]" kaldı. Yani doğru cevap çöpe gitti.

    YENİ KURAL: satır sorunun TAMAMIYLA başlamalı VE geriye önemsiz bir
    kuyruk kalmalı. Soruyu tekrarlayıp ARDINDAN bilgi veren satırlar korunur.
    """
    if not question:
        return answer

    q_core = question.strip().rstrip("?").lower()
    if len(q_core) < 12:
        return answer

    lines = answer.split("\n")
    kept = []
    for line in lines:
        probe = _LEAD_MARKDOWN.sub("", line).strip().strip("*").rstrip("?").lower()
        if not kept and probe and probe.startswith(q_core):
            # Sorudan sonra anlamlı bir şey kalmıyorsa bu satır saf tekrardır
            if len(probe) - len(q_core) <= _ECHO_TRAILING_SLACK:
                continue
        kept.append(line)
    return "\n".join(kept).strip() or answer


# Yineleme (döngü) tespiti için ayarlar
_REPEAT_MIN_WORDS = 6      # bu uzunluktaki kelime dizileri kontrol edilir
_REPEAT_MAX_ALLOWED = 2    # aynı dizi bu sayıdan fazla geçerse döngü sayılır


def trim_repetition(text: str) -> str:
    """Küçük modellerin girdiği YİNELEME DÖNGÜSÜNÜ keser.

    SORUN
    1.5B'lik modeller bazen aynı ifadeyi durmadan tekrarlıyor. Gerçek çıktı:

      "Thrashing, bir sistem üzerindeki çoklu süreçlerin birbirleriyle
       birbirine sahip olması nedeniyle, bu süreçlerin birbirleriyle
       birbirine sahip olması nedeniyle, sistem tarafından hafızda
       saklanmaya çalışılan belirli bir sayının aşılması nedeniyle..."

    Aynı 6 kelimelik dizi üç kez geçiyor. Cevap okunamaz hâle geliyor.

    NEDEN frequency_penalty KULLANMIYORUZ?
    Kullanabilirdik ama o ayar modelin bağlamdaki TERİMLERİ (TTL, Dijkstra,
    referans biti) tekrar etmesini de cezalandırıyor - RAG'de tam istemediğimiz
    şey. Nitekim projenin ilk hâlinde frequency_penalty=0.4 vardı ve yanlış
    cevapların sebeplerinden biriydi. Bunun yerine üretimi serbest bırakıp
    çıktıda döngüyü tespit edip kesiyoruz: terim tekrarı serbest, cümle
    döngüsü engelli.
    """
    words = text.split()
    if len(words) < _REPEAT_MIN_WORDS * (_REPEAT_MAX_ALLOWED + 1):
        return text

    seen = {}
    for i in range(len(words) - _REPEAT_MIN_WORDS + 1):
        window = " ".join(words[i:i + _REPEAT_MIN_WORDS]).lower()
        seen[window] = seen.get(window, 0) + 1
        if seen[window] > _REPEAT_MAX_ALLOWED:
            # Döngü başladı: bu pencerenin İLK geçişinden sonrasını at.
            cut = " ".join(words[:i])
            # Yarım kalan cümleyi son noktalama işaretinde bitir
            for mark in (". ", "! ", "? ", ".\n"):
                pos = cut.rfind(mark)
                if pos > len(cut) // 2:
                    return cut[:pos + 1].strip()
            return cut.strip()

    return text


def clean_answer(text: str, question: str = "") -> str:
    """Model çıktısındaki prompt sızıntılarını ve fazla boşluğu temizler.

    1.5B'lik küçük modeller prompt'u cevaba kopyalamaya meyilli. Tam testte
    gözlenen üç desen:
        1. "CEVAP:" etiketini tekrar yazmak
        2. Kaynak başlığını kopyalamak  ("bilgisayarağları.txt - 3. ANAHT...")
        3. Soruyu markdown başlığı olarak tekrar etmek

    Kaynak NUMARASINI ([2]) tutuyoruz çünkü onu bilerek istedik; dosya adı
    ve başlık kuyruğunu atıyoruz.
    """
    if not text:
        return ""
    answer = text.strip()

    # Baştaki "CEVAP:" gibi etiketleri at (bazen üst üste tekrarlanıyor)
    previous = None
    while previous != answer:
        previous = answer
        answer = _LEAD_LEAK.sub("", answer).strip()

    answer = _SOURCE_ECHO.sub(r"\1", answer)
    answer = _TRAILING_SOURCE.sub("", answer)
    answer = _BARE_SOURCE_LINE.sub("", answer).strip()
    answer = _strip_question_echo(answer, question)
    answer = _LEAD_MARKDOWN.sub("", answer).strip()
    answer = trim_repetition(answer)

    # 3+ boş satırı sadeleştir
    return re.sub(r"\n{3,}", "\n\n", answer).strip()


def generate_answer(chat_model, question: str, results, fallback: str) -> str:
    """Chat modelini çağırıp temizlenmiş cevabı döndürür."""
    messages = build_messages(question, results, fallback)
    response = chat_model.complete_chat(messages)
    # Soruyu da veriyoruz ki cevabın başındaki soru tekrarı ayıklanabilsin
    return clean_answer(response.choices[0].message.content, question)


# Akışta baştan kaç karakter tamponlanacak.
# clean_answer() tam metin ister ama akışta metin parça parça gelir.
# Baştaki "CEVAP:" / "**CEVAP:**" gibi etiketleri yakalamak için ilk
# parçaları biriktirip temizledikten sonra yayınlıyoruz.
_STREAM_LEAD_BUFFER = 60

# Sondan kaç karakter geciktirilecek.
# Model bazen cevabın sonuna "**Kaynak:** dosya.txt ..." ekliyor. Bunu
# ancak metnin sonu geldiğinde anlayabiliriz, o yüzden son parçayı
# yayınlamayı geciktiriyoruz. 48 karakter tipik kuyruğu yakalıyor ve
# akış hissini bozmuyor.
_STREAM_TAIL_HOLD = 48


def stream_answer(chat_model, question: str, results, fallback: str, on_text) -> str:
    """Cevabı akış hâlinde üretir; her yeni parçayı on_text(parca) ile bildirir.

    Döner: temizlenmiş TAM cevap metni.

    AKIŞTA TEMİZLİK NASIL YAPILIYOR?
    clean_answer() tam metin üzerinde çalışır, ama akışta metin parça parça
    gelir. İki tamponla çözüyoruz:

      BAŞ  (60 krk) : "CEVAP:" gibi etiketler cevabın başındadır. İlk 60
                      karakteri biriktirip temizledikten sonra yayınlıyoruz.
      SON  (48 krk) : Kaynak kuyruğu ("**Kaynak:** dosya.txt") cevabın
                      sonundadır. Son 48 karakteri elde tutup akış bitince
                      temizleyip yayınlıyoruz.

    Arada kalan her şey ANINDA yayınlanır, yani akış hissi korunur.
    """
    messages = build_messages(question, results, fallback)

    raw_parts = []       # ham metnin tamamı (sonunda temizlemek için)
    emitted = 0          # on_text ile kaç karakter yayınlandı
    lead_done = False
    lead_offset = 0      # temizlik sırasında baştan silinen karakter sayısı
    buffer = ""          # henüz yayınlanmamış metin

    for piece in chat_model.stream_chat(messages):
        raw_parts.append(piece)
        buffer += piece

        if not lead_done:
            if len(buffer) < _STREAM_LEAD_BUFFER:
                continue
            cleaned_lead = _LEAD_LEAK.sub("", buffer).lstrip()
            cleaned_lead = _LEAD_MARKDOWN.sub("", cleaned_lead).lstrip()
            lead_offset = len(buffer) - len(cleaned_lead)
            buffer = cleaned_lead
            lead_done = True

        # Sondan _STREAM_TAIL_HOLD karakteri elde tut, gerisini yayınla
        if len(buffer) > _STREAM_TAIL_HOLD:
            ready = buffer[:-_STREAM_TAIL_HOLD]
            on_text(ready)
            emitted += len(ready)
            buffer = buffer[-_STREAM_TAIL_HOLD:]

    full_clean = clean_answer("".join(raw_parts), question)

    # Akış bitti: temizlenmiş metnin henüz yayınlanmamış kısmını gönder.
    # emitted + lead_offset kadarı zaten ekranda; kalanı tamamlıyoruz.
    remaining = full_clean[emitted:] if emitted <= len(full_clean) else ""
    if remaining:
        on_text(remaining)

    return full_clean
