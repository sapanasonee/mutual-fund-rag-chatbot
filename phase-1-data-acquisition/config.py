from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


GROK_API_KEY = os.getenv("GROK_API_KEY", "")


@dataclass(frozen=True)
class IndMoneySchemeSource:
    name: str
    url: str


INDMONEY_SCHEMES: List[IndMoneySchemeSource] = [
    IndMoneySchemeSource(
        name="HDFC Small Cap Fund Direct Growth",
        url="https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
    ),
    IndMoneySchemeSource(
        name="HDFC Flexi Cap Fund Direct Growth",
        url="https://www.indmoney.com/mutual-funds/hdfc-flexi-cap-fund-direct-plan-growth-option-3184",
    ),
    IndMoneySchemeSource(
        name="SBI Contra Fund Direct Growth",
        url="https://www.indmoney.com/mutual-funds/sbi-contra-fund-direct-growth-2612",
    ),
    IndMoneySchemeSource(
        name="HDFC ELSS Tax Saver Fund Direct Growth",
        url="https://www.indmoney.com/mutual-funds/hdfc-elss-taxsaver-direct-plan-growth-option-2685",
    ),
]


@dataclass(frozen=True)
class ReferencePage:
    source: str  # e.g. "SEBI", "AMFI", "HDFC AMC"
    topic: str
    url: str


# Authoritative public pages from SEBI / AMFI / AMCs for FAQs, riskometer, statements, etc.
REFERENCE_PAGES: List[ReferencePage] = [
    ReferencePage(
        source="SEBI",
        topic="ELSS overview",
        url="https://investor.sebi.gov.in/elss.html",
    ),
    ReferencePage(
        source="SEBI",
        topic="Riskometer explanation",
        url="https://investor.sebi.gov.in/riskometer.html",
    ),
    ReferencePage(
        source="SEBI",
        topic="Disclosure of expenses, returns and riskometer",
        url="https://www.sebi.gov.in/legal/circulars/nov-2024/disclosure-of-expenses-half-yearly-returns-yield-and-risk-o-meter-of-schemes-of-mutual-funds_88230.html",
    ),
    ReferencePage(
        source="AMFI",
        topic="Investor service FAQs",
        url="https://www.amfiindia.com/investor-corner/investor-center/investor-faq.html",
    ),
    ReferencePage(
        source="AMFI",
        topic="Mutual fund dividend / income distribution FAQs",
        url="https://www.amfiindia.com/investor-corner/knowledge-center/FAQs.html",
    ),
    ReferencePage(
        source="AMFI",
        topic="NAV explanation",
        url="https://www.amfiindia.com/investor-corner/knowledge-center/net-asset-value.html",
    ),
    ReferencePage(
        source="AMFI",
        topic="Understanding returns",
        url="https://www.amfiindia.com/investor-corner/knowledge-center/understand-return.html",
    ),
    ReferencePage(
        source="HDFC AMC",
        topic="Download account statement",
        url="https://www.hdfcfund.com/account-statement",
    ),
    ReferencePage(
        source="HDFC AMC",
        topic="Request statement",
        url="https://www.hdfcfund.com/investor-services/request-statement",
    ),
]

