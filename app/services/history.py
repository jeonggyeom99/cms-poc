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


def filter_by_cutoff(items: list[dict[str, Any]], cutoff: date | None, *, strictly_before: bool = False) -> list[dict[str, Any]]:
    result=[]
    for item in items:
        try:
            item_date = date.fromisoformat(str(item.get("date")))
            valid = cutoff is None or (item_date < cutoff if strictly_before else item_date <= cutoff)
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


def _identity(value: Any) -> str:
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _same_equipment(item: dict[str, Any], equipment: dict[str, Any] | None, dataset_id: str) -> bool:
    """Prefer stable sensor/equipment identifiers; retain datasetId only for legacy callers."""
    if equipment:
        equipment_id = _identity(equipment.get("id"))
        sensor = _identity(equipment.get("sensorNumber"))
        item_sensor = _identity(item.get("sensorNumber"))
        if item_sensor and item_sensor in {equipment_id.removeprefix("V"), sensor}:
            return True
        item_name, equipment_name = _identity(item.get("equipmentName")), _identity(equipment.get("name"))
        return bool(item_name and equipment_name and item_name == equipment_name)
    return item.get("datasetId") == dataset_id


def select_ai_related_history(dataset_id: str, fft: dict[str, Any], items: list[dict[str, Any]], selected_fault_type: str | None = None, until: date | None = None, limit: int = 5, *, equipment: dict[str, Any] | None = None) -> dict[str, Any]:
    measured=str(fft.get("measuredAt","")).split(" ")[0]
    try: cutoff=min(date.fromisoformat(measured),until) if until else date.fromisoformat(measured)
    except ValueError: cutoff=until
    eligible=filter_by_cutoff(items,cutoff,strictly_before=True); tag=normalize_fault_tag(fft,selected_fault_type)
    # AI comparison history is deliberately narrow: same equipment *and* same
    # standardized fault type.  Do not invent a similar case when none exists.
    selected=[item for item in eligible if _same_equipment(item,equipment,dataset_id) and matches_fault(item,tag)]
    selected=deduplicate_history(selected)[:limit]
    return {"cutoffDate":cutoff.isoformat() if cutoff else None,"faultTag":tag,"sameEquipmentCount":len(selected),"similarFaultCount":0,"items":selected}
