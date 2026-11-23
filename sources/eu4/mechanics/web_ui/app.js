const byId = (id) => document.getElementById(id);
const chatView = byId("chat-view");
const knowledgeView = byId("knowledge-view");
const questionField = byId("question");
const searchField = byId("search");
const conversation = byId("conversation");
const questionError = byId("question-error");
const modelBar = byId("model-bar");
const modelStatus = byId("model-status");
const setupModel = byId("setup-model");
const sendQuestion = byId("send-question");
const knowledgeMessage = byId("knowledge-message");
const searchStatus = byId("search-status");
const results = byId("results");
const loadMore = byId("load-more");
const sourceDialog = byId("source-dialog");
const sourceTitle = byId("source-title");
const sourceContent = byId("source-content");

let modelReady = false;
let preparing = false;
let settingUpModel = false;
let sending = false;
let modelTimer;
let modelRefresh;
let previousExchange;
let activeQuery;
let offset = 0;
let activeSearch;
let activeSource;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

async function api(path, fallback, options) {
  let response;
  try {
    response = await fetch(`/api/${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(fallback);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) {
    throw new Error(typeof body?.detail === "string" ? body.detail : fallback);
  }
  return body;
}

function endpoint(path, parameters) {
  return `${path}?${new URLSearchParams(parameters)}`;
}

function updateSendButton() {
  sendQuestion.disabled = !modelReady || sending || !questionField.value.trim();
}

function showModelStatus(state, message) {
  modelBar.dataset.state = state;
  if (modelStatus.textContent !== message) modelStatus.textContent = message;
}

async function refreshModel() {
  if (modelRefresh || settingUpModel) return;
  clearTimeout(modelTimer);
  modelTimer = undefined;
  const controller = new AbortController();
  modelRefresh = controller;
  try {
    const status = await api("status", "Nie można sprawdzić gotowości czatu.", { signal: controller.signal });
    if (controller.signal.aborted) return;
    const message = status.knowledge_message || "";
    if (knowledgeMessage.textContent !== message) knowledgeMessage.textContent = message;
    knowledgeMessage.hidden = !message;
    modelReady = status.model_ready;
    preparing = ["downloading", "loading"].includes(status.model_state);
    const actions = {
      model_missing: "Pobierz model",
      model_installed: "Wczytaj model",
      error: "Spróbuj ponownie",
      gpu_required: "Spróbuj ponownie",
    };
    const action = actions[status.model_state];
    setupModel.hidden = modelReady || preparing || !action;
    if (action) setupModel.textContent = action;
    let state = "unavailable";
    if (modelReady) state = "ready";
    if (preparing) state = "busy";
    showModelStatus(state, status.message);
    if (preparing) modelTimer = setTimeout(refreshModel, 2000);
    if (["runtime_unavailable", "model_missing"].includes(status.model_state)) {
      modelTimer = setTimeout(refreshModel, 8000);
    }
  } catch (error) {
    if (controller.signal.aborted) return;
    modelReady = false;
    showModelStatus("unavailable", `${error.message} Ponawiam próbę…`);
    setupModel.hidden = true;
    modelTimer = setTimeout(refreshModel, 4000);
  } finally {
    if (modelRefresh === controller) modelRefresh = undefined;
    updateSendButton();
  }
}

setupModel.addEventListener("click", async () => {
  if (preparing) return;
  preparing = true;
  settingUpModel = true;
  modelRefresh?.abort();
  modelRefresh = undefined;
  clearTimeout(modelTimer);
  modelTimer = undefined;
  setupModel.hidden = true;
  showModelStatus("busy", "Przygotowuję model…");
  try {
    const result = await api("model", "Nie udało się przygotować modelu. Spróbuj ponownie.", { method: "POST" });
    showModelStatus("busy", result.message);
    modelTimer = setTimeout(refreshModel, 1000);
  } catch (error) {
    preparing = false;
    setupModel.hidden = false;
    showModelStatus("unavailable", error.message);
  } finally {
    settingUpModel = false;
  }
});

function refreshVisibleModel() {
  if (document.visibilityState === "visible" && !preparing) void refreshModel();
}

window.addEventListener("focus", refreshVisibleModel);
document.addEventListener("visibilitychange", refreshVisibleModel);

function sourceButton(source, label, className) {
  const button = element("button", className, label);
  button.type = "button";
  button.addEventListener("click", () => openSource(source));
  return button;
}

function answerBody(answer, sources) {
  const body = element("div", "answer-text");
  const numbered = new Map(sources.map((source, index) => [source.number ?? index + 1, source]));
  const cited = new Set();
  const tokens = /\[([\d,\s]+)\]|\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;
  let start = 0;
  for (const match of answer.matchAll(tokens)) {
    body.append(answer.slice(start, match.index));
    start = match.index + match[0].length;
    if (match[2] || match[3]) {
      body.append(element(match[2] ? "strong" : "code", null, match[2] || match[3]));
      continue;
    }
    const numbers = (match[1].match(/\d+/g) || []).map(Number);
    if (!numbers.length || numbers.some((number) => !numbered.has(number))) {
      body.append(match[0]);
      continue;
    }
    for (const number of numbers) {
      const source = numbered.get(number);
      const button = sourceButton(source, `[${number}]`, "citation");
      button.setAttribute("aria-label", `Źródło ${number}. ${source.title}`);
      body.append(button);
      cited.add(number);
    }
  }
  body.append(answer.slice(start));
  return { body, sources: [...numbered].filter(([number]) => !cited.size || cited.has(number)) };
}

function appendMessage(kind, label, content) {
  const message = element("article", `message ${kind}`);
  message.append(element("h2", "message-label", label), content);
  conversation.append(message);
  return message;
}

function keepRecentMessageVisible() {
  conversation.scrollTop = conversation.scrollHeight;
}

byId("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionField.value.trim();
  if (!question || !modelReady || sending) return;
  sending = true;
  questionError.hidden = true;
  questionField.readOnly = true;
  updateSendButton();
  const userMessage = appendMessage("player", "Twoje pytanie", element("p", null, question));
  const pending = appendMessage("atlas", "Atlas EU4", element("p", "working", "Szukam odpowiedzi…"));
  keepRecentMessageVisible();

  try {
    const request = { question };
    if (previousExchange) {
      request.previous_question = previousExchange.question;
      request.previous_answer = previousExchange.answer;
    }
    const { answer, sources } = await api("chat", "Nie udało się uzyskać odpowiedzi. Wyślij pytanie ponownie.", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const rendered = answerBody(answer, sources);
    pending.replaceChildren(element("h2", "message-label", "Atlas EU4"), rendered.body);
    if (rendered.sources.length) {
      const sourceList = element("div", "source-list");
      sourceList.append(element("span", "source-label", "Źródła"));
      for (const [number, source] of rendered.sources) {
        sourceList.append(sourceButton(source, `[${number}] ${source.title}`, "source-link"));
      }
      pending.append(sourceList);
    }
    previousExchange = { question, answer };
    questionField.value = "";
    byId("examples").hidden = true;
    conversation.scrollTop = pending.offsetTop;
  } catch (error) {
    pending.remove();
    userMessage.remove();
    questionError.textContent = error.message;
    questionError.hidden = false;
    if (!preparing) void refreshModel();
  } finally {
    sending = false;
    questionField.readOnly = false;
    updateSendButton();
    if (!chatView.hidden && !sourceDialog.open) questionField.focus({ preventScroll: true });
  }
});

questionField.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (!sendQuestion.disabled) byId("chat-form").requestSubmit();
  }
});

questionField.addEventListener("input", updateSendButton);
byId("examples").addEventListener("click", (event) => {
  const question = event.target.closest("button")?.dataset.question;
  if (!question || sending) return;
  questionField.value = question;
  updateSendButton();
  questionField.focus();
});

function recordMeta(record) {
  return [record.section, record.game_version && `EU4 ${record.game_version}`].filter(Boolean).join(" · ");
}

function resultCard(record) {
  const article = element("article", "result-card");
  const title = element("h2", "result-title");
  title.append(sourceButton(record, record.title || "Przeczytaj źródło", "result-link"));
  const meta = recordMeta(record);
  article.append(title);
  if (meta) article.append(element("p", "meta", meta));
  if (record.text) article.append(element("p", "excerpt", record.text));
  return article;
}

async function searchKnowledge(query, append = false) {
  activeSearch?.abort();
  const controller = new AbortController();
  activeSearch = controller;
  if (!append) {
    offset = 0;
    activeQuery = query;
    results.replaceChildren();
  }
  searchStatus.classList.remove("error");
  searchStatus.textContent = append ? "Wczytuję więcej…" : "Szukam w wiedzy o grze…";
  loadMore.disabled = true;

  try {
    const page = await api(endpoint("knowledge", { q: query, offset }), "Nie udało się wczytać wiedzy o grze. Spróbuj ponownie.", {
      signal: controller.signal,
    });
    if (controller !== activeSearch) return;
    results.append(...page.items.map(resultCard));
    offset += page.items.length;
    searchStatus.textContent = offset ? "" : "Nie znaleziono wyników. Spróbuj wpisać inny temat.";
    loadMore.hidden = !page.more || !page.items.length;
    if (append && page.items.length) {
      results.children[offset - page.items.length].querySelector("button").focus();
    }
  } catch (error) {
    if (controller !== activeSearch) return;
    searchStatus.classList.add("error");
    searchStatus.textContent = error.message;
    loadMore.hidden = !append;
  } finally {
    if (controller === activeSearch) loadMore.disabled = false;
  }
}

byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  void searchKnowledge(searchField.value.trim());
});
loadMore.addEventListener("click", () => void searchKnowledge(activeQuery, true));

function sourceLocation(path, lines) {
  if (!path) return "";
  const numbers = Array.isArray(lines) ? lines.filter(Number.isInteger) : [];
  if (!numbers.length) return path;
  const [first, last] = numbers;
  return !last || first === last ? `${path} · wiersz ${first}` : `${path} · wiersze ${first}–${last}`;
}

function externalSource(value) {
  try {
    const link = new URL(value);
    return ["https:", "http:"].includes(link.protocol) ? link.href : null;
  } catch {
    return null;
  }
}

function renderSource(record) {
  sourceTitle.textContent = record.title || "Źródło";
  sourceContent.replaceChildren();
  const meta = recordMeta(record);
  if (meta) sourceContent.append(element("p", "meta", meta));
  if (record.text) sourceContent.append(element("p", "record-text", record.text));

  const url = externalSource(record.citation_url) || externalSource(record.source_url) || externalSource(record.source_path);
  const location = sourceLocation(record.source_path, record.lines);
  if (location && !externalSource(record.source_path)) {
    sourceContent.append(element("p", "record-location", location));
  }
  if (url) {
    const link = element("a", "external-link", "Otwórz źródło w nowej karcie ↗");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    sourceContent.append(link);
  }

  const refs = (record.game_refs || []).map((ref) => {
    const path = ref.source_path || ref.path;
    const lines = ref.lines || [ref.line];
    return sourceLocation(path, lines);
  }).filter((entry) => entry && entry !== location);
  if (refs.length) {
    const list = element("ul", "reference-list");
    list.append(...[...new Set(refs)].map((ref) => element("li", null, ref)));
    sourceContent.append(element("h3", "record-subtitle", "Powiązane pliki gry"), list);
  }
}

async function openSource(source) {
  activeSource?.abort();
  const controller = new AbortController();
  activeSource = controller;
  renderSource(source);
  if (!sourceDialog.open) sourceDialog.showModal();
  sourceContent.scrollTop = 0;
  if (!source.chunk_id) return;
  try {
    const record = await api(endpoint("record", { id: source.chunk_id }), "Nie udało się wczytać pełnego źródła.", {
      signal: controller.signal,
    });
    if (controller === activeSource) renderSource({ ...source, ...record });
  } catch (error) {
    if (controller === activeSource) sourceContent.append(element("p", "notice error", error.message));
  }
}

sourceDialog.addEventListener("close", () => {
  activeSource?.abort();
  activeSource = null;
});

function showView() {
  const showKnowledge = location.hash === "#wiedza";
  chatView.hidden = showKnowledge;
  knowledgeView.hidden = !showKnowledge;
  byId("chat-nav").setAttribute("aria-current", showKnowledge ? "false" : "page");
  byId("knowledge-nav").setAttribute("aria-current", showKnowledge ? "page" : "false");
  if (showKnowledge && activeQuery === undefined) void searchKnowledge("");
  if (showKnowledge) searchField.focus({ preventScroll: true });
  else questionField.focus({ preventScroll: true });
}

window.addEventListener("hashchange", showView);
showView();
void refreshModel();
