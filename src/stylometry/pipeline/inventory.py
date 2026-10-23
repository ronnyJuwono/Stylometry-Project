"""Separate synthetic planning representation. No change to S2A/SQL models."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from stylometry import contracts as c
from stylometry.paper1 import TaskCode


class StudyCode(StrEnum):
    P1 = "P1"
    P2 = "P2"
    D1 = "D1"


class SubmissionState(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNRESOLVED = "unresolved"


class StudyPlan(c.Contract):
    id: UUID
    code: StudyCode
    slot_codes: tuple[c.Label, ...]

    @model_validator(mode="after")
    def validate_slots(self):
        if not self.slot_codes or len(set(self.slot_codes)) != len(self.slot_codes):
            raise ValueError("Explicit unique slot definitions required")
        if self.code == StudyCode.P1 and self.slot_codes != tuple(str(t) for t in TaskCode):
            raise ValueError("P1 retains exactly the approved five task definitions")
        return self


class AuthorshipEntity(c.Contract):
    id: UUID
    kind: Literal["individual", "group"]


class InventoryUnit(c.Contract):
    id: UUID
    author_id: UUID
    kind: Literal["task_collection", "section_document", "submission", "reference"]
    parent_unit_id: UUID | None = None
    reference_category: c.Label | None = None


class InventorySlot(c.Contract):
    id: UUID
    unit_id: UUID
    slot_code: c.Label
    status: SubmissionState
    source_document_id: UUID | None = None
    provenance_id: UUID

    @model_validator(mode="after")
    def validate_submission(self):
        if self.status == SubmissionState.PRESENT and self.source_document_id is None:
            raise ValueError("Present submission requires its source metadata")
        if self.status == SubmissionState.MISSING and self.source_document_id is not None:
            raise ValueError("Missing submission cannot claim a source")
        return self


class InventorySummary(c.Contract):
    synthetic_only: Literal[True] = True
    study: StudyCode
    expected_slots: int
    declared_slots: int
    present: int
    missing: int
    unresolved: int
    undeclared_slots: tuple[tuple[UUID, str], ...]
    complete: bool


class SyntheticInventory(c.Contract):
    synthetic_only: Literal[True]
    study: StudyPlan
    inventory_version: c.Label
    corpus: c.Corpus
    provenance: tuple[c.Provenance, ...]
    authors: tuple[AuthorshipEntity, ...]
    units: tuple[InventoryUnit, ...]
    documents: tuple[c.SourceDocument, ...]
    slots: tuple[InventorySlot, ...]

    @model_validator(mode="after")
    def validate_graph(self):
        records = (self.study, self.corpus, *self.provenance, *self.authors,
                   *self.units, *self.documents, *self.slots)
        if len({r.id for r in records}) != len(records):
            raise ValueError("Planning record identifiers must be unique")
        evidence = {p.id for p in self.provenance}
        if self.corpus.provenance_id not in evidence:
            raise ValueError("Unresolved corpus provenance")
        authors = {a.id: a for a in self.authors}
        units = {u.id: u for u in self.units}
        documents = {d.id: d for d in self.documents}
        if not authors or not units:
            raise ValueError("Explicit authorship entities and writing units required")
        for document in self.documents:
            if document.corpus_id != self.corpus.id or document.provenance_id not in evidence:
                raise ValueError("Source corpus/provenance mismatch")
        p1_authors = set()
        for unit in self.units:
            if unit.author_id not in authors:
                raise ValueError("Unresolved writing-unit authorship")
            if self.study.code == StudyCode.P1:
                if (authors[unit.author_id].kind != "individual" or unit.kind != "task_collection"
                        or unit.author_id in p1_authors or unit.parent_unit_id is not None
                        or unit.reference_category is not None):
                    raise ValueError("P1 planning must fit the approved writer/task slot model")
                p1_authors.add(unit.author_id)
            elif self.study.code == StudyCode.P2:
                if unit.kind != "section_document" or unit.parent_unit_id is not None or unit.reference_category is not None:
                    raise ValueError("P2 uses explicitly declared document-section units")
            elif unit.kind not in ("submission", "reference"):
                raise ValueError("D1 requires explicit submission/reference units")
            if (unit.kind == "reference") != (unit.reference_category is not None):
                raise ValueError("Reference units require an explicit category only")
            seen = {unit.id}
            parent_id = unit.parent_unit_id
            while parent_id is not None:
                if parent_id in seen or parent_id not in units:
                    raise ValueError("Unresolved or cyclic writing-unit lineage")
                seen.add(parent_id)
                parent = units[parent_id]
                if parent.author_id != unit.author_id:
                    raise ValueError("Draft lineage must retain its supplied authorship")
                parent_id = parent.parent_unit_id
        if {u.author_id for u in self.units} != set(authors):
            raise ValueError("Each declared author requires an explicit writing unit")
        keys = set()
        for slot in self.slots:
            key = (slot.unit_id, slot.slot_code)
            if key in keys:
                raise ValueError("Duplicate logical slot; this is not duplicate-text detection")
            keys.add(key)
            if slot.unit_id not in units or slot.slot_code not in self.study.slot_codes:
                raise ValueError("Unresolved unit or study slot")
            if slot.provenance_id not in evidence:
                raise ValueError("Unresolved slot provenance")
            if slot.source_document_id is not None and slot.source_document_id not in documents:
                raise ValueError("Unresolved source document")
        return self

    def summary(self) -> InventorySummary:
        present_keys = {(s.unit_id, s.slot_code) for s in self.slots}
        absent = tuple((u.id, code) for u in self.units for code in self.study.slot_codes
                       if (u.id, code) not in present_keys)
        counts = {status: sum(s.status == status for s in self.slots) for status in SubmissionState}
        return InventorySummary(study=self.study.code, expected_slots=len(self.units) * len(self.study.slot_codes),
            declared_slots=len(self.slots), present=counts[SubmissionState.PRESENT],
            missing=counts[SubmissionState.MISSING], unresolved=counts[SubmissionState.UNRESOLVED],
            undeclared_slots=absent, complete=not absent)

    def as_p1_bundle(self) -> c.ResearchBundle:
        """Only the representable P1 subset. Status/source-slot links stay in receipt."""
        if self.study.code != StudyCode.P1 or not self.summary().complete:
            raise ValueError("Only complete explicit P1 inventory can use the current SQL schema")
        units = {u.id: u for u in self.units}
        return c.ResearchBundle(provenance=self.provenance, corpora=(self.corpus,),
            writers=tuple(c.AnonymizedWriter(id=a.id, corpus_id=self.corpus.id) for a in self.authors),
            documents=self.documents, samples=tuple(c.TextSample(id=s.id, corpus_id=self.corpus.id,
                writer_id=units[s.unit_id].author_id, task=TaskCode(s.slot_code), provenance_id=s.provenance_id)
                for s in self.slots), extractions=(), derivations=(), evaluations=(), snapshots=(), runs=())
