"""SQLite veri katmanı: chunk'ları ve embedding vektörlerini saklar.

TASARIM KARARLARI

1) Embedding'i BLOB olarak saklıyoruz, JSON metin olarak değil.
   1024 boyutlu bir vektör JSON'da ~20 KB metin, float32 BLOB'da 4 KB.
   Okurken json.loads() yerine np.frombuffer() kullanıyoruz -> çok daha hızlı.

2) "meta" tablosu embedding modelinin adını ve boyutunu tutar.
   Klasik hata: ingest'i bir modelle yapıp sorguyu başka modelle çalıştırmak.
   Vektörler uyumsuz olur ama kod patlamaz, sadece saçma cevaplar gelir.
   Bu tablo sayesinde uyumsuzluğu açıkça yakalayıp uyarabiliyoruz.
"""

import sqlite3
import numpy as np

# Vektörleri hep bu tiple sakla/oku. float64 kullanmaya gerek yok:
# kosinüs benzerliği için float32 hassasiyeti fazlasıyla yeterli.
VECTOR_DTYPE = np.float32

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,   -- kaynak dosya adı
    chunk_index INTEGER NOT NULL,   -- belge içindeki sıra numarası
    heading     TEXT,               -- ait olduğu bölüm başlığı
    text        TEXT    NOT NULL,   -- chunk metni (başlık dahil)
    word_count  INTEGER NOT NULL,
    embedding   BLOB    NOT NULL    -- float32 vektör
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# chunks tablosunda bulunması ZORUNLU sütunlar.
# Şema değişince eski .db dosyasını tanıyıp yeniden kurmak için kullanılır:
# CREATE TABLE IF NOT EXISTS eski tabloyu güncellemez, sessizce bırakır ve
# INSERT sırasında "no such column" hatası alırsın. Bu kontrol onu önler.
_REQUIRED_COLUMNS = {
    "id", "source", "chunk_index", "heading", "text", "word_count", "embedding"
}


def _schema_is_current(conn) -> bool:
    """Mevcut chunks tablosu güncel şemaya uyuyor mu?"""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
    ).fetchone()
    if not exists:
        return True  # tablo yok, sıfırdan oluşturulacak

    columns = {row[1] for row in conn.execute("PRAGMA table_info(chunks)")}
    return _REQUIRED_COLUMNS.issubset(columns)


def connect(db_path):
    """Veri tabanına bağlanır, yoksa klasörünü ve şemayı oluşturur.

    Eski sürüm bir veri tabanı bulursa chunks tablosunu düşürüp yeniden kurar.
    Veri kaybı değil: chunk'lar zaten belgelerden yeniden üretilebiliyor.
    """
    db_path = str(db_path)
    from pathlib import Path

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if not _schema_is_current(conn):
        print("  Eski veri tabani semasi bulundu, chunks tablosu yenileniyor...")
        conn.executescript("DROP TABLE IF EXISTS chunks;")
        conn.commit()

    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def vector_to_blob(vector) -> bytes:
    """Python listesi / numpy dizisi -> float32 BLOB."""
    return np.asarray(vector, dtype=VECTOR_DTYPE).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    """float32 BLOB -> numpy dizisi."""
    return np.frombuffer(blob, dtype=VECTOR_DTYPE)


def clear_chunks(conn) -> None:
    """Tüm chunk'ları siler (yeniden ingest öncesi)."""
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='chunks'")
    conn.commit()


def insert_chunks(conn, source: str, chunks) -> int:
    """Bir belgenin chunk'larını embedding'leriyle birlikte yazar.

    chunks: her elemanı {"heading","text","word_count","embedding"} olan liste.
    """
    rows = [
        (
            source,
            i,
            c.get("heading"),
            c["text"],
            c["word_count"],
            vector_to_blob(c["embedding"]),
        )
        for i, c in enumerate(chunks)
    ]
    conn.executemany(
        "INSERT INTO chunks (source, chunk_index, heading, text, word_count, embedding)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def load_chunks(conn):
    """Tüm chunk'ları okur.

    Döner: (kayitlar, matris)
      kayitlar -> [{"id","source","heading","text","word_count"}, ...]
      matris   -> (N, D) boyutlu float32 numpy dizisi, satır sırası kayitlarla aynı

    Vektörleri tek bir matriste toplamak önemli: benzerlik hesabını
    tek bir matris çarpımıyla yapabiliyoruz (chunk başına döngü yerine).
    """
    rows = conn.execute(
        "SELECT id, source, chunk_index, heading, text, word_count, embedding"
        " FROM chunks ORDER BY source, chunk_index"
    ).fetchall()

    if not rows:
        return [], np.zeros((0, 0), dtype=VECTOR_DTYPE)

    records = [
        {
            "id": r["id"],
            "source": r["source"],
            "chunk_index": r["chunk_index"],
            "heading": r["heading"],
            "text": r["text"],
            "word_count": r["word_count"],
        }
        for r in rows
    ]
    matrix = np.vstack([blob_to_vector(r["embedding"]) for r in rows])
    return records, matrix


def count_chunks(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]


def stats_by_source(conn):
    """Kaynak dosya başına chunk sayısı (ingest sonrası doğrulama için)."""
    return conn.execute(
        "SELECT source, COUNT(*) AS n FROM chunks GROUP BY source ORDER BY source"
    ).fetchall()


def set_meta(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_meta(conn, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default
