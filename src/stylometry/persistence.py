"""Explicit contract/ORM conversion, not an ingestion or snapshot-sealing service."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from stylometry import contracts as c, models as m


RECORDS = {
    "provenance": (c.Provenance, m.Provenance),
    "corpora": (c.Corpus, m.Corpus),
    "writers": (c.AnonymizedWriter, m.Writer),
    "documents": (c.SourceDocument, m.SourceDocument),
    "samples": (c.TextSample, m.TextSample),
    "extractions": (c.ExtractionEvent, m.ExtractionEvent),
    "derivations": (c.CleanTextDerivation, m.CleanTextDerivation),
    "evaluations": (c.QCEvaluation, m.QCEvaluation),
    "snapshots": (c.DatasetSnapshot, m.DatasetSnapshot),
    "runs": (c.ExperimentRun, m.ExperimentRun),
}
REPRO_FIELDS = tuple(c.Reproducibility.model_fields)


def to_record(contract: c.Contract):
    """Return transient records only; no session, files, or database is accessed."""
    contract = type(contract).model_validate_json(contract.model_dump_json())
    model = next(model for cls, model in RECORDS.values() if type(contract) is cls)
    data = contract.model_dump()
    if "reproducibility" in data:
        data.update(data.pop("reproducibility"))
    if isinstance(contract, c.TextSample):
        data["task_code"] = data.pop("task")
    if isinstance(contract, c.QCEvaluation):
        kind, target = data.pop("target_kind"), data.pop("target_id")
        data.update(sample_id=target if kind == "sample" else None,
                    writer_id=target if kind == "writer" else None)
        data["reasons"] = [m.QCReason(reason_code=reason) for reason in data.pop("reasons")]
        data["related_samples"] = [m.QCRelatedSample(related_sample_id=key)
                                   for key in data.pop("related_sample_ids")]
    if isinstance(contract, c.DatasetSnapshot):
        data["members"] = [m.SnapshotMember(**member) for member in data["members"]]
    if isinstance(contract, c.ExperimentRun):
        data["outputs"] = [m.RunOutput(provenance_id=key) for key in data.pop("output_provenance_ids")]
    return model(**data)


def to_contract(record) -> c.Contract:
    """Revalidate a persisted row, including its child rows, through S2A."""
    cls = next(cls for cls, model in RECORDS.values() if type(record) is model)
    data = {column.key: getattr(record, column.key) for column in record.__table__.columns}
    if isinstance(record, m.Reproducible):
        data["reproducibility"] = {key: data.pop(key) for key in REPRO_FIELDS}
    if isinstance(record, m.TextSample):
        data["task"] = data.pop("task_code")
    if isinstance(record, m.QCEvaluation):
        sample, writer = data.pop("sample_id"), data.pop("writer_id")
        if (sample is None) == (writer is None):
            raise ValueError("QC requires exactly one target")
        data.update(target_kind="sample" if sample is not None else "writer",
                    target_id=sample if sample is not None else writer,
                    reasons=sorted(row.reason_code for row in record.reasons),
                    related_sample_ids=sorted((row.related_sample_id for row in record.related_samples), key=str))
    if isinstance(record, m.DatasetSnapshot):
        data["members"] = [
            {key: getattr(member, key) for key in c.SnapshotMember.model_fields}
            for member in sorted(record.members, key=lambda member: str(member.sample_id))
        ]
    if isinstance(record, m.ExperimentRun):
        data["output_provenance_ids"] = sorted((row.provenance_id for row in record.outputs), key=str)
    def encode(value):
        from datetime import datetime
        from uuid import UUID
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError("Unsupported metadata value")
    return cls.model_validate_json(json.dumps(data, default=encode))


def load_validated_bundle(session: Session) -> c.ResearchBundle:
    """Read/validate a closed graph, without sealing or locking it.

    Suitable for synthetic verification. Concurrent research writers require a
    future reviewed transaction/isolation/locking service before ingestion.
    """
    return c.ResearchBundle(**{
        name: tuple(to_contract(row) for row in session.scalars(select(model).order_by(model.id)))
        for name, (_, model) in RECORDS.items()
    })
