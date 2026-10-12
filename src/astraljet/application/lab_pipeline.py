from __future__ import annotations

from dataclasses import asdict, dataclass

from astraljet.domain.records import (
    CandidateRecord,
    DataRecord,
    ExperimentRecord,
    RunRecord,
    SourceRecord,
    StrategyRecord,
    record_content_hash,
)
from astraljet.lab.reproduction import ReproductionReport


@dataclass(frozen=True, slots=True)
class LabStageEvidence:
    stage_id: str
    title: str
    status: str
    owner: str
    evidence: tuple[str, ...]
    limitation: str | None
    next_action: str


@dataclass(frozen=True, slots=True)
class LabEvidencePackage:
    overall_status: str
    stages: tuple[LabStageEvidence, ...]
    limitations: tuple[str, ...]
    package_hash: str


def build_lab_evidence_package(
    *,
    source: SourceRecord,
    candidate: CandidateRecord,
    strategy: StrategyRecord,
    data: DataRecord,
    experiment: ExperimentRecord,
    runs: tuple[RunRecord, ...],
    reproduction: ReproductionReport,
    mechanics_evidence: tuple[str, ...],
) -> LabEvidencePackage:
    first_run = runs[0]
    reproduction_run = runs[1] if len(runs) > 1 else None
    stages = (
        LabStageEvidence("LAB-01", "Przyjąć materiał", "completed", "AJ-02 + AJ-05", (source.record_id,), None, "Przejdź do mapy reguł."),
        LabStageEvidence("LAB-02", "Sprawdzić źródła i kompletność", "completed", "AJ-05", (candidate.record_id,), "Braki CAND pozostają jawne.", "Formalizuj bez zgadywania."),
        LabStageEvidence("LAB-03", "Zbudować specyfikację", "completed", "AJ-05", (strategy.record_id,), strategy.source_adaptation or None, "Używaj wyłącznie tej wersji STRAT."),
        LabStageEvidence("LAB-04", "Wyjaśnić hipotezę", "completed", "AJ-05", (experiment.record_id,), "Hipoteza nie jest dowodem przewagi.", "Oceń względem zamrożonego benchmarku."),
        LabStageEvidence("LAB-05", "Uzgodnić plan eksperymentu", "completed", "AJ-05 + AJ-07", (experiment.record_id, experiment.plan_hash), None, "Nie zmieniaj planu po wyniku."),
        LabStageEvidence("LAB-06", "Odebrać dane", "completed", "AJ-06 + AJ-07", (data.record_id, data.sha256), "Hash nie dowodzi jakości ekonomicznej danych.", "Używaj tylko do zatwierdzonego EXP."),
        LabStageEvidence("LAB-07", "Sprawdzić mechanikę implementacji", "completed", "AJ-07", mechanics_evidence, "Test mechaniki nie potwierdza rentowności.", "Zachowaj testy wraz z kodem."),
        LabStageEvidence("LAB-08", "Wykonać bazowy backtest", "completed", "AJ-07", (first_run.record_id, str(first_run.reproduction.get("output_hash"))), "BACKTEST nie jest prognozą.", "Przekaż wszystkie RUN do porównania."),
        LabStageEvidence("LAB-09", "Porównać warianty", "completed", "AJ-07", tuple(run.record_id for run in runs), "Fixture obejmuje tylko warianty zapisane w EXP.", "Nowy wariant wymaga nowego EXP albo wpisu na liście."),
        LabStageEvidence("LAB-10", "Sprawdzić odporność i OOS", "completed", "AJ-07", (str(experiment.out_of_sample), first_run.record_id), "Syntetyczne OOS sprawdza pipeline, nie odporność rynkową.", "Powtórz na zatwierdzonych DATA rynkowych."),
        LabStageEvidence("LAB-11", "Oddać wynik do przeglądu", "blocked", "AJ-08 + AJ-09", tuple(run.record_id for run in runs), "Brak niezależnego REVIEW i RISK-DECISION.", "Utwórz niezależny REVIEW w US2."),
        LabStageEvidence(
            "LAB-12",
            "Odtworzyć i wydać raport",
            "blocked",
            "AJ-07; odbiór AJ-08",
            tuple(filter(None, (reproduction_run.record_id if reproduction_run else None, str(reproduction.verified)))),
            None if reproduction.verified else "Drugi przebieg jest poza tolerancją.",
            "Uwzględnij odtworzenie w końcowej REVIEW przed rozważeniem mandatu.",
        ),
    )
    overall_status = "completed" if all(stage.status == "completed" for stage in stages) else "blocked"
    limitations = (
        "Pakiet fixture ma siłę dowodową test_only.",
        "Brak REVIEW blokuje promocję do inkubacji.",
    )
    package_hash = record_content_hash(
        {
            "overall_status": overall_status,
            "stages": [asdict(stage) for stage in stages],
            "limitations": limitations,
        }
    )
    return LabEvidencePackage(
        overall_status=overall_status,
        stages=stages,
        limitations=limitations,
        package_hash=package_hash,
    )
