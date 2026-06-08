"""Lazily imports every sibling service's ``<name>_core`` business-logic
package so the gateway can call it directly, in-process, when
``AEGIS_SYNC_MODE`` is on -- both for the one-shot demo pipeline
(``gateway_core.demo_pipeline``) and for ordinary BFF reads
(``gateway_core.reads``) that would otherwise need a running sibling
container.

Imports are deferred into :func:`get_modules` (rather than happening at
module import time) so a gateway deployed in pure-proxy mode -- one that
only ever talks to already-running services over HTTP -- never needs these
sibling packages installed in its image at all.
"""

from __future__ import annotations

from types import SimpleNamespace

_modules: SimpleNamespace | None = None
_dbs_ready: set[str] = set()


def get_modules() -> SimpleNamespace:
    global _modules
    if _modules is not None:
        return _modules

    from ingestion_core.models import RawEnvelope
    from ingestion_core.replay import list_scenarios, load_scenario

    from normalization_core.normalize import NormalizationError, normalize_raw_message

    from enrichment_core.pipeline import enrich_event

    from graph_core.writer import derive_graph_updates, observation_for

    from detection_core.pipeline import get_default_state, new_detection_state, process_event

    from case_core import repository as case_repository
    from case_core.db import init_db as case_init_db
    from case_core.db import sessionmaker_for as case_sessionmaker_for
    from case_core.schemas import CaseOut, CaseSearchParams

    from triage_core.pipeline import gather_evidence, generate_triage_report
    from triage_core.tools import InProcessEvidenceTools

    from policy_core import store as policy_store
    from policy_core.recommend import recommend_action

    from approval_core import repository as approval_repository
    from approval_core.audit_client import InProcessAuditSink
    from approval_core.db import init_db as approval_init_db
    from approval_core.db import sessionmaker_for as approval_sessionmaker_for
    from approval_core.schemas import ApprovalOut, CreateApprovalRequest

    from audit_core import repository as audit_repository
    from audit_core.db import init_db as audit_init_db
    from audit_core.db import sessionmaker_for as audit_sessionmaker_for
    from audit_core.schemas import AuditEventIn, AuditEventOut

    _modules = SimpleNamespace(
        RawEnvelope=RawEnvelope,
        list_scenarios=list_scenarios,
        load_scenario=load_scenario,
        NormalizationError=NormalizationError,
        normalize_raw_message=normalize_raw_message,
        enrich_event=enrich_event,
        derive_graph_updates=derive_graph_updates,
        observation_for=observation_for,
        get_default_state=get_default_state,
        new_detection_state=new_detection_state,
        process_event=process_event,
        case_repository=case_repository,
        case_init_db=case_init_db,
        case_sessionmaker_for=case_sessionmaker_for,
        CaseOut=CaseOut,
        CaseSearchParams=CaseSearchParams,
        gather_evidence=gather_evidence,
        generate_triage_report=generate_triage_report,
        InProcessEvidenceTools=InProcessEvidenceTools,
        policy_store=policy_store,
        recommend_action=recommend_action,
        approval_repository=approval_repository,
        InProcessAuditSink=InProcessAuditSink,
        approval_init_db=approval_init_db,
        approval_sessionmaker_for=approval_sessionmaker_for,
        ApprovalOut=ApprovalOut,
        CreateApprovalRequest=CreateApprovalRequest,
        audit_repository=audit_repository,
        audit_init_db=audit_init_db,
        audit_sessionmaker_for=audit_sessionmaker_for,
        AuditEventIn=AuditEventIn,
        AuditEventOut=AuditEventOut,
    )
    return _modules


async def ensure_db(name: str, init_fn, dsn: str) -> None:
    if name in _dbs_ready:
        return
    await init_fn(dsn)
    _dbs_ready.add(name)


def reset_for_tests() -> None:
    global _modules, _dbs_ready
    _modules = None
    _dbs_ready = set()
    try:
        from aegis_common.graphstore import reset_store_for_tests
        from detection_core.pipeline import reset_default_state

        reset_store_for_tests()
        reset_default_state()
    except Exception:
        pass
