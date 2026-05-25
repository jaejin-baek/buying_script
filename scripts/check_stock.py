"""
Cartier d'Amour bracelet (small, CRB6043300) 재고 감시기.

상품 페이지 HTML을 받아서
- '상담원 연결' 같은 '재고 없음' 마커가 보이면 → 재고 없음
- '장바구니에 담기' / '사이즈 선택' 같은 '재고 있음' 마커가 보이면 → 재고 있음
판정하고, 재고 있음일 때만 이메일 알림을 보낸다.

오탐을 줄이기 위해:
- fetch 실패는 알림 없이 비정상 종료
- '재고 있음' 마커가 있어도 '재고 없음' 마커가 같이 있으면 보수적으로 '없음' 처리
- 직전 상태를 state 파일에 저장해 두고, '없음 → 있음' 전이일 때만 알림
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

PRODUCT_URL = (
    "https://www.cartier.com/ko-kr/주얼리/브레이슬릿/다이아몬드-컬렉션/"
    "까르띠에-다무르-브레이슬릿-브릴리언트-컷-다이아몬드-스몰(small)-모델-"
    "CRB6043300.html"
)

# 한국어 / 영어 페이지 양쪽에서 관찰된 '재고 없음' 신호들.
OUT_OF_STOCK_MARKERS = [
    "상담원 연결",
    "상담원에게 문의",
    "현재 온라인에서 구매",  # "현재 온라인에서 구매할 수 없습니다" 등
    "재입고 알림",
    "Contact an ambassador",
    "Currently unavailable online",
    "Receive a notification as soon as",
    "back in stock",
]

# '재고 있음' 신호 — 하나라도 보이고 위쪽 마커가 없으면 거의 확실히 구매 가능.
IN_STOCK_MARKERS = [
    "장바구니에 담기",
    "장바구니에 추가",
    "사이즈 선택",
    "사이즈를 선택",
    "Add to cart",
    "Add to bag",
    "Select your size",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
}

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "last_status.json"


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def judge(html: str) -> tuple[bool, list[str], list[str]]:
    found_in = [m for m in IN_STOCK_MARKERS if m in html]
    found_out = [m for m in OUT_OF_STOCK_MARKERS if m in html]
    in_stock = bool(found_in) and not found_out
    return in_stock, found_in, found_out


def load_prev_status() -> bool | None:
    if not STATE_PATH.exists():
        return None
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return bool(data.get("in_stock"))
    except Exception:
        return None


def save_status(in_stock: bool) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"in_stock": in_stock}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    try:
        html = fetch_page(PRODUCT_URL)
    except Exception as e:
        print(f"[ERROR] fetch failed: {e}", file=sys.stderr)
        return 1

    in_stock, found_in, found_out = judge(html)
    prev = load_prev_status()

    print(f"[INFO] in_stock={in_stock} prev={prev}")
    print(f"[INFO] found_in={found_in}")
    print(f"[INFO] found_out={found_out}")

    # 마커가 하나도 안 잡히면 페이지 구조가 바뀌었거나 봇 차단 가능성 → 조용히 종료
    if not found_in and not found_out:
        print("[WARN] no marker matched. Page layout may have changed or got blocked.")
        return 2

    if in_stock and prev is not True:
        # '없음 → 있음' 전이일 때만 알림 (또는 첫 실행)
        from notify import send_notification

        body_lines = [
            "까르띠에 다무르 브레이슬릿(스몰, CRB6043300) 재고가 감지되었습니다.",
            "",
            f"상품 페이지: {PRODUCT_URL}",
            "",
            f"감지된 in-stock 마커: {found_in}",
            f"감지된 out-of-stock 마커: {found_out}",
            "",
            "⚠️ 빠르게 품절될 수 있으니 즉시 확인하세요.",
        ]
        try:
            send_notification(
                subject="🎉 [Cartier] 다무르 스몰 재고 발견",
                body="\n".join(body_lines),
            )
            print("[INFO] notification sent")
        except Exception as e:
            print(f"[ERROR] notification failed: {e}", file=sys.stderr)
            # 알림 실패해도 상태 저장은 하지 않음 → 다음 실행에서 재시도
            return 3

    save_status(in_stock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
