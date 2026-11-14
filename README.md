# 주말 빈자리

아이와 자주 가는 박물관의 **주말·공휴일 회차별 잔여석**을 휴대폰에서 한눈에 보는 페이지예요.

- GitHub Actions가 30분마다 각 박물관 예약 페이지를 조회해요 (`scraper/`)
- 결과(`data.json`)와 페이지(`site/`)를 GitHub Pages에 올려요
- 예약은 하지 않고 **조회만** 해요. 회차를 누르면 박물관 예약 페이지로 이동해요.

## 지원하는 박물관

| 박물관 | 조회 방식 |
|---|---|
| 국립민속박물관 어린이박물관 | 예약 달력에 열린 날짜만 회차별 잔여석 조회 (로그인 불필요) |
| 국립중앙박물관 어린이박물관 | 예약 페이지가 쓰는 공개 JSON API로 회차별 잔여석 조회 (개인예약 2~5명) |
| 스포츠박물관 어린이박물관 | 세션 쿠키와 CSRF 토큰을 받은 뒤 날짜별 회차 조회 (정원-예약수, 오픈일은 `rsvtOpenYmd`) |
| 국립항공박물관 어린이공항 | `todayData.do`(gcode4) 한 번 호출로 열린 날짜 전체의 회차별 잔여석 조회. 아이 수 기준 |

## 로컬에서 실행

```
python scraper/scrape.py
cd site && python -m http.server 8000   # http://localhost:8000
```

## 박물관 추가하기

1. `scraper/museums/<이름>.py`에 `INFO`(id, name, bookingUrl)와 `fetch()`를 작성해요.
   `fetch()`는 주말 날짜 목록과 회차별 `remaining`, `status`(open/full/ended)를 돌려줘요.
2. `scraper/museums/__init__.py`의 `ALL`에 추가해요.

한 박물관 조회에 실패하면 직전 데이터를 유지하고 페이지에 안내 문구를 띄워요.
