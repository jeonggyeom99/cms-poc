export function populateSummary(data) {
  const { equipment } = data;

  document.getElementById("plant-name").textContent = equipment.plant;
  document.getElementById("sensor-number").textContent = equipment.sensorNumber ?? equipment.id;
  document.getElementById("equipment-title").textContent = equipment.name;
  const until = new URLSearchParams(window.location.search).get("until");
  const reference = document.getElementById("dashboard-until");
  reference.hidden = !until;
  reference.textContent = until ? `${until.replaceAll("-", ".")} 기준` : "";
  document.title = `${equipment.id} | CMS AI Dashboard`;
}
