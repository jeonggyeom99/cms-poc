import { availabilityLabel } from "../core/format.js";

export function populateSummary(data) {
  const { equipment } = data;

  document.getElementById("plant-name").textContent = equipment.plant;
  document.getElementById("line-name").textContent = equipment.line;
  document.getElementById("equipment-code").textContent = equipment.id;
  document.getElementById("equipment-title").textContent = equipment.name;
  document.getElementById("measurement-point").textContent = `측정 위치 · ${equipment.measurementPoint}`;
  const measuredAt = equipment.lastMeasuredAt
    ? `최근 측정 ${equipment.lastMeasuredAt}`
    : "최근 측정 데이터 없음";
  document.getElementById("last-updated").textContent = measuredAt;
  document.getElementById("overview-measured-at").textContent = measuredAt;
  document.getElementById("dataset-availability").textContent = availabilityLabel(data.meta.availability);
  document.title = `${equipment.id} | CMS AI Dashboard`;
}
