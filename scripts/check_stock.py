"""
Cartier d'Amour bracelet (small, CRB6043300) 재고 감시기.

Playwright(헤드리스 Chromium) 로 페이지를 열어서 HTML을 받는다.
까르띠에 사이트가 GitHub Actions IP 대역의 requests 요청은 403으로 막기 때문에,
실제 브라우저로 위장해야 통과한다.

판정 로직:
- '상담원 연결' 같은 '재고 없음' 마커가 보이면 → 재고 없음
- '장바구니에 담기' / '사이즈 선택' 같은 '재고 있음' 마커가 보이면 → 재고 있음
- '없음 → 있음' 전이일 때만 메일 알림
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PRODUCT_URL = (
    "https://www.cartier.com/ko-kr/주얼리/브레이슬릿/다이아몬드-컬렉션/"
    "까르띠에-다무르-브레이슬릿-브릴리언트-컷-다이아몬드-스몰(small)-모델-"
    "CRB6043300.html"
)

OUT_OF_STOCK_MARKERS = [
    "상담원 연결",
    "상담원에게 문의",
    "현재 온라인에서 구매",
    "재입고 알림",
    "Contact an ambassador",
    "Currently unavailable online",
    "Receive a notification as soon as",
    "back in stock",
]

IN_STOCK_MARKERS = [
    "장바구니에 담기",
    "장바구니에 추가",
    "사이즈 선택",
    "사이즈를 선택",
    "Add to cart",
    "Add to bag",
    "Select your size",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "last_status.json"


def fetch_page(url: str) -> str:
    """Playwright로 페이지를 열고 최종 HTML을 반환."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # JS 렌더가 끝날 시간을 좀 줌 (네트워크 idle 까지 기다리지 않는 이유:
        # 까르띠에 페이지에 backgroud poll 등이 있어서 영원히 안 끝날 수 있음)
        page.wait_for_timeout(5_000)
        html = page.content()
        browser.close()
        return html


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

    print(f"[INFO] html length = {len(html)}")
    print(f"[INFO] in_stock={in_stock} prev={prev}")
    print(f"[INFO] found_in={found_in}")
    print(f"[INFO] found_out={found_out}")

    if not found_in and not found_out:
        print("[WARN] no marker matched. Page layout may have changed or got blocked.")
        # 디버깅용: HTML 앞부분만 출력해서 어떤 페이지를 받았는지 확인
        print("[DEBUG] html head:", html[:2000])
        return 2

    if in_stock and prev is not True:
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
            return 3

    save_status(in_stock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
