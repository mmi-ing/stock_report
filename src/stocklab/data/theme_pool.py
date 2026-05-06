"""테마 키워드 → 후보 종목 매핑.

README §10 (한국 테마) 와 §11 (미국 테마) 의 사전을 코드로.
키워드 매칭은 정확 일치가 아닌 부분 일치 — "소부장 추천", "AI 반도체 공격적" 같은
입력에서도 키워드를 잡아낼 수 있게 router 가 부분 검색한다.
"""
from __future__ import annotations

THEME_KR: dict[str, list[str]] = {
    "소부장": [
        "042700.KQ", "058470.KQ", "005290.KQ", "039030.KQ", "240810.KQ",
        "403870.KQ", "357780.KQ", "036930.KQ", "319660.KQ",
    ],
    "반도체 소부장": [
        "042700.KQ", "058470.KQ", "005290.KQ", "039030.KQ", "240810.KQ",
        "403870.KQ", "357780.KQ",
    ],
    "K-방산": [
        "012450.KS", "079550.KS", "064350.KS", "047810.KS", "103140.KS",
    ],
    "방산": [
        "012450.KS", "079550.KS", "064350.KS", "047810.KS", "103140.KS",
    ],
    "2차전지": [
        "373220.KS", "006400.KS", "096770.KS", "003670.KS", "247540.KQ",
        "066970.KQ", "005490.KS",
    ],
    "배터리": [
        "373220.KS", "006400.KS", "096770.KS", "003670.KS", "247540.KQ",
    ],
    "바이오": [
        "207940.KS", "068270.KS", "326030.KS", "000100.KS", "128940.KS",
        "196170.KQ",
    ],
    "제약": [
        "000100.KS", "128940.KS", "207940.KS", "068270.KS",
    ],
    "조선": [
        "009540.KS", "010140.KS", "042660.KS", "329180.KS",
    ],
    "원전": [
        "034020.KS", "052690.KS", "083650.KQ", "032820.KQ",
    ],
    "엔터": [
        "352820.KS", "041510.KQ", "035900.KQ", "122870.KQ",
    ],
    "미디어": [
        "352820.KS", "041510.KQ", "035900.KQ",
    ],
    "게임": [
        "259960.KS", "036570.KS", "263750.KQ", "293490.KQ", "251270.KS",
    ],
    "로봇": [
        "277810.KQ", "454910.KS", "056080.KQ",
    ],
    "우주항공": [
        "047810.KS", "208370.KQ", "189300.KQ", "211270.KQ",
    ],
    "K-AI": [
        "108860.KQ", "304100.KQ", "402030.KQ", "300080.KQ",
    ],
    "한국 AI": [
        "108860.KQ", "304100.KQ", "402030.KQ", "300080.KQ",
    ],
    "화장품": [
        "051900.KS", "090430.KS", "192820.KS", "161890.KS", "237880.KQ",
    ],
    "K-뷰티": [
        "051900.KS", "090430.KS", "192820.KS", "161890.KS", "237880.KQ",
    ],
}

THEME_US: dict[str, list[str]] = {
    "AI 반도체": ["NVDA", "AMD", "AVGO", "TSM", "MU", "ARM", "MRVL", "ASML"],
    "AI 칩": ["NVDA", "AMD", "AVGO", "TSM", "MU"],
    "반도체": ["NVDA", "AMD", "AVGO", "TSM", "MU", "INTC"],
    "클라우드": ["MSFT", "AMZN", "GOOGL", "ORCL", "CRM", "NOW", "SNOW"],
    "EV": ["TSLA", "RIVN", "LCID", "F", "GM"],
    "전기차": ["TSLA", "RIVN", "LCID", "F", "GM"],
    "자동차": ["TSLA", "F", "GM", "TM", "STLA"],
    "우주": ["LMT", "RTX", "BA", "ASTS", "RKLB", "LHX", "NOC"],
    "우주항공": ["LMT", "RTX", "BA", "ASTS", "RKLB"],
    "핀테크": ["V", "MA", "SQ", "PYPL", "SOFI", "COIN", "AFRM"],
    "사이버보안": ["CRWD", "PANW", "ZS", "NET", "OKTA", "S", "FTNT"],
    "보안": ["CRWD", "PANW", "ZS", "NET", "OKTA"],
    "양자컴퓨팅": ["IBM", "IONQ", "RGTI", "QBTS"],
    "양자": ["IBM", "IONQ", "RGTI", "QBTS"],
    "헬스케어": ["LLY", "NVO", "PFE", "MRK", "JNJ"],
    "비만약": ["LLY", "NVO"],
    "AI 인프라": ["VST", "CEG", "NEE", "GEV", "ETR"],
    "데이터센터": ["DLR", "EQIX", "AMT", "CCI"],
}

MACRO_THEMES: dict[str, list[str]] = {
    "금리 인하 수혜주": ["DLR", "EQIX", "AMT", "CCI", "VICI", "O", "NEE"],
    "환율 수혜주": ["005930.KS", "000660.KS", "012450.KS", "047810.KS"],
    "인플레 헤지": ["GLD", "SLV", "XLE", "XOM", "CVX"],
    "고배당주": ["O", "MO", "VZ", "T", "XOM", "CVX", "PFE"],
    "가치주": ["BRK-B", "JNJ", "JPM", "PG", "KO"],
    "성장주": ["NVDA", "META", "TSLA", "GOOGL", "AMZN"],
}


def all_themes() -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    merged.update(THEME_KR)
    merged.update(THEME_US)
    merged.update(MACRO_THEMES)
    return merged


def find_theme(text: str) -> tuple[str, list[str]] | None:
    """입력 텍스트에서 가장 긴 매칭 테마 키워드를 찾아 (키워드, 종목 리스트) 반환.

    "소부장 추천 공격적" → ("소부장", [...]).
    가장 긴 키 우선으로 매칭해 "AI 반도체" 가 "AI" 보다 먼저 잡히게 한다.
    """
    pool = all_themes()
    for key in sorted(pool.keys(), key=len, reverse=True):
        if key in text:
            return key, pool[key]
    return None
