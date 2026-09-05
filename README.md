# Yerel RAG Soru-Cevap Asistanı

Tamamen **çevrim dışı** çalışan bir ders notu soru-cevap asistanı.
Microsoft **Foundry Local** (cihaz üstü LLM) + **SQLite** (vektör deposu) +
**RAG** (Retrieval-Augmented Generation) mimarisi kullanır. Hiçbir internet
bağlantısı veya bulut hesabı gerektirmez.

---

## Hızlı başlangıç

```bash
pip install -r requirements.txt

python main.py ingest        # Belgeleri oku, parçala, vektörle, SQLite'a yaz
streamlit run app.py         # Web arayüzü  (veya:  python main.py chat)
```

Tüm komutlar:

```bash
# Web arayüzü
streamlit run app.py

# Komut satırı
python main.py chat                    # Etkileşimli soru-cevap (akışlı)
python main.py ask "TTL kaç bittir?"   # Tek soru
python main.py chat --fast             # Hız modu: küçük model (~35 sn)
python main.py chat --no-stream        # Akışı kapat
python main.py info                    # Veri tabanı durumu
python main.py ingest                  # Belgeleri yeniden indeksle

# Testler
python tests/test_units.py             # Birim testler (~3 sn, model yüklemez)
python tests/test_rag.py --retrieval   # Arama testleri (~60 sn)
python tests/test_rag.py --fast        # Tam testler, hızlı model (~12 dk)
python tests/test_rag.py               # Tam testler, kaliteli model (~30 dk)
```

> **Cevap süresi:** Bu makinede soru başına ~35 sn (hız modu) veya ~90 sn
> (kalite modu). Cevap **akış hâlinde** yazıldığı için ilk kelimeler birkaç
> saniyede görünür. Aynı soru tekrar sorulursa önbellekten **anında** döner.
> Ayrıntı: "Bilinen kısıtlar" bölümü.

---

## Hangi dosyada ne var?

```
rag_project/
├── SUNUM.md                DEMO VE SUNUM REHBERİ
│                           Kontrol listesi, demo senaryosu, muhtemel sorular
├── app.py                  WEB ARAYÜZÜ (Streamlit)
│                           Akışlı cevap, kaynak kartları, skor göstergeleri
├── main.py                 KOMUT SATIRI ARAYÜZÜ
│                           ingest / chat / ask / info komutlarını yönetir
├── config.py               TÜM AYARLAR burada. Başka dosyada sabit değer yok.
│                           Model adları, chunk boyutu, eşik değerleri, bellek ayarları
├── requirements.txt        Python bağımlılıkları
│
├── src/
│   ├── text_utils.py       BELGE TEMİZLEME
│   │                       PDF'ten gelen bozuk semboller, tekrar eden slayt
│   │                       footer'ları ve sayfa numaralarını ayıklar
│   │
│   ├── chunker.py          PARÇALAMA (CHUNKING)
│   │                       Metni başlık hiyerarşisine saygı göstererek
│   │                       ~80 kelimelik anlamlı parçalara böler
│   │
│   ├── database.py         SQLITE KATMANI
│   │                       Şema, chunk yazma/okuma, embedding BLOB dönüşümü,
│   │                       meta tablosu (hangi modelle indekslendi)
│   │
│   ├── foundry_client.py   MODEL YÖNETİMİ
│   │                       Foundry Local model yükleme, varyant seçimi,
│   │                       yedekleme zinciri, düşük bellek modu
│   │
│   ├── ingest.py           VERİ AKTARIM HATTI
│   │                       docs/*.txt -> temizle -> parçala -> vektörle -> SQLite
│   │
│   ├── retriever.py        ARAMA (RETRIEVAL)
│   │                       Hibrit arama: kosinüs benzerliği + IDF ağırlıklı
│   │                       anahtar kelime eşleşmesi
│   │
│   ├── generator.py        CEVAP ÜRETİMİ
│   │                       Prompt tasarımı, karakter bütçesi, tekrar eleme,
│   │                       akışlı üretim, prompt sızıntılarını temizleme
│   │
│   └── pipeline.py         BORU HATTI
│                           answer_query(): arama + eşik + üretim + önbellek
│
├── tests/
│   ├── test_units.py       BİRİM TESTLERİ (model yüklemeden, saniyeler)
│   ├── test_questions.py   Test soru bankası (cevaplanabilir / cevaplanamaz / uç durum)
│   └── test_rag.py         Test koşucusu (arama modu ve tam mod)
│
├── docs/                   BİLGİ TABANI (.txt ders notları)
│   ├── bilgisayarağları.txt   Ağ katmanı, IP, anahtarlama, yönlendirme
│   ├── işletimsistemi.txt     CPU Scheduling (FCFS, SJF, RR, gerçek zamanlı)
│   ├── işletimsistemi2.txt    Deadlock + bellek yönetimi
│   └── sanalbellek.txt        Sayfa değiştirme, thrashing, working set
│
└── db/rag.db               SQLite veri tabanı (ingest üretir, 107 chunk)
```

Yeni belge eklemek için `docs/` klasörüne `.txt` koy ve
`python main.py ingest` çalıştır. Şema veya belge seti değişirse veri tabanı
otomatik yeniden kurulur.

---

## Mimari akış

```
                         SORU
                          │
                          ▼
              ┌───────────────────────┐
              │ retriever.py          │
              │  soruyu vektöre çevir │  <- qwen3-embedding-0.6b
              │  (Instruct: ... öneki)│
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │ HİBRİT ARAMA          │      ┌──────────────┐
              │ 0.7 x kosinüs         │ <--- │ db/rag.db    │
              │ 0.3 x anahtar kelime  │      │ 107 chunk    │
              │ -> en iyi 8 aday      │      │ 1024-boyutlu │
              └───────────┬───────────┘      └──────────────┘
                          ▼
              ┌───────────────────────┐
              │ EŞİK KONTROLÜ (0.45)  │  --- düşükse --->  "Bu bilgi elimdeki
              │ pipeline.py           │                     dokümanlarda yok."
              └───────────┬───────────┘                     (model çağrılmaz)
                          ▼
              ┌───────────────────────┐
              │ BÜTÇE SEÇİMİ          │  8 adaydan 1300 karaktere
              │ skor sırasına göre    │  sığanlar (~2-3 chunk)
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │ generator.py          │
              │  tekrar edeni ele     │  <- phi-3.5-mini
              │  belge sırasına diz   │     (yoksa qwen2.5-1.5b)
              │  prompt kur, üret     │
              └───────────┬───────────┘
                          ▼
                        CEVAP
```

**Neden iki ayrı sıralama?** Bütçe seçimi **skor** sırasına göre yapılır (en
alakalı chunk mutlaka girsin), ama prompt'a yazarken **belge** sırası
kullanılır (model metni akış hâlinde okusun). Bu ikisi karıştırılırsa en
yüksek skorlu chunk bütçe dışında kalabiliyor — bir kez yaşandı ve
"Link-State" sorusuna "Flooding" cevabı verilmesine yol açtı.

---

## Nasıl çalışıyor? (kısa teknik özet)

### 1. Veri aktarımı (`python main.py ingest`)

1. `docs/*.txt` okunur.
2. **Temizlenir** — PDF'ten kopyalanan belgelerde tekrar eden slayt
   footer'ları ve bozuk sembol karakterleri var. `işletimsistemi.txt`
   dosyasının 382 satırının **104'ü çöptü** (%27); bunlar embedding
   vektörünü bozuyordu.
3. **Parçalanır** — başlık hiyerarşisi korunarak ~80 kelimelik chunk'lara
   bölünür. Her chunk'ın başına ait olduğu bölüm başlığı yazılır:
   ```
   [2. IP PROTOKOLÜ VE DATAGRAM YAPISI > Alan Boyut Açıklama]
   TTL 8 bit Datagramın ağda kalabileceği süre (saniye cinsinden)
   ```
   Başlık olmadan bu satır "IP" kelimesini hiç içermezdi ve
   "IP başlığındaki TTL nedir?" sorusuyla eşleşmezdi.
4. **Vektörlenir** — `qwen3-embedding-0.6b` ile 16'lı gruplar hâlinde.
5. **SQLite'a yazılır** — embedding'ler `float32 BLOB` olarak
   (JSON metinden 4 kat küçük, okuma çok daha hızlı).

### 2. Soru-cevap (`python main.py chat`)

1. Soru, `Instruct: ...\nQuery: ...` öneki eklenerek vektöre çevrilir.
   Qwen3 embedding modelleri bu **asimetrik** format için eğitilmiştir.
2. **Hibrit arama** yapılır:
   ```
   skor = 0.7 x kosinüs_benzerliği + 0.3 x anahtar_kelime_skoru
   ```
   Anahtar kelime skoru IDF ağırlıklıdır (nadir terimler daha değerli) ve
   Türkçenin eklemeli yapısı için ilk 6 harf üzerinden eşleşir
   ("yönlendirme" ↔ "yönlendirmenin").
3. En iyi skor **0.45 eşiğinin altındaysa** model hiç çağrılmaz,
   "Bu bilgi elimdeki dokümanlarda yok." cevabı döner.
4. Bütçeye sığan chunk'lar **skor sırasına göre** seçilir, sonra
   **belge sırasına göre** dizilip prompt'a konur.
5. `qwen2.5-1.5b` cevabı üretir.

---

## İlk sürüme göre neler değişti

Proje tek dosyalık bir `query.py` olarak başlamıştı ve bazı sorulara yanlış
cevap veriyordu. Bulunan 8 sorun ve düzeltmeleri:

| # | Sorun | Neden yanlış cevap üretiyordu | Düzeltme |
|---|---|---|---|
| 1 | Belgelerde PDF çöpü | `işletimsistemi.txt`'nin 382 satırının 104'ü tekrar eden slayt footer'ı ve bozuk sembol. Alakasız iki chunk aynı footer'ı taşıdığı için "benzer" görünüyordu | `text_utils.py` temizliyor |
| 2 | `frequency_penalty=0.4` | Modelin **aynı kelimeyi tekrar etmesini cezalandırıyordu**. RAG'de tam tersi istenir: model bağlamdaki terimleri aynen tekrarlamalı. Bu ayar modeli eş anlamlı uydurmaya itiyordu | Kaldırıldı |
| 3 | Chunk'lar çok büyük | 300 kelime = tek chunk 4 konu birden. Toplam 18 chunk vardı | 80 kelime, 76 chunk (ölçümle) |
| 4 | `temperature=0.5` | Bilgi çıkarma işinde yaratıcılık istenmez | 0.1 |
| 5 | Model çok küçük | `qwen2.5-1.5b` Türkçede zayıf | `phi-3.5-mini` (bellek çözülünce mümkün oldu) |
| 6 | Qwen3 query öneki yok | `qwen3-embedding` asimetrik arama için eğitildi; sorgular `Instruct: ...\nQuery: ...` formatında gömülmeli. Model soruyu "belge" sanıyordu | Önek eklendi |
| 7 | Anahtar kelime araması yok | "TTL", "IHL", "OSPF" gibi kesin terimler salt vektör aramasıyla kaçıyordu | Hibrit arama (0.7/0.3) |
| 8 | Eşik işe yaramıyordu | 0.35 ham kosinüs. "Karnıyarık tarifi" sorusu 0.411 alıyordu, yani eşiğin **üstünde** — koruma hiç devreye girmiyordu | 0.45 hibrit skor (ölçümle) |

Ayrıca eklendi: SQLite şema göçü, embedding'lerin BLOB olarak saklanması,
toplu (batch) embedding, model yedekleme zinciri, düşük bellek modu, geçici
bellek hatalarında yeniden deneme, tekrar eleme ve üç kademeli test seti.

---

## Hız iyileştirmeleri

Bu makinede üretim yavaş (~35-90 sn). Üç yaklaşım kullanıldı:

### 1. Akışlı üretim (streaming)

Cevap tamamlanmasını beklemek yerine **token token** yazdırılıyor. Toplam
süre aynı ama kullanıcı boş ekrana bakmıyor:

```
ÖNCE:   Soru: TTL nedir?
        [......... 90 saniye sessizlik .........]
        Cevap: 8 bit

SONRA:  Soru: TTL nedir?
        --- kaynaklar (2 sn) ---
        Cevap: 8 bit...   <- birkaç saniyede akmaya başlar
```

Zorluk: `clean_answer()` tam metin ister ama akışta metin parça parça gelir.
İki tamponla çözüldü — baştan 60 karakter (`CEVAP:` gibi etiketler için),
sondan 48 karakter (kaynak kuyruğu için). Aradaki her şey anında yayınlanır.
Birim testler **ekrana akan metin ile döndürülen metnin aynı olduğunu**
doğruluyor; farklı olsa kullanıcı ekranda başka, kayıtta başka şey görürdü.

### 2. Cevap önbelleği

Aynı soru tekrar sorulunca üretim tamamen atlanıyor: **45 sn → 0.0 sn**.
Sunumda aynı soruyu tekrar sormak çok yaygın. Oturum içi tutulur.

### 3. Hız modu (`--fast`)

Model seçimini tersine çevirir. Ölçülen takas:

| Mod | Model | Süre | Doğruluk (hedefli test) |
|---|---|---|---|
| Varsayılan | phi-3.5-mini (3.8B) | ~90 sn | 4/5 |
| `--fast` | qwen2.5-1.5b | ~35 sn | 3/5 |

Ayrıca **eşik koruması** sayesinde alakasız sorular modele hiç gitmiyor:
2-6 saniyede "dokümanlarda yok" cevabı dönüyor.

---

## Tasarım kararları ve neden böyle

| Karar | Değer | Gerekçe |
|---|---|---|
| Chunk boyutu | 80 kelime | **Ölçümle** seçildi; bağlam bütçesine göre belirlenmeli (aşağıya bak) |
| Chunk overlap | 25 kelime | Sınırda kesilen bilginin iki chunk'ta da bulunması için |
| TOP_K | 8 | Maliyeti yok (bütçe kırpıyor), "hiç bulunamıyor" vakasını sıfırladı |
| Hibrit ağırlık | 0.7 vektör / 0.3 kelime | Salt vektör "TTL", "IHL", "OSPF" gibi kesin terimleri kaçırıyor |
| Benzerlik eşiği | 0.45 | **Ölçümle** belirlendi (aşağıya bak), tahminle değil |
| Bağlam bütçesi | 1300 karakter | **Ölçümle**; büyütmek isabeti artırmıyor, üstelik bellek duvarına yaklaşıyor |
| Sıcaklık | 0.1 | Bilgi çıkarma işi, yaratıcılık istenmiyor |
| frequency_penalty | **kullanılmıyor** | Modelin bağlamdaki terimleri aynen tekrar etmesini istiyoruz |
| Embedding saklama | float32 BLOB | JSON metinden 4 kat küçük ve hızlı |

### Eşik değeri nasıl belirlendi?

Tahmin etmek yerine ölçtük. 12 "belgede olan" ve 6 "belgede olmayan" soruyla
arama skorları toplandı:

| Grup | En düşük | Ortalama | En yüksek |
|---|---|---|---|
| Cevabı belgelerde **olan** | 0.593 | 0.688 | 0.810 |
| Cevabı belgelerde **olmayan** | 0.208 | 0.260 | 0.326 |

İki grup arasında **0.326 – 0.593** aralığında temiz bir boşluk var.
**0.45** bu boşluğun ortasında.

---

## Bilinen kısıtlar

### 1. Bellek duvarı (bu makineye özgü)

Bu makinede 16 GB RAM var ama tipik olarak sadece ~3.7-4.8 GB'ı boş.

**a) İki model aynı anda belleğe sığmıyor.** Ölçüm:

```
başlangıç              3.70 GB boş
+ embedding (0.6B)     3.06 GB boş
+ sohbet    (1.5B)     1.82 GB boş
-> embedding çalıştırma denemesi: bad allocation
```

Çözüm: **düşük bellek modu**. Embedding modeli sadece soruyu vektöre
çevirirken gerekli; üretim başlamadan bellekten atılıyor, sonraki soruda
~3.5 sn'de geri yükleniyor. Hangisinin taşınacağı yükleme süresine göre
seçildi (embedding 8.8 sn, sohbet 3.0 sn ilk yükleme).

**Bu değişikliğin beklenmedik faydası:** Phi-3.5-mini başta hiç
yüklenemiyordu ("bad allocation" — 4-6 GB istiyor). Embedding modeli
üretim sırasında bellekten atılınca **yer açıldı ve Phi çalışır hâle
geldi**. PDF planının önerdiği model artık kullanılabiliyor ve kalite
farkı ölçüldü:

| Model | Hedefli test | Soru başına süre |
|---|---|---|
| **phi-3.5-mini (3.8B)** | **4/5** | ~75-105 sn |
| qwen2.5-1.5b | 3/5 | ~30-45 sn |

Phi varsayılan; `config.py` içindeki `CHAT_MODEL_CANDIDATES` sırasını ters
çevirirsen hız kazanır, kaliteden verirsin. Phi yüklenemezse sistem
otomatik olarak qwen'e düşer (yedekleme zinciri).

**b) Prompt uzunluğu sınırlı.** Ölçüm (temiz süreçte kademeli uzatarak):

| Prompt boyutu | Sonuç |
|---|---|
| ~1700 karakter | çalışıyor (33 sn) |
| ~2294 karakter | çalışıyor (41 sn) |
| ~2494 karakter | `bad allocation`, çöküyor |

Sebep: ONNX Runtime, `lm_head` çıktısı için
`(token_sayısı × 152.000 kelime dağarcığı)` boyutunda **tek parça** bellek
ayırıyor. ~1100 token için bu ~690 MB bitişik blok demektir; parçalanmış
bellekte bulunamıyor.

Çözüm: `MAX_CONTEXT_CHARS = 1300` bütçesi.

RAM'i bol bir makinede `config.py` içinde şunları açabilirsin:
```python
LOW_MEMORY_MODE = False     # modeller bellekte kalsın (çok daha hızlı)
MAX_CONTEXT_CHARS = 6000    # daha fazla bağlam
```

### 2. Yanıt süresi

PDF planı ~1-3 saniye hedefliyor. Bu makinede ölçülen:

| Durum | Süre |
|---|---|
| Alakasız soru (eşik koruması, model çağrılmaz) | **2-6 sn** |
| Aynı soru tekrar (önbellek) | **0.0 sn** |
| Hız modu (`--fast`, qwen2.5-1.5b) | ~35 sn |
| Kalite modu (phi-3.5-mini) | ~90 sn |

Akış sayesinde **ilk kelimeler birkaç saniyede** görünür; kullanıcı tam
süreyi boş ekranda beklemez.

Boş RAM 4 GB'ın altına düştüğünde bellek takası başlıyor ve tek bir soru
**30 dakikaya** kadar çıkabiliyor (ölçüldü: 1885 sn ve 2664 sn). Tarayıcı
sekmelerini kapatmak bunu belirgin şekilde düzeltiyor.

Sebepler: CPU çıkarımı (kullanılabilir GPU yok), düşük bellek modundaki
model yükleme/boşaltma döngüsü, bellek baskısı altında yavaşlayan çıkarım.
Arama katmanı hızlı (~2 sn); süreyi alan tamamen LLM üretimi.

Alakasız sorular **2 saniyede** cevaplanıyor, çünkü eşik koruması modeli
hiç çağırmıyor.

### 3. Ölçekleme

Tüm vektörler belleğe okunup kaba kuvvetle karşılaştırılıyor. 56 chunk için
bu tamamen yeterli. Binlerce belgede gerçek bir vektör veri tabanı
(FAISS, Chroma, `sqlite-vec`) gerekir — PDF planında da bu not ediliyor.

---

## Testler

Üç kademe var; hızlıdan yavaşa doğru:

### 1. Birim testleri — `python tests/test_units.py` (~3 sn)

Model yüklemeden saf Python mantığını doğrular: gürültü temizleme, satır
birleştirme, başlık sınıflandırma, Türkçe tokenizasyon, IDF skorlama,
kosinüs benzerliği, karakter bütçesi, tekrar eleme, **akışlı üretim**,
çıktı temizleme.

```
SONUC: 48/48
```

Her kod değişikliğinden sonra bunu koş — bedava ve anında.

### 2. Arama testleri — `python tests/test_rag.py --retrieval` (~60 sn)

Sohbet modeli yüklenmez, sadece arama katmanı ölçülür. Üç şeyi ayrı ayrı
kontrol eder:

```
Dogru belge                        18/18   dogru dosya ilk siralarda mi
Baglam isabeti                     18/18   cevabin METNI modele ulasiyor mu
Esik korumasi                        5/5   alakasiz sorular esigin altinda mi
TOPLAM                             41/41
```

**Bağlam isabeti** en kritik metrik: bütçe kırpmasından *sonra* cevabın
metni hâlâ bağlamda mı? Bu 12/12 değilse model doğru cevap veremez, çünkü
bilgi önüne hiç konmamış olur.

### 3. Tam testler — `python tests/test_rag.py` (~25 dk)

Cevap üretimi dahil, uçtan uca. 18 cevaplanabilir + 5 alakasız + 3 uç durum.

```
Tam: belgede olan                  18/18
Tam: belgede olmayan                5/5     <- hic halusinasyon yok
Uc durumlar                         3/3
TOPLAM                             26/26
```

**Gelişim:**

```
Cevaplanabilir sorular:  12/18  ->  17/18  ->  18/18
                           ^        ^          ^
                           |        |          +-- temizleme hatası düzeltildi
                           |        +------------- chunker + alıştırma filtresi
                           +---------------------- başlangıç
```

> **Dürüstlük notu:** 26/26, *bu 18 soruluk test setinde* hata görülmediği
> anlamına gelir — sistemin hiç hata yapmadığı anlamına değil. Test seti
> proje kapsamında yazıldı ve dört belgeyi de kapsıyor, ama sonlu.

**Ölçüm koşulları:** 7.1 GB boş RAM, düşük bellek modu kapalı, soru başına
20-40 saniye. Bellek daraldığında (4 GB altı) süreler 70-130 saniyeye
çıkıyor ve Foundry Local ara sıra geçici `Operation was cancelled` hatası
veriyor — bu koşuda hiç görülmedi.

**Neden üç kademe?** Arama hatası ile üretim hatası farklı şeylerdir.
Arama 17/17, üretim 8/12 çıkıyorsa sorun net: doğru chunk bulunuyor ama
1.5B model onu doğru kullanamıyor. Ayrı ölçmesen bunu bilemezsin.

### Hata analizi: ölçüm testi nasıl yanılttı

Bu projedeki en öğretici bölüm burası.

**İlk teşhis (yanlıştı):** Başarısız 4 soruya bakınca hepsinde model prompt'u
tekrarlıyordu. "Demek ki sorun prompt tasarımında" diye düşünüldü ve 2 farklı
prompt varyantı A/B testine sokuldu. Sonuç: **ikisi de 0/4**. Prompt'u
değiştirmek hiçbir şeyi düzeltmedi.

**Asıl teşhis:** Modele giden bağlamın içine bakılınca gerçek sebep çıktı —
**cevap zaten bağlamda yoktu.**

| Soru | Cevap bağlamda var mıydı? | Gerçek sorun |
|---|---|---|
| Sanal devre örnek protokoller | ✅ "ATM, X.25 örnek." vardı | Model hatası |
| Foundry Local GPU gerektirir mi | ✅ "GPU gerektirmez" vardı | Model hatası |
| TTL kaç bit | ❌ Tablonun kuyruğu gelmişti | **Arama hatası** |
| Second-chance diğer adı | ❌ "Clock" hiç yoktu | **Arama hatası** |

**Test neden yanılttı?** Arama testi sadece *"doğru BELGE ilk sıralara geldi
mi?"* diye kontrol ediyordu ve 12/12 geçiyordu. Ama doğru belgenin **yanlış
parçası** gelebiliyordu. Test yeşil yanıyor, sistem yanlış cevap veriyordu.

Bunun üzerine `expect_context` alanı eklendi: *"cevabın METNİ bağlama girdi
mi?"*. Bu ölçümle gerçek tablo ortaya çıktı:

```
Doğru metin ilk 5 sonuç içinde  : 11/12   <- arama sıralaması iyi
Doğru metin BAĞLAMA giriyor     :  8/12   <- asıl darboğaz
Hiç bulunamıyor                 :  1/12
```

Yani 3 soruda doğru chunk bulunuyordu ama **1300 karakterlik bütçeye
sığmadığı için eleniyordu**. 120 kelimelik chunk'lar (~600-900 karakter) bu
bütçeye sadece 2 tane sığıyordu.

**Yapılan düzeltme.** Chunk boyutu bütçeye göre yeniden seçildi. 4 boyut
ölçüldü (ölçüt: bütçe kırpmasından sonra cevabın metni bağlamda kaldı mı):

| boyut / overlap | chunk | ort. karakter | bağlam isabeti |
|---|---|---|---|
| 120 / 30 (eski) | 61 | 504 | 9/12 |
| **80 / 25** | **76** | **428** | **11/12** |
| 60 / 20 | 92 | 359 | 10/12 |
| 45 / 15 | 113 | 294 | 11/12 |

Ayrıca `TOP_K` 5'ten 8'e çıkarıldı — maliyeti yok (bütçe zaten kırpıyor),
ama "hiç bulunamıyor" vakasını sıfırladı.

Sonuç: **bağlam isabeti 8/12 → 12/12.**

### Model, cevabı değil komşu chunk'ın BAŞLIĞINI kopyalıyordu

Üç soru yanlış cevaplanıyordu. Modele giden bağlama bakınca ortak desen
çıktı: **doğru cevap her üçünde de 1. chunk'ta duruyordu**, ama model
komşu chunk'ın *başlığını* cevap sanıyordu.

| Soru | Bağlamda ne vardı | Model ne dedi |
|---|---|---|
| "Second-chance'in diğer adı?" | *"**Clock** (saat) algoritması olarak da bilinir"* | "Enhanced Second-Chance" ← 2. chunk'ın başlığı |
| "En kolay değiştirilen sınıf?" | *"**1 (En iyi)** ... değiştirilecek en iyi page"* | "4 (En kötü)" ← 3. chunk'ın başlığı |

İki kök sebep bulundu ve düzeltildi:

**1. Chunker tablo hücrelerini başlık sanıyordu.**
`2. Enhanced Second-Chance Algoritması > 4 (En kötü)` — buradaki
"4 (En kötü)" bir tablo hücresi, başlık değil. Kural eklendi: rakamla
başlayan bir satır ancak `N.` veya `N)` kalıbına uyuyorsa başlıktır.
Böylece `1) Temel Kavramlar` başlık kalır, `4 (En kötü)` gövdeye iner.

**2. Boşluk doldurma alıştırmaları bağlamı işgal ediyordu.**
Ders notlarındaki sınav provası bölümleri şöyle:
```
1. Second-chance algoritması ___________ algoritması olarak da bilinir.
```
Bu satır sorunun kendisini içeriyor ama **cevabı içermiyor**. Arama bunu
çok alakalı buluyor (soruyla neredeyse aynı kelimeler) ve bağlamın değerli
yerini kaplıyor. `is_low_information()` ile eleniyor.

Dikkat: **cevap anahtarları elenmiyor.** `1. Clock 2. ikinci şans / 0`
satırlarında alt çizgi yok, dolayısıyla filtre onlara dokunmuyor — ki
onlar gerçekten değerli.

Sonuç: 110 → 107 chunk (3 gürültü chunk'ı elendi), arama testleri 41/41'de
kaldı.

### Yineleme (döngü) koruması

1.5B'lik modeller bazen aynı ifadeyi durmadan tekrarlıyor. Gerçek çıktı:

> "Thrashing, bir sistem üzerindeki çoklu süreçlerin **birbirleriyle
> birbirine sahip olması nedeniyle**, bu süreçlerin **birbirleriyle
> birbirine sahip olması nedeniyle**, sistem tarafından hafızda saklanmaya
> çalışılan belirli bir sayının aşılması nedeniyle oluşan bir durumdur.
> Bu durum, bir sistem üzerinde çoklu süreçlerin **birbirleriyle
> birbirine sahip olması** nedeni ile..."

**Neden `frequency_penalty` kullanmıyoruz?** Kullanabilirdik, ama o ayar
modelin bağlamdaki *terimleri* (TTL, Dijkstra, referans biti) tekrar
etmesini de cezalandırıyor — RAG'de tam istemediğimiz şey. Nitekim projenin
ilk hâlinde `frequency_penalty=0.4` vardı ve yanlış cevapların
sebeplerinden biriydi.

Bunun yerine üretimi serbest bırakıp **çıktıda döngüyü tespit edip
kesiyoruz** (`trim_repetition()`): aynı 6 kelimelik dizi ikiden fazla
geçerse oradan kırpılıyor. Sonuç: terim tekrarı serbest, cümle döngüsü
engelli. Birim testler ikisini de doğruluyor.

### Tekrar eleme (deduplication)

Chunk overlap (25 kelime) kasıtlı: sınırda kesilen bilgi iki chunk'ta da
bulunsun diye. Ama arama komşu iki chunk'ı birden getirdiğinde bütçenin
büyük kısmı **aynı metnin ikinci kopyasına** gidiyordu.

Somut vaka — "Foundry Local GPU gerektirir mi?" sorusunda seçilen iki
chunk'ın ikisi de şu cümleleri içeriyordu:

```
"Bulut hesabı veya harici bir GPU gerektirmez; ..."
"RAG (Retrieval-Augmented Generation): ..."
```

1300 karakterlik bütçenin ~%40'ı tekrardı. `select_within_budget()` artık
karakter bazlı örtüşme oranına bakıyor (%50 üstü = tekrar) ve o yeri farklı
bilgi taşıyan başka bir chunk'a veriyor.

### Ders 1: bütçeyi büyütmek her zaman iyileştirmez

| bütçe | bağlam isabeti | en uzun prompt |
|---|---|---|
| **1300** | **11/12** | **1763** |
| 1500 | 10/12 | 1910 |
| 1700 | 10/12 | 2144 |
| 1900 | 11/12 | 2335 (bellek duvarının üstünde) |

Sebep: bütçe seçici "sığmayanı atla, sonrakine bak" mantığıyla çalışıyor.
Daha büyük bütçe, **uzun** bir chunk'ı içeri alıp arkasından gelen **iki
kısa** chunk'ı dışarıda bırakabiliyor. Büyük bütçenin seçimi küçüğünkinin
üst kümesi değil.

### Ders 2: yanlış ölçen test, yanlış yön verir

Bu proje boyunca **altı** ölçüm kusuru yakalandı. Hepsinde test "KALDI"
diyordu ama sistem aslında doğru çalışıyordu (ya da tersi):

| # | Kusur | Sonuç |
|---|---|---|
| 1 | "Doğru **belge** geldi mi" ölçüsü | 12/12 geçiyordu ama doğru belgenin *yanlış parçası* geliyordu |
| 2 | `"8" in "128 oktettir"` | Alt dizge araması yanlış cevabı doğru saydı. `\b` kelime sınırı eklendi |
| 3 | Tek ifade beklemek (IHL) | Bilgi belgede iki ifadeyle geçiyor, test birini arıyordu |
| 4 | `(0,0)` yerine tablo biçimi `0 0` | Cevap bağlamdaydı ama farklı yazımla |
| 5 | Model `ÇEVAP:` yazdı (Ç ile) | Regex sadece `CEVAP` arıyordu |
| 6 | "Sınıf 1" cevabı yanlış sayıldı | Belgedeki tabloda `(0,0)` sınıfının **numarası 1** — cevap doğruydu |
| 7 | **Temizleyici doğru cevabı sildi** | Aşağıda ayrı başlık — tek "aktif zarar veren" kusur |
| 8 | Türkçe ekler kaçırıldı | Cevapta "belleğe"/"korumak" vardı, test "bellek"/"koruma" arıyordu |

**8. kusur özellikle ironik:** Türkçenin eklemeli yapısı sorununu
*retriever*'da ön-ek eşleştirmesiyle çözmüştüm, ama aynı sorunun *testte*
de olduğunu görmemiştim. `bellek → belleğe` (ünsüz yumuşaması) ve
`koruma → korumak` (ek) eşleşmeleri kaçıyordu. Test artık uzun anahtar
kelimelerde ilk 5 harfe göre eşleştiriyor — ama sayısal anahtarlarda
(`"8"`) katı kelime sınırı korunuyor, yoksa 2. kusur geri gelirdi.

### 7. kusur: temizleme kodu doğru cevapları yok ediyordu

Diğer yedisi *yanlış ölçüyordu*; bu **aktif olarak zarar veriyordu.**

Model doğru cevabı üretmişti:

```
"Priority scheduling'de starvation sorunu aygıt ile çözülür: Aging"
```

Ama `clean_answer()` bu satırı tamamen sildi, geriye `"Cevabın numarası: [1]"`
kaldı. Sebep: soru tekrarını ayıklayan kod *"satır sorunun ilk 40 karakteriyle
başlıyorsa sil"* diyordu. Model soruyu **yeniden ifade ederek cevaplamıştı** —
Türkçede son derece doğal bir biçim.

Yeni kural: satır sorunun **tamamıyla** başlamalı **ve** geriye 15 karakterden
az bir kuyruk kalmalı. Soruyu tekrarlayıp ardından bilgi veren satırlar
korunuyor. Bir regresyon testi bu davranışı kilitliyor.

**Ders:** Çıktı temizleme kodu sessizce zarar verebilir. Ham model çıktısını
temizlenmiş hâliyle yan yana koymadan "model yanlış cevap verdi" denmemeli.

**Alınan ders:** Testin *geçmesi* değil, *doğru şeyi ölçmesi* önemli.
Yanlış ölçen bir metriği iyileştirmeye çalışmak zaman kaybıdır — nitekim
prompt'u iyileştirmek için yapılan A/B testi (2 varyant) **0/4** verdi,
çünkü sorun prompt'ta değildi, doğru chunk bağlama hiç girmiyordu.

Pratik sonuç: **başarısız her testin TAM çıktısına bakılmalı.** Testin
gösterdiği ilk 60 karakter yanıltıcı olabiliyor.

---

## Bilinen kısıt: konu örtüşen ama cevabı olmayan sorular

Gerçek kullanımda yakalanan en öğretici hata:

```
Soru : "Sanal bellek nedir?"
Cevap: "Bellek belleği, CPU'nun program counter'a göre komutu bellekten
        getirdiği ... sanal bellek olarak tanımlanır."   ← anlamsız
```

**Sebep — model uydurmadı, yanlış kaynağı doğru sandı:**

| Terim | Korpusta durumu |
|---|---|
| "sanal bellek" | **0 kez geçiyor** |
| "sanal" | sadece **"Sanal Devre"** olarak, hem de **ağ belgesinde** |

Dosya adı `sanalbellek.txt` ama içeriği sayfa değiştirme, thrashing, frame
tahsisi — kavramın tanımı hiç yok. Arama, ağ belgesindeki "Sanal Devre"
bölümünü getirdi (skor 0.519) ve model iki farklı konuyu birleştirdi.

**Neden kolayca düzeltilemiyor:**

```
Cevaplanabilir soruların en düşük skoru : 0.528
"Sanal bellek nedir?"                   : 0.519
Marj                                    : 0.009
```

Eşiği bu tuzağı kesecek kadar yükseltmek, meşru soruları reddetme riskini
getiriyor. Üstelik skor sorunun yazımına göre 0.498–0.519 arasında
oynuyor — bu kadar ince ayara güvenilmez.

**Denenen ve geri alınan iki çözüm** (ikisi de kodda gerekçesiyle duruyor):

1. *Kelime skorlamasına kısmi eşleşme cezası.* Tuzağı 0.498→0.431'e
   düşürdü ama meşru soruları da aynı oranda düşürdü (0.528→0.460).
   Ayrım boşluğu 0.030'dan 0.029'a — **hiç iyileşme yok.**
2. *Prompt'a "konu aynı ama cevap yoksa reddet" kuralı.* Model yine
   uydurdu ("sanal bellek, bir sanal ağ üzerinde kullanılan bellek
   tipidir"), üstelik prompt uzadı.

**Ders:** Bir düzeltmenin hedefi düşürmesi yetmez — hedefi *diğerlerinden
daha çok* düşürmesi gerekir. Mutlak değil, **göreli** iyileşmeye bakılmalı.

**Pratikte hafifletme:** Arayüz her cevapta kaynakları gösteriyor. Bu
soruda kullanıcı, cevabın `bilgisayarağları.txt`'ten geldiğini görüp
güvenmemesi gerektiğini anlayabiliyor. Şeffaflık, mükemmel olmayan bir
sistemde en gerçekçi savunma.

---

## Sonraki adımlar

Test setindeki 18 sorunun tamamı doğru cevaplanıyor. Bu, sistemin hatasız
olduğu anlamına gelmez — **ölçtüğümüz kapsamda** hata görülmediği anlamına
gelir. Kapsamı büyütmek en doğru bir sonraki adım olurdu.

Son üç hata şu düzeltmelerle çözüldü (hepsi *veri hazırlama* ve *çıktı
işleme* tarafındaydı, model değiştirilmedi):

| Hata | Kök sebep | Düzeltme |
|---|---|---|
| "Enhanced Second-Chance" (doğrusu Clock) | Komşu chunk'ın başlığı dikkat dağıtıyordu | Alıştırma chunk'ları elendi |
| "4 (En kötü)" (doğrusu Sınıf 1) | Tablo hücresi başlık sanılmıştı | Chunker kuralı düzeltildi |
| "Cevabın numarası: [1]" (boş cevap) | **Temizleme kodu doğru cevabı siliyordu** | Soru-tekrarı kuralı daraltıldı |

Denenebilecek sonraki adımlar:

0. **Test setini büyütmek** — 18 soru sonlu. Daha fazla ve daha çeşitli
   soru, gerçek doğruluğu daha iyi gösterir.

1. **Daha fazla boş RAM** — en ucuz kazanç. 7 GB boş RAM ile süre 90 sn'den
   20 sn'ye düşüyor ve geçici hatalar büyük ölçüde kayboluyor.
2. **Daha büyük model** — `foundry model download phi-4-reasoning` (10 GB).
3. **Sorgu genişletme** — soruyu embedding'lemeden önce eş anlamlılarla
   zenginleştirmek ("diğer adı" → "alternatif isim, takma ad").
4. **Yeniden sıralama (re-ranking)** — ilk 8 adayı küçük bir cross-encoder
   ile yeniden puanlamak.
5. **Kaynak biçimini düzeltmek** — bazı satırlar iki kuralı birden içeriyor:
   `"q büyük olursa → FCFS gibi davranır q çok küçük olursa → çok fazla
   context switch"`. Ayırıcı olmadığı için küçük modeller yanlış yarısını
   seçebiliyor. RAG kalitesi kaynak kalitesini aşamaz.

---

## Kurulum notları

### DİKKAT: hangi Python ortamı?

Projede boş bir `venv/` klasörü var (içinde sadece `pip` kurulu). Gerçek
paketler **Anaconda** ortamında:

```
Çalışan ortam : C:\Users\afrao\anaconda3\python.exe   (paketler burada)
venv/         : boş, sadece pip
```

VS Code bazen `venv/` klasörünü otomatik seçiyor. O terminalde
`python main.py` çalıştırırsan `No module named numpy` hatası alırsın.
İki çözümden biri:

1. VS Code'da yorumlayıcıyı Anaconda'ya çevir
   (`Ctrl+Shift+P` → *Python: Select Interpreter* → anaconda3),
2. veya paketleri venv'e kur:
   `venv\Scripts\pip install -r requirements.txt`



- **Foundry Local** kurulu ve modeller indirilmiş olmalı:
  ```bash
  foundry model download qwen3-embedding-0.6b
  foundry model download qwen2.5-1.5b
  ```
- Model önbellek klasörü `config.py` içindeki `CACHE_DIR` ile ayarlanır
  (şu an `D:\foundry-cache`).
- Yeni belge eklemek için `docs/` klasörüne `.txt` dosyası koy ve
  `python main.py ingest` komutunu tekrar çalıştır.

---

## Kaynaklar

- [Microsoft Learn — Foundry Local ile RAG uygulaması](https://learn.microsoft.com/azure/ai-foundry/foundry-local/)
- [Tech Community — Building Your First Local RAG Application with Foundry Local](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-your-first-local-rag-application-with-foundry-local/4501968)
- [SQLite resmi sitesi](https://sqlite.org/)
