# Cartier d'Amour stock watcher

까르띠에 다무르 브레이슬릿(브릴리언트 컷 다이아몬드, **스몰**, `CRB6043300`) 의 공식몰 재고를
**11분마다** 확인해서, 재고가 들어오면 이메일로 알림을 보내는 GitHub Actions 봇.

알림 수신자:

- `sigkgk100@gmail.com`
- `qufquf_@naver.com`

## 동작 원리

상품 페이지 HTML을 받아서 다음을 본다.

- **재고 없음 마커**: "상담원 연결", "재입고 알림", "Contact an ambassador" 등
- **재고 있음 마커**: "장바구니에 담기", "사이즈 선택", "Add to cart" 등

두 마커 집합을 비교해서 **재고 있음 마커가 있고 + 재고 없음 마커가 없을 때만** 재고 있음으로
판정한다. 그리고 직전 상태(`state/last_status.json`)와 비교해 **'없음 → 있음' 전이일 때만**
메일을 보낸다 (똑같은 알림 반복 방지).

## 셋업

### 1. 이 레포 fork / clone

private 레포 권장. (수신자 메일 주소가 워크플로 yaml에 노출되어 있음)

### 2. Gmail 앱 비밀번호 발급

발신 계정으로 Gmail을 쓴다는 가정.

1. Google 계정에서 2단계 인증 켜기
2. <https://myaccount.google.com/apppasswords> 에서 앱 비밀번호 16자리 발급

### 3. GitHub Secrets 등록

레포 → **Settings → Secrets and variables → Actions → New repository secret** 에서
다음을 등록.

| 이름            | 값 예시                                           |
| --------------- | ------------------------------------------------- |
| `SMTP_HOST`     | `smtp.gmail.com`                                  |
| `SMTP_PORT`     | `465` (SSL) 또는 `587` (STARTTLS)                 |
| `SMTP_USER`     | 발신용 Gmail 주소                                 |
| `SMTP_PASSWORD` | Gmail 앱 비밀번호 16자리 (공백 없이)              |
| `MAIL_FROM`     | 발신용 Gmail 주소 (생략 시 `SMTP_USER` 사용)      |

> `MAIL_TO`는 워크플로 yaml에 이미 박혀 있으므로 secret으로 등록할 필요 없음.
> 나중에 수신자를 바꾸고 싶으면 `.github/workflows/stock-check.yml` 의 `MAIL_TO` 줄을 수정.

### 4. 동작 확인

레포 **Actions 탭 → "Cartier d'Amour stock check" → Run workflow** 로 수동 실행.

로그에 다음이 보이면 OK.

```
[INFO] in_stock=False prev=None
[INFO] found_in=[]
[INFO] found_out=['상담원 연결', ...]
```

(재고가 없는 게 정상이므로 `in_stock=False` 가 정상 동작)

이후 11분 간격으로 자동 실행되고, 재고가 들어오면 메일이 두 주소 모두에 도착한다.

> 네이버 메일은 외부 발신 메일을 스팸함으로 보내는 경우가 있다. 첫 메일 도착 후 스팸함도
> 한 번 확인하고, 발신 주소를 화이트리스트에 추가해 두면 안전하다.

## 트러블슈팅

### `[WARN] no marker matched` 가 뜬다

페이지가 JS로 늦게 그려지는 경우 `requests` 단순 GET으로는 본문이 안 잡힐 수 있다.
이 경우 두 가지 선택지:

1. `OUT_OF_STOCK_MARKERS` / `IN_STOCK_MARKERS` 를 실제 응답 HTML을 보고 보강
   - Actions 로그에서 응답 일부를 출력하도록 임시로 `print(html[:5000])` 추가
2. Playwright 같은 헤드리스 브라우저로 교체
   ```yaml
   - run: pip install playwright && playwright install chromium
   ```
   그리고 `check_stock.py`의 `fetch_page` 를 Playwright `page.content()` 로 교체

### 차단당하는 것 같다

- cron 간격을 더 길게 (15~30분) 늘린다
- `HEADERS`의 `User-Agent`를 더 최신 브라우저 것으로 갈아끼운다
- 그래도 안 되면 GitHub Actions IP가 차단당한 것 — Cloudflare Workers / 본인 VPS로 옮긴다

### 알림은 왔는데 들어가 보니 재고가 없다

판정 로직이 너무 느슨할 수 있다. `IN_STOCK_MARKERS` 에서 "사이즈 선택" 같은 약한 신호를 빼고
"장바구니에 담기" 류만 남기면 false positive 가 줄어든다.

## 주의사항

- 이 봇은 **감지 + 알림**만 한다. 자동 구매는 하지 않으며, 권장하지도 않는다 (이용약관 위반
  + 봇 차단 위험).
- GitHub Actions cron 은 정시 보장이 없어서 실제로는 5~10분 늦게 트리거되는 경우가 있다.
  더 정확한 주기가 필요하면 외부 cron (Cloudflare Workers Cron Triggers 등) 으로 옮기는 게 좋다.
- public 레포로 두면 수신 메일 주소와 워크플로 로그가 노출된다. **private 레포 권장**.
