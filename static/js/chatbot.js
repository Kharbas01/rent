/* Floating AI assistant widget. Loaded only on authenticated pages. */
(function () {
  const fab = document.getElementById("aiChatToggle");
  const panel = document.getElementById("aiChatPanel");
  if (!fab || !panel) return; // not present on this page (e.g. login)

  const messagesEl = document.getElementById("aiChatMessages");
  const form = document.getElementById("aiChatForm");
  const input = document.getElementById("aiChatInput");
  const closeBtn = document.getElementById("aiChatClose");
  const themeBtn = document.getElementById("aiChatThemeToggle");
  const suggestionsEl = document.getElementById("aiChatSuggestions");
  const statusEl = document.getElementById("aiChatStatus");

  let history = []; // { role: 'user' | 'ai', text }
  let sending = false;

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function avatar(role) {
    return role === "user" ? "&#128100;" : "&#129302;";
  }

  function renderMessage(role, text) {
    const row = document.createElement("div");
    row.className = "ai-msg-row ai-msg-" + role;
    row.innerHTML =
      '<span class="ai-msg-avatar" aria-hidden="true">' + avatar(role) + "</span>" +
      '<div class="ai-msg-bubble"></div>';
    row.querySelector(".ai-msg-bubble").textContent = text; // textContent: never render HTML from replies
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function renderTyping() {
    const row = document.createElement("div");
    row.className = "ai-msg-row ai-msg-ai ai-msg-typing";
    row.id = "aiTypingRow";
    row.innerHTML =
      '<span class="ai-msg-avatar" aria-hidden="true">&#129302;</span>' +
      '<div class="ai-msg-bubble"><span class="ai-typing-dot"></span><span class="ai-typing-dot"></span><span class="ai-typing-dot"></span></div>';
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function removeTyping() {
    const row = document.getElementById("aiTypingRow");
    if (row) row.remove();
  }

  function openPanel() {
    panel.hidden = false;
    fab.setAttribute("aria-expanded", "true");
    if (!history.length) {
      renderMessage("ai", "Hi! I'm your rent management assistant. Ask me anything about rent, tenants, properties or payments.");
    }
    setTimeout(() => input.focus(), 50);
  }

  function closePanel() {
    panel.hidden = true;
    fab.setAttribute("aria-expanded", "false");
  }

  fab.addEventListener("click", () => (panel.hidden ? openPanel() : closePanel()));
  closeBtn.addEventListener("click", closePanel);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) closePanel();
  });

  if (themeBtn && window.Theme) {
    themeBtn.addEventListener("click", () => window.Theme.toggle());
  }

  async function send(text) {
    if (!text.trim() || sending) return;
    sending = true;
    renderMessage("user", text);
    history.push({ role: "user", text });
    input.value = "";
    suggestionsEl.hidden = true;
    statusEl.textContent = "Typing…";
    renderTyping();

    try {
      const data = await API.post("/api/chatbot/message", { message: text });
      removeTyping();
      renderMessage("ai", data.reply);
      history.push({ role: "ai", text: data.reply });
    } catch (err) {
      removeTyping();
      renderMessage("ai", "Sorry, something went wrong. Please try again.");
    } finally {
      statusEl.textContent = "Online";
      sending = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(input.value);
  });

  suggestionsEl.querySelectorAll(".ai-chip").forEach((chip) => {
    chip.addEventListener("click", () => send(chip.textContent));
  });
})();
