"""Veri aktarım (ingestion) hattı: belge -> temizlik -> chunk -> vektör -> SQLite.

BORU HATTI
    docs/*.txt
      -> text_utils.clean_document()   gürültüyü at
      -> chunker.chunk_document()      anlamlı parçalara böl
      -> embedding modeli              her parçayı vektöre çevir (TOPLU)
      -> database.insert_chunks()      SQLite'a yaz

ESKİ KODA GÖRE FARKLAR
  1. Temizleme adımı eklendi (footer/sembol çöpü embedding'i bozuyordu).
  2. Chunk'lama başlık duyarlı hale geldi (18 chunk -> 57 chunk).
  3. Embedding'ler toplu hesaplanıyor: eskiden chunk başına 1 model çağrısı
     yapılıyordu. Artık 16'lık gruplar hâlinde tek çağrı -> belirgin hızlanma.
  4. Kullanılan embedding modeli 'meta' tablosuna kaydediliyor.
"""

import sys
from pathlib import Path

# Proje kökünü sys.path'e ekle ki 'config' ve 'src.*' importları çalışsın
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src import database, foundry_client
from src.chunker import chunk_document
from src.text_utils import clean_document

# Embedding modeline tek seferde kaç metin gönderilecek.
# Çok büyük yaparsak bellek/istek sınırına takılırız, çok küçük yaparsak yavaş.
EMBED_BATCH_SIZE = 16


def embed_batch(client, texts):
    """Metin listesini vektör listesine çevirir (toplu istek)."""
    response = client.generate_embeddings(texts)
    # Gelen sıra bozulabilir diye index'e göre sırala
    ordered = sorted(response.data, key=lambda d: d.index)
    return [d.embedding for d in ordered]


def embed_chunks(client, chunks, verbose=True):
    """Chunk listesine 'embedding' alanını ekler."""
    texts = [c["text"] for c in chunks]
    vectors = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        vectors.extend(embed_batch(client, batch))
        if verbose:
            done = min(start + EMBED_BATCH_SIZE, len(texts))
            print(f"      embedding {done}/{len(texts)}", end="\r", flush=True)

    if verbose:
        print(" " * 40, end="\r")

    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


def process_document(path: Path, embedding_client, verbose=True):
    """Tek bir belgeyi okur, temizler, böler ve embedding'lerini üretir."""
    raw = path.read_text(encoding="utf-8")
    if verbose:
        print(f"\n  {path.name}  ({len(raw)} karakter)")

    cleaned = clean_document(raw, verbose=verbose)
    if verbose:
        saved = len(raw) - len(cleaned)
        print(f"    temizlik sonrasi: {len(cleaned)} karakter ({saved} atildi)")

    chunks = chunk_document(
        cleaned,
        chunk_size=config.CHUNK_SIZE,
        overlap=config.CHUNK_OVERLAP,
        min_words=config.MIN_CHUNK_WORDS,
    )
    if not chunks:
        print(f"    UYARI: {path.name} icin chunk uretilemedi, atlaniyor")
        return []

    if verbose:
        counts = [c["word_count"] for c in chunks]
        print(
            f"    {len(chunks)} chunk | kelime: "
            f"min={min(counts)} ort={sum(counts) // len(counts)} max={max(counts)}"
        )

    return embed_chunks(embedding_client, chunks, verbose=verbose)


def run(verbose: bool = True) -> int:
    """Tüm ingestion hattını çalıştırır. Yazılan chunk sayısını döndürür."""
    print("=" * 60)
    print("VERI AKTARIMI (INGESTION)")
    print("=" * 60)

    doc_paths = sorted(Path(config.DOCS_DIR).glob("*.txt"))
    if not doc_paths:
        raise RuntimeError(f"{config.DOCS_DIR} icinde .txt belge bulunamadi.")
    print(f"{len(doc_paths)} belge bulundu.")

    manager = foundry_client.get_manager(config.APP_NAME, config.CACHE_DIR)
    print(f"\nEmbedding modeli: {config.EMBEDDING_MODEL}")
    # Ingest sırasında sohbet modeline ihtiyaç yok, bellek sorunu çıkmıyor.
    embedding_client = foundry_client.EmbeddingModel(
        manager, config.EMBEDDING_MODEL, config.DEVICE_PREFERENCE
    )

    conn = database.connect(config.DB_PATH)
    database.clear_chunks(conn)  # her ingest sifirdan baslar

    total = 0
    dimension = None
    for path in doc_paths:
        chunks = process_document(path, embedding_client, verbose=verbose)
        if not chunks:
            continue
        if dimension is None:
            dimension = len(chunks[0]["embedding"])
        total += database.insert_chunks(conn, path.name, chunks)

    # Sorgu tarafinin dogrulayabilmesi icin model bilgisini kaydet
    database.set_meta(conn, "embedding_model", config.EMBEDDING_MODEL)
    database.set_meta(conn, "embedding_dim", dimension or 0)
    database.set_meta(conn, "chunk_size", config.CHUNK_SIZE)
    database.set_meta(conn, "chunk_overlap", config.CHUNK_OVERLAP)

    print("\n" + "=" * 60)
    print("OZET")
    print("=" * 60)
    for row in database.stats_by_source(conn):
        print(f"  {row['source']:<28} {row['n']:>4} chunk")
    print(f"  {'TOPLAM':<28} {total:>4} chunk  (boyut: {dimension})")
    print(f"\nVeri tabani: {config.DB_PATH}")

    conn.close()
    return total


if __name__ == "__main__":
    run()
