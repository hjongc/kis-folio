from pathlib import Path

from folio.config import KISSettings
from folio.kis import KISClient, parse_balance, parse_daily_prices


def test_parse_kis_balance_payload() -> None:
    payload = {
        "rt_cd": "0",
        "output1": [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "10",
                "pchs_avg_pric": "72000",
                "prpr": "79000",
                "evlu_amt": "790000",
                "evlu_pfls_amt": "70000",
                "evlu_pfls_rt": "9.72",
                "bstp_kor_isnm": "전기전자",
            },
            {"pdno": "000000", "hldg_qty": "0"},
        ],
        "output2": [
            {
                "scts_evlu_amt": "790000",
                "dnca_tot_amt": "100000",
                "evlu_pfls_smtl_amt": "70000",
            }
        ],
    }

    balance = parse_balance("main", payload)

    assert balance.eval_total == 790000
    assert balance.cash == 100000
    assert len(balance.positions) == 1
    assert balance.positions[0].sector == "전기전자"


def test_enrich_position_sectors_from_price_payload() -> None:
    class FakeKISClient(KISClient):
        def get_price(self, code: str) -> dict:
            assert code == "005930"
            return {"output": {"bstp_kor_isnm": "전기·전자"}}

    client = FakeKISClient(
        KISSettings(
            base_url="https://openapi.koreainvestment.com:9443",
            app_key="app-key",
            app_secret="app-secret",
            cano="12345678",
            product_code="01",
            hts_id="hts",
            token_cache_path=Path("token.json"),
        )
    )
    balance = parse_balance(
        "main",
        {
            "output1": [
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "hldg_qty": "1",
                    "evlu_amt": "80000",
                }
            ],
            "output2": [{"scts_evlu_amt": "80000"}],
        },
    )

    client.enrich_position_sectors(balance)

    assert balance.positions[0].sector == "전기·전자"


def test_parse_daily_prices_sorts_bars() -> None:
    bars = parse_daily_prices(
        {
            "output2": [
                {
                    "stck_bsop_date": "20260503",
                    "stck_oprc": "70000",
                    "stck_hgpr": "72000",
                    "stck_lwpr": "69000",
                    "stck_clpr": "71000",
                    "acml_vol": "1000",
                },
                {
                    "stck_bsop_date": "20260502",
                    "stck_oprc": "68000",
                    "stck_hgpr": "70000",
                    "stck_lwpr": "67000",
                    "stck_clpr": "69000",
                    "acml_vol": "900",
                },
            ]
        }
    )

    assert [bar.date for bar in bars] == ["20260502", "20260503"]
    assert bars[-1].close == 71000
