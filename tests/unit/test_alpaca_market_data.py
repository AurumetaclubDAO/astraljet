from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from astraljet.domain.errors import TechnicalError, ValidationError
from astraljet.infrastructure.alpaca_market_data import (
    AlpacaCredentials,
    AlpacaCryptoDataClient,
    CryptoBarsRequest,
    HttpJsonResponse,
    load_alpaca_credentials,
    _atomic_write_json,
)


class FakeTransport:
    def __init__(self, responses: list[HttpJsonResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_json(self, url: str, headers: dict[str, str]) -> HttpJsonResponse:
        self.calls.append((url, headers))
        return self.responses.pop(0)


def response(payload: dict[str, object], request_id: str) -> HttpJsonResponse:
    return HttpJsonResponse(
        status=200,
        payload=payload,
        headers={"x-request-id": request_id},
    )


class AlpacaCredentialsTest(unittest.TestCase):
    def test_loads_credentials_without_exposing_values_in_repr(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env_file = Path(workspace) / ".env"
            env_file.write_text(
                "ALPACA_API_KEY_ID=paper-key\n"
                "ALPACA_API_SECRET_KEY='paper-secret'\n"
                "ALPACA_DATA_BASE_URL=https://data.alpaca.markets/v1beta3\n",
                encoding="utf-8",
            )

            credentials, base_url = load_alpaca_credentials(env_file)

            self.assertEqual("paper-key", credentials.key_id)
            self.assertEqual("paper-secret", credentials.secret_key)
            self.assertEqual("https://data.alpaca.markets/v1beta3", base_url)
            self.assertNotIn("paper-secret", repr(credentials))
            self.assertNotIn("paper-key", repr(credentials))

    def test_missing_secret_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env_file = Path(workspace) / ".env"
            env_file.write_text("ALPACA_API_KEY_ID=paper-key\n", encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "ALPACA_API_SECRET_KEY"):
                load_alpaca_credentials(env_file)

    def test_root_data_url_gets_current_api_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env_file = Path(workspace) / ".env"
            env_file.write_text(
                "ALPACA_API_KEY_ID=paper-key\n"
                "ALPACA_API_SECRET_KEY=paper-secret\n"
                "ALPACA_DATA_BASE_URL=https://data.alpaca.markets\n",
                encoding="utf-8",
            )

            _credentials, base_url = load_alpaca_credentials(env_file)

            self.assertEqual("https://data.alpaca.markets/v1beta3", base_url)

    def test_credentials_are_not_sent_to_untrusted_data_host(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            env_file = Path(workspace) / ".env"
            env_file.write_text(
                "ALPACA_API_KEY_ID=paper-key\n"
                "ALPACA_API_SECRET_KEY=paper-secret\n"
                "ALPACA_DATA_BASE_URL=https://example.invalid/v1beta3\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValidationError, "data.alpaca.markets"):
                load_alpaca_credentials(env_file)


class AlpacaCryptoDataClientTest(unittest.TestCase):
    def test_existing_csv_or_metadata_blocks_before_network_and_preserves_bytes(self) -> None:
        for existing_suffix in ('.csv', '.csv.metadata.json'):
            with self.subTest(suffix=existing_suffix), tempfile.TemporaryDirectory() as workspace:
                output = Path(workspace) / 'version.csv'
                existing = Path(workspace) / ('version' + existing_suffix)
                existing.write_bytes(b'original-version')
                transport = FakeTransport([])
                client = AlpacaCryptoDataClient(AlpacaCredentials('key', 'secret'), transport=transport)
                with self.assertRaisesRegex(ValidationError, 'istnieje'):
                    client.fetch_to_csv(CryptoBarsRequest(symbols=('BTC/USD',),
                        start='2026-09-16T00:00:00Z', end='2026-09-18T00:00:00Z'), output)
                self.assertEqual([], transport.calls)
                self.assertEqual(b'original-version', existing.read_bytes())
                self.assertEqual([existing], list(Path(workspace).iterdir()))

    def test_publication_race_does_not_replace_competing_version(self) -> None:
        import os
        original_link = os.link
        with tempfile.TemporaryDirectory() as workspace:
            output = Path(workspace) / 'snapshot.metadata.json'
            def competing_write(source, destination):
                Path(destination).write_bytes(b'competing-version')
                return original_link(source, destination)
            with patch('astraljet.infrastructure.alpaca_market_data.os.link', side_effect=competing_write):
                with self.assertRaises(ValidationError):
                    _atomic_write_json(output, {'test': True})
            self.assertEqual(b'competing-version', output.read_bytes())
            self.assertEqual([output], list(Path(workspace).iterdir()))

    def test_missing_optional_fields_are_not_fabricated(self) -> None:
        transport = FakeTransport([response({'bars': {'BTC/USD': [
            {'t': '2026-09-16T00:00:00Z', 'o': 100, 'h': 110, 'l': 90, 'c': 105, 'v': 0}
        ]}, 'next_page_token': None}, 'test')])
        client = AlpacaCryptoDataClient(AlpacaCredentials('key', 'secret'), transport=transport)
        with tempfile.TemporaryDirectory() as workspace:
            result = client.fetch_to_csv(CryptoBarsRequest(symbols=('BTC/USD',),
                start='2026-09-16T00:00:00Z', end='2026-09-18T00:00:00Z'), Path(workspace) / 'snapshot.csv')
            with result.csv_path.open(encoding='utf-8', newline='') as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual('0', row['volume'])
            self.assertEqual('', row['trade_count'])
            self.assertEqual('', row['vwap'])

    def test_fetches_all_pages_and_writes_canonical_snapshot(self) -> None:
        transport = FakeTransport(
            [
                response(
                    {
                        "bars": {
                            "BTC/USD": [
                                {"t": "2026-09-16T00:00:00Z", "o": 100, "h": 110, "l": 90, "c": 105, "v": 2, "n": 4, "vw": 102}
                            ],
                            "ETH/USD": [
                                {"t": "2026-09-16T00:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 5, "n": 7, "vw": 10.5}
                            ],
                        },
                        "next_page_token": "next-token",
                    },
                    "request-1",
                ),
                response(
                    {
                        "bars": {
                            "BTC/USD": [
                                {"t": "2026-09-17T00:00:00Z", "o": 105, "h": 112, "l": 101, "c": 109, "v": 3, "n": 5, "vw": 107}
                            ],
                            "ETH/USD": [
                                {"t": "2026-09-17T00:00:00Z", "o": 11, "h": 13, "l": 10, "c": 12, "v": 6, "n": 8, "vw": 11.5}
                            ],
                        },
                        "next_page_token": None,
                    },
                    "request-2",
                ),
            ]
        )
        client = AlpacaCryptoDataClient(
            credentials=AlpacaCredentials("key", "secret"),
            transport=transport,
        )

        with tempfile.TemporaryDirectory() as workspace:
            output = Path(workspace) / "btc_eth.csv"
            result = client.fetch_to_csv(
                CryptoBarsRequest(
                    symbols=("BTC/USD", "ETH/USD"),
                    start="2026-09-16T00:00:00Z",
                    end="2026-09-18T00:00:00Z",
                ),
                output,
            )

            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(4, result.row_count)
        self.assertEqual(2, result.page_count)
        self.assertEqual(["BTCUSD", "ETHUSD", "BTCUSD", "ETHUSD"], [row["instrument"] for row in rows])
        self.assertIn("page_token=next-token", transport.calls[1][0])
        self.assertEqual("key", transport.calls[0][1]["APCA-API-KEY-ID"])
        self.assertEqual(["request-1", "request-2"], metadata["request_ids"])
        self.assertEqual(result.csv_sha256, metadata["csv_sha256"])
        self.assertNotIn("secret", json.dumps(metadata))
        self.assertNotIn("key", json.dumps(metadata))

    def test_duplicate_bar_across_pages_is_rejected(self) -> None:
        bar = {"t": "2026-09-16T00:00:00Z", "o": 100, "h": 110, "l": 90, "c": 105, "v": 2}
        transport = FakeTransport(
            [
                response({"bars": {"BTC/USD": [bar]}, "next_page_token": "again"}, "one"),
                response({"bars": {"BTC/USD": [bar]}, "next_page_token": None}, "two"),
            ]
        )
        client = AlpacaCryptoDataClient(AlpacaCredentials("key", "secret"), transport=transport)

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaisesRegex(TechnicalError, "duplikat"):
                client.fetch_to_csv(
                    CryptoBarsRequest(
                        symbols=("BTC/USD",),
                        start="2026-09-16T00:00:00Z",
                        end="2026-09-18T00:00:00Z",
                    ),
                    Path(workspace) / "btc.csv",
                )

    def test_missing_requested_symbol_is_rejected(self) -> None:
        transport = FakeTransport(
            [response({"bars": {"BTC/USD": [{"t": "2026-09-16T00:00:00Z", "o": 100, "h": 110, "l": 90, "c": 105, "v": 2}]}, "next_page_token": None}, "one")]
        )
        client = AlpacaCryptoDataClient(AlpacaCredentials("key", "secret"), transport=transport)

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaisesRegex(TechnicalError, "ETH/USD"):
                client.fetch_to_csv(
                    CryptoBarsRequest(
                        symbols=("BTC/USD", "ETH/USD"),
                        start="2026-09-16T00:00:00Z",
                        end="2026-09-18T00:00:00Z",
                    ),
                    Path(workspace) / "btc_eth.csv",
                )

    def test_current_daily_bar_is_rejected_as_not_closed(self) -> None:
        transport = FakeTransport(
            [
                response(
                    {
                        "bars": {
                            "BTC/USD": [
                                {"t": "2026-09-19T00:00:00Z", "o": 100, "h": 110, "l": 90, "c": 105, "v": 2}
                            ]
                        },
                        "next_page_token": None,
                    },
                    "one",
                )
            ]
        )
        client = AlpacaCryptoDataClient(
            AlpacaCredentials("key", "secret"),
            transport=transport,
            clock=lambda: "2026-09-19T20:00:00Z",
        )

        with tempfile.TemporaryDirectory() as workspace:
            with self.assertRaisesRegex(TechnicalError, "niezamkniętą"):
                client.fetch_to_csv(
                    CryptoBarsRequest(
                        symbols=("BTC/USD",),
                        start="2026-09-19T00:00:00Z",
                        end="2026-09-19T23:59:59Z",
                    ),
                    Path(workspace) / "btc.csv",
                )


if __name__ == "__main__":
    unittest.main()
