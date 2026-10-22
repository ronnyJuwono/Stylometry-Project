"""Metadata-only artificial fixtures. No writing, identities, or real IDs/hashes."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from stylometry.contracts import (
    AnonymizedWriter, CleanTextDerivation, Corpus, DatasetSnapshot, ExperimentRun,
    ExtractionEvent, ExtractionStatus, Provenance, QCContext, QCEvaluation, QCStatus,
    Reproducibility, ResearchBundle, RunStatus, SnapshotMember, SourceDocument,
    TextSample, canonical_sha256,
)
from stylometry.paper1 import TaskCode


def uid(value: int) -> UUID:
    return UUID(int=value)


@pytest.fixture
def synthetic_bundle() -> ResearchBundle:
    """Four artificial task slots with supplied dummy counts, not measured text."""
    now = datetime(2026, 10, 22, tzinfo=timezone.utc)
    fake_hash = canonical_sha256({"synthetic_contract_fixture": True})
    repro = Reproducibility(
        configuration_version="synthetic-only.v1", configuration_ref=uid(9001),
        configuration_sha256=fake_hash, code_commit="0" * 40,
        working_tree_dirty=True, environment_lock_sha256=fake_hash,
    )
    provenance = Provenance(id=uid(1), recorded_at=now,
                            evidence_ref=uid(9002), evidence_sha256=fake_hash)
    corpus = Corpus(id=uid(2), version="synthetic-only.v1", created_at=now, provenance_id=uid(1))
    writer = AnonymizedWriter(id=uid(3), corpus_id=uid(2))
    document = SourceDocument(
        id=uid(4), corpus_id=uid(2), private_object_ref=uid(9003),
        byte_sha256=fake_hash, media_type="application/octet-stream",
        provenance_id=uid(1), acquired_at=now,
    )
    samples, extractions, derivations, evaluations, members = [], [], [], [], []
    writer_qc = QCEvaluation(
        id=uid(5), target_kind="writer", target_id=writer.id,
        context=QCContext.PRIMARY_80, status=QCStatus.PASS,
        word_threshold=80, minimum_eligible_tasks=4, eligible_task_count=4,
        provenance_id=uid(1), reproducibility=repro, evaluated_at=now,
    )
    for index, task in enumerate(list(TaskCode)[:4]):
        base = 100 + 10 * index
        sample = TextSample(id=uid(base), corpus_id=corpus.id, writer_id=writer.id,
                            task=task, provenance_id=provenance.id)
        event = ExtractionEvent(
            id=uid(base + 1), sample_id=sample.id, source_document_id=document.id,
            source_span_ref=uid(9100 + index), provenance_id=provenance.id,
            method_ref=uid(9004), reproducibility=repro, started_at=now, finished_at=now,
            status=ExtractionStatus.SUCCEEDED, extracted_object_ref=uid(9200 + index),
            extracted_byte_sha256=fake_hash,
        )
        derivation = CleanTextDerivation(
            id=uid(base + 2), sample_id=sample.id, extraction_event_id=event.id,
            version=1, private_object_ref=uid(9300 + index), byte_sha256=fake_hash,
            method_ref=uid(9005), provenance_id=provenance.id, reproducibility=repro,
            created_at=now,
        )
        qc = QCEvaluation(
            id=uid(base + 3), target_kind="sample", target_id=sample.id,
            context=QCContext.PRIMARY_80, status=QCStatus.PASS,
            derivation_id=derivation.id, word_count=80, word_threshold=80,
            tokenizer_method_ref=uid(9006), provenance_id=provenance.id,
            reproducibility=repro, evaluated_at=now,
        )
        samples.append(sample)
        extractions.append(event)
        derivations.append(derivation)
        evaluations.append(qc)
        members.append(SnapshotMember(
            sample_id=sample.id, derivation_id=derivation.id, clean_byte_sha256=fake_hash,
            sample_qc_id=qc.id, writer_qc_id=writer_qc.id,
        ))
    snapshot_fields = dict(
        id=uid(6), corpus_id=corpus.id, version="synthetic-only.v1", context=QCContext.PRIMARY_80,
        created_at=now, reproducibility=repro, members=tuple(members),
    )
    # JSON encoding is explicit; UUID/time/enum values follow the contract serializer.
    from pydantic import TypeAdapter
    manifest = TypeAdapter(dict).dump_python(snapshot_fields, mode="json")
    snapshot = DatasetSnapshot(**snapshot_fields, manifest_sha256=canonical_sha256(manifest))
    run = ExperimentRun(
        id=uid(7), experiment_version="synthetic-only.v1", snapshot_id=snapshot.id,
        snapshot_manifest_sha256=snapshot.manifest_sha256, stage_number=1,
        status=RunStatus.PLANNED, reproducibility=repro, created_at=now,
    )
    return ResearchBundle(
        provenance=(provenance,), corpora=(corpus,), writers=(writer,), documents=(document,),
        samples=tuple(samples), extractions=tuple(extractions), derivations=tuple(derivations),
        evaluations=(*evaluations, writer_qc), snapshots=(snapshot,), runs=(run,),
    )
