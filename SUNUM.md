
# LocalMind — Yerel RAG Soru-Cevap Asistanı

Bu dosya 8–10 dakikalık final sunumu ve canlı demo için hazır akıştır.

---

## Slayt 1 — Problem

- Ders notlarında doğru bilgiyi elle bulmak yavaş ve zahmetli.
- Genel amaçlı bulut modelleri kaynak dışı bilgi uydurabilir.
- Belgelerin cihaz dışına gönderilmesi gizlilik ve internet bağımlılığı yaratır.
- Hedef: yalnızca yerel ders notlarına dayanarak cevap veren çevrim dışı bir asistan.

Konuşmacı notu: “Amacımız yeni bilgi uyduran bir sohbet botu değil, elimizdeki
belgelerde doğru bölümü bulup kaynaklı cevap üreten bir çalışma yardımcısıydı.”

---

## Slayt 2 — Çözüm

**LocalMind**, Microsoft Foundry Local üzerinde çalışan yerel bir RAG
(Retrieval-Augmented Generation) uygulamasıdır.

- İnternet ve bulut hesabı gerektirmez.
- Belgeler ve sorular cihazdan çıkmaz.
- İlgili parçaları hibrit aramayla bulur.
- Yanıtı yerel LLM ile üretir.
- Kullanılan kaynakları ve benzerlik skorlarını gösterir.

---

## Slayt 3 — Mimari

```text
TXT belgeler
   ↓ temizleme ve başlık-duyarlı parçalama
Foundry Local embedding modeli
   ↓ 1024 boyutlu float32 vektörler
SQLite bilgi tabanı
   ↓
Kullanıcı sorusu → sorgu genişletme → hibrit arama
   ↓                         (vektör %70 + anahtar kelime %30)
En alakalı parçalar → bağlam bütçesi → yerel sohbet modeli
   ↓
Akışlı yanıt + kaynak kartları
```

Katmanlar:

- İstemci: Streamlit web arayüzü ve CLI
- Servis: RAG pipeline, retrieval ve generation
- Veri: SQLite içinde metin, başlık ve embedding BLOB’ları
- Yapay zekâ: Foundry Local embedding ve sohbet modelleri

---

## Slayt 4 — Veri Aktarımı

1. `docs/*.txt` belgeleri UTF-8 olarak okunur.
2. Slayt numarası, tekrar eden footer ve bozuk semboller temizlenir.
3. Metin başlıkları korunarak 80 kelimelik, 25 kelime örtüşmeli parçalara ayrılır.
4. Embedding’ler 16’lı gruplar hâlinde hesaplanır.
5. Metin ve vektörler SQLite’a yazılır.

Güncel bilgi tabanı:

- 4 kaynak belge
- 116 indekslenmiş parça
- 1024 boyutlu embedding

---

## Slayt 5 — Retrieval ve Güvenilirlik

- Semantik vektör araması yeniden ifade edilmiş soruları yakalar.
- IDF tabanlı anahtar kelime araması `TTL`, `IHL`, `SRTF` gibi kesin terimleri korur.
- Türkçe ekler için hafif ön-ek eşleştirmesi uygulanır.
- “Diğer adı” ve “bilinen sorunu” gibi niyetler teknik eş anlamlılarla genişletilir.
- En iyi 8 aday aranır; tekrarlar elenir ve 1300 karakterlik bağlama sığanlar seçilir.
- En iyi skor 0.52’nin altındaysa LLM çağrılmaz ve sistem
  “Bu bilgi elimdeki dokümanlarda yok.” yanıtını verir.

---

## Slayt 6 — Arayüz ve Özellikler

- Tek tıkla sohbet ekranına geçen karşılama sayfası
- Akış hâlinde yanıt
- Kaynak dosyası, bölüm, skor ve kullanılan-parça göstergesi
- Hızlı ve yüksek doğruluk model seçenekleri
- Sohbet geçmişi ve temizleme kontrolü
- Aynı soru için oturum içi yanıt önbelleği
- CLI üzerinden `ingest`, `info`, `ask` ve `chat` komutları

---

## Slayt 7 — Test Sonuçları

```text
Birim testleri                 80/80
Doğru belge                    45/45
Bağlam isabeti                 45/45
Kapsam dışı eşik koruması      11/11
Retrieval toplamı             101/101
Tam fonksiyonel koşu            61/61
```

Test seti 45 cevaplanabilir, 11 kapsam dışı ve 5 uç durum sorusu içerir.
Sonuçlar bu test kapsamını ifade eder; sistemin bütün olası sorularda hatasız
olduğu iddia edilmez.

Tam koşuda 45 cevaplanabilir, 11 kapsam dışı ve 5 uç durumun tamamı geçmiştir.

---

## Slayt 8 — Performans ve Kısıtlar

| Durum | Gözlenen süre |
|---|---:|
| Hızlı kaynak modu | 1–3 sn |
| Kapsam dışı soru, LLM çağrılmaz | 2–3 sn |
| Aynı soru, oturum önbelleği | yaklaşık 0 sn |
| Kalite modu, phi-3.5-mini | yaklaşık 76–90 sn |

PDF’deki 1–3 saniye hedefi hızlı kaynak modunda karşılanmıştır. Bu mod en güçlü
kaynak kanıtını LLM'e yeniden yazdırmadan döndürür. Daha doğal açıklama isteyen
kullanıcı “Açıklamalı LLM yanıtı” seçeneğiyle yerel LLM moduna geçebilir.

Diğer sınırlar:

- 16 GB RAM’de iki model aynı anda her zaman sığmıyor.
- Büyük belge koleksiyonlarında `sqlite-vec`, FAISS veya benzeri indeks gerekir.
- Bilgi kaynak belgelerde yoksa doğru yanıt üretilemez.

---

## Slayt 9 — Öğrenilen Dersler

- Doğru belgenin bulunması yetmez; doğru metin bağlam bütçesine de girmelidir.
- Daha büyük bağlam her zaman daha iyi değildir: süreyi ve bellek hatasını artırabilir.
- Türkçe ekler ve teknik kısaltmalar salt semantik aramada kaybolabilir.
- Çıktı temizleme kodu doğru cevabı yanlışlıkla silebilir; regresyon testi gerekir.
- “Kolay” kapsam dışı sorularla eşik kalibrasyonu yanıltıcıdır.
- Testin geçmesi kadar doğru şeyi ölçmesi de önemlidir.

---

## Slayt 10 — Canlı Demo

Ön hazırlık:

```bash
python main.py info
streamlit run app.py
```

Demo sırası:

1. **Belgede olan:** “IP datagramında TTL alanı kaç bittir?”
   - Beklenen: `8 bit`, kaynak olarak `bilgisayarağları.txt`.
2. **Eş anlamlı arama:** “FIFO sayfa değiştirme algoritmasının bilinen sorunu nedir?”
   - Beklenen: `Belady anomalisi`.
3. **Kapsam dışı:** “Sanal bellek nedir?”
   - Tanım belgelerde bulunmadığı için beklenen fallback yanıtı.
4. Aynı ilk soruyu tekrar sor.
   - Önbellekten anlık dönmesini göster.
5. Kaynak panelini açıp kullanılan parçaları ve skorları göster.

---

## Muhtemel Sorular

**Neden SQLite?** 116 parçalık küçük koleksiyonda sunucusuz, taşınabilir ve
yeterince hızlı. Vektörler BLOB olarak saklanıyor, benzerlik NumPy ile hesaplanıyor.

**Neden hibrit arama?** Vektör araması anlamı, anahtar kelime araması kesin teknik
terimleri yakalıyor. Birlikte tek başlarına olduklarından daha güvenilirler.

**Sistem uydurmayı tamamen engelliyor mu?** Hayır. Eşik koruması, kaynakla
sınırlandırılmış prompt ve kaynak görünürlüğü riski azaltır; tamamen ortadan kaldırmaz.

**İnternet gerçekten gerekmiyor mu?** Modeller önceden indirildikten sonra soru-cevap
ve indeksleme cihaz üzerinde çalışır. İlk model indirme işlemi internet gerektirir.

**macOS desteği var mı?** Yol ve bellek ölçümü kodu platform bağımsızlaştırıldı;
`start.sh` eklendi. Gerçek macOS cihazında Foundry Local uçtan uca doğrulaması ayrıca
yapılmalıdır.
