export function populateSummary(data) {
  const { equipment } = data;

  document.getElementById("plant-name").textContent = equipment.plant;
  document.getElementById("sensor-number").textContent = equipment.sensorNumber ?? equipment.id;
  document.getElementById("equipment-title").textContent = equipment.name;
  document.title = `${equipment.id} | CMS AI Dashboard`;
}
