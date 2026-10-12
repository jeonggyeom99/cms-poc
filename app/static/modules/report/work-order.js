export function workOrderDefaults(equipment, summary, now = new Date()) {
  const localTime = (date) => new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const start = new Date(now); start.setDate(start.getDate() + 1); start.setHours(9, 0, 0, 0);
  const finish = new Date(start); finish.setHours(17);
  return [
    ['작업주문', '자동 부여 (발행 시)'], ['area', equipment.plant || '미지정'],
    ['설비', equipment.name || equipment.id], ['작업명', `${equipment.name} 진동 이상 점검`],
    ['보조설명', summary || '회전체 상태 점검 및 동일 운전 조건 진동 재측정'],
    ['Job plan', '회전체 부착물·마모·체결 점검 → 필요 시 청소 및 밸런싱 → 동일 조건 진동 재측정'],
    ['작업 유형', '예방 정비'], ['수행유형', '현장 점검'], ['휴지유형', '계획 정지'],
    ['계획 시작일시', localTime(start), 'datetime-local'], ['계획 완료일시', localTime(finish), 'datetime-local'],
    ['계획 부서', '설비보전팀'], ['담당자', '미지정'], ['스케줄 부서', '정비계획팀'],
    ['스케줄러', '미지정'], ['수행부서', '기계정비팀'], ['희망부서', '설비보전팀'],
    ['실행부서', '기계정비팀'], ['상태', '작성 중'], ['담당자 전화번호', '', 'tel'],
    ['등록자', '데모 사용자'], ['등록일시', localTime(now), 'datetime-local'],
    ['발생유형', '상태 감시 알람'], ['발행항목', '진동 속도 알람 / Unbalance'],
    ['발생유형(추가)', '진동 우상향'], ['발생유형(추가) 사유', '속도 알람과 진동 상승 경향이 함께 확인되어 점검 작업을 계획합니다.'],
  ];
}

export function bindWorkOrder(getDashboard) {
  const button = document.getElementById('work-order-open');
  const dialog = document.getElementById('work-order-dialog');
  const form = document.getElementById('work-order-form');
  const status = document.getElementById('work-order-status');
  button.addEventListener('click', () => {
    const data = getDashboard();
    if (!data?.equipment) return;
    form.replaceChildren();
    for (const [label, value, type] of workOrderDefaults(data.equipment, document.getElementById('ai-analysis-description').textContent)) {
      const field = document.createElement('label'); field.className = 'work-order-field';
      const caption = document.createElement('span'); caption.textContent = label;
      const multiline = ['보조설명', 'Job plan', '발생유형(추가) 사유'].includes(label);
      const input = document.createElement(multiline ? 'textarea' : 'input');
      if (!multiline) input.type = type || 'text';
      input.name = label; input.value = value || '';
      input.required = ['설비', '작업명', '계획 시작일시', '계획 완료일시'].includes(label);
      if (['작업주문', '상태', '등록일시'].includes(label)) input.readOnly = true;
      if (multiline) { input.rows = 2; field.classList.add('work-order-field-wide'); }
      field.append(caption, input); form.append(field);
    }
    status.textContent = '항목을 확인한 후 데모 작업주문을 발행하세요.';
    document.getElementById('work-order-issue').disabled = false;
    dialog.showModal();
  });
  document.getElementById('work-order-close').addEventListener('click', () => dialog.close());
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    if (values['계획 완료일시'] <= values['계획 시작일시']) {
      status.textContent = '계획 완료일시는 시작일시보다 늦어야 합니다.'; return;
    }
    values['작업주문'] = `WO-DEMO-${Date.now()}`; values['상태'] = '발행 완료 (데모)';
    form.elements.namedItem('작업주문').value = values['작업주문'];
    form.elements.namedItem('상태').value = values['상태'];
    const url = URL.createObjectURL(new Blob([JSON.stringify(values, null, 2)], {type:'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = `${values['작업주문']}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status.textContent = `${values['작업주문']} 발행 완료. 작업주문 파일을 저장했습니다.`;
    document.getElementById('work-order-issue').disabled = true;
  });
}
