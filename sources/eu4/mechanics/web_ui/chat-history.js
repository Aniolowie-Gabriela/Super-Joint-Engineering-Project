(() => {
  const lastChatKey = "atlas-eu4:last-chat";
  const dateFormat = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short", year: "numeric" });
  const durationFormat = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
  const historyPanel = document.querySelector(".chat-history");
  const historyToggle = byId("toggle-chat-history");
  const historyList = byId("chat-list");
  const historyStatus = byId("chat-history-status");
  const historyRetry = byId("retry-chat-history");
  const chatForm = byId("chat-form");
  const examples = byId("examples");
  const retryChat = byId("retry-chat");
  const removeButton = byId("remove-chat");
  const removeDialog = byId("remove-chat-dialog");
  const removeError = byId("remove-chat-error");
  const confirmRemove = byId("confirm-remove-chat");
  const cancelRemove = byId("cancel-remove-chat");

  const chats = new Map();
  let history = [];
  let historyRequest;
  let draftChat = blankChat();
  let activeChat = draftChat;

  function blankChat(id = null, title = "Nowa rozmowa") {
    return { id, title, messages: [], draft: "", loaded: !id };
  }

  function titleFromQuestion(question) {
    const characters = [...question.replace(/\s+/gu, " ")];
    return characters.length > 72 ? `${characters.slice(0, 71).join("").trimEnd()}…` : characters.join("");
  }

  async function chatRequest(path, fallback, options) {
    let response;
    try {
      response = await fetch(`/api/${path}`, options);
    } catch (error) {
      if (error.name === "AbortError") throw error;
      throw new Error(fallback);
    }
    if (response.status === 204) return null;
    const body = await response.json().catch(() => null);
    if (!response.ok || !body) {
      const error = new Error(typeof body?.detail === "string" ? body.detail : fallback);
      error.status = response.status;
      error.diagnostics = body?.diagnostics;
      throw error;
    }
    return body;
  }

  function chatPath(id) {
    return `chats/${encodeURIComponent(id)}`;
  }

  function rememberChat(id) {
    try {
      if (id) localStorage.setItem(lastChatKey, id);
      else localStorage.removeItem(lastChatKey);
    } catch {
      // Rozmowy są nadal zapisane przez Atlas.
    }
  }

  function lastChat() {
    try {
      return localStorage.getItem(lastChatKey);
    } catch {
      return null;
    }
  }

  function expandHistory(expanded) {
    historyPanel.dataset.expanded = String(expanded);
    historyToggle.setAttribute("aria-expanded", String(expanded));
  }

  function focusQuestion() {
    if (!chatView.hidden && !document.querySelector("dialog[open]") && !questionField.readOnly) {
      questionField.focus({ preventScroll: true });
    }
  }

  function renderHistory() {
    const focusedId = document.activeElement?.dataset.chatId;
    const buttons = history.map(({ id, title, updated_at }) => {
      const button = element("button", "chat-entry");
      button.type = "button";
      button.dataset.chatId = id;
      button.setAttribute("aria-current", id === activeChat.id ? "true" : "false");
      button.append(element("span", null, title));
      const updated = new Date(updated_at);
      if (!Number.isNaN(updated.getTime())) {
        const time = element("time", null, dateFormat.format(updated));
        time.dateTime = updated_at;
        button.append(time);
      }
      button.addEventListener("click", () => {
        expandHistory(false);
        void openChat(id, title, true);
      });
      const item = element("li");
      item.append(button);
      return item;
    });
    historyList.replaceChildren(...buttons);
    if (focusedId) {
      const match = buttons.find((item) => item.firstElementChild.dataset.chatId === focusedId);
      match?.firstElementChild.focus({ preventScroll: true });
    }
  }

  async function loadHistory() {
    historyRequest?.abort();
    const request = new AbortController();
    historyRequest = request;
    historyStatus.classList.remove("error");
    historyStatus.textContent = history.length ? "" : "Wczytuję rozmowy…";
    historyRetry.hidden = true;
    try {
      const { items } = await chatRequest("chats", "Nie udało się wczytać historii rozmów.", { signal: request.signal });
      if (request !== historyRequest) return;
      history = items;
      historyStatus.textContent = items.length ? "" : "Tu pojawią się Twoje rozmowy.";
      renderHistory();
    } catch (error) {
      if (request !== historyRequest) return;
      historyStatus.classList.add("error");
      historyStatus.textContent = error.message;
      historyRetry.hidden = false;
    }
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
        const button = sourceButton(source, `[${number}]`, "citation", true);
        button.setAttribute("aria-label", `Źródło ${number}. ${source.title}`);
        body.append(button);
        cited.add(number);
      }
    }
    body.append(answer.slice(start));
    return { body, cited: [...numbered].filter(([number]) => cited.has(number)) };
  }

  const methodLabels = {
    gemma: "Odpowiedź wygenerowana przez model",
    checked_guide: "Gotowa odpowiedź z poradnika",
    guide_with_gemma: "Gotowa odpowiedź z poradnika wybrana przez model",
    game_trade_route: "Odpowiedź z danych gry",
  };

  const stageLabels = {
    retrieval: "Nie udało się wyszukać źródeł.",
    generation: "Nie udało się przygotować odpowiedzi.",
    model_ready: "Model nie był gotowy.",
    storage: "Nie udało się odczytać albo zapisać rozmowy.",
  };

  function traceSources(diagnostics, failed) {
    const items = new Map();
    const cited = new Set(diagnostics.cited_numbers ?? []);
    function add(source, label) {
      const key = source.chunk_id || JSON.stringify([source.document_id, source.source_path, source.title, source.lines, source.text]);
      if (!items.has(key)) items.set(key, { source, labels: [] });
      const item = items.get(key);
      if (label !== "Znalezione") item.source = source;
      item.labels.push(label);
    }
    for (const source of diagnostics.candidates ?? []) add(source, "Znalezione");
    const available = diagnostics.sources ?? [];
    const supporting = diagnostics.supporting_sources ?? [];
    for (const source of available) add(source, failed ? "Wybrane do odpowiedzi" : "Przekazane do modelu");
    for (const source of supporting) add(source, "Użyte w gotowej odpowiedzi");
    for (const source of [...available, ...supporting]) {
      if (cited.has(source.number)) add(source, "Cytowane");
    }
    return [...items.values()];
  }

  function answerDiagnostics(diagnostics, failed = false) {
    const details = element("details", "answer-diagnostics");
    details.append(element("summary", null, failed ? "Gdzie wystąpił błąd?" : "Jak powstała odpowiedź?"));
    if (!diagnostics) {
      details.append(element("p", "diagnostic-explanation", "Szczegóły tej odpowiedzi nie zostały zapisane."));
      return details;
    }

    const { method, stage, game_version: version, model, seconds, search_terms: terms, retrieval_query: query } = diagnostics;
    const facts = [
      methodLabels[method],
      version && `EU4 ${version}`,
      model && (diagnostics.model_called || diagnostics.retrieval_model_called) && `Model ${model}`,
      Number.isFinite(seconds) && `${durationFormat.format(seconds)} s`,
    ].filter(Boolean);
    if (failed && stageLabels[stage]) details.append(element("p", null, stageLabels[stage]));
    if (facts.length) details.append(element("p", "diagnostic-explanation", facts.join(" · ")));
    if (query) details.append(element("p", "diagnostic-explanation", `Pytanie użyte do wyszukiwania · ${query}`));
    if (terms?.length) details.append(element("p", "diagnostic-explanation", `Słowa wyszukiwania · ${terms.join(", ")}`));

    const status = [];
    if (diagnostics.truncated) status.push("Odpowiedź została ucięta przez limit długości.");
    if ((diagnostics.excluded_count ?? 0) > 0) {
      status.push(`Poza limitem miejsca na źródła · ${diagnostics.excluded_count}.`);
    }
    if (!failed && !diagnostics.sources?.length && !diagnostics.supporting_sources?.length && stage === "completed") {
      status.push(diagnostics.candidates?.length
        ? "Żadne ze znalezionych źródeł nie trafiło do odpowiedzi."
        : "Nie znaleziono źródeł do tego pytania.");
    } else if (!failed && !diagnostics.cited_numbers?.length && !diagnostics.unknown_cited_numbers?.length) {
      status.push("W odpowiedzi nie ma cytatów ze źródeł.");
    }
    if (diagnostics.unknown_cited_numbers?.length) {
      const unknown = diagnostics.unknown_cited_numbers.map((number) => `[${number}]`).join(", ");
      status.push(`Te odsyłacze nie wskazują żadnego źródła: ${unknown}.`);
    }
    for (const note of status) details.append(element("p", null, note));

    const items = traceSources(diagnostics, failed);
    if (items.length) {
      const list = element("ul", "diagnostic-list");
      for (const { source, labels } of items) {
        const item = element("li");
        const title = source.title || "Otwórz źródło";
        const label = source.number ? `[${source.number}] ${title}` : title;
        item.append(sourceButton(source, label, "source-link", true), element("span", "diagnostic-explanation", labels.join(" · ")));
        list.append(item);
      }
      details.append(list);
    }
    return details;
  }

  function appendMessage(kind, label, content) {
    const message = element("article", `message ${kind}`);
    message.append(element("h2", "message-label", label), content);
    conversation.append(message);
    return message;
  }

  function appendExchange(exchange) {
    appendMessage("player", "Twoje pytanie", element("p", null, exchange.question));
    const { body, cited } = answerBody(exchange.answer, exchange.sources ?? []);
    const message = appendMessage("atlas", "Atlas EU4", body);
    if (cited.length) {
      const sourceList = element("div", "source-list");
      sourceList.append(element("span", "source-label", "Cytowane źródła"));
      for (const [number, source] of cited) {
        sourceList.append(sourceButton(source, `[${number}] ${source.title}`, "source-link", true));
      }
      message.append(sourceList);
    }
    message.append(answerDiagnostics(exchange.diagnostics));
    return message;
  }

  function renderComposer() {
    const chat = activeChat;
    questionField.readOnly = Boolean(chat.pending || chat.loading || chat.loadError || chat.missing);
    questionError.textContent = chat.loadError || chat.sendError || "";
    questionError.hidden = !questionError.textContent;
    retryChat.hidden = !chat.loadError && !chat.missing;
    retryChat.textContent = chat.missing ? "Rozpocznij nową rozmowę" : "Wczytaj rozmowę";
    byId("chat-waiting").hidden = !sending || Boolean(chat.pending);
    byId("current-chat").hidden = !chat.id;
    byId("current-chat-title").textContent = chat.title;
    removeButton.hidden = !chat.loaded || Boolean(chat.missing);
    removeButton.disabled = Boolean(chat.pending);
    examples.hidden = Boolean(chat.id || chat.pending || chat.sendError || chat.messages.length);
    updateSendButton();
  }

  function renderConversation() {
    const chat = activeChat;
    conversation.setAttribute("aria-busy", "true");
    conversation.replaceChildren();
    for (const message of chat.messages) appendExchange(message);
    if (chat.loading) appendMessage("atlas", "Atlas EU4", element("p", "working", "Wczytuję rozmowę…"));
    if (chat.pending) {
      appendMessage("player", "Twoje pytanie", element("p", null, chat.pending));
      appendMessage("atlas", "Atlas EU4", element("p", "working", "Szukam odpowiedzi…"));
    } else if (chat.failureDiagnostics) {
      appendMessage("atlas", "Atlas EU4", answerDiagnostics(chat.failureDiagnostics, true));
    }
    conversation.removeAttribute("aria-busy");
    conversation.scrollTop = conversation.scrollHeight;
    questionField.value = chat.draft;
    renderComposer();
  }

  function selectChat(chat) {
    activeChat.draft = questionField.value;
    activeChat = chat;
    rememberChat(chat.id);
    renderConversation();
    renderHistory();
  }

  async function loadChat(chat) {
    chat.loading = true;
    chat.loadError = "";
    if (activeChat === chat) renderConversation();
    try {
      const saved = await chatRequest(chatPath(chat.id), "Nie udało się wczytać rozmowy.");
      chat.title = saved.title;
      chat.messages = saved.messages;
      chat.loaded = true;
      chat.missing = false;
    } catch (error) {
      chat.loadError = error.message;
      if (error.status === 404) {
        chat.missing = true;
        if (activeChat === chat) rememberChat(null);
        void loadHistory();
      }
    } finally {
      chat.loading = false;
      if (activeChat === chat) renderConversation();
    }
  }

  async function openChat(id, title, focus = false) {
    if (!chats.has(id)) chats.set(id, blankChat(id, title));
    const chat = chats.get(id);
    selectChat(chat);
    if ((!chat.loaded || chat.loadError) && !chat.loading) await loadChat(chat);
    if (focus && activeChat === chat) {
      if (chat.loadError) retryChat.focus({ preventScroll: true });
      else focusQuestion();
    }
  }

  function openDraft() {
    expandHistory(false);
    selectChat(draftChat);
    focusQuestion();
  }

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = questionField.value.trim();
    if (!question || sendQuestion.disabled) return;
    const chat = activeChat;
    chat.draft = questionField.value;
    chat.pending = question;
    chat.sendError = "";
    chat.failureDiagnostics = null;
    sending = true;
    renderConversation();

    try {
      const request = { question };
      if (chat.id) {
        request.chat_id = chat.id;
        request.expected_message_id = chat.messages.at(-1)?.id;
      }
      const exchange = await chatRequest("chat", "Nie udało się uzyskać odpowiedzi.", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      chat.messages.push({ ...exchange, question, id: exchange.message_id });
      chat.draft = "";
      if (!chat.id) {
        chat.id = exchange.chat_id;
        chat.title = exchange.title || titleFromQuestion(question);
        chats.set(chat.id, chat);
        draftChat = blankChat();
        if (activeChat === chat) rememberChat(chat.id);
      }
      void loadHistory();
    } catch (error) {
      chat.sendError = /spróbuj|ponownie/i.test(error.message) ? error.message : `${error.message} Wyślij pytanie ponownie.`;
      chat.failureDiagnostics = error.diagnostics;
      if (error.status === 404 && chat.id) {
        chat.sendError = error.message;
        chat.missing = true;
        if (activeChat === chat) rememberChat(null);
        void loadHistory();
      }
      if (error.status === 409 && chat.id) {
        chat.sendError = `${error.message} Sprawdź ostatnią odpowiedź i wyślij pytanie ponownie.`;
        chat.failureDiagnostics = null;
        void loadChat(chat);
        void loadHistory();
      }
      if (!preparing) void refreshModel();
    } finally {
      chat.pending = "";
      sending = false;
      if (activeChat === chat) {
        renderConversation();
        if (!chat.sendError) conversation.scrollTop = conversation.lastElementChild.offsetTop;
        focusQuestion();
      } else {
        renderComposer();
      }
    }
  });

  questionField.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!sendQuestion.disabled) chatForm.requestSubmit();
    }
  });
  questionField.addEventListener("input", updateSendButton);
  examples.addEventListener("click", (event) => {
    const question = event.target.closest("button")?.dataset.question;
    if (!question || questionField.readOnly) return;
    questionField.value = question;
    updateSendButton();
    focusQuestion();
  });

  byId("new-chat").addEventListener("click", openDraft);
  historyToggle.addEventListener("click", () => expandHistory(historyPanel.dataset.expanded !== "true"));
  historyRetry.addEventListener("click", () => void loadHistory());
  retryChat.addEventListener("click", () => {
    if (activeChat.missing) {
      const question = questionField.value;
      openDraft();
      if (question && !questionField.value) {
        questionField.value = question;
        updateSendButton();
      }
    } else {
      void openChat(activeChat.id, activeChat.title, true);
    }
  });

  removeButton.addEventListener("click", () => {
    byId("remove-chat-prompt").textContent = `Rozmowa „${activeChat.title}” zniknie z historii.`;
    removeError.textContent = "";
    removeDialog.showModal();
  });

  removeDialog.addEventListener("cancel", (event) => {
    if (confirmRemove.disabled) event.preventDefault();
  });

  confirmRemove.addEventListener("click", async () => {
    const chat = activeChat;
    confirmRemove.disabled = true;
    cancelRemove.disabled = true;
    removeError.textContent = "";
    try {
      await chatRequest(chatPath(chat.id), "Nie udało się usunąć rozmowy.", { method: "DELETE" });
      chats.delete(chat.id);
      history = history.filter(({ id }) => id !== chat.id);
      removeDialog.close();
      openDraft();
      void loadHistory();
    } catch (error) {
      removeError.textContent = `${error.message} Spróbuj ponownie.`;
    } finally {
      confirmRemove.disabled = false;
      cancelRemove.disabled = false;
      if (removeDialog.open) confirmRemove.focus();
    }
  });

  const rememberedId = lastChat();
  if (rememberedId) void openChat(rememberedId, "Rozmowa");
  void loadHistory();
})();
