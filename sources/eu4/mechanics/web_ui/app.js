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
  if (response.status === 204) return;
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
  sendQuestion.disabled = !modelReady || sending || questionField.readOnly || !questionField.value.trim();
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

function sourceButton(source, label, className, snapshot = false) {
  const button = element("button", className, label);
  button.type = "button";
  button.addEventListener("click", () => openSource(source, snapshot));
  return button;
}

function recordMeta(record) {
  if (record.source_type === "user_source") return "Własne źródło";
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

async function openSource(source, snapshot = false) {
  activeSource?.abort();
  const controller = new AbortController();
  activeSource = controller;
  renderSource(source);
  if (!sourceDialog.open) sourceDialog.showModal();
  sourceContent.scrollTop = 0;
  if (snapshot || !source.chunk_id) return;
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

const ownedDialog = byId("owned-dialog");
const ownedStatus = byId("owned-status");
const ownedEmpty = byId("owned-empty");
const ownedList = byId("owned-list");
const ownedEditor = byId("owned-editor");
const ownedName = byId("owned-name");
const ownedText = byId("owned-text");
const ownedUrl = byId("owned-url");
const sourceFile = byId("source-file");
const sourceSiteUrl = byId("source-site-url");
const sourceSiteForm = byId("source-site-form");
const importModes = byId("import-modes");
const saveOwned = byId("save-owned");
const retryOwned = byId("retry-owned");
const closeOwned = byId("close-owned");
const backOwnedEdit = byId("back-owned-edit");
const backOwnedDelete = byId("back-owned-delete");
const deleteOwned = byId("delete-owned");
const addOwned = byId("add-owned");
const previewSource = byId("preview-source");

let selectedOwned;
let ownedRequest;
let importMode = "paste";
let loadedImport = false;
let manualDraft = {};

function setOwnedStatus(message, error = false) {
  ownedStatus.textContent = message;
  ownedStatus.classList.toggle("error", error);
  if (error) ownedStatus.focus();
}

function showOwnedView(view, title) {
  for (const name of ["list", "edit", "delete"]) {
    byId(`owned-${name}-view`).hidden = name !== view;
  }
  byId("owned-title").textContent = title;
  ownedDialog.querySelector(".owned-content").scrollTop = 0;
}

function cancelOwnedRequest() {
  if (ownedRequest?.locked) return false;
  ownedRequest?.controller.abort();
  ownedRequest = undefined;
  return true;
}

function updateOwnedControls() {
  const busy = Boolean(ownedRequest);
  const locked = Boolean(ownedRequest?.locked);
  for (const button of [closeOwned, backOwnedEdit, backOwnedDelete]) button.disabled = locked;
  for (const control of [importModes, sourceFile, previewSource, saveOwned, deleteOwned]) control.disabled = busy;
  for (const field of [sourceSiteUrl, ownedName, ownedText, ownedUrl]) field.readOnly = busy;
}

async function runOwnedRequest(message, task, onSuccess, { locked = false, onFailure } = {}) {
  if (!cancelOwnedRequest()) return;
  const request = { controller: new AbortController(), locked };
  ownedRequest = request;
  updateOwnedControls();
  setOwnedStatus(message);
  let result;
  try {
    result = await task(request.controller.signal);
  } catch (error) {
    if (request !== ownedRequest) return;
    ownedRequest = undefined;
    updateOwnedControls();
    setOwnedStatus(error.message, true);
    onFailure?.();
    return;
  }
  if (request !== ownedRequest) return;
  ownedRequest = undefined;
  updateOwnedControls();
  onSuccess(result);
}

function jsonRequest(method, body, signal) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  };
}

function ownedPath(item) {
  return item ? `sources/${encodeURIComponent(item.id)}` : "sources";
}

function ownedAction(label, item, handler) {
  const button = element("button", "button secondary compact", label);
  button.type = "button";
  button.setAttribute("aria-label", `${label} źródło „${item.title}”`);
  button.addEventListener("click", () => handler(item));
  return button;
}

function ownedRow(item) {
  const row = element("li");
  const name = element("strong", null, item.title);
  const actions = element("div", "owned-row-actions");
  actions.append(ownedAction("Popraw", item, editOwnedSource), ownedAction("Usuń", item, confirmOwnedDelete));
  row.append(name, actions);
  return row;
}

function showOwnedList(message = "") {
  showOwnedView("list", "Moje źródła");
  ownedEmpty.hidden = true;
  retryOwned.hidden = true;
  ownedList.replaceChildren();
  addOwned.focus();
  void runOwnedRequest(message || "Wczytuję źródła…",
    (signal) => api("sources", "Nie udało się wczytać źródeł.", { signal }),
    ({ items }) => {
      ownedList.append(...items.map(ownedRow));
      ownedEmpty.hidden = items.length > 0;
      setOwnedStatus(message);
    },
    { onFailure: () => { retryOwned.hidden = false; } }
  );
}

function updateImportView() {
  const showFile = !selectedOwned && importMode === "file";
  const showPage = !selectedOwned && importMode === "site";
  byId("source-file-view").hidden = !showFile;
  sourceSiteForm.hidden = !showPage;
  ownedEditor.hidden = (showFile || showPage) && !loadedImport;
  saveOwned.hidden = ownedEditor.hidden;
}

function fillOwnedEditor(record) {
  ownedName.value = record.title || "";
  ownedText.value = record.text || "";
  ownedUrl.value = record.url || "";
}

function readOwnedEditor() {
  return { title: ownedName.value, text: ownedText.value, url: ownedUrl.value };
}

function invalidateOwnedImport() {
  if (loadedImport) fillOwnedEditor({});
  loadedImport = false;
  setOwnedStatus("");
  updateImportView();
}

function showOwnedEditor(item) {
  selectedOwned = item;
  importMode = "paste";
  loadedImport = false;
  manualDraft = {};
  fillOwnedEditor(item || {});
  sourceFile.value = "";
  sourceSiteUrl.value = "";
  importModes.hidden = Boolean(item);
  importModes.querySelector('[value="paste"]').checked = true;
  updateImportView();
  setOwnedStatus("");
  showOwnedView("edit", item ? "Popraw źródło" : "Dodaj źródło");
  ownedName.focus();
}

function editOwnedSource(item) {
  void runOwnedRequest("Wczytuję źródło…",
    (signal) => api(ownedPath(item), "Nie udało się wczytać źródła. Spróbuj ponownie.", { signal }),
    showOwnedEditor
  );
}

function confirmOwnedDelete(item) {
  if (!cancelOwnedRequest()) return;
  updateOwnedControls();
  selectedOwned = item;
  setOwnedStatus("");
  byId("owned-delete-prompt").textContent = `Czy usunąć na zawsze „${item.title}”?`;
  showOwnedView("delete", "Usuń źródło");
  backOwnedDelete.focus();
}

function acceptOwnedImport(record, message) {
  loadedImport = true;
  fillOwnedEditor(record);
  updateImportView();
  setOwnedStatus(message);
  ownedName.focus();
}

byId("open-owned-sources").addEventListener("click", () => {
  ownedDialog.showModal();
  showOwnedList();
});
closeOwned.addEventListener("click", () => ownedDialog.close());
ownedDialog.addEventListener("cancel", (event) => {
  if (ownedRequest?.locked) event.preventDefault();
});
ownedDialog.addEventListener("close", () => {
  cancelOwnedRequest();
  updateOwnedControls();
});
retryOwned.addEventListener("click", () => showOwnedList());
backOwnedEdit.addEventListener("click", () => showOwnedList());
backOwnedDelete.addEventListener("click", () => showOwnedList());
addOwned.addEventListener("click", () => {
  if (!cancelOwnedRequest()) return;
  updateOwnedControls();
  showOwnedEditor();
});
importModes.addEventListener("change", () => {
  if (importMode === "paste") manualDraft = readOwnedEditor();
  importMode = importModes.querySelector(":checked").value;
  invalidateOwnedImport();
  if (importMode === "paste") fillOwnedEditor(manualDraft);
});

sourceFile.addEventListener("change", () => {
  const file = sourceFile.files[0];
  sourceFile.value = "";
  if (!file) return;
  invalidateOwnedImport();
  void runOwnedRequest("Wczytuję plik…", async () => {
    if (!/\.(txt|md)$/i.test(file.name)) throw new Error("Wybierz plik z rozszerzeniem TXT lub MD.");
    if (file.size > ownedText.maxLength * 4 + 3) {
      throw new Error("Plik jest za długi. Wybierz plik do miliona znaków.");
    }
    let text;
    try {
      const buffer = await file.arrayBuffer();
      text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
    } catch {
      throw new Error("Zapisz plik w kodowaniu UTF-8 i wybierz go ponownie.");
    }
    if (!text.trim()) throw new Error("Plik jest pusty. Wybierz plik z treścią.");
    if (text.length > ownedText.maxLength) throw new Error("Plik jest za długi. Wybierz plik do miliona znaków.");
    return { title: file.name.replace(/\.(txt|md)$/i, "").slice(0, ownedName.maxLength), text };
  }, (record) => acceptOwnedImport(record, "Wczytano treść z pliku. Sprawdź ją przed zapisaniem."));
});

sourceSiteUrl.addEventListener("input", invalidateOwnedImport);

sourceSiteForm.addEventListener("submit", (event) => {
  event.preventDefault();
  invalidateOwnedImport();
  const url = externalSource(sourceSiteUrl.value.trim());
  if (!url) {
    setOwnedStatus("Wpisz adres strony zaczynający się od https:// lub http://.", true);
    return;
  }
  void runOwnedRequest("Pobieram treść strony…",
    (signal) => api("sources/preview", "Nie udało się pobrać strony. Sprawdź adres i spróbuj ponownie.",
      jsonRequest("POST", { url }, signal)),
    (record) => acceptOwnedImport(record, "To podgląd treści strony. Możesz ją poprawić przed zapisaniem.")
  );
});

ownedEditor.addEventListener("submit", (event) => {
  event.preventDefault();
  if (ownedRequest || ownedEditor.hidden) return;
  const draft = readOwnedEditor();
  const title = draft.title.trim();
  const text = draft.text.trim();
  const url = draft.url.trim();
  if (!title || !text) {
    setOwnedStatus("Wpisz tytuł i treść źródła.", true);
    return;
  }
  if (url && !externalSource(url)) {
    setOwnedStatus("Link do pochodzenia powinien zaczynać się od https:// lub http://.", true);
    return;
  }
  const path = ownedPath(selectedOwned);
  const method = selectedOwned ? "PUT" : "POST";
  void runOwnedRequest("Zapisuję źródło…",
    (signal) => api(path, "Nie udało się zapisać źródła. Spróbuj ponownie.",
      jsonRequest(method, { title, text, url: url || null }, signal)),
    () => {
      showOwnedList("Zapisano źródło.");
      if (!knowledgeView.hidden) void searchKnowledge(activeQuery ?? "");
    },
    { locked: true }
  );
});

deleteOwned.addEventListener("click", () => {
  const path = ownedPath(selectedOwned);
  void runOwnedRequest("Usuwam źródło…",
    (signal) => api(path, "Nie udało się usunąć źródła. Spróbuj ponownie.", { method: "DELETE", signal }),
    () => {
      showOwnedList("Usunięto źródło.");
      if (!knowledgeView.hidden) void searchKnowledge(activeQuery ?? "");
    },
    { locked: true }
  );
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
