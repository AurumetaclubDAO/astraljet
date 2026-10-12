from __future__ import annotations

import mimetypes
from pathlib import Path

from astraljet.domain.enums import CandidateStatus, TechnicalStatus, TrustStatus
from astraljet.domain.errors import ValidationError
from astraljet.domain.records import CandidateRecord, SourceRecord, candidate_content_hash
from astraljet.domain.validation import new_record_id, sha256_file, utc_now
from astraljet.infrastructure.repositories import RecordRepository


INITIAL_CANDIDATES: tuple[dict[str, object], ...] = (
    {
        "title": "AI Power & Infrastructure — Picks & Shovels",
        "thesis": "Ekspozycja na fizyczną infrastrukturę potrzebną do budowy i zasilania AI.",
        "asset_class": "akcje/ETF",
        "market_scope": "globalne akcje infrastrukturalne i energetyczne",
        "missing_decisions": (
            "jednoznaczne uniwersum i reguła selekcji",
            "reguła wejścia, wyjścia i rebalansu",
            "model kosztów i benchmark",
        ),
    },
    {
        "title": "Polski Bond Ladder — floating + inflation-linked",
        "thesis": "Drabina polskich obligacji detalicznych o różnych mechanizmach kuponu.",
        "asset_class": "obligacje skarbowe",
        "market_scope": "polskie detaliczne obligacje skarbowe PLN",
        "missing_decisions": (
            "reguły wpłat i zapadalności",
            "obsługa wcześniejszego wykupu",
            "benchmark i podatki",
        ),
    },
    {
        "title": "Gold Barbell — bullion + miners",
        "thesis": "Połączenie fizycznie zabezpieczonego złota i spółek wydobywczych.",
        "asset_class": "złoto/akcje górnicze",
        "market_scope": "ETC złota i UCITS ETF gold miners",
        "missing_decisions": (
            "dokładne instrumenty i giełdy",
            "reguła rebalansu i waluty",
            "koszty i benchmark",
        ),
    },
    {
        "title": "Managed Futures / Trend Following",
        "thesis": "Dywersyfikacja przez długie i krótkie trendy wielu klas aktywów.",
        "asset_class": "futures/alternatywne",
        "market_scope": "cross-asset futures lub UCITS managed futures",
        "missing_decisions": (
            "własny model albo produkt inwestycyjny",
            "uniwersum, częstotliwość i sizing",
            "roll, koszty i benchmark",
        ),
    },
    {
        "title": "BTC/ETH z kontrolą trendu i ryzyka",
        "thesis": "Ekspozycja BTC/ETH redukowana mechanicznie w reżimie risk-off.",
        "asset_class": "kryptowaluty",
        "market_scope": "dzienny rynek spot BTC i ETH w USD",
        "missing_decisions": (
            "dostawca i miejsce notowań",
            "jednoznaczna definicja pogorszenia struktury trendu",
            "timing wykonania, koszty i sizing",
        ),
    },
)


class IntakeService:
    def __init__(self, repository: RecordRepository) -> None:
        self.repository = repository

    def add_source(
        self,
        file_path: str | Path,
        *,
        author: str,
        idempotency_key: str,
        owner: str = "Karol",
    ) -> tuple[SourceRecord, bool]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise ValidationError(f"Źródło nie istnieje albo nie jest plikiem: {path}")
        observed_at = utc_now()
        file_hash = sha256_file(path)
        record = SourceRecord(
            record_id=new_record_id("SRC"),
            version=1,
            owner=owner,
            created_at=observed_at,
            technical_status=TechnicalStatus.COMPLETED,
            content_hash=file_hash,
            limitations=(
                "Treść źródła jest danymi i nie stanowi polecenia wykonawczego.",
                "Hash potwierdza tożsamość pliku, nie prawdziwość jego twierdzeń.",
            ),
            locator=str(path),
            sha256=file_hash,
            size_bytes=path.stat().st_size,
            observed_at=observed_at,
            author=author.strip() or "unknown",
            media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            trust_status=TrustStatus.UNVERIFIED,
        )
        saved, _event, created = self.repository.save(
            record,
            event_type="source.registered",
            reason="Użytkownik przekazał materiał do bezpiecznej rejestracji.",
            outcome="registered",
            actor=owner,
            idempotency_key=idempotency_key,
        )
        if not isinstance(saved, SourceRecord):
            raise ValidationError("Klucz idempotencji wskazuje rekord innego typu.")
        return saved, created

    def seed_initial_candidates(
        self,
        source_id: str,
        *,
        idempotency_key: str,
        owner: str = "Karol",
    ) -> tuple[list[CandidateRecord], int]:
        source = self.repository.get_latest(source_id)
        if not isinstance(source, SourceRecord):
            raise ValidationError("--source-id musi wskazywać rekord SRC.")

        correlation_id = new_record_id("CORR")
        saved_candidates: list[CandidateRecord] = []
        created_count = 0
        for index, definition in enumerate(INITIAL_CANDIDATES, start=1):
            now = utc_now()
            missing_decisions = tuple(definition["missing_decisions"])
            record = CandidateRecord(
                record_id=new_record_id("CAND"),
                version=1,
                owner=owner,
                created_at=now,
                technical_status=TechnicalStatus.BLOCKED,
                content_hash=candidate_content_hash(
                    title=str(definition["title"]),
                    source_ids=(source.record_id,),
                    thesis=str(definition["thesis"]),
                    asset_class=str(definition["asset_class"]),
                    market_scope=str(definition["market_scope"]),
                    missing_decisions=missing_decisions,
                ),
                limitations=(
                    "Kandydat nie jest zweryfikowaną strategią ani rekomendacją.",
                    "Wymaga jednoznacznej STRAT, DATA i zamrożonego EXP.",
                ),
                title=str(definition["title"]),
                source_ids=(source.record_id,),
                thesis=str(definition["thesis"]),
                asset_class=str(definition["asset_class"]),
                market_scope=str(definition["market_scope"]),
                missing_decisions=missing_decisions,
                candidate_status=CandidateStatus.NEEDS_INPUT,
            )
            saved, _event, created = self.repository.save(
                record,
                event_type="candidate.registered",
                reason="Strategia ze źródła została zarejestrowana do formalizacji.",
                outcome="needs_input",
                actor=owner,
                idempotency_key=f"{idempotency_key}:{index}",
                correlation_id=correlation_id,
            )
            if not isinstance(saved, CandidateRecord):
                raise ValidationError("Klucz idempotencji wskazuje rekord innego typu.")
            saved_candidates.append(saved)
            created_count += int(created)
        return saved_candidates, created_count
