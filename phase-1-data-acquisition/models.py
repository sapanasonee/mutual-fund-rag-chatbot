from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl


class Holding(BaseModel):
    holding_name: str
    sector: Optional[str] = None
    asset_class: Optional[str] = None
    weight_percentage: Optional[float] = None


class FundScheme(BaseModel):
    scheme_id: Optional[str] = None  # internal ID, if available
    external_id: Optional[str] = None  # slug / ID from source
    scheme_name: str
    amc: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    riskometer: Optional[str] = None
    benchmark: Optional[str] = None
    lock_in_period_months: Optional[int] = None
    plan_type: Optional[str] = None  # Direct / Regular
    option: Optional[str] = None  # Growth / IDCW etc.
    expense_ratio: Optional[float] = None
    exit_load: Optional[str] = None
    minimum_sip_amount: Optional[float] = None
    minimum_lump_sum_amount: Optional[float] = None
    is_tax_saving: Optional[bool] = None
    # Key numeric metrics we want to surface for Q&A
    last_nav: Optional[float] = None
    last_nav_date: Optional[date] = None
    aum: Optional[float] = None  # Assets under management (approximate, as scraped)
    return_1y: Optional[float] = None  # 1-year return percentage
    return_3y: Optional[float] = None  # 3-year return percentage
    return_5y: Optional[float] = None  # 5-year return percentage
    source_url: Optional[HttpUrl] = None
    scraped_at: datetime


class NavPoint(BaseModel):
    scheme_name: str
    scheme_external_id: Optional[str] = None
    date: date
    nav: float


class FundMetadataText(BaseModel):
    scheme_name: str
    scheme_external_id: Optional[str] = None
    source: str  # e.g. "indmoney_description", "fund_objective"
    source_url: Optional[HttpUrl] = None
    clean_text: str
    scraped_at: datetime


class FaqPage(BaseModel):
    source: str  # SEBI / AMFI / AMC etc.
    topic: str
    url: HttpUrl
    clean_text: str
    scraped_at: datetime


class FundSnapshot(BaseModel):
    scheme: FundScheme
    holdings: List[Holding] = []
    metadata_blocks: List[FundMetadataText] = []

