from __future__ import annotations

from pathlib import Path

# Support running both as a module (package context) and as a standalone script.
try:  # pragma: no cover - simple import fallback
    from .indmoney_scraper import (
        scrape_all_selected_schemes,
        serialize_snapshots_to_jsonl,
    )
    from .reference_scraper import scrape_all_reference_pages
except ImportError:  # Direct script execution
    from indmoney_scraper import (
        scrape_all_selected_schemes,
        serialize_snapshots_to_jsonl,
    )
    from reference_scraper import scrape_all_reference_pages


def main() -> None:
    base_output = Path("data") / "phase1"
    base_output.mkdir(parents=True, exist_ok=True)

    snapshots = scrape_all_selected_schemes()
    serialize_snapshots_to_jsonl(
        snapshots, str(base_output / "indmoney_schemes.jsonl")
    )

    faq_pages = scrape_all_reference_pages()
    faqs_path = base_output / "reference_faqs.jsonl"
    with faqs_path.open("w", encoding="utf-8") as f:
        import json

        for faq in faq_pages:
            f.write(json.dumps(faq.model_dump(), default=str) + "\n")


if __name__ == "__main__":
    main()

