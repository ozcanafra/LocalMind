"""Yerel RAG Soru-Cevap Asistanı - komut satırı arayüzü.

KULLANIM
    python main.py ingest              Belgeleri okuyup veri tabanını kurar
    python main.py chat                Etkileşimli soru-cevap (varsayılan)
    python main.py ask "sorunuz"       Tek soru sorup çıkar
    python main.py info                Veri tabanı durumunu gösterir

PDF planındaki "Seçenek A: CLI" arayüzüne karşılık gelir.
"""

import argparse
import sys
from pathlib import Path

# Proje kökünü sys.path'e ekle (nereden çalıştırılırsa çalıştırılsın importlar bulunsun)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

EXIT_WORDS = {"exit", "quit", "çık", "cik", "q"}


def print_sources(sources, show_all: bool = True) -> None:
    """Kullanılan kaynakları skorlarıyla yazdırır (şeffaflık + hata ayıklama)."""
    if not sources:
        return
    print("  --- Bulunan kaynaklar ('*' = modele gönderildi) ---")
    for i, s in enumerate(sources, start=1):
        heading = s.get("heading") or "-"
        mark = "*" if s.get("used_in_prompt") else " "
        print(
            f"  {mark}[{i}] {s['source']}  (skor {s['score']:.3f}"
            f" | vektör {s['dense_score']:.3f}"
            f" | kelime {s['keyword_score']:.3f})"
        )
        if show_all:
            print(f"       {heading[:78]}")


def print_result(result, verbose: bool = True) -> None:
    if verbose:
        print()
        print_sources(result["sources"])
        print()
    print(f"Cevap: {result['answer']}")
    if verbose:
        print(f"\n({_timing(result)})")
    print("=" * 60)


def _timing(result) -> str:
    """Süre satırı. Önbellekten geldiyse belirtir (şeffaflık)."""
    if result.get("cached"):
        return f"{result['elapsed']:.1f} saniye - önbellekten"
    return f"{result['elapsed']:.1f} saniye"


def ask_streaming(pipeline, question: str, verbose: bool = True):
    """Soruyu sorar ve cevabı AKIŞ hâlinde ekrana yazar.

    Sıra önemli: önce kaynaklar (~2 sn), sonra akan cevap (~90 sn).
    Kullanıcı ilk saniyelerde neyin bulunduğunu görür, sonra cevabın
    yazıldığını izler. Toplam süre aynı ama bekleme hissi çok daha az.
    """
    state = {"started": False}

    def show_sources(sources):
        if verbose:
            print()
            print_sources(sources)
        print("\nCevap: ", end="", flush=True)
        state["started"] = True

    def show_text(piece):
        print(piece, end="", flush=True)

    result = pipeline.answer_query(
        question, on_text=show_text, on_sources=show_sources
    )

    # Eşik koruması devreye girdiyse akış hiç başlamaz (model çağrılmaz)
    if not state["started"]:
        print(f"\nCevap: {result['answer']}")
    else:
        print()

    if verbose:
        print(f"\n({_timing(result)})")
    print("=" * 60)
    return result


# --- komutlar ---------------------------------------------------------------


def cmd_ingest(args) -> int:
    from src import ingest

    ingest.run(verbose=not args.quiet)
    return 0


def cmd_info(args) -> int:
    from src import database

    conn = database.connect(config.DB_PATH)
    total = database.count_chunks(conn)

    print(f"Veri tabanı : {config.DB_PATH}")
    print(f"Toplam chunk: {total}")
    if total:
        print(f"Embedding   : {database.get_meta(conn, 'embedding_model')}"
              f" (boyut {database.get_meta(conn, 'embedding_dim')})")
        print(f"Chunk ayarı : {database.get_meta(conn, 'chunk_size')} kelime,"
              f" {database.get_meta(conn, 'chunk_overlap')} overlap")
        print("\nBelge başına:")
        for row in database.stats_by_source(conn):
            print(f"  {row['source']:<28} {row['n']:>4} chunk")
    else:
        print("\nVeri tabanı boş. 'python main.py ingest' çalıştır.")
    conn.close()
    return 0


def cmd_ask(args) -> int:
    from src.pipeline import RagPipeline

    pipeline = RagPipeline.create(verbose=not args.quiet, fast=args.fast)
    try:
        if args.no_stream:
            result = pipeline.answer_query(args.question)
            print_result(result, verbose=not args.quiet)
        else:
            result = ask_streaming(pipeline, args.question, verbose=not args.quiet)
        return 0 if result["found"] else 1
    finally:
        pipeline.close()


def cmd_chat(args) -> int:
    from src.pipeline import RagPipeline

    print("=" * 60)
    print("YEREL RAG ASİSTANI")
    print("=" * 60)

    pipeline = RagPipeline.create(verbose=True, fast=args.fast)
    print("Sorularınızı yazın. Çıkmak için 'exit'.\n" + "=" * 60)

    try:
        while True:
            try:
                question = input("\nSoru: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGörüşürüz.")
                break

            if question.lower() in EXIT_WORDS:
                print("Görüşürüz.")
                break
            if not question:
                continue

            if args.no_stream:
                print_result(pipeline.answer_query(question), verbose=True)
            else:
                ask_streaming(pipeline, question, verbose=True)
    finally:
        pipeline.close()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Yerel RAG Soru-Cevap Asistanı (Foundry Local + SQLite)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Ayrıntılı çıktıyı kapat"
    )
    parser.add_argument(
        "--no-stream", action="store_true",
        help="Akışı kapat (cevap tamamlanınca tek seferde yazılır)",
    )
    parser.add_argument(
        "--fast", action="store_true",
        help="Hız modu: küçük modeli tercih et (~35 sn, kalite biraz düşer)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ingest", help="Belgeleri veri tabanına aktar")
    sub.add_parser("info", help="Veri tabanı durumunu göster")
    sub.add_parser("chat", help="Etkileşimli soru-cevap (varsayılan)")

    p_ask = sub.add_parser("ask", help="Tek soru sor")
    p_ask.add_argument("question", help="Sorulacak soru")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "ingest": cmd_ingest,
        "info": cmd_info,
        "ask": cmd_ask,
        "chat": cmd_chat,
    }
    handler = handlers.get(args.command or "chat")

    try:
        return handler(args)
    except RuntimeError as exc:
        print(f"\nHATA: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
