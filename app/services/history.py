from __future__ import annotations

from datetime import date
from typing import Any


def normalize_fault_tag(fft: dict[str, Any], selected_fault_type: str | None = None) -> dict[str, str] | None:
    diagnosis=(fft.get("analysis") or {}).get("diagnosis") if isinstance(fft.get("analysis"),dict) else None
    if not isinstance(diagnosis,dict) or diagnosis.get("status") != "analyzed": return None
    faults=diagnosis.get("faults")
    if isinstance(faults,list):
        selected=next((item for item in faults if isinstance(item,dict) and item.get("type")==selected_fault_type),None) or next((item for item in faults if isinstance(item,dict) and item.get("type")==diagnosis.get("defaultFaultType")),None)
        return {"fault":"베어링","faultType":selected["type"]} if selected and selected.get("hasAnomaly") else None
    return {"fault":"축","faultType":{"unbalance":"Unbalance","misalignment":"Misalignment","complex":"Complex"}[diagnosis["diagnosis"]]} if diagnosis.get("diagnosis") in {"unbalance","misalignment","complex"} else None


def matches_fault(item: dict[str, Any], tag: dict[str, str] | None) -> bool:
    return tag is not None and item.get("fault") == tag["fault"] and item.get("faultType") == tag["faultType"]


def filter_by_cutoff(items: list[dict[str, Any]], cutoff: date | None) -> list[dict[str, Any]]:
    result=[]
    for item in items:
        try: valid=cutoff is None or date.fromisoformat(str(item.get("date"))) <= cutoff
        except ValueError: valid=False
        if valid: result.append(item)
    return sorted(result,key=lambda item:str(item.get("date")),reverse=True)


def deduplicate_history(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected=[]; seen=set()
    for item in items:
        identity=item.get("id")
        if identity in seen: continue
        seen.add(identity); selected.append(item)
    return selected


def search_history(items: list[dict[str, Any]], *, process: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
    keyword=(keyword or "").strip().lower(); process=(process or "").strip()
    return [item for item in items if (not process or item.get("process")==process) and (not keyword or keyword in " ".join(str(item.get(key,"")) for key in ("equipmentName","issue","analysis","result","feedback","fault","faultType")).lower())]


def select_dashboard_related_history(fft: dict[str, Any], items: list[dict[str, Any]], selected_fault_type: str | None = None, until: date | None = None) -> dict[str, Any]:
    tag=normalize_fault_tag(fft,selected_fault_type); cutoff=until
    return {"faultTag":tag,"items":filter_by_cutoff([item for item in items if matches_fault(item,tag)],cutoff)}


def select_ai_related_history(dataset_id: str, fft: dict[str, Any], items: list[dict[str, Any]], selected_fault_type: str | None = None, until: date | None = None, limit: int = 5) -> dict[str, Any]:
    measured=str(fft.get("measuredAt","")).split(" ")[0]
    try: cutoff=min(date.fromisoformat(measured),until) if until else date.fromisoformat(measured)
    except ValueError: cutoff=until
    eligible=filter_by_cutoff(items,cutoff); tag=normalize_fault_tag(fft,selected_fault_type); same=[item for item in eligible if item.get("datasetId")==dataset_id]; similar=[item for item in eligible if matches_fault(item,tag)]
    selected=deduplicate_history(same+similar)[:limit]
    return {"cutoffDate":cutoff.isoformat() if cutoff else None,"faultTag":tag,"sameEquipmentCount":len(same),"similarFaultCount":len(similar),"items":selected}
