"""Projenin tüm ayarları burada. Başka hiçbir dosyada sabit değer yazmıyoruz."""

from pathlib import Path

# --- Yollar -----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DOCS_DIR = PROJECT_ROOT / "docs"
DB_PATH = PROJECT_ROOT / "db" / "rag.db"

# Foundry Local modellerinin indirildiği klasör
CACHE_DIR = r"D:\foundry-cache"
APP_NAME = "rag_project"

# --- Modeller ---------------------------------------------------------------
# Embedding modeli: metni sayısal vektöre çeviren model.
EMBEDDING_MODEL = "qwen3-embedding-0.6b"

# Chat modeli: cevabı yazan model.
#
# SIRAYLA DENENİR, ilk yüklenen kullanılır.
#
# Phi-3.5-mini (3.8B) başta YÜKLENEMİYORDU ("bad allocation"): embedding
# modeli bellekteyken 4-6 GB boş yer kalmıyordu. Düşük bellek modu eklenip
# embedding modeli üretim sırasında bellekten atılınca YER AÇILDI ve
# Phi-3.5-mini çalışır hâle geldi.
#
# Kalite farkı ölçüldü (5 soruluk hedefli test seti):
#     phi-3.5-mini  4/5
#     qwen2.5-1.5b  3/5
# Phi, qwen'in kaçırdığı iki soruyu düzeltti ("Hop Counter (Atlama Sayacı)"
# ve "Referans biti" cevapları).
#
# BEDELİ: hız. Soru başına ~75-105 sn (qwen ~30-45 sn). Kalite öncelikli
# olduğu için Phi başa alındı. Hız istersen sırayı ters çevir.
CHAT_MODEL_CANDIDATES = ["phi-3.5-mini", "qwen2.5-1.5b"]

# CPU mu GPU mu? Cache'de hangisi varsa onu seçer, öncelik buradaki sıra.
DEVICE_PREFERENCE = ["cpu", "gpu"]

# --- Bellek yönetimi --------------------------------------------------------
# Bu makinede embedding modeli ile sohbet modeli AYNI ANDA belleğe sığmıyor
# (ölçüm: chat yüklendikten sonra 1.82 GB boş kalıyor, embedding çalışamıyor).
#
# Düşük bellek modunda sohbet modeli sadece cevap üretirken yüklenir ve
# hemen sonra bellekten atılır. Bedeli soru başına ~3 saniye ek yükleme.
#
# None  -> otomatik karar ver (boş RAM < LOW_MEMORY_THRESHOLD_GB ise aç)
# True  -> her zaman düşük bellek modu
# False -> her zaman modelleri bellekte tut (hızlı, ama RAM ister)
LOW_MEMORY_MODE = None
LOW_MEMORY_THRESHOLD_GB = 6.0

# --- Chunk'lama (belgeyi parçalara ayırma) ----------------------------------
#
# ÖNEMLİ: Chunk boyutu TEK BAŞINA seçilemez, MAX_CONTEXT_CHARS bütçesine
# göre seçilmelidir. Chunk ne kadar büyükse bütçeye o kadar azı sığar.
#
# Bu değer ölçümle bulundu. 4 boyut denendi; ölçüt "bütçe kırpmasından SONRA
# cevabın metni bağlamda kaldı mı?" (12 soruluk test seti, TOP_K=8):
#
#   boyut/overlap   chunk   ort.karakter   BAĞLAM İSABETİ
#      120 / 30       61        504            9/12
#       80 / 25       76        428           11/12   <-- seçildi
#       60 / 20       92        359           10/12
#       45 / 15      113        294           11/12
#
# 80 ve 45 aynı skoru veriyor. 80 seçildi çünkü 45 kelimelik parçalar çok
# küçük: modele bağlamsız cümle kırıntıları gidiyor. Üretim modeli zayıf
# (1.5B) olduğu için bütünlüklü pasajlar önemli.
CHUNK_SIZE = 80
CHUNK_OVERLAP = 25  # Ardışık chunk'ların ortak kelime sayısı (bilgi kesilmesin diye)
MIN_CHUNK_WORDS = 12  # Bundan kısa parçalar tek başına anlamsız, öncekine eklenir

# --- Arama (retrieval) ------------------------------------------------------
# Aramada kaç aday chunk bulunacak.
#
# 5'ten 8'e çıkarıldı. Maliyeti neredeyse sıfır (76 vektör üzerinde tek matris
# çarpımı) ama faydası ölçüldü: TOP_K=5 iken doğru metin 11/12 soruda
# bulunuyordu, TOP_K=8 ile 12/12 oldu ("Second-chance'in diğer adı Clock"
# sorusu 5'in dışında kalıyormuş).
#
# Not: bu sayı modele giden chunk sayısı DEĞİL. Bütçe (MAX_CONTEXT_CHARS)
# bunlardan sığanları seçiyor. Yani geniş arayıp dar göndermek bedava.
TOP_K = 8

# Hibrit arama ağırlıkları: skor = ALPHA*vektör + (1-ALPHA)*anahtar_kelime
# 1.0 = sadece vektör, 0.0 = sadece kelime eşleşmesi.
HYBRID_ALPHA = 0.7

# Bu skorun altındaki hiçbir chunk bulunamazsa "dokümanlarda yok" denir.
#
# Bu değer TAHMİNLE DEĞİL, ÖLÇÜMLE belirlendi. 45 "belgede olan" ve
# 10 "belgede olmayan" soru ile arama skorları ölçüldü
# (4 belge / 116 chunk):
#
#   Belgede OLAN sorular   : 0.528 - 0.888  (ortalama 0.693)
#   Belgede OLMAYAN sorular: 0.177 - 0.498
#
# Boşluk: 0.498 .. 0.528  ->  0.51 secildi
#
# EN ZOR NEGATIF: "Sanal bellek nedir?" -> 0.498
# Gercek kullanimda yakalandi. Belge adi sanalbellek.txt ama icinde bu
# ifade hic gecmiyor; "sanal" kelimesi AG belgesinde "Sanal Devre" olarak
# geciyor. Sistem ag belgesinden alinti yapip anlamsiz cevap uretiyordu.
# Eski esik 0.49 bunu kil payi geciriyordu.
#
# ZOR NEGATİFLER MARJI DARALTTI - bu projenin önemli derslerinden biri:
#
# İlk kalibrasyon sadece KOLAY negatiflerle yapılmıştı (yemek tarifi, spor,
# hava durumu) ve boşluk 0.267 genişliğinde görünüyordu; eşik çok güvenli
# sanılıyordu. Teste "bilgisayar bilimi konulu ama BU belgelerde olmayan"
# sorular eklenince gerçek tablo çıktı:
#
#   Quicksort zaman karmaşıklığı  -> 0.450   <- eski eşiğin (0.45) TAM üstünde
#   TCP three-way handshake       -> 0.386
#   Docker vs sanal makine        -> 0.353
#
# Gerçek boşluk 0.267 değil 0.078'miş. Eski eşik "Quicksort" sorusunu
# modele gönderiyordu. Kolay negatiflerle ölçmek yanıltıcıydı.
#
# NOT: Belgeler değişirse bu ölçümü tekrarla. Değerleri üreten kod:
#   python tests/test_rag.py --retrieval   (3. bölüm: eşik koruması)
#
# NOT: Eski koddaki 0.35 değeri HAM kosinüs üzerindeydi ve işe yaramıyordu:
# "Karnıyarık tarifi verir misin?" sorusunun ham kosinüs skoru 0.411,
# yani eşiğin üstünde. Koruma hiç devreye girmiyor, model alakasız
# bağlamla cevap uyduruyordu.
SIMILARITY_THRESHOLD = 0.51

# Qwen3-embedding modeli sorguları bu formatta bekler (asimetrik arama).
# Belgeler ham hâlde, sorgular bu ön ekle gömülür.
QUERY_INSTRUCTION = (
    "Instruct: Verilen soruya cevap içeren ders notu pasajını bul\nQuery: "
)

# --- Üretim (generation) ----------------------------------------------------
# Üretilecek en fazla token sayısı.
#
# 220'den 160'a düşürüldü. Cevaplar tipik olarak 10-40 token; sınır nadiren
# devreye giriyor. AMA model bazen gereksiz uzatıyor ("Kaynak numarası: [1]
# Bilgi: Kaynak, Second-c...") ve o durumlarda üretim uzuyor. 160 bu
# savrulmayı kesiyor, normal cevapları etkilemiyor.
MAX_TOKENS = 160
TEMPERATURE = 0.1  # Bilgi çıkarma işi -> neredeyse deterministik olmalı
TOP_P = 0.9

# Prompt'a girecek KAYNAK metnin karakter üst sınırı.
#
# Bu da tahminle değil ÖLÇÜMLE belirlendi ve İKİ KEZ ölçüldü, çünkü
# sınır makinenin bellek durumuna göre değişiyor.
#
# 1) DAR BELLEKTE (~3 GB boş, modeller sürekli yüklenip boşaltılırken):
#        ~2294 karakter -> çalışıyor
#        ~2494 karakter -> "bad allocation", çöküyor
#    Sebep: ONNX Runtime lm_head çıktısı için (token x 152.000 kelime)
#    boyutunda TEK PARÇA bellek ayırıyor; parçalanmış bellekte bulunamıyor.
#
# 2) BOL BELLEKTE (~4.4 GB boş, modeller bellekte kalıyor):
#        prompt      süre
#        1394 krk    37 sn
#        2094 krk    55 sn
#        2694 krk    71 sn
#        4094 krk   110 sn
#        5094 krk   çöküyor (zaman aşımı)
#    Duvar yükseldi ama SÜRE prompt uzunluğuyla doğrusal artıyor:
#    her ~700 karakter ~17 saniye ekliyor.
#
# BÜTÇE SEÇİMİ - burada bir ARA METRİK TUZAĞINA düştük, ders niteliğinde:
#
# Ölçüm 1 (sadece bağlam isabeti, LLM çalıştırmadan):
#   bütçe   bağlam isabeti   en uzun prompt
#    1300       43/45            1942
#    2000       45/45            2618        <- "daha iyi" görünüyordu
#
# Bu tabloya bakıp 2000'e çıkardık. İki soru kazanacaktık.
#
# Ölçüm 2 (60 soruluk UÇTAN UCA test, gerçek cevap üretimiyle):
#   bütçe   uçtan uca   medyan süre   zaman aşımı hatası
#    1300     26/26        ~30 sn            0
#    2000     42/60       ~101 sn           ~15        <- ÇOK DAHA KÖTÜ
#
# Uzun prompt -> yavaş üretim -> Foundry Local isteği iptal ediyor
# ("Operation was cancelled"). Teoride kazanılan 2 soruya karşılık
# pratikte 15 soru tamamen cevapsız kaldı.
#
# DERS: Bağlam isabeti bir ARA metrik (proxy). Onu tek başına
# iyileştirmek sistemi bozabiliyor. Karar UÇTAN UCA ölçümle verilmeli.
#
# 1300'e geri dönüldü. Kaybedilen 2 soru, kazanılan kararlılığa değer.
MAX_CONTEXT_CHARS = 1300
# frequency_penalty BİLEREK kullanılmıyor: modelin bağlamdaki terimleri
# aynen tekrar etmesini istiyoruz, cezalandırmak istemiyoruz.

FALLBACK_ANSWER = "Bu bilgi elimdeki dokümanlarda yok."
