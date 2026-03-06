from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import List, Tuple

import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from difflib import SequenceMatcher

import requests

# Support both package and direct-script imports
try:  # pragma: no cover - import flexibility
    from .config import INDMONEY_SCHEMES
    from .models import FundMetadataText, FundScheme, FundSnapshot, Holding
except ImportError:  # When run as a plain script
    from config import INDMONEY_SCHEMES
    from models import FundMetadataText, FundScheme, FundSnapshot, Holding

from playwright.sync_api import sync_playwright


_BOT_BLOCK_MARKERS = (
    "verifies you are not a bot",
    "protect against malicious bots",
    "checking your browser",
    "just a moment",
)


def _looks_like_bot_block(html: str) -> bool:
    if not html:
        return True
    lower = html.lower()
    return any(m in lower for m in _BOT_BLOCK_MARKERS)


def _mfapi_best_match(query_name: str) -> dict | None:
    """
    Best-effort mapping from fund name -> MFAPI scheme code.
    MFAPI is a public mutual-fund NAV API (AMFI-backed). This is used ONLY as a fallback
    when INDMoney pages are blocked by bot protections.
    """
    q = (query_name or "").strip()
    if not q:
        return None
    try:
        resp = requests.get(
            "https://api.mfapi.in/mf/search",
            params={"q": q},
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not resp.ok:
            return None
        items = resp.json()
        if not isinstance(items, list) or not items:
            return None

        ql = q.lower()
        best = None
        best_score = -1.0
        for it in items[:50]:
            name = str(it.get("schemeName") or "")
            nl = name.lower()
            score = SequenceMatcher(a=ql, b=nl).ratio()
            # bonus if all query words appear
            words = [w for w in re.split(r"\s+", ql) if len(w) > 2]
            if words and all(w in nl for w in words[:3]):
                score += 0.2
            if score > best_score:
                best = it
                best_score = score
        return best
    except Exception:
        return None


def _mfapi_fetch_nav_series(scheme_code: str) -> list[tuple[datetime, float]]:
    try:
        resp = requests.get(
            f"https://api.mfapi.in/mf/{scheme_code}",
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not resp.ok:
            return []
        payload = resp.json()
        data = payload.get("data") or []
        out: list[tuple[datetime, float]] = []
        for row in data:
            d = row.get("date")
            nav = row.get("nav")
            if not d or nav in (None, ""):
                continue
            try:
                # MFAPI date format: DD-MM-YYYY
                dt = datetime.strptime(str(d), "%d-%m-%Y")
                out.append((dt, float(str(nav))))
            except Exception:
                continue
        out.sort(key=lambda x: x[0])  # ascending
        return out
    except Exception:
        return []


def _return_pct(nav_latest: float, nav_then: float) -> float | None:
    if nav_latest <= 0 or nav_then <= 0:
        return None
    return round((nav_latest / nav_then - 1.0) * 100.0, 2)


def _nav_at_or_before(series: list[tuple[datetime, float]], target: datetime) -> float | None:
    # series ascending; scan from end
    for dt, nav in reversed(series):
        if dt <= target:
            return nav
    return None


def _fallback_snapshot_from_mfapi(scheme_name_hint: str, indmoney_url: str) -> FundSnapshot:
    scraped_at = datetime.utcnow()
    match = _mfapi_best_match(scheme_name_hint)
    series: list[tuple[datetime, float]] = []
    mfapi_code = None
    mfapi_name = scheme_name_hint or "Unknown Scheme"
    if match:
        mfapi_code = str(match.get("schemeCode") or "") or None
        mfapi_name = str(match.get("schemeName") or "") or mfapi_name
        if mfapi_code:
            series = _mfapi_fetch_nav_series(mfapi_code)

    last_nav = None
    last_nav_date = None
    ret_1y = ret_3y = ret_5y = None
    if series:
        dt_latest, nav_latest = series[-1]
        last_nav = nav_latest
        last_nav_date = dt_latest.date()

        nav_1y = _nav_at_or_before(series, dt_latest.replace(year=dt_latest.year - 1))
        nav_3y = _nav_at_or_before(series, dt_latest.replace(year=dt_latest.year - 3))
        nav_5y = _nav_at_or_before(series, dt_latest.replace(year=dt_latest.year - 5))
        if nav_1y:
            ret_1y = _return_pct(nav_latest, nav_1y)
        if nav_3y:
            ret_3y = _return_pct(nav_latest, nav_3y)
        if nav_5y:
            ret_5y = _return_pct(nav_latest, nav_5y)

    # Simple heuristic: ELSS schemes have 3-year lock-in.
    lock_in_months = 36 if re.search(r"\belss\b|tax saver", mfapi_name.lower()) else None

    scheme = FundScheme(
        scheme_name=mfapi_name,
        external_id=mfapi_code,  # MFAPI scheme code as external id for retrieval/filtering
        lock_in_period_months=lock_in_months,
        last_nav=last_nav,
        last_nav_date=last_nav_date,
        return_1y=ret_1y,
        return_3y=ret_3y,
        return_5y=ret_5y,
        source_url=indmoney_url,
        scraped_at=scraped_at,
    )

    blocks = [
        FundMetadataText(
            scheme_name=mfapi_name,
            scheme_external_id=mfapi_code,
            source="mfapi_fallback",
            source_url="https://api.mfapi.in/",
            clean_text=(
                "INMoney scheme page was blocked by bot protection during automated ingestion. "
                "As a fallback, NAV history was fetched from MFAPI (AMFI-backed NAV API) to populate "
                "latest NAV and approximate period returns where available."
            ),
            scraped_at=scraped_at,
        )
    ]

    return FundSnapshot(scheme=scheme, holdings=[], metadata_blocks=blocks)


def _fetch_html(url: str) -> str:
    with sync_playwright() as p:
        # Try to reduce automation fingerprinting. This is best-effort and may still
        # be blocked by stronger bot protections.
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()
        page.set_extra_http_headers(
            {
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page.add_init_script(
            """
            // Minimize obvious automation signals
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
            """
        )

        html: str = ""
        # Some providers do a JS-based check then redirect; wait + retry/reload.
        for attempt in range(3):
            try:
                page.goto(url, timeout=90000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=90000)
                page.wait_for_timeout(2000 + attempt * 1500)
                html = page.content()

                if not _looks_like_bot_block(html):
                    break

                # Try a hard reload to allow the verification redirect to complete.
                page.reload(timeout=90000, wait_until="networkidle")
                page.wait_for_timeout(4000 + attempt * 2000)
                html = page.content()
                if not _looks_like_bot_block(html):
                    break
            except Exception:
                # Continue attempts; caller will handle empty/blocked HTML downstream.
                continue

        context.close()
        browser.close()
        return html
def _parse_scheme_basic_info(soup: BeautifulSoup, url: str) -> FundScheme:
    scraped_at = datetime.utcnow()

    title_el = soup.find("h1")
    scheme_name = title_el.get_text(strip=True) if title_el else "Unknown Scheme"

    # Use the last URL path segment as an external_id/slug.
    try:
        path = urlparse(url).path.strip("/")
        external_id = path.split("/")[-1] if path else None
    except Exception:
        external_id = None

    page_text = soup.get_text(separator="\n", strip=True)

    def _re_first(pattern: str) -> str | None:
        m = re.search(pattern, page_text, flags=re.IGNORECASE)
        if not m:
            return None
        return (m.group(1) or "").strip()

    def _re_first_float(pattern: str) -> float | None:
        s = _re_first(pattern)
        if not s:
            return None
        s = s.replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            return None

    def _re_first_int(pattern: str) -> int | None:
        f = _re_first_float(pattern)
        if f is None:
            return None
        return int(f)

    scheme = FundScheme(
        scheme_name=scheme_name,
        external_id=external_id,
        amc=None,
        category=None,
        sub_category=None,
        riskometer=None,
        benchmark=None,
        lock_in_period_months=None,
        plan_type=None,
        option=None,
        expense_ratio=None,
        exit_load=None,
        minimum_sip_amount=None,
        minimum_lump_sum_amount=None,
        is_tax_saving=None,
        last_nav=None,
        last_nav_date=None,
        source_url=url,
        scraped_at=scraped_at,
    )

    # Structured metrics extraction (regex-based)
    scheme.expense_ratio = _re_first_float(r"Expense\s*ratio\s*([\d.]+)\s*%")

    # AUM: store numeric crores when present (e.g., "₹36941 Cr" -> 36941.0)
    scheme.aum = _re_first_float(r"AUM\s*₹\s*([\d,]+(?:\.\d+)?)\s*Cr")

    # Exit load: prefer the key-stats block value (often a percentage like "1.0%")
    exit_load_val = None
    m_exit = re.search(
        r"Exit\s*Load\s*(?:\n|\s)+\s*([0-9]+(?:\.[0-9]+)?\s*%[^\n]*)",
        page_text,
        flags=re.IGNORECASE,
    )
    if m_exit:
        exit_load_val = (m_exit.group(1) or "").strip()
    if not exit_load_val:
        # Fallback (may hit descriptive sentences; keep only if it looks like a value)
        candidate = _re_first(r"Exit\s*Load\s*([^\n]+)")
        if candidate and re.search(r"%|\d", candidate):
            exit_load_val = candidate.strip()
    if exit_load_val:
        scheme.exit_load = exit_load_val

    # Lock-in
    lock_raw = _re_first(r"Lock\s*In\s*([^\n]+)")
    if lock_raw:
        if re.search(r"no\s*lock", lock_raw, flags=re.IGNORECASE):
            scheme.lock_in_period_months = 0
        else:
            # Attempt to parse "3 years" / "36 months" etc.
            months = None
            m_months = re.search(r"(\d+)\s*month", lock_raw, flags=re.IGNORECASE)
            m_years = re.search(r"(\d+)\s*year", lock_raw, flags=re.IGNORECASE)
            if m_months:
                months = int(m_months.group(1))
            elif m_years:
                months = int(m_years.group(1)) * 12
            if months is not None:
                scheme.lock_in_period_months = months

    # Benchmark
    bench_val = _re_first(r"Benchmark\s*([^\n]+)")
    if bench_val:
        scheme.benchmark = bench_val

    # Minimum SIP / Lumpsum when presented as "₹100/₹100"
    min_pair = _re_first(r"Min\s*Lumpsum\/SIP\s*₹\s*([\d,]+)\s*\/\s*₹\s*([\d,]+)")
    if min_pair:
        # _re_first only returns first group; so parse with a dedicated regex:
        m = re.search(
            r"Min\s*Lumpsum\/SIP\s*₹\s*([\d,]+)\s*\/\s*₹\s*([\d,]+)",
            page_text,
            flags=re.IGNORECASE,
        )
        if m:
            try:
                scheme.minimum_lump_sum_amount = float(m.group(1).replace(",", ""))
                scheme.minimum_sip_amount = float(m.group(2).replace(",", ""))
            except Exception:
                pass

    # NAV and date (e.g. "₹148.23" + "NAV as on 05 Mar 2026")
    nav_val = _re_first_float(r"NAV\s*as\s*on\s*\d{2}\s*[A-Za-z]{3}\s*\d{4}[\s\S]*?₹\s*([\d.]+)")
    nav_date_str = _re_first(r"NAV\s*as\s*on\s*(\d{2}\s*[A-Za-z]{3}\s*\d{4})")
    if nav_val is None:
        # Most pages present the value before the "NAV as on" label.
        nav_val = _re_first_float(r"₹\s*([\d.]+)\s*\n.*?\nNAV\s*as\s*on")
    if nav_val is not None:
        scheme.last_nav = nav_val
    if nav_date_str:
        try:
            scheme.last_nav_date = datetime.strptime(nav_date_str, "%d %b %Y").date()
        except Exception:
            pass

    return scheme


def _parse_holdings(soup: BeautifulSoup) -> List[Holding]:
    holdings: List[Holding] = []
    tables = soup.find_all("table")
    for table in tables:
        header_els = table.find_all("th")
        headers = [th.get_text(strip=True).lower() for th in header_els]
        if not headers:
            continue
        if not any(
            "holding" in h or "company" in h or "stock" in h or "weight" in h
            for h in headers
        ):
            continue

        weight_col = None
        name_col = None
        sector_col = None
        for i, h in enumerate(headers):
            if "weight" in h or (i < len(headers) and "%" in h):
                weight_col = i
            if "holding" in h or "company" in h or "stock" in h or "name" in h:
                name_col = i
            if "sector" in h:
                sector_col = i

        for row in table.find_all("tr"):
            tds = row.find_all("td")
            if not tds:
                continue
            cells = []
            for td in tds:
                link = td.find("a")
                text = (link.get_text(strip=True) if link else td.get_text(strip=True)) or ""
                cells.append(text)

            if len(cells) < 2:
                continue

            weight = None
            if weight_col is not None and weight_col < len(cells):
                raw = cells[weight_col].replace("%", "").strip()
                try:
                    w = float(raw)
                    if 0 <= w <= 100:
                        weight = w
                except ValueError:
                    pass

            if weight is None:
                for i, c in enumerate(cells):
                    raw = c.replace("%", "").strip()
                    try:
                        w = float(raw)
                        if 0 <= w <= 100:
                            weight = w
                            if weight_col is None:
                                weight_col = i
                            break
                    except ValueError:
                        continue

            name = None
            if name_col is not None and name_col < len(cells):
                cand = cells[name_col]
                if cand and not re.match(r"^[\d.%\s-]+$", cand):
                    name = cand
            if not name:
                for i, c in enumerate(cells):
                    if c and not re.match(r"^[\d.%\s-]+$", c) and len(c) > 3:
                        name = c
                        break

            sector = None
            if sector_col is not None and sector_col < len(cells):
                sector = cells[sector_col] or None

            if name and weight is not None:
                holdings.append(
                    Holding(
                        holding_name=name,
                        sector=sector,
                        asset_class=None,
                        weight_percentage=weight,
                    )
                )

    if holdings:
        return holdings

    page_text = soup.get_text(separator="\n", strip=True)
    for m in re.finditer(
        r"([A-Za-z][A-Za-z0-9\s&.,-]*(?:Ltd|Limited|Co|Corp)?)\s*\((\d+(?:\.\d+)?)\s*%\)",
        page_text,
    ):
        name, pct = m.group(1).strip(), float(m.group(2))
        if 0 < pct <= 100 and len(name) > 4:
            holdings.append(
                Holding(
                    holding_name=name,
                    sector=None,
                    asset_class=None,
                    weight_percentage=pct,
                )
            )
    return holdings


def _parse_metadata_blocks(soup: BeautifulSoup, url: str) -> List[FundMetadataText]:
    scraped_at = datetime.utcnow()
    blocks: List[FundMetadataText] = []

    paragraphs = soup.find_all("p")
    text_chunks: List[str] = []
    for p in paragraphs:
        txt = p.get_text(" ", strip=True)
        if txt:
            text_chunks.append(txt)

    if text_chunks:
        blocks.append(
            FundMetadataText(
                scheme_name="",
                scheme_external_id=None,
                source="indmoney_page_text",
                source_url=url,
                clean_text="\n".join(text_chunks),
                scraped_at=scraped_at,
            )
        )

    return blocks


def scrape_indmoney_scheme(url: str) -> FundSnapshot:
    # Backward-compatible wrapper; prefer scrape_indmoney_scheme_named for better fallback.
    return scrape_indmoney_scheme_named(url, scheme_name_hint=url)


def scrape_indmoney_scheme_named(url: str, scheme_name_hint: str) -> FundSnapshot:
    html = _fetch_html(url)
    if _looks_like_bot_block(html):
        return _fallback_snapshot_from_mfapi(scheme_name_hint, url)
    soup = BeautifulSoup(html, "html.parser")
    scheme = _parse_scheme_basic_info(soup, url)
    holdings = _parse_holdings(soup)
    metadata_blocks = _parse_metadata_blocks(soup, url)
    if metadata_blocks:
        for block in metadata_blocks:
            block.scheme_name = scheme.scheme_name
    return FundSnapshot(scheme=scheme, holdings=holdings, metadata_blocks=metadata_blocks)


def scrape_all_selected_schemes() -> List[FundSnapshot]:
    snapshots: List[FundSnapshot] = []
    for src in INDMONEY_SCHEMES:
        snapshot = scrape_indmoney_scheme_named(src.url, src.name)
        snapshots.append(snapshot)
    return snapshots


def serialize_snapshots_to_jsonl(snapshots: List[FundSnapshot], output_path: str) -> None:
    import json
    from pathlib import Path

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for snap in snapshots:
            record = {
                "scheme": snap.scheme.model_dump(),
                "holdings": [h.model_dump() for h in snap.holdings],
                "metadata_blocks": [m.model_dump() for m in snap.metadata_blocks],
            }
            f.write(json.dumps(record, default=str) + "\n")

