# folio — 한투 계좌 분석 어드바이저 PRD v1.0

> **상태**: ✅ Finalized
> **작성일**: 2026-05-04
> **작성자**: 본인 (개인 프로젝트)
> **범위**: 국내주식 한정, 분석 전용 (주문 기능 없음)

---

## 1. 한 줄 정의

한국투자증권 OpenAPI로 내 국내주식 계좌 데이터를 직접 가져와, 포트폴리오를 자동 분석하고 LLM 어드바이저가 검토 의견을 제시하는 **로컬 1인 TUI 도구**. 일별 스냅샷과 LLM 출력을 SQLite에 누적해 시계열 분석을 지원한다.

이름 **folio**는 portfolio의 줄임이자 "책 한 장"을 뜻하는 영단어.

## 2. 배경 & 문제

- 한투 MTS는 잔고/거래만 보여주고 분석 시각이 없음
- LLM이 잘하는 영역인데 내 실데이터에 직접 붙는 개인용 도구가 없음
- 매일 빠르게 확인할 수 있는 CLI/TUI 형태가 본인 사용 패턴(개발자, 터미널 상주)에 잘 맞음
- 시계열 분석을 위해 가벼운 영속화 필요 → SQLite로 운영 부담 최소화

## 3. 목표 / 비목표

### 목표
- KIS OpenAPI로 국내주식 잔고/시세/거래내역 직접 조회
- 포트폴리오 핵심 메트릭 자동 산출 (집중도, 섹터, 수익률, 리스크)
- LLM 어드바이저 검토 의견 제시 + 모든 출력 영속화
- 일/주 스냅샷 누적 → 시계열 추이
- 다중 계좌(Account) 지원 — 본인 보유 한투 계좌들 (실전 한정)
- 로컬 실행, TUI 인터페이스

### 비목표
- **자동 주문 / 알고리즘 트레이딩** — 코드 레벨에서 주문 API import 자체 금지
- **모의투자 사용** — 분석 전용이므로 실전 계좌 직접 연결
- **해외주식** — 국내주식만
- **알림 채널** — 능동 푸시 X, 사용자가 능동적으로 TUI 실행
- 다중 사용자
- 백테스팅 (`strategy_builder/`, `backtester/` 미사용)
- 공개 서비스화
- 종목 추천 (특정 종목 매수 권유)
- 모바일 앱 / 웹 UI / GUI 디자인 시스템

## 4. 사용자 시나리오

| 시점 | 시나리오 | 핵심 가치 |
|---|---|---|
| 출근 전 | `folio status` → 어제 마감 상태 한눈에 | 30초 인사이트 |
| 점심 | `folio analyze` → 시장 변동 영향 분석 | 빠른 영향도 파악 |
| 저녁 | `folio chat` → LLM과 대화하며 비중 조정 검토 | 의사결정 보조 |
| 주말 | `folio trend --week` → 한 주 누적 추이 | 회고/계획 |
| 아무 때나 | `folio history` → 한 달 전 LLM 의견 검색 | 기록 활용 |

## 5. 기능 요구사항

### Phase 1 — PoC (1주)
- F1. KIS 인증 (실전 계좌) + 토큰 파일 캐시
- F2. 잔고 조회: 현금, 보유종목, 평가손익
- F3. 종목별 정보: 비중, 섹터 (KIS 응답의 KRX 업종분류)
- F4. 포트폴리오 메트릭: HHI, 섹터 분포, 상위 N 비중
- F5. LLM 어드바이저: 단일 도구 `get_portfolio_summary`
- F6. TUI 단일 화면 (Textual)
- F7. 단일 Account 등록 및 조회
- F8. 호출 결과 SQLite 저장 (Snapshot, AdvisorOutput)

### Phase 2 — 심화 (2-4주)
- F9. 일배치 잔고 스냅샷 (스케줄러)
- F10. 시간가중수익률(TWR), 벤치마크(KOSPI/KOSDAQ) 비교
- F11. 리스크 지표: 변동성, 베타, MDD
- F12. 시계열 차트 (TUI sparkline + png 출력 옵션)
- F13. LLM 도구 확장: 시장 지표, 뉴스 검색, 종목 일자별 시세
- F14. LLM 출력 히스토리 조회/검색 TUI 화면
- F15. 다중 Account 활용 (본인 한투 실전 계좌들)
- F16. CLI 서브커맨드 정비

## 6. 비기능 요구사항

### 보안 (최우선)
- App Key/Secret은 `.env` + `gitignore`. **DB에 저장 X** (참조 키 이름만)
- 토큰 캐시는 OS keychain 또는 600 권한 파일
- **주문 API는 코드에서 import 자체 금지** — 정적 검사(ruff custom rule 또는 grep CI)로 강제
- 외부 노출 X — TUI 본질적으로 로컬 전용
- SQLite 파일 권한 600

### 성능 / 호출 제한
- KIS 신규 고객 초당 5회 제한 준수 (rate limiter)
- 종목 시세는 잔고 응답 평가가 우선 사용
- 추가 시세는 5분 메모리 캐시
- LLM 분석 응답 < 30초

### 안정성
- 토큰 만료 자동 감지/재발급 (1분 1회 발급 한도 인지)
- KIS 장애 시 마지막 스냅샷 fallback 표시
- 모든 외부 API 호출 stderr 로깅

### 데이터 관리
- SQLite 파일 위치: `~/.folio/folio.db`
- 스키마 관리: Phase 1은 SQLModel 단순 init, Phase 2에서 Alembic 도입
- 백업: 사용자가 수동 (단일 파일이라 `cp` 한 번)
- AdvisorOutput 보관: 무제한 (1인 도구라 부담 없음)

## 7. 시스템 아키텍처

```
┌──────────────────────────────────────────┐
│  TUI (Textual)                            │
│  화면: dashboard / advisor / history      │
└───────────────────┬──────────────────────┘
                    │ in-process
┌───────────────────▼──────────────────────┐
│  Core (Python, async)                     │
│  ┌──────────┬──────────┬──────────────┐ │
│  │ KIS      │ Analyzer │ LLM Advisor  │ │
│  │ Adapter  │ (메트릭) │ (Claude)     │ │
│  └──────────┴──────────┴──────────────┘ │
│  Account Manager  │  Scheduler            │
└───┬─────────────┬────────────────┬───────┘
    │             │                │
    ▼             ▼                ▼
┌────────┐   ┌──────────────┐  ┌──────────┐
│ KIS    │   │ SQLite       │  │ Anthropic│
│ OpenAPI│   │ ~/.folio/    │  │ Claude   │
│ (실전) │   │  folio.db    │  │ API      │
└────────┘   └──────────────┘  └──────────┘
```

**계층별 책임**:
- 어댑터: KIS 응답을 도메인 모델로 정규화
- Analyzer: 외부 의존성 없는 순수 함수
- Advisor: 도구 호출 루프 + 결과 영속화
- TUI가 Core를 직접 호출 (in-process, HTTP 레이어 없음)

## 8. KIS API 연동

### 라이브러리
- 공식 레포 `koreainvestment/open-trading-api`
- `examples_user/domestic_stock/`에서 필요 함수만 어댑터로 발췌
- `strategy_builder/`, `backtester/` 미사용

### 사용 엔드포인트

| 카테고리 | 엔드포인트 | Phase |
|---|---|---|
| 인증 | `/oauth2/tokenP` | 1 |
| 잔고 | `inquire-balance` | 1 |
| 현재가 | `inquire-price` (`bstp_kor_isnm` 포함) | 1 |
| 일자별 시세 | `inquire-daily-itemchartprice` | 2 |
| 지수 | KOSPI / KOSDAQ | 2 |

### 사용 안 하는 엔드포인트 (명시적 봉인)
- 주문: `order-cash`, `order-credit`, `order-rsvn`, `order-modify` 등 — **import 금지**
- 해외주식: `overseas-stock/*` 전체

### 환경
- 실전 도메인 단일 사용: `openapi.koreainvestment.com:9443`
- 모의 도메인 (`openapivts.koreainvestment.com:29443`) 미사용

### 섹터 매핑
- 별도 매핑 데이터 X
- KIS 종목 응답의 `bstp_kor_isnm` (KRX 업종한글명) 그대로 사용
- 종목 마스터 파일(MST) 필요 시 KIS에서 다운로드해 캐시

## 9. LLM 어드바이저

### 시스템 프롬프트 관리
- 위치: `prompts/advisor.md` (코드 레포 내)
- 버전 관리: **git tag** (`prompt-v1`, `prompt-v2` 등)
- AdvisorOutput에 호출 시점 git tag 또는 commit hash 기록
- 변경 이력은 git log로 추적

### 시스템 프롬프트 원칙
- **톤**: 보수적, 단정적 권유 금지
- **출력 구조** (3개 카드 고정):
  1. 현재 상태 요약 (1-2문장)
  2. 주요 리스크 (3개 이내, 근거 포함)
  3. 관찰/검토 포인트 (3개 이내, 액션 제안 X)
- **금지**: 신규 종목 매수 권유, 매도 단정, 가격 예측

### 도구 카탈로그

| Phase | 도구 | 용도 |
|---|---|---|
| 1 | `get_portfolio_summary` | 잔고 + 메트릭 |
| 2 | `get_market_indicators` | KOSPI/KOSDAQ/USDKRW/금리 |
| 2 | `get_position_history` | 종목별 30일 시세 |
| 2 | `search_news` | 보유 종목 관련 뉴스 (웹 검색) |
| 2 | `get_sector_performance` | 섹터별 흐름 |

### 모델
- 1차: `claude-opus-4-7` (분석 깊이)
- 단순 조회는 `claude-sonnet-4-6` 라우팅 검토

### 출력 영속화
- 모든 어드바이저 호출을 `AdvisorOutput`으로 SQLite 저장
- 항목: 시각, 모델, account_id, snapshot_id, 프롬프트 git ref, 도구 호출 내역, 응답 카드 3종, 토큰 사용량
- TUI `history` 화면에서 날짜/계좌/키워드 검색

## 10. 데이터 모델

| 엔티티 | 핵심 필드 | 비고 |
|---|---|---|
| **Account** | id, label, account_no, kis_appkey_ref, is_active, created_at | 실전 계좌 한정. App Key/Secret은 .env 참조 키만 |
| Position | account_id, code, name, qty, avg_price, current_price, eval_amount, pnl, pnl_pct, sector | KIS 잔고 응답 정규화 |
| Balance | account_id, ts, cash, eval_total, pnl_total, positions[] | 시점 스냅샷 |
| Snapshot | id, account_id, date, balance, metrics, market_context | 일배치 누적 |
| Metrics | hhi, sector_dist, top_n_pct, volatility, beta, mdd | 분석 결과 |
| **AdvisorOutput** | id, account_id, snapshot_id, ts, model, prompt_git_ref, tool_calls(json), summary, risks(json), watchlist(json), token_usage | LLM 호출 영속화 |

### Account 운영
- Phase 1: 단일 Account 1건만 등록되더라도 다중 계좌 스키마
- App Key/Secret은 DB에 저장 X, `.env`의 키 이름만 참조 (`kis_appkey_ref="MAIN_APPKEY"`)
- TUI: `folio account add/list/use` 서브커맨드

## 11. UI / CLI

### TUI 프레임워크
- **Textual** (Python, async, 모던 위젯)
- 폴백: Rich 단독

### 화면 구성
- **Dashboard** (Phase 1 단일)
  - 상단 metric bar: 평가금액 / 평가손익(색) / 현금
  - 중앙 종목 테이블: 코드 / 이름 / 비중 / 평가손익 / 섹터
  - 하단 메트릭: HHI, 섹터 분포 (sparkline)
  - 액션: `[A] 분석 받기`, `[H] 히스토리`, `[R] 새로고침`, `[Q] 종료`
- **Advisor 결과 modal**
  - 3개 카드 (요약/리스크/관찰)
  - `[S] 저장됨`, `[C] 클립보드 복사`, `[B] 닫기`
- **History 화면** (Phase 2)
  - 좌측: 날짜별 AdvisorOutput 목록
  - 우측: 선택한 출력의 카드 + 당시 메트릭 비교
  - 검색 바: 키워드/종목코드/날짜 범위

### CLI 서브커맨드 (Phase 2 정비)
- `folio` — TUI 메인 진입 (= `folio status` 화면)
- `folio status` — 현재 잔고 즉석 출력 (TUI 안 띄우고 텍스트만)
- `folio analyze` — LLM 분석 1회 실행
- `folio chat` — LLM과 대화 모드
- `folio trend [--week|--month]` — 시계열 추이
- `folio history` — AdvisorOutput 검색
- `folio account add|list|use` — 계좌 관리

### 디자인 톤
- TenantNote와 분리 — folio는 TUI 시각 언어만
- 색상은 터미널 친화 (muted bg, 손익 양/음 강조)
- 폰트는 사용자 터미널 설정 그대로

## 12. 개발 일정

### Week 1 — Phase 1 PoC
| Day | Task | DoD |
|---|---|---|
| Mon | KIS Developers 신청, 실전 계좌로 키 발급, repo 셋업, Account 모델 + DB init | `folio account add` 동작 |
| Tue | KIS 어댑터 (잔고/시세/지수) + 토큰 캐시 | 실전 잔고 1회 조회 성공 |
| Wed | Analyzer (메트릭) + Snapshot 저장 | 메트릭 dataclass 반환 + DB 1건 |
| Thu | LLM Advisor + AdvisorOutput 저장 | CLI 분석 출력 + DB 1건 |
| Fri | Textual TUI Dashboard | `folio` 실행으로 완주 |

### Week 2-4 — Phase 2 심화
- 일배치 스냅샷, TWR/벤치마크, 리스크 지표, 시계열 차트
- LLM 도구 확장 (시장 지표, 뉴스, 종목 시세, 섹터)
- History 화면, 다중 계좌, CLI 서브커맨드 정비

## 13. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| **실전 계좌 사용 중 주문 API 실수 호출** | **실제 매매 발생** | **import 자체 금지 + CI 정적 검사로 강제** |
| KIS Rate limit 도달 | API 차단 | 토큰 캐시, 시세 캐시, rate limiter |
| LLM 권고 신뢰 과잉 | 잘못된 의사결정 | "참고용" 명시, 자동 주문 X |
| 토큰/시크릿 누출 | 계좌 노출 | env + gitignore + keychain, DB에 키 저장 X |
| KIS API 스펙 변경 | 어댑터 깨짐 | 어댑터 레이어 격리, 테스트 |
| LLM 비용 폭증 | 운영 부담 | 일일 호출 한도, AdvisorOutput으로 모니터링 |
| AdvisorOutput DB 비대화 | 디스크/조회 지연 | 무제한 보관, 추후 정책 재검토 |
| DB 스키마 변경 | 마이그레이션 부담 | Phase 1 init만, Phase 2 Alembic 도입 |

## 14. 성공 지표

- **Week 1 (Phase 1)**: TUI에서 잔고 → 메트릭 → LLM 분석 → DB 저장까지 1회 완주
- **Week 4 (Phase 2)**: 매일 자동 스냅샷 + 시계열 차트 + 다중 계좌 + History 화면
- **3개월**: 본인 매주 1회 이상 사용 + AdvisorOutput 50건 이상 누적

## 15. 향후 백로그 (v1.1+ 후보, 본 PRD 범위 외)

- 해외주식 통합 (USD/KRW 환산)
- 알림 채널 (이메일/Slack)
- 백테스팅 (`backtester/` 활용)
- 자동 리밸런싱 시뮬레이션 (실행 X, 시뮬만)
- 모바일 알림 (단순 푸시 채널)

---

## 부록 A. 변경 이력

| 버전 | 일자 | 핵심 변경 |
|---|---|---|
| v0.1 | 2026-05-04 | 초안 골격, 미해결 항목 정의 |
| v0.2 | 2026-05-04 | 프로젝트명 "장부", 섹터 KRX, Account 엔티티, AdvisorOutput, TUI 전환 |
| v0.3 | 2026-05-04 | 프로젝트명 "folio", 영속화 전면 제거 (stateless) |
| v0.4 | 2026-05-04 | 영속화 복원 (SQLite), 알림 기능 활성화 |
| **v1.0** | **2026-05-04** | **국내주식 한정, 실전 계좌 직접 사용, 모의투자/해외주식/알림 비목표화, 시스템 프롬프트 git tag 관리** |

## 부록 B. 핵심 설계 원칙 요약

1. **분석 전용** — 주문 기능 코드 레벨 봉인
2. **Stateful** — 시계열 분석을 위한 SQLite 영속화
3. **Local-first** — 외부 노출 없음, TUI in-process
4. **국내주식만** — 범위 명확
5. **LLM은 어드바이저, 트레이더가 아님** — 검토 의견만, 실행은 사람
6. **시크릿은 .env에만** — DB는 참조 키만
7. **프롬프트는 코드처럼** — git tag 버전 관리
