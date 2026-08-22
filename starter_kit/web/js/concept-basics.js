// Focused concept explorer: sidebar navigation and one explanation at a time.

const CONCEPTS = [
  { id: 'qubit', next: '量子门' },
  { id: 'gate', next: '量子电路' },
  { id: 'circuit', next: '测量' },
  { id: 'measurement', next: null },
];

export class ConceptBasics {
  constructor(root) {
    this.root = root;
    this.activeIndex = 0;
    this.gateState = 'zero';
    this.lastGateAction = 'zero';
    this.measurements = { zero: 0, one: 0 };
  }

  init() {
    this.root.querySelectorAll('[data-concept-target]').forEach((button) => {
      button.addEventListener('click', () => this.selectConcept(button.dataset.conceptTarget));
    });
    this.root.querySelectorAll('[data-basic-action]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.dataset.basicAction === 'measure') this.measureOnce();
        else this.applyGate(button.dataset.basicAction);
      });
    });
    this.root.querySelector('#next-concept').addEventListener('click', () => {
      if (this.activeIndex < CONCEPTS.length - 1) {
        this.selectConcept(CONCEPTS[this.activeIndex + 1].id);
      }
    });
    this.reset();
  }

  reset() {
    this.gateState = 'zero';
    this.lastGateAction = 'zero';
    this.measurements = { zero: 0, one: 0 };
    this.renderGate();
    this.renderMeasurements(null);
    this.selectConcept('qubit');
  }

  selectConcept(conceptId) {
    const nextIndex = CONCEPTS.findIndex((concept) => concept.id === conceptId);
    if (nextIndex < 0) return;
    this.activeIndex = nextIndex;
    this.root.dataset.activeConcept = conceptId;

    this.root.querySelectorAll('[data-concept-target]').forEach((button) => {
      if (button.dataset.conceptTarget === conceptId) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    this.root.querySelectorAll('[data-concept-panel]').forEach((panel) => {
      const active = panel.dataset.conceptPanel === conceptId;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });

    const concept = CONCEPTS[nextIndex];
    this.root.querySelector('#concept-position').textContent = `概念 ${nextIndex + 1} / ${CONCEPTS.length}`;
    const nextButton = this.root.querySelector('#next-concept');
    nextButton.hidden = !concept.next;
    nextButton.textContent = concept.next ? `下一个：${concept.next} →` : '';
  }

  applyGate(action) {
    this.lastGateAction = action;
    if (action === 'x') {
      this.gateState = 'one';
    } else if (action === 'h') {
      this.gateState = 'superposition';
    } else {
      this.gateState = 'zero';
    }
    this.renderGate();
    this.animateGate(action);
  }

  renderGate() {
    this.root.dataset.qubitState = this.gateState;
    const copy = {
      zero: {
        label: '|0⟩',
        text: '从确定的 |0⟩ 状态开始；线路上还没有量子门。',
      },
      one: { label: '|1⟩', text: 'X 门像一次翻转：输入是 |0⟩，通过后变成确定的 |1⟩。' },
      superposition: {
        label: '0 或 1',
        text: 'H 门改变了状态：现在测量可能得到 0，也可能得到 1；一次测量仍只得到一个结果。',
      },
    }[this.gateState];
    this.root.querySelector('#basic-gate-state').textContent = copy.label;
    this.root.querySelector('#basic-gate-narration').textContent = copy.text;
    this.root.querySelectorAll('[data-basic-action]:not([data-basic-action="measure"])').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.basicAction === this.lastGateAction ? 'true' : 'false');
    });
  }

  animateGate(action) {
    const chip = this.root.querySelector('#basic-gate-chip');
    const loading = this.root.querySelector('#basic-gate-loading');
    const labels = {
      zero: { chip: '准备', loading: '线路已重置' },
      x: { chip: 'X', loading: 'X 门已加载' },
      h: { chip: 'H', loading: 'H 门已加载' },
    }[action];

    chip.classList.remove('is-loading');
    // Force a new animation even when the same gate is selected twice.
    void chip.offsetWidth;
    chip.dataset.gate = action === 'zero' ? 'ready' : action;
    chip.textContent = labels.chip;
    loading.textContent = action === 'zero' ? labels.loading : `正在加载 ${labels.chip} 门…`;
    chip.classList.add('is-loading');
    chip.addEventListener('animationend', () => {
      loading.textContent = labels.loading;
    }, { once: true });
  }

  measureOnce() {
    const result = Math.random() < 0.5 ? 'zero' : 'one';
    this.measurements[result] += 1;
    this.renderMeasurements(result);
  }

  renderMeasurements(result) {
    const total = this.measurements.zero + this.measurements.one;
    const resultLabel = this.root.querySelector('#basic-measure-result');
    resultLabel.textContent = result === null ? '等待测量' : `这一次得到 ${result === 'zero' ? '0' : '1'}`;
    resultLabel.dataset.result = result || 'waiting';
    this.root.querySelector('#basic-measure-counts').textContent =
      `已测量 ${total} 次 · 0：${this.measurements.zero} 次 · 1：${this.measurements.one} 次`;
  }
}
