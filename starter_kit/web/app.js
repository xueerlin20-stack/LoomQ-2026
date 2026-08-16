const conversation = document.querySelector('#conversation');
const composer = document.querySelector('#composer');
const promptInput = document.querySelector('#prompt');
const sendButton = document.querySelector('#send');
const loadingTemplate = document.querySelector('#loading-template');

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => {
    promptInput.value = button.dataset.prompt;
    promptInput.focus();
    document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
});

promptInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

composer.addEventListener('submit', async (event) => {
  event.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt || sendButton.disabled) return;

  addUserMessage(prompt);
  promptInput.value = '';
  setBusy(true);
  const loading = loadingTemplate.content.firstElementChild.cloneNode(true);
  conversation.append(loading);
  scrollConversation();

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    const data = await response.json();
    loading.remove();
    if (!response.ok) throw new Error(data.error || '请求失败');
    addAgentResult(data);
  } catch (error) {
    loading.remove();
    addError(error.message || '暂时无法连接 LoomQ Agent，请稍后再试。');
  } finally {
    setBusy(false);
    promptInput.focus();
    scrollConversation();
  }
});

function addUserMessage(text) {
  const article = document.createElement('article');
  article.className = 'message user-message';
  article.innerHTML = '<div class="avatar" aria-hidden="true">YOU</div><div class="message-body"><div class="message-meta">你的需求</div></div>';
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  article.querySelector('.message-body').append(paragraph);
  conversation.append(article);
}

function addAgentResult(data) {
  const english = data.response_language === 'en';
  const article = document.createElement('article');
  article.className = 'message agent-message';
  article.innerHTML = '<div class="avatar" aria-hidden="true">LQ</div><div class="message-body"><div class="message-meta">LoomQ Agent</div></div>';
  const body = article.querySelector('.message-body');

  const summary = document.createElement('p');
  summary.textContent = data.display_text;
  body.append(summary);

  if (!data.ok) {
    const error = document.createElement('div');
    error.className = 'error-card';
    error.textContent = data.message || (english ? 'The task could not be completed.' : '暂时无法完成这个任务。');
    body.append(error);
  } else if (data.qasm) {
    body.append(createQasmCard(data, english));
  } else if (data.backend_id) {
    body.append(createBackendCard(data, english));
  }

  conversation.append(article);
}

function createQasmCard(data, english) {
  const card = document.createElement('div');
  card.className = 'result-card';

  const head = document.createElement('div');
  head.className = 'result-head';
  head.innerHTML = `<span class="validation-badge">${english ? 'Executed & validated' : '已运行并验证'}</span>`;
  const copy = document.createElement('button');
  copy.className = 'copy-button';
  copy.type = 'button';
  copy.textContent = english ? 'Copy QASM' : '复制 QASM';
  copy.addEventListener('click', async () => {
    await navigator.clipboard.writeText(data.qasm);
    copy.textContent = english ? 'Copied' : '已复制';
    window.setTimeout(() => { copy.textContent = english ? 'Copy QASM' : '复制 QASM'; }, 1400);
  });
  head.append(copy);
  card.append(head);

  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.textContent = data.qasm;
  pre.append(code);
  card.append(pre);

  const validation = data.validation || {};
  const panel = document.createElement('div');
  panel.className = 'run-panel';
  const summary = document.createElement('div');
  summary.className = 'run-summary';
  summary.textContent = validation.explanation || (english ? 'The circuit ran successfully.' : '电路已成功运行。');
  panel.append(summary);
  if (validation.counts) panel.append(createCounts(validation.counts, validation.shots));
  card.append(panel);
  return card;
}

function createCounts(counts, shots) {
  const container = document.createElement('div');
  container.className = 'counts';
  Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .forEach(([state, count]) => {
      const percent = shots ? (count / shots) * 100 : 0;
      const row = document.createElement('div');
      row.className = 'count-row';
      const label = document.createElement('span');
      label.textContent = state;
      const track = document.createElement('div');
      track.className = 'count-track';
      const fill = document.createElement('div');
      fill.className = 'count-fill';
      fill.style.width = `${Math.max(1, percent)}%`;
      track.append(fill);
      const value = document.createElement('span');
      value.textContent = `${percent.toFixed(1)}%`;
      row.append(label, track, value);
      container.append(row);
    });
  return container;
}

function createBackendCard(data, english) {
  const card = document.createElement('div');
  card.className = 'backend-card';
  const id = document.createElement('div');
  id.className = 'backend-id';
  id.textContent = data.backend_id;
  const reason = document.createElement('p');
  reason.textContent = data.explanation || (english ? 'This backend matches your constraints.' : '该后端符合你的运行条件。');
  card.append(id, reason);
  if (data.alternatives?.length) {
    const alternatives = document.createElement('p');
    alternatives.textContent = `${english ? 'Alternatives' : '备选'}: ${data.alternatives.join(', ')}`;
    card.append(alternatives);
  }
  return card;
}

function addError(message) {
  addAgentResult({ ok: false, display_text: '连接或运行遇到问题。', message });
}

function setBusy(busy) {
  sendButton.disabled = busy;
  promptInput.disabled = busy;
  sendButton.querySelector('span:first-child').textContent = busy ? '实验进行中…' : '开始实验';
}

function scrollConversation() {
  conversation.scrollTo({ top: conversation.scrollHeight, behavior: 'smooth' });
}
