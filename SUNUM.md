# Sunum ve Demo Rehberi

PDF planının son teslimi: *"Her grup kısa bir demo ve sunum yapacak."*

---

## ⚡ TEK SAYFA HATIRLATMA

> Sunum sırasında elinde tutacağın kısım burası. Gerisi hazırlık için.

**Demo soruları (bu sırayla, hepsi test edildi):**

| # | Soru | Beklenen | Vurgu |
|---|---|---|---|
| 1 | `IP datagramında TTL alanı kaç bittir?` | `8 bit [1]` | Kaynak kartını aç |
| 2 | `Link-State algoritması en kısa yolu hangi algoritmayla hesaplar?` | `Dijkstra algoritması [1]` | 3 skoru göster |
| 3 | `Karnıyarık tarifi verir misin?` | **1.8 sn** ret | **"Model hiç çalışmadı"** |
| 4 | *(1. soruyu tekrar sor)* | **0.0 sn** | Önbellek |
| 5 | `Safe state nedir?` | Uzun cevap | Akışı izlet |

**Ezberlenecek 5 rakam:**
- 4 belge → **107 parça**
- Arama testleri **41/41**, bağlam isabeti **18/18**
- Alakasız soruda uydurma: **0** (5/5 reddetti)
- Eşik **0.45** — cevaplanabilir sorular 0.567+, alakasızlar 0.280−
- Uçtan uca **26/26**

**Bir şey bozulursa:** sol panelden *Hız modu*'nu aç → tekrar sor.

---

## 1. Demo öncesi kontrol listesi (T-15 dakika)

```bash
# 1. BELLEK BOŞALT  <- en kritik adım, atlamma
#    Chrome sekmelerini ve ağır uygulamaları kapat.
#    Ölçüm:  7 GB boş RAM -> soru başına 20 sn
#            4 GB boş RAM -> soru başına 90 sn
#    Dört kat fark. Bunu atlarsan demo çok yavaş olur.

# 2. Doğru Python ortamında mısın?
python -c "import numpy; print('TAMAM')"
#    Hata verirse: Ctrl+Shift+P -> Python: Select Interpreter -> anaconda3

# 3. Veri tabanı yerinde mi?
python main.py info          # "Toplam chunk: 107" görmelisin

# 4. Testleri koş (3 saniye - sunumda göstermeye değer)
python tests/test_units.py   # 58/58

# 5. Uygulamayı aç VE BİR SORU SOR
streamlit run app.py
```

> **5. adım neden önemli?** İlk soru modelleri belleğe yükler, ekstra
> 10-15 saniye sürer. Sunumdan önce bir kez sorarsan canlı demoda ilk
> soru da hızlı gelir.

---

## 2. Canlı demo senaryosu

**Bu beş soru prova edildi, doğru cevap verdikleri ölçüldü.**

Test setimizdeki **18 sorunun 18'i de** doğru cevaplanıyor. Yine de kendi
sorunu eklemek istersen **önce dene** — test setinin dışındaki sorular
ölçülmedi, garanti veremeyiz.

**Yedek sorular** (bunlar da test edildi, doğru cevap veriyorlar):

| Soru | Beklenen cevap |
|---|---|
| `Second-chance algoritmasının diğer adı nedir?` | `Clock (saat) algoritması` |
| `Priority scheduling'de starvation sorunu nasıl çözülür?` | `Aging` |
| `Flooding algoritmasında sonsuz döngü nasıl önlenir?` | `Hop Counter (Atlama Sayacı)...` |
| `IP protokolünün iki temel görevi nedir?` | `Adresleme ve Yönlendirme` |
| `Round-Robin'de time quantum çok büyük seçilirse ne olur?` | `FCFS'ye benzer davranır` |
| `Thrashing nedir?` | Paging'e harcanan zamanın sınırı aşması |

---

### Soru 1 — Temel çalışma ve kaynak gösterme
```
IP datagramında TTL alanı kaç bittir?
```
**Beklenen:** `8 bit` + `[1]`

**Yap:** Kaynak kartını aç, modele giden ham metni göster.

**Söyle:**
> "Cevap doğru. Ama asıl önemli olan şu: model bunu nereden buldu,
> görebiliyoruz. İşte modele giden metin — TTL satırı burada. Yani cevabı
> doğrulayabiliyorum, körlemesine güvenmek zorunda değilim."

---

### Soru 2 — Hibrit arama
```
Link-State algoritması en kısa yolu hangi algoritmayla hesaplar?
```
**Beklenen:** `Dijkstra algoritması [1]`

**Yap:** Kaynak kartındaki üç skoru göster.

**Söyle:**
> "Burada üç skor var. **Vektör skoru** anlamsal benzerlik — 'en kısa yol'
> ile 'shortest path' birbirine yakın çıkar. **Kelime skoru** birebir terim
> eşleşmesi. İkisini `0.7 × vektör + 0.3 × kelime` diye topluyoruz.
>
> Neden ikisi birden? Salt vektör araması 'TTL', 'IHL', 'OSPF' gibi kesin
> terimleri kaçırıyor. Salt kelime araması ise yeniden ifade edilmiş
> soruları kaçırıyor. Ölçtük: bir soruda vektör skoru sadece 0.42'ydi ama
> kelime skoru 1.0 — hibrit olmasa o soru kaybolacaktı."

---

### Soru 3 — Uydurmayı engelleme ⭐ EN ÖNEMLİ
```
Karnıyarık tarifi verir misin?
```
**Beklenen:** **~2 saniyede** `Bu bilgi elimdeki dokümanlarda yok.`

**Söyle:**
> "Dikkat edin — **iki saniye**. Az önceki sorular çok daha uzun sürüyordu.
> Çünkü model **hiç çalıştırılmadı**. Arama skoru eşiğin altında kaldı ve
> sistem soruyu modele göndermeden reddetti.
>
> Bu hem hızlı hem güvenli: model alakasız bağlam görmediği için uydurma
> ihtimali yok. Eşiği tahminle değil ölçümle seçtik: **cevaplanabilir
> soruların skoru 0.567–0.874, alakasızların 0.184–0.280.** Eşiğimiz 0.45,
> tam ortada. Test setimizde 5 alakasız sorunun **5'i de** doğru reddedildi."

---

### Soru 4 — Önbellek
```
(Soru 1'i aynen tekrar sor)
IP datagramında TTL alanı kaç bittir?
```
**Beklenen:** **0.0 saniye**, "önbellekten" notu

**Söyle:**
> "Aynı soru tekrar gelince üretimi tamamen atlıyoruz. Yarım dakika → sıfır."

---

### Soru 5 — Akış (streaming)
```
Safe state nedir?
```
**Beklenen:** Cevap kelime kelime akar

**Söyle:**
> "Toplam süre değişmiyor ama kullanıcı boş ekrana bakmıyor. Yazı akmaya
> başlıyor. Bunu yapmak göründüğü kadar basit değildi: çıktıyı temizleyen
> kodumuz tam metin bekliyordu, akışta ise metin parça parça geliyor.
> Baştan 60, sondan 48 karakterlik tamponla çözdük."

---

## 3. Sunum akışı (~10 dakika)

### Slayt 1 — Problem (1 dk)
> "Ders notlarım var, sınavdan önce 'TTL kaç bit?' diye sormak istiyorum.
> ChatGPT'ye sorsam benim notlarımı bilmiyor — uydurabilir. Üstelik notlarım
> kişisel, internete yüklemek istemiyorum."

**Slayta koy:** Bir ders notu ekran görüntüsü + soru işareti

---

### Slayt 2 — Neden RAG? (1 dk)
> "İki seçenek vardı. Sadece LLM: hızlı ama notlarımı bilmiyor, uydurur.
> RAG: önce notlarımdan ilgili parçayı **bul**, sonra modele **ver**, sonra
> cevap **ürettir**. Sonuç: kaynağı gösterilebilir cevaplar."

**Slayta koy:**
```
Retrieve  ->  Augment  ->  Generate
 (bul)        (besle)      (ürettir)
```

---

### Slayt 3 — Mimari (2 dk)
**Slayta koy:**
```
4 ders notu ─► temizle ─► 107 parçaya böl ─► vektör ─► SQLite
                                                          │
Soru ─► vektör ─► HİBRİT ARAMA ◄──────────────────────────┘
                       │
                  eşik kontrolü ──düşükse──► "bilmiyorum"
                       │                     (model çalışmaz)
                  en iyi parçalar ─► yerel LLM ─► CEVAP
```

**Anlat:** İki teknik detayı vurgula —
1. **Hibrit arama** (yukarıda Soru 2'de anlatılan)
2. **Türkçe sorunu:** *"Türkçe eklemeli bir dil. Soruda 'yönlendirme',
   belgede 'yönlendirmenin'. Tam eşleşme kaçırıyor. İlk 6 harfe göre
   eşleştiriyoruz — kaba ama Türkçede şaşırtıcı derecede etkili."*

---

### Slayt 4 — CANLI DEMO (3 dk)
Yukarıdaki 5 soru. Slayt yok, ekranı paylaş.

---

### Slayt 5 — Ölçüm disiplini ⭐ (2 dk)

**Sunumun en güçlü bölümü burası. Atlamak yok.**

> "Bir noktada 4 soru yanlış cevaplanıyordu. Hepsinde model prompt'u
> tekrarlıyordu, ben de 'sorun prompt tasarımında' diye düşündüm. İki farklı
> prompt yazıp A/B testi yaptım.
>
> Sonuç: **ikisi de 0/4.** Hiçbir şey düzelmedi.
>
> Sonra modele giden metnin içine baktım. Gerçek sebep oradaydı:
> **cevap zaten bağlamda yoktu.**
>
> Testim beni yanıltmıştı. Test *'doğru **belge** ilk sıralara geldi mi?'*
> diye soruyordu ve 12/12 geçiyordu. Ama doğru belgenin **yanlış parçası**
> geliyordu. Test yeşil yanıyordu, sistem yanlış cevap veriyordu."

**Slayta koy:**
```
ESKİ ÖLÇÜT: "doğru BELGE geldi mi?"     ->  12/12  ✓ (yanıltıcı)
YENİ ÖLÇÜT: "cevabın METNİ ulaştı mı?"  ->   8/12  ✗ (gerçek)

Chunk boyutu ölçümle yeniden seçildi    ->  18/18  ✓
```

> "Toplamda **8 ölçüm kusuru** buldum. İki örnek:
>
> Test `"8"` dizgisini arıyordu, model `"128 oktettir"` demişti — yanlış
> cevap, ama `"8"`, `"128"` içinde geçtiği için test **geçti sandı**.
>
> Ve sonuncusu en can sıkıcıydı: **kendi temizleme kodum doğru cevapları
> siliyordu.** Model *'starvation sorunu Aging ile çözülür'* demişti, ben
> bunu 'soru tekrarı' sanıp silmiştim — çünkü model soruyu yeniden ifade
> ederek cevaplamıştı, Türkçede gayet doğal bir biçim."

**Kapanış cümlesi:**
> "Öğrendiğim şey: testin *geçmesi* değil, *doğru şeyi ölçmesi* önemli.
> Ve her başarısız testin **tam çıktısına** bakmak gerekiyor — 8 kusurun
> hepsini ancak öyle buldum."

**Sonuç grafiği — bunu da slayta koy:**
```
Cevaplanabilir sorular:   12/18  ->  17/18  ->  18/18
                            ^        ^          ^
                            |        |          +-- temizleme hatası düzeltildi
                            |        +------------- chunker + alıştırma filtresi
                            +---------------------- başlangıç
```

---

### Slayt 6 — Sonuçlar ve kısıtlar (1 dk)

**Slayta koy:**

| Ölçüm | Sonuç |
|---|---|
| Birim testleri | 58/58 |
| Arama testleri | 41/41 |
| Uçtan uca | **26/26** |
| Alakasız soruda uydurma | **0** |

**Dürüstlük bölümü — bunu söyle:**
> "Test setimizdeki 18 sorunun 18'ini de doğru cevaplıyor. Ama şunu açıkça
> söyleyeyim: bu **kendi yazdığım 18 soruluk test seti**. Sistemin hiç hata
> yapmadığı anlamına gelmiyor, ölçtüğüm kapsamda hata görmediğim anlamına
> geliyor.
>
> Yanıt süresi hedefin altında kaldı: plan 1-3 saniye diyordu, bizde 20-40
> saniye. Sebebi CPU üzerinde çıkarım ve sınırlı RAM. Bellek boşken 20,
> doluyken 90 saniyeye çıkıyor — bunu da ölçtük."

---

## 4. Demo sırasında bir şey bozulursa

| Belirti | Ne yap |
|---|---|
| Çok yavaş (>2 dk) | Sol panelden **Hız modu**'nu aç, soruyu tekrar sor |
| `Operation was cancelled` | Geçici Foundry hatası. Soruyu tekrar sor (kodda 3 deneme var) |
| Sayfa yanıt vermiyor | Terminalde `Ctrl+C`, `streamlit run app.py` ile tekrar aç |
| `Veri tabanı boş` | `python main.py ingest` |
| Model yanlış cevap verdi | **Panikleme, fırsata çevir:** *"İşte bilinen sınırlardan biri. 1.5 milyar parametreli bir model kullanıyoruz; arama doğru parçayı buldu ama model yorumlamada hata yaptı. Raporda bunu belgeledik."* |

**Altın kural:** Yanlış cevap gelirse üstünü örtme. Sistemin sınırlarını
bilerek anlatmak, bilmiyormuş gibi yapmaktan çok daha güçlü.

---

## 5. Muhtemel sorular ve cevapları

**"Neden bulut yerine yerel model?"**
Ders notları kişisel veri. Ayrıca internet gerekmiyor, ücret yok. Foundry
Local cihaz üstünde çalışıyor — PDF planının da temel şartı buydu.

**"Neden bu kadar yavaş?"**
CPU üzerinde çıkarım yapıyoruz, kullanılabilir GPU yok. Ayrıca bu makinede
16 GB RAM'in çoğu dolu; embedding modeli ile sohbet modeli aynı anda
sığmadığı için yükle-boşalt döngüsü var. Bol RAM'li koşuda 20 saniyeye
iniyor — ölçtük.

**"Model yanlış cevap verirse ne olur?"**
Üç savunma katmanı var: (1) eşik koruması alakasız soruları modele hiç
göndermiyor, (2) prompt sadece kaynaklardaki bilgiyi kullanmasını söylüyor,
(3) her cevapta kaynak gösteriliyor — kullanıcı doğrulayabiliyor.

**"Kaç belge ekleyebilirsin?"**
Şu an tüm vektörler belleğe okunup kaba kuvvetle karşılaştırılıyor; 107 parça için fazlasıyla yeterli. Binlerce belge için gerçek bir vektör veri
tabanı (FAISS, Chroma, sqlite-vec) gerekir.

**"Chunk boyutunu neden 80 kelime seçtin?"**
Tahmin etmedim, ölçtüm. 120/80/60/45 denedim; ölçüt "cevabın metni bağlama
giriyor mu" idi. 80 en iyisini verdi (11/12, diğerleri 9-10/12). Önemli
nokta: chunk boyutu tek başına seçilemez, **bağlam bütçesine göre** seçilir.

**"`frequency_penalty` neden kullanmıyorsun?"**
Projenin ilk hâlinde 0.4'tü ve yanlış cevapların sebeplerinden biriydi.
O ayar modelin aynı kelimeyi tekrar etmesini cezalandırıyor — ama RAG'de
modelin kaynaktaki terimleri (TTL, Dijkstra) **aynen** tekrarlamasını
isteriz. Bunun yerine üretimi serbest bırakıp çıktıda yineleme döngüsünü
tespit edip kesiyoruz.

**"Testler ne kadar sürüyor?"**
Üç kademe: birim testleri 3 saniye (model yüklemez), arama testleri 1
dakika, uçtan uca testler 25 dakika. Geliştirirken ilk ikisini sürekli
koşuyorum — hızlı geri bildirim önemli.

**"Bu projede en zor kısım neydi?"**
Ölçümün kendisi. Kodu yazmak değil, doğru şeyi ölçtüğümden emin olmak.
8 kez ölçüm katmanım bana yanlış bilgi verdi - biri de doğru cevapları
sessizce siliyordu.

---

## 6. Rakamlar (ezberlenecek)

| Ölçüm | Değer |
|---|---|
| Belge / parça | 4 belge, **107 parça** |
| Parça boyutu | 80 kelime, 25 kelime örtüşme |
| Vektör boyutu | 1024 (`qwen3-embedding-0.6b`) |
| Sohbet modeli | `phi-3.5-mini` (yedek: `qwen2.5-1.5b`) |
| Hibrit ağırlık | 0.7 vektör / 0.3 kelime |
| Eşik | **0.45** |
| Birim testleri | **58/58** |
| Arama testleri | **41/41** (bağlam isabeti 18/18) |
| Uçtan uca | **26/26** |
| Alakasız soruda uydurma | **0** (5/5 reddedildi) |
| Yanıt süresi | 20-40 sn (bol RAM) / 70-130 sn (dar RAM) |
| Alakasız soru | **1-2 sn** |
| Tekrar sorulan soru | **0.0 sn** |
