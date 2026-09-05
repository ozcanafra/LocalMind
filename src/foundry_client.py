"""Foundry Local model yükleme işlemleri.

Bu kod önceden hem ingest.py hem query.py içinde kopyalanmıştı ve cihaz
tipi ("cpu") koda gömülüydü. Tek yere topladık; cihaz tercihi config'ten
geliyor ve cache'de hangi varyant varsa ona düşüyor.
"""

import ctypes
import time

from foundry_local_sdk import Configuration, FoundryLocalManager
from foundry_local_sdk.openai.chat_client import ChatClientSettings

_manager = None

# Geçici hatalarda kaç kez denenecek ve aralarda ne kadar beklenecek.
#
# Foundry Local ara sıra "Operation was cancelled" ve "bad allocation"
# hataları veriyor. Bunlar kalıcı değil: modeli tazeleyip BİRAZ BEKLEYİP
# tekrar denenince genelde geçiyor. Beklemesiz tekrar deneme işe yaramadı
# (30 dakikalık bir test koşusu bu yüzden çöktü), o yüzden gecikme var.
# Bekleme her denemede artıyor: 2 sn, 4 sn.
_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 2.0


# --- Bellek ölçümü ----------------------------------------------------------


class _MemoryStatusEx(ctypes.Structure):
    """Windows GlobalMemoryStatusEx yapısı (boş RAM'i öğrenmek için)."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_memory_gb():
    """Boş fiziksel bellek (GB). Ölçemezse None döner."""
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullAvailPhys / 1024**3
    except Exception:
        return None


def get_manager(app_name: str, cache_dir: str):
    """FoundryLocalManager örneğini döndürür (bir kez başlatılır).

    Manager tekil (singleton) bir kaynak: aynı süreçte iki kez initialize
    etmeye çalışırsak hata verir. Bu yüzden modül düzeyinde saklıyoruz.
    """
    global _manager
    if _manager is None:
        config = Configuration(app_name=app_name, model_cache_dir=cache_dir)
        FoundryLocalManager.initialize(config)
        _manager = FoundryLocalManager.instance
    return _manager


def _pick_variant(model, device_preference):
    """Cache'lenmiş varyantlar arasından tercih sırasına göre birini seçer.

    Bir model birden çok varyantla gelir (generic-cpu, openvino-gpu, ...).
    Sadece indirilmiş (is_cached) olanlar kullanılabilir.
    """
    cached = [v for v in model.variants if v.is_cached]
    if not cached:
        available = ", ".join(v.id for v in model.variants) or "(yok)"
        raise RuntimeError(
            f"'{model.alias}' için indirilmiş varyant yok.\n"
            f"  Mevcut varyantlar: {available}\n"
            f"  Çözüm: 'foundry model download {model.alias}' komutunu çalıştır."
        )

    for device in device_preference:
        for variant in cached:
            if device.lower() in variant.id.lower():
                return variant

    # Tercih listesinde eşleşme yoksa eldeki ilk cache'li varyantı kullan
    return cached[0]


def load_model(manager, alias: str, device_preference, verbose: bool = True):
    """Modeli alias ile bulur, uygun varyantı seçer ve belleğe yükler."""
    model = manager.catalog.get_model(alias)
    if model is None:
        raise RuntimeError(f"'{alias}' adlı model katalogda bulunamadı.")

    variant = _pick_variant(model, device_preference)
    model.select_variant(variant)

    if not model.is_loaded:
        if verbose:
            print(f"  Model yükleniyor: {variant.id} ...")
        model.load()
    elif verbose:
        print(f"  Model zaten yüklü: {variant.id}")

    return model


def get_embedding_client(manager, alias: str, device_preference, verbose=True):
    """Embedding (metin -> vektör) istemcisi döndürür."""
    model = load_model(manager, alias, device_preference, verbose)
    return model.get_embedding_client()


def get_chat_client(
    manager,
    alias: str,
    device_preference,
    max_tokens: int,
    temperature: float,
    top_p: float,
    verbose: bool = True,
):
    """Sohbet (cevap üretme) istemcisi döndürür.

    ÖNEMLİ: frequency_penalty BİLEREK ayarlanmıyor.
    Eski kodda frequency_penalty=0.4 vardı ve bu, modelin aynı kelimeyi
    tekrar etmesini cezalandırıyordu. RAG'de tam tersini isteriz: model
    bağlamdaki terimleri (TTL, OSPF, Dijkstra...) AYNEN tekrar etmeli.
    Bu ayar modeli eş anlamlı kelime uydurmaya itiyordu -> yanlış cevaplar.
    """
    model = load_model(manager, alias, device_preference, verbose)
    client = model.get_chat_client()
    client.settings = ChatClientSettings(
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    return client


class EmbeddingModel:
    """Embedding modelini yöneten sarmalayıcı (gerektiğinde boşaltılabilir).

    NEDEN BOŞALTILABİLİR OLMALI?
    Bu makinede embedding modeli bellekteyken sohbet modeli uzun bir RAG
    prompt'unu işleyemiyor ("bad allocation"). Ölçüm:
        embedding YÜKLÜ  + 1300 karakter bağlam -> çöküyor
        embedding BOŞ    + 1688 karakter bağlam -> çalışıyor

    Neyse ki embedding sadece sorunun BAŞINDA gerekiyor: soruyu vektöre
    çevirdikten sonra üretim bitene kadar boşta duruyor. Bu yüzden
    "soruyu göm -> boşalt -> cevabı üret" sırası kurulabiliyor.

    Yeniden yükleme maliyeti düşük çünkü dosyalar işletim sistemi
    önbelleğinde sıcak kalıyor:
        ilk yükleme     : 8.8 s
        yeniden yükleme : 3.5 s
    """

    def __init__(self, manager, alias, device_preference, verbose=True):
        self._manager = manager
        self.alias = alias
        self._device_preference = device_preference
        self._verbose = verbose
        self._model = None
        self._client = None

    def _ensure_loaded(self):
        if self._client is not None and self._model.is_loaded:
            return
        self._model = load_model(
            self._manager, self.alias, self._device_preference, verbose=False
        )
        self._client = self._model.get_embedding_client()

    def _call_with_retry(self, method_name, argument):
        """Çağrıyı yapar; "bad allocation" alırsa modeli tazeleyip bir kez daha dener.

        Bu makinede ONNX Runtime zaman zaman geçici "bad allocation" veriyor:
        bellek toplamda yeterli olsa bile yeterince büyük BİTİŞİK blok
        bulunamıyor (bellek parçalanması). Modeli boşaltıp yeniden yüklemek
        ayırmayı sıfırladığı için ikinci deneme genelde başarılı oluyor.

        Tek yeniden deneme yapıyoruz: sorun kalıcıysa (gerçekten RAM yok)
        döngüye girmek yerine anlaşılır bir hata vermek daha doğru.
        """
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                self._ensure_loaded()
                return getattr(self._client, method_name)(argument)
            except Exception:
                self.release()
                if attempt == _MAX_ATTEMPTS:
                    raise
                if self._verbose:
                    print(f"  (embedding modeli tazeleniyor, deneme "
                          f"{attempt + 1}/{_MAX_ATTEMPTS}...)")
                time.sleep(_RETRY_DELAY_SECONDS * attempt)

    def generate_embedding(self, text):
        return self._call_with_retry("generate_embedding", text)

    def generate_embeddings(self, texts):
        return self._call_with_retry("generate_embeddings", texts)

    def release(self):
        """Modeli bellekten atar. Sonraki çağrıda otomatik geri yüklenir."""
        if self._model is not None:
            try:
                self._model.unload()
            except Exception:
                pass
        self._client = None

    def close(self):
        self.release()


class ChatModel:
    """Sohbet modelini yöneten sarmalayıcı: yedekleme zinciri + bellek yönetimi.

    İKİ SORUNU BİRDEN ÇÖZER

    1) YEDEKLEME ZİNCİRİ
       Bir model diskte olsa bile belleğe SIĞMAYABİLİR. Phi-3.5-mini bu
       makinede "bad allocation" ile düşüyor. Tek sabit model yerine aday
       listesi deneyip ilk yüklenebileni kullanıyoruz; program çökmüyor.

    2) DÜŞÜK BELLEK MODU (keep_loaded=False)
       Bu makinede embedding modeli ile sohbet modeli AYNI ANDA bellekte
       duramıyor. Ölçüm:
           başlangıç              3.70 GB boş
           + embedding (0.6B)     3.06 GB boş
           + sohbet    (1.5B)     1.82 GB boş
           -> embedding çalıştırma denemesi: bad allocation

       Çözüm: sohbet modelini sadece cevap üretirken yükle, hemen sonra
       bellekten at. Embedding modeli kalıcı kalır.

       Neden embedding kalıcı, sohbet geçici? Yükleme süreleri:
           embedding yükleme: 7.2 s
           sohbet    yükleme: 3.0 s
       Ucuz olanı taşımak mantıklı.
    """

    def __init__(
        self,
        manager,
        aliases,
        device_preference,
        max_tokens: int,
        temperature: float,
        top_p: float,
        keep_loaded: bool = True,
        verbose: bool = True,
    ):
        self._manager = manager
        self._aliases = list(aliases)
        self._device_preference = device_preference
        self._settings = ChatClientSettings(
            max_tokens=max_tokens, temperature=temperature, top_p=top_p
        )
        self.keep_loaded = keep_loaded
        self._verbose = verbose

        self.alias = None      # hangi aday işe yaradı
        self._model = None
        self._client = None

    def _try_load(self, alias):
        """Tek bir adayı yüklemeyi dener; başarılıysa (model, client) döner."""
        model = load_model(self._manager, alias, self._device_preference, verbose=False)
        client = model.get_chat_client()
        client.settings = self._settings
        return model, client

    def _ensure_loaded(self):
        """Model bellekte değilse yükler. Adaylar sırayla denenir."""
        if self._client is not None:
            return

        # Daha önce çalışan bir aday bulduysak doğrudan onu kullan
        candidates = [self.alias] if self.alias else self._aliases

        errors = []
        for alias in candidates:
            try:
                self._model, self._client = self._try_load(alias)
                if self.alias != alias and self._verbose:
                    print(f"  Sohbet modeli: {alias}")
                self.alias = alias
                return
            except Exception as exc:  # SDK farklı istisna tipleri fırlatıyor
                errors.append(f"  - {alias}: {str(exc).splitlines()[0][:120]}")
                if self._verbose:
                    print(f"  {alias} yuklenemedi, sonraki adaya geciliyor...")

        raise RuntimeError(
            "Hicbir sohbet modeli yuklenemedi.\n"
            + "\n".join(errors)
            + "\n\nOneriler:\n"
            "  - Bellek bosalt (tarayici/IDE kapat) ve tekrar dene\n"
            "  - 'foundry model download qwen2.5-0.5b' ile daha kucuk model indir\n"
            "  - config.py icindeki CHAT_MODEL_CANDIDATES listesini duzenle"
        )

    def warm_up(self):
        """Hangi adayın çalıştığını başlangıçta belirler.

        NEDEN GEREKLİ?
        Model tembel (lazy) yükleniyordu, yani ilk soru sorulduğunda.
        Sonuç olarak "Sohbet modeli: phi-3.5-mini" mesajı akan cevabın
        ORTASINA giriyordu:
            Cevap:   Sohbet modeli: phi-3.5-mini
            Adresleme ve Yönlendirme

        Başlangıçta bir kez yükleyip alias'ı çözüyoruz. Düşük bellek
        modunda hemen boşaltıyoruz (yer açılsın), ama artık hangi modelin
        çalıştığını biliyoruz ve mesaj doğru yerde çıkıyor.
        """
        self._ensure_loaded()
        if not self.keep_loaded:
            self.release()
        return self.alias

    def release(self):
        """Modeli bellekten atar (düşük bellek modunda her cevaptan sonra)."""
        if self._model is not None:
            try:
                self._model.unload()
            except Exception:
                pass  # zaten boşaltılmışsa sorun değil
        self._model = None
        self._client = None

    def complete_chat(self, messages):
        """Cevap üretir. Düşük bellek modunda üretim sonrası modeli boşaltır.

        EmbeddingModel'deki ile aynı sebeple bir kez yeniden deniyoruz:
        geçici "bad allocation" hataları modeli tazeleyince genelde geçiyor.
        """
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                self._ensure_loaded()
                result = self._client.complete_chat(messages)
                if not self.keep_loaded:
                    self.release()
                return result
            except Exception:
                self.release()
                if attempt == _MAX_ATTEMPTS:
                    raise
                if self._verbose:
                    print(f"  (sohbet modeli tazeleniyor, deneme "
                          f"{attempt + 1}/{_MAX_ATTEMPTS}...)")
                # Bekleme ŞART: "Operation was cancelled" hatasında hemen
                # tekrar denemek işe yaramıyordu. Foundry Local servisinin
                # önceki isteği temizlemesi için zaman gerekiyor.
                time.sleep(_RETRY_DELAY_SECONDS * attempt)

    def stream_chat(self, messages):
        """Cevabı parça parça üretir (generator: her adımda yeni metin parçası).

        NEDEN AKIŞ (STREAMING)?
        Bu makinede bir cevap 85-115 saniye sürüyor. Akışsız çalışınca
        kullanıcı bu sürenin TAMAMINDA boş ekrana bakıyor. Akışla ilk
        kelimeler birkaç saniyede görünmeye başlıyor: toplam süre aynı
        kalıyor ama algılanan bekleme çok azalıyor.

        YENİDEN DENEME NOTU: akış başladıktan sonra güvenle tekrarlanamaz,
        çünkü kullanıcı yarım metni zaten görmüş olur ve baştan yazmak kafa
        karıştırır. Bu yüzden sadece HİÇ parça üretilmeden hata olursa bir
        kez yeniden deniyoruz.
        """
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            produced = False
            try:
                self._ensure_loaded()
                for chunk in self._client.complete_streaming_chat(messages):
                    if not chunk.choices:
                        continue
                    piece = chunk.choices[0].delta.content
                    if piece:
                        produced = True
                        yield piece
                if not self.keep_loaded:
                    self.release()
                return
            except Exception:
                self.release()
                if produced or attempt == _MAX_ATTEMPTS:
                    raise
                if self._verbose:
                    print(f"  (sohbet modeli tazeleniyor, deneme "
                          f"{attempt + 1}/{_MAX_ATTEMPTS}...)")
                time.sleep(_RETRY_DELAY_SECONDS * attempt)

    def close(self):
        self.release()
