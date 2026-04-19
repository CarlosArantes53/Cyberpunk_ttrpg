// ============ TTS ============
let _ttsAudio = null;
let _ttsActiveBtn = null;
const _ttsTexts = {};
let _ttsCounter = 0;

// Armazena texto e retorna a chave para uso no botão
function storeTTS(text) {
  const key = ++_ttsCounter;
  _ttsTexts[key] = text;
  return key;
}

// Constrói o botão 🔊 HTML para injetar no DOM
function ttsBtn(key) {
  return `<button class="tts-play-btn" title="Ouvir resposta" onclick="speakStored(${key}, this)">🔊</button>`;
}

async function speakStored(key, btn) {
  const text = _ttsTexts[key];
  if (!text) return;
  await speak(text, btn);
}

async function speak(text, btn) {
  const voice = document.getElementById('tts-voice').value;

  // Para áudio anterior e reseta botão anterior
  if (_ttsAudio) {
    _ttsAudio.pause();
    _ttsAudio = null;
  }
  if (_ttsActiveBtn && _ttsActiveBtn !== btn) {
    _ttsActiveBtn.classList.remove('playing');
    _ttsActiveBtn.textContent = '🔊';
  }

  if (btn) { btn.classList.add('playing'); btn.textContent = '⏹'; }
  _ttsActiveBtn = btn || null;

  try {
    const r = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto: text, voz: voice })
    });
    if (!r.ok) {
      const errData = await r.json();
      throw new Error(`TTS falhou: ${errData.erro || r.status}`);
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    _ttsAudio = new Audio(url);
    _ttsAudio.onended = () => {
      URL.revokeObjectURL(url);
      if (btn) { btn.classList.remove('playing'); btn.textContent = '🔊'; }
      _ttsActiveBtn = null;
    };
    await _ttsAudio.play();
  } catch (e) {
    if (btn) { btn.classList.remove('playing'); btn.textContent = '🔊'; }
    _ttsActiveBtn = null;
    console.error('TTS erro:', e);
  }
}

// ============ MICROFONE / TRANSCRIÇÃO ============
let _recorder = null;
let _recChunks = [];
let _activeMicBtn = null;

async function toggleMic(targetId, btn) {
  if (_recorder && _recorder.state === 'recording') {
    _recorder.stop();
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    alert('Permissão de microfone negada.');
    return;
  }

  _recChunks = [];
  _activeMicBtn = btn;
  _recorder = new MediaRecorder(stream);

  _recorder.ondataavailable = e => { if (e.data.size > 0) _recChunks.push(e.data); };

  _recorder.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    btn.className = 'mic-btn processing';
    btn.textContent = '⏳';

    const blob = new Blob(_recChunks, { type: 'audio/webm' });
    const fd = new FormData();
    fd.append('audio', blob, 'audio.webm');

    try {
      const r = await fetch('/api/transcribe', { method: 'POST', body: fd });
      const d = await r.json();
      if (d.erro) throw new Error(d.erro);
      const ta = document.getElementById(targetId);
      ta.value = (ta.value ? ta.value + ' ' : '') + d.texto;
      ta.focus();
    } catch (e) {
      alert('Erro na transcrição: ' + e.message);
    } finally {
      btn.className = 'mic-btn';
      btn.textContent = '🎙';
      _recorder = null;
      _activeMicBtn = null;
    }
  };

  _recorder.start();
  btn.className = 'mic-btn recording';
  btn.textContent = '⏹';
}

// ============ ABAS ============
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById('panel-' + t.dataset.panel).classList.add('active');
    if (t.dataset.panel === 'anotador') carregarMemoria();
  });
});

// ============ MESTRE ============
async function uploadPDF() {
  const input = document.getElementById('pdf-input');
  const status = document.getElementById('pdf-status');
  if (!input.files[0]) {
    status.textContent = '// selecione um arquivo';
    status.className = 'status err';
    return;
  }
  status.textContent = '// enviando...';
  status.className = 'status';
  const fd = new FormData();
  fd.append('pdf', input.files[0]);
  try {
    const r = await fetch('/api/mestre/upload', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.erro) throw new Error(d.erro);
    status.textContent = '// ' + d.nome + ' OK';
    status.className = 'status ok';
  } catch (e) {
    status.textContent = '// erro: ' + e.message;
    status.className = 'status err';
  }
}

async function perguntarMestre() {
  const p = document.getElementById('pergunta-mestre').value.trim();
  if (!p) return;
  const log = document.getElementById('log-mestre');
  log.innerHTML = '<span class="user">> ' + p + '</span>\n\n<span class="bot spin">consultando</span>';
  try {
    const r = await fetch('/api/mestre/perguntar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pergunta: p })
    });
    const d = await r.json();
    if (d.erro) throw new Error(d.erro);
    const key = storeTTS(d.resposta);
    log.innerHTML =
      `<div class="response-hdr"><span class="who-label">JUIZ</span>${ttsBtn(key)}</div>` +
      '<span class="user">> ' + p + '</span>\n\n' +
      '<span class="bot">' + d.resposta + '</span>';
  } catch (e) {
    log.innerHTML = '<span style="color:var(--danger)">ERRO: ' + e.message + '</span>';
  }
}

// ============ ANOTADOR ============
async function anotar() {
  const d = document.getElementById('desc-anotador').value.trim();
  if (!d) return;
  const log = document.getElementById('log-anotador');
  log.innerHTML = '<span class="spin">extraindo entidades</span>';
  try {
    const r = await fetch('/api/anotador', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ descricao: d })
    });
    const res = await r.json();
    if (res.erro) throw new Error(res.erro);
    const resumo = Object.entries(res.extraido)
      .filter(([, v]) => Array.isArray(v) && v.length)
      .map(([k, v]) => `${v.length} ${k}`)
      .join(', ');
    const fala = resumo ? `Extração concluída: ${resumo} registrados.` : 'Extração concluída.';
    const key = storeTTS(fala);
    log.innerHTML =
      `<div class="response-hdr"><span class="who-label">ESCRIBA</span>${ttsBtn(key)}</div>` +
      '<span class="bot">✓ Extraido:</span>\n' +
      JSON.stringify(res.extraido, null, 2);
    document.getElementById('desc-anotador').value = '';
    renderMemoria(res.memoria_total);
  } catch (e) {
    log.innerHTML = '<span style="color:var(--danger)">ERRO: ' + e.message + '</span>';
  }
}

async function carregarMemoria() {
  const r = await fetch('/api/memoria');
  const d = await r.json();
  renderMemoria(d);
}

async function limparMemoria() {
  if (!confirm('Zerar toda a memoria da campanha?')) return;
  await fetch('/api/memoria/limpar', { method: 'POST' });
  carregarMemoria();
}

function renderMemoria(mem) {
  const container = document.getElementById('memoria-display');
  let html = '';
  const secoes = [
    ['itens', 'ITENS', 'itens'],
    ['locais', 'LOCAIS', 'locais'],
    ['personagens', 'PERSONAGENS', 'personagens'],
    ['eventos', 'EVENTOS', 'eventos']
  ];
  for (const [chave, titulo, cls] of secoes) {
    const lista = mem[chave] || [];
    if (lista.length === 0) continue;
    html += `<div class="section-title">// ${titulo} (${lista.length})</div><div class="grid">`;
    for (const it of lista) {
      const nome = it.nome || it.titulo || '???';
      const meta = it.tipo || it.papel || (it.relacao ? it.relacao : '');
      const desc = it.descricao || it.resumo || '';
      const tags = (it.tags || []).map(t => `<span class="tag-pill">${t}</span>`).join('');
      html += `<div class="card ${cls}">
        <h4>${nome}</h4>
        <div class="meta">${meta}</div>
        <div>${desc}</div>
        <div class="tags">${tags}</div>
      </div>`;
    }
    html += '</div>';
  }
  if (!html) html = '<p class="status">// memoria vazia</p>';
  container.innerHTML = html;
}

// ============ NETRUNNER ============
let netrunnerHist = [];

async function falarNetrunner() {
  const m = document.getElementById('msg-netrunner').value.trim();
  if (!m) return;
  const chat = document.getElementById('chat-netrunner');
  chat.innerHTML += `<div class="msg user"><span class="who">MESTRE</span>> ${escapeHtml(m)}</div>`;
  chat.innerHTML += `<div class="msg model" id="pending"><span class="who">ICE-9</span><span class="spin">processando</span></div>`;
  chat.scrollTop = chat.scrollHeight;
  document.getElementById('msg-netrunner').value = '';

  try {
    const r = await fetch('/api/netrunner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensagem: m, historico: netrunnerHist })
    });
    const d = await r.json();
    if (d.erro) throw new Error(d.erro);
    document.getElementById('pending').remove();
    const key = storeTTS(d.resposta);
    chat.innerHTML += `<div class="msg model"><span class="who">ICE-9 ${ttsBtn(key)}</span>> ${escapeHtml(d.resposta)}</div>`;
    netrunnerHist.push({ role: 'user', text: m });
    netrunnerHist.push({ role: 'model', text: d.resposta });
    chat.scrollTop = chat.scrollHeight;
  } catch (e) {
    document.getElementById('pending').remove();
    chat.innerHTML += `<div class="msg" style="color:var(--danger)">ERRO: ${e.message}</div>`;
  }
}

function limparChat() {
  netrunnerHist = [];
  document.getElementById('chat-netrunner').innerHTML =
    '<div class="msg model"><span class="who">ICE-9</span>> Sessao reiniciada. Pronta.</div>';
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

// Carrega memoria ao abrir
carregarMemoria();
