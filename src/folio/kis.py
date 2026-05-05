from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import KISSettings
from .logging_utils import external_call
from .models import Balance, Position, PriceBar
from .security import ensure_private_file

TOKEN_PATH = "/oauth2/tokenP"
BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
DAILY_CHART_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"


class KISError(RuntimeError):
    pass


@dataclass
class Token:
    access_token: str
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return self.access_token != "" and self.expires_at > datetime.now(
            tz=timezone.utc
        ) + timedelta(minutes=5)


class RateLimiter:
    def __init__(self, calls_per_second: float = 5.0) -> None:
        self.min_interval = 1.0 / calls_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


class KISClient:
    """Small KIS production adapter based on official OpenAPI examples."""

    def __init__(self, settings: KISSettings, timeout: float = 20.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self.rate_limiter = RateLimiter()

    def get_balance(self, account_id: str) -> Balance:
        payload = self.request(
            "GET",
            BALANCE_PATH,
            tr_id="TTTC8434R",
            params={
                "CANO": self.settings.cano,
                "ACNT_PRDT_CD": self.settings.product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        balance = parse_balance(account_id, payload)
        self.enrich_position_sectors(balance)
        return balance

    def get_price(self, code: str) -> dict[str, Any]:
        return self.request(
            "GET",
            PRICE_PATH,
            tr_id="FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        )

    def get_daily_prices(self, code: str, start_date: str, end_date: str) -> list[PriceBar]:
        payload = self.request(
            "GET",
            DAILY_CHART_PATH,
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        return parse_daily_prices(payload)

    def enrich_position_sectors(self, balance: Balance) -> None:
        for position in balance.positions:
            if position.sector != "Unknown":
                continue
            try:
                payload = self.get_price(position.code)
            except KISError:
                continue
            output = payload.get("output") or {}
            sector = str(output.get("bstp_kor_isnm") or "").strip()
            if sector:
                position.sector = sector

    def request(
        self,
        method: str,
        path: str,
        tr_id: str | None = None,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.rate_limiter.wait()
        token = self.get_token()
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token.access_token}",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
        }
        if tr_id:
            headers["tr_id"] = tr_id

        url = self.settings.base_url.rstrip("/") + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request_body = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=request_body, headers=headers, method=method)
        return self._send(req)

    def get_token(self) -> Token:
        cached = self._read_cached_token(self.settings.token_cache_path)
        if cached and cached.is_valid:
            return cached
        if not self.settings.app_key or not self.settings.app_secret:
            raise KISError("KIS app key/secret are not configured")
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
        }
        req = urllib.request.Request(
            self.settings.base_url.rstrip("/") + TOKEN_PATH,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json; charset=utf-8"},
            method="POST",
        )
        raw = self._send(req)
        access_token = str(raw.get("access_token", ""))
        expires_in = int(raw.get("expires_in", 0) or 0)
        token = Token(
            access_token=access_token,
            expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in),
        )
        self._write_cached_token(self.settings.token_cache_path, token)
        return token

    def _send(self, req: urllib.request.Request) -> dict[str, Any]:
        operation = req.get_method() + " " + urllib.parse.urlparse(req.full_url).path
        with external_call("kis", operation):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = response.read().decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise KISError(f"KIS HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise KISError(f"KIS network error: {exc.reason}") from exc
        parsed = json.loads(data)
        rt_cd = str(parsed.get("rt_cd", "0"))
        if rt_cd not in {"0", ""}:
            raise KISError(f"KIS API error {parsed.get('msg_cd')}: {parsed.get('msg1')}")
        return parsed

    @staticmethod
    def _read_cached_token(path: Path) -> Token | None:
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Token(
            access_token=str(raw.get("access_token", "")),
            expires_at=datetime.fromisoformat(raw.get("expires_at")),
        )

    @staticmethod
    def _write_cached_token(path: Path, token: Token) -> None:
        ensure_private_file(path)
        path.write_text(
            json.dumps(
                {"access_token": token.access_token, "expires_at": token.expires_at.isoformat()}
            ),
            encoding="utf-8",
        )


def parse_number(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(",", "").strip()
    if text == "":
        return 0.0
    return float(text)


def parse_int(value: Any) -> int:
    return int(parse_number(value))


def parse_balance(account_id: str, payload: dict[str, Any]) -> Balance:
    output1 = payload.get("output1") or []
    output2 = payload.get("output2") or []
    summary = output2[0] if isinstance(output2, list) and output2 else {}
    positions = [
        Position(
            code=str(row.get("pdno", "")),
            name=str(row.get("prdt_name", "")),
            qty=parse_int(row.get("hldg_qty")),
            avg_price=parse_number(row.get("pchs_avg_pric")),
            current_price=parse_number(row.get("prpr")),
            eval_amount=parse_number(row.get("evlu_amt")),
            pnl=parse_number(row.get("evlu_pfls_amt")),
            pnl_pct=parse_number(row.get("evlu_pfls_rt")),
            sector=str(row.get("bstp_kor_isnm") or row.get("sector") or "Unknown"),
        )
        for row in output1
        if parse_int(row.get("hldg_qty")) > 0
    ]
    eval_total = parse_number(summary.get("scts_evlu_amt")) or sum(
        position.eval_amount for position in positions
    )
    cash = parse_number(summary.get("dnca_tot_amt") or summary.get("nass_amt"))
    pnl_total = parse_number(summary.get("evlu_pfls_smtl_amt")) or sum(
        position.pnl for position in positions
    )
    return Balance(
        account_id=account_id,
        ts=datetime.now(tz=timezone.utc),
        cash=cash,
        eval_total=eval_total,
        pnl_total=pnl_total,
        positions=positions,
    )


def parse_daily_prices(payload: dict[str, Any]) -> list[PriceBar]:
    rows = payload.get("output2") or payload.get("output") or []
    bars = [
        PriceBar(
            date=str(row.get("stck_bsop_date", "")),
            open=parse_number(row.get("stck_oprc")),
            high=parse_number(row.get("stck_hgpr")),
            low=parse_number(row.get("stck_lwpr")),
            close=parse_number(row.get("stck_clpr")),
            volume=parse_int(row.get("acml_vol")),
        )
        for row in rows
        if row.get("stck_bsop_date")
    ]
    return sorted(bars, key=lambda bar: bar.date)
