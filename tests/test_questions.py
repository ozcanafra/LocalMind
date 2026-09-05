"""Test soru bankası (PDF planı, 5. Hafta: Fonksiyonel Testler).

Üç kategori var:
  ANSWERABLE   - cevabı belgelerde olan sorular
  UNANSWERABLE - cevabı belgelerde OLMAYAN sorular (asistan "bilmiyorum" demeli)
  EDGE_CASES   - uç durumlar (boş girdi, çok genel soru)

Her ANSWERABLE sorusunda:
  expect_source   -> cevabın hangi belgeden gelmesi gerektiği
  expect_context  -> BAĞLAMA girmesi gereken metin parçası.
                     LİSTE olarak yazılır: aynı bilgi belgede birden fazla
                     ifadeyle geçebilir, herhangi biri yeterlidir.
  expect_keywords -> cevapta geçmesi beklenen anahtar kelimeler
                     (hepsi değil, en az biri yeterli sayılır)

expect_context NEDEN AYRI BİR ALAN?

İlk sürümde sadece "doğru BELGE ilk sıralara geldi mi?" diye kontrol
ediyorduk ve test 12/12 geçiyordu. Ama cevaplar hâlâ yanlıştı. Bağlamın
içine bakınca sebep çıktı: doğru belge geliyordu ama YANLIŞ PARÇASI.

expect_context bunu yakalar: bağlamda bu metin geçmiyorsa test kalır.
Üstelik LLM çalıştırmadan ölçülür -> saniyeler içinde sonuç.

KORPUS (4 belge, 107 chunk):
  bilgisayarağları.txt  - Ağ katmanı, IP, anahtarlama, yönlendirme
  işletimsistemi.txt    - CPU Scheduling (FCFS, SJF, RR, öncelik, gerçek zamanlı)
  işletimsistemi2.txt   - Deadlock (avoidance, detection, recovery) + Bellek yönetimi
  sanalbellek.txt       - Sayfa değiştirme, frame tahsisi, thrashing, working set

KAPSAM
Set 18 sorudan 40 soruya çıkarıldı. Amaç: "18/18 geçiyor" iddiasını
genişletmek. Küçük bir test setinde tam skor almak kolaydır; asıl soru
sistemin KAPSAM büyüyünce de dayanıp dayanmadığıdır.
"""

ANSWERABLE = [
    # ================= bilgisayarağları.txt : ağ katmanı =================
    {
        "question": "IP datagramında TTL alanı kaç bittir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["TTL 8 bit"],
        "expect_keywords": ["8 bit", "8bit", "8"],
    },
    {
        "question": "IP protokolünün iki temel görevi nedir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["Adresleme ve Yönlendirme"],
        "expect_keywords": ["adresleme", "yönlendirme"],
    },
    {
        "question": "Link-State algoritması en kısa yolu hangi algoritmayla hesaplar?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["Dijkstra"],
        "expect_keywords": ["dijkstra"],
    },
    {
        "question": "Flooding algoritmasında sonsuz döngü nasıl önlenir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["Hop Counter"],
        "expect_keywords": ["hop counter", "atlama sayac", "sayaç"],
    },
    {
        "question": "Sanal devre anahtarlamaya örnek protokoller nelerdir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["ATM, X.25", "ATM ve X.25"],
        "expect_keywords": ["atm", "x.25", "x25"],
    },
    {
        "question": "Protokol alanında TCP ve UDP için hangi değerler kullanılır?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["TCP=6, UDP=17"],
        "expect_keywords": ["6", "17"],
    },
    {
        "question": "IHL alanı en az ve en fazla kaç oktettir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["min 20, max 60 oktet", "en az 20, en fazla 60 oktet"],
        "expect_keywords": ["20", "60"],
    },
    {
        "question": "Bir datagramın alabileceği en büyük ve en küçük uzunluk nedir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["min 576, max 65535", "65535"],
        "expect_keywords": ["65535", "576"],
    },
    {
        "question": "Mesaj anahtarlamada veri hangi yöntemle iletilir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["store-and-forward", "sakla-ve-gönder"],
        "expect_keywords": ["store-and-forward", "sakla", "gönder"],
    },
    {
        "question": "Devre anahtarlamanın dezavantajları nelerdir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["Verimsiz kullanım"],
        "expect_keywords": ["verimsiz", "pahalı", "kurulum"],
    },
    {
        "question": "Distance Vector algoritmasının dezavantajı nedir?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["yavaş adapte", "yakınsaklık"],
        "expect_keywords": ["yavaş", "yakınsak", "gecikme"],
    },
    {
        "question": "Kaynakta yönlendirmede (source routing) geçilecek düğümleri kim belirler?",
        "expect_source": "bilgisayarağları.txt",
        "expect_context": ["Kaynak düğüm"],
        "expect_keywords": ["kaynak"],
    },

    # ================= işletimsistemi.txt : CPU Scheduling =================
    {
        "question": "FCFS algoritmasında ortaya çıkan convoy effect nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["convoy"],
        "expect_keywords": ["convoy", "kısa", "uzun", "bekle"],
    },
    {
        "question": "Ortalama bekleme süresini en aza indiren scheduling algoritması hangisidir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["SJF"],
        "expect_keywords": ["sjf", "shortest"],
    },
    {
        "question": "Round-Robin algoritmasında time quantum çok büyük seçilirse ne olur?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["FCFS gibi davranır"],
        "expect_keywords": ["fcfs", "first-come", "benzer", "davranır"],
    },
    {
        "question": "Priority scheduling'de starvation sorunu nasıl çözülür?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Aging"],
        "expect_keywords": ["aging", "yaşlandırma", "öncelik"],
    },
    {
        "question": "Rate-monotonic scheduling'de hangi process daha yüksek öncelik alır?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["rate-monotonic", "periyot"],
        "expect_keywords": ["kısa", "küçük", "periyot"],
    },
    {
        "question": "Dispatcher nedir ve ne iş yapar?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Dispatcher:"],
        "expect_keywords": ["cpu", "context switch", "geçiren", "process"],
    },
    {
        "question": "Dispatch latency nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Dispatch Latency"],
        "expect_keywords": ["durdur", "başlat", "süre", "geçen"],
    },
    {
        "question": "Turnaround time neyi ölçer?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Turnaround Time"],
        "expect_keywords": ["sunul", "tamamlan", "süre", "bekleme"],
    },
    {
        "question": "Scheduling kriterlerinden hangileri maksimum yapılmak istenir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["CPU Utilization + Throughput"],
        "expect_keywords": ["throughput", "utilization", "kullanım"],
    },
    {
        "question": "Preemptive SJF algoritmasının diğer adı nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Shortest-Remaining-Time-First"],
        "expect_keywords": ["srtf", "shortest-remaining", "remaining"],
    },
    {
        "question": "Multilevel feedback queue'nun multilevel queue'dan farkı nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["kuyruklar arasında geçiş"],
        "expect_keywords": ["geçiş", "kuyruk", "taşın"],
    },
    {
        "question": "Processor affinity nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["Processor Affinity"],
        "expect_keywords": ["cache", "önbellek", "cpu", "taşı"],
    },
    {
        "question": "Multiprogramming nedir?",
        "expect_source": "işletimsistemi.txt",
        "expect_context": ["aynı anda bellekte tutulması"],
        "expect_keywords": ["bellek", "birden fazla", "program"],
    },

    # ================= işletimsistemi2.txt : Deadlock + Bellek =================
    {
        "question": "Safe state nedir?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["safe state", "Safe state"],
        "expect_keywords": ["deadlock", "sıra", "tamamlan", "güvenli"],
    },
    {
        "question": "Deadlock ile starvation arasındaki fark nedir?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["starvation"],
        "expect_keywords": ["starvation", "deadlock", "bekle", "sonsuz"],
    },
    {
        "question": "Base ve limit register ne işe yarar?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["limit register"],
        "expect_keywords": ["adres", "koruma", "bellek", "sınır"],
    },
    {
        "question": "Unsafe state her zaman deadlock anlamına gelir mi?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["deadlock var demek değildir"],
        "expect_keywords": ["değildir", "gelmez", "hayır", "olabilir"],
    },
    {
        "question": "Banker's algorithm'de Need nasıl hesaplanır?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["Need = Max - Allocation"],
        "expect_keywords": ["max", "allocation", "çıkar"],
    },
    {
        "question": "Deadlock recovery için hangi iki yöntem kullanılır?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["Resource preemption"],
        "expect_keywords": ["termination", "preemption", "sonland", "kaynak"],
    },
    {
        "question": "Logical address ile physical address arasındaki fark nedir?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["Logical address", "Physical address"],
        "expect_keywords": ["cpu", "mmu", "üretilen", "gerçek"],
    },
    {
        "question": "Modern sistemlerde hangi address binding türü kullanılır?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["execution-time binding"],
        "expect_keywords": ["execution-time", "execution", "çalışma"],
    },
    {
        "question": "Register ile ana bellek arasındaki erişim hızı farkı nedir?",
        "expect_source": "işletimsistemi2.txt",
        "expect_context": ["bir CPU cycle"],
        "expect_keywords": ["cycle", "hızlı", "yavaş", "uzun"],
    },

    # ================= sanalbellek.txt : Sanal bellek =================
    {
        "question": "Second-chance algoritmasının diğer adı nedir?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["Clock"],
        "expect_keywords": ["clock", "saat"],
    },
    {
        "question": "Second-chance algoritması hangi bite bakarak karar verir?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["referans biti"],
        "expect_keywords": ["referans"],
    },
    {
        "question": "Thrashing nedir?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["thrashing"],
        "expect_keywords": ["paging", "sayfa", "zaman", "fazla"],
    },
    {
        "question": "Enhanced second-chance algoritmasında en kolay değiştirilen sınıf hangisidir?",
        "expect_source": "sanalbellek.txt",
        # DİKKAT: aynı bilgi belgede İKİ FARKLI BİÇİMDE geçiyor:
        #   cevap anahtarında : "(0,0) - ne kullanılmış ne değiştirilmiş"
        #   karşılaştırma tablosunda : "0 0 Ne kullanılmış ne değiştirilmiş"
        "expect_context": ["(0,0)", "(0, 0)", "Ne kullanılmış ne değiştirilmiş"],
        # Tablo satırı: "1 (En iyi) 0 0 ..." -> (0,0) sınıfının NUMARASI 1.
        # Model "Sınıf 1" dediğinde cevap DOĞRU.
        "expect_keywords": [
            "(0,0)", "(0, 0)", "sınıf 1", "sinif 1",
            "ne kullanılmış", "kullanılmamış ve değiştirilmemiş",
        ],
    },
    {
        "question": "Global replacement ile local replacement arasındaki fark nedir?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["global", "local"],
        "expect_keywords": ["tüm", "kendi", "frame", "havuz"],
    },
    {
        "question": "FIFO sayfa değiştirme algoritmasının bilinen sorunu nedir?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["Belady"],
        "expect_keywords": ["belady", "anomali"],
    },
    {
        "question": "Optimal (OPT) algoritması hangi page'i bellekten çıkarır?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["En uzun süre kullanılmayacak"],
        "expect_keywords": ["kullanılmayacak", "gelecek", "uzun süre"],
    },
    {
        "question": "LRU algoritması hangi page'i seçer?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["En uzun süre kullanılmayan"],
        "expect_keywords": ["kullanılmayan", "geçmiş", "uzun süre"],
    },
    {
        "question": "LFU ve MFU algoritmaları pratikte yaygın mıdır?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["yaygın değildir"],
        "expect_keywords": ["yaygın değil", "değildir", "pahalı", "hayır"],
    },
    {
        "question": "Working-set window neyi ifade eder?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["Working-set window"],
        "expect_keywords": ["referans", "son", "pencere"],
    },
    {
        "question": "NUMA mimarisinde Solaris hangi çözümü kullanır?",
        "expect_source": "sanalbellek.txt",
        "expect_context": ["lgroups"],
        "expect_keywords": ["lgroup", "locality"],
    },
]

# Cevabı belgelerde OLMAYAN sorular.
#
# İki tür var:
#   KOLAY NEGATİF : konuyla hiç ilgisi yok (yemek tarifi, spor)
#   ZOR NEGATİF   : bilgisayar bilimi konusu ama BU belgelerde yok.
#                   Eşik korumasının gerçek sınavı bunlar - konu benzerliği
#                   yüksek olduğu için arama skorları eşiğe yaklaşabilir.
UNANSWERABLE = [
    # Kolay negatifler
    {"question": "Türkiye'nin başkenti neresidir?"},
    {"question": "Karnıyarık nasıl yapılır, tarifi verir misin?"},
    {"question": "Basketbolda bir takımda sahada kaç oyuncu bulunur?"},
    {"question": "2024 Yaz Olimpiyatları hangi şehirde yapıldı?"},
    {"question": "Bugün hava durumu nasıl olacak?"},
    # KELİME TUZAĞI - gerçek kullanımda yakalandı, en zor negatif.
    #
    # Belge dosyasının adı "sanalbellek.txt" ama içinde "sanal bellek"
    # ifadesi HİÇ geçmiyor (sayfa değiştirme, thrashing, frame tahsisi
    # anlatıyor). Buna karşılık "sanal" kelimesi AĞ belgesinde
    # "Sanal Devre" olarak geçiyor - tamamen farklı bir kavram.
    #
    # Sistem bu soruya ağ belgesinden alıntı yaparak anlamsız bir cevap
    # üretiyordu ("Bellek belleği, CPU'nun program counter'a göre...").
    # Skor 0.498 idi ve o zamanki eşik 0.49'u kıl payı geçiyordu.
    {"question": "Sanal bellek nedir?"},
    # Zor negatifler - bilgisayar bilimi ama belgelerde yok
    {"question": "TCP three-way handshake nasıl çalışır?"},
    {"question": "Quicksort algoritmasının ortalama zaman karmaşıklığı nedir?"},
    {"question": "SQL'de INNER JOIN ile LEFT JOIN arasındaki fark nedir?"},
    {"question": "Docker container ile sanal makine arasındaki fark nedir?"},
    {"question": "HTTP 404 hata kodu ne anlama gelir?"},
]

EDGE_CASES = [
    {"question": "", "note": "boş girdi"},
    {"question": "   ", "note": "sadece boşluk"},
    {"question": "?", "note": "tek karakter"},
    {"question": "a", "note": "tek harf"},
    {"question": "!@#$%^&*()", "note": "sadece noktalama"},
]
