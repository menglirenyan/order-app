function formatValue(value) {
  if (value === undefined || value === null || value === "") return "未识别";
  return value;
}

function renderDraftCards(orders, topIssues, forceReview = false) {
  const list = document.getElementById("draft-list");
  if (!list) return;
  if (!orders || (!forceReview && orders.length <= 1)) {
    list.hidden = true;
    list.innerHTML = "";
    return;
  }

  list.innerHTML = orders.map((entry, index) => {
    const draft = entry.draft || {};
    const issues = entry.issues || [];
    const issueHtml = issues.length ? `<div class="draft-issues">${issues.join("；")}</div>` : "";
    return `
      <div class="draft-card">
        <div class="draft-card-head">
          <strong>草稿 ${index + 1}</strong>
          <button class="btn-secondary draft-apply-btn" type="button" data-index="${index}">填入这一单</button>
        </div>
        <div class="draft-fields">
          <span class="${draft.customer ? "" : "missing"}">客户：${formatValue(draft.customer)}</span>
          <span>类型：${formatValue(draft.order_type || "瓦楞板")}</span>
          <span class="${draft.item_name ? "" : "missing"}">内容：${formatValue(draft.item_name)}</span>
          <span>尺寸：${formatValue(draft.size)}</span>
          <span class="${draft.quantity > 0 ? "" : "missing"}">数量：${formatValue(draft.quantity)}</span>
          <span class="${draft.unit_price > 0 ? "" : "missing"}">单价：${formatValue(draft.unit_price)}</span>
          <span>已收：${formatValue(draft.paid_amount)}</span>
        </div>
        ${issueHtml}
      </div>
    `;
  }).join("");
  list.hidden = false;
  list.querySelectorAll(".draft-apply-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const entry = orders[Number(btn.dataset.index)];
      if (entry && entry.draft) {
        applyDraft(entry.draft);
        const message = document.getElementById("draft-message");
        message.hidden = false;
        message.textContent = "已填入选中的草稿，可以继续修改后提交。";
      }
    });
  });
}

async function parseVoiceText() {
  const voiceText = document.getElementById("voice-text");
  const message = document.getElementById("draft-message");
  if (!voiceText || !message) return;
  const text = voiceText.value.trim();
  if (!text) {
    message.hidden = false;
    message.textContent = "先说一句或输入一段订单内容。";
    return;
  }

  message.hidden = false;
  message.textContent = "正在生成草稿...";
  const resp = await fetch("/api/voice-order-draft", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({text}),
  });
  const data = await resp.json();
  if (!data.ok) {
    message.textContent = data.message || "解析失败";
    return;
  }

  const orders = data.orders || (data.draft ? [{draft: data.draft, issues: data.issues || []}] : []);
  const needsReview = Boolean(data.needs_review || data.confidence < 0.65 || (data.issues && data.issues.length));
  if (orders.length && !needsReview) {
    applyDraft(orders[0].draft);
  }
  renderDraftCards(orders, data.issues || [], needsReview);
  const issueText = needsReview
    ? `请先核对草稿，确认无误后点击“填入这一单”。${data.issues && data.issues.length ? ` 提示：${data.issues.join("；")}` : ""}`
    : "已自动填入表单，可以继续修改后提交。";
  const confidenceText = data.confidence !== undefined ? ` 置信度：${Math.round(data.confidence * 100)}%` : "";
  message.textContent = `${issueText} 来源：${data.source_model}${confidenceText}`;
}

function setupVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceBtn = document.getElementById("voice-btn");
  const status = document.getElementById("voice-status");
  if (!voiceBtn || !status) return;
  if (!SpeechRecognition) {
    status.textContent = "当前浏览器不支持语音识别，可以直接输入文字后解析。";
    voiceBtn.disabled = true;
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "zh-CN";
  recognition.interimResults = false;
  recognition.continuous = false;

  voiceBtn.addEventListener("click", () => {
    status.textContent = "正在听...";
    voiceBtn.classList.add("recording");
    recognition.start();
  });

  recognition.addEventListener("result", (event) => {
    const text = Array.from(event.results).map((result) => result[0].transcript).join("");
    document.getElementById("voice-text").value = text;
    status.textContent = "已识别，正在生成草稿。";
    parseVoiceText();
  });

  recognition.addEventListener("end", () => {
    voiceBtn.classList.remove("recording");
    if (status.textContent === "正在听...") {
      status.textContent = "语音已结束。";
    }
  });

  recognition.addEventListener("error", (event) => {
    voiceBtn.classList.remove("recording");
    status.textContent = `语音识别失败：${event.error || "请重试"}`;
  });
}

(() => {
  let deferredInstallPrompt = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    const installButton = document.getElementById("install-app-btn");
    if (!installButton) return;
    event.preventDefault();
    deferredInstallPrompt = event;
    installButton.hidden = false;
  });

  document.getElementById("install-app-btn")?.addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    document.getElementById("install-app-btn").hidden = true;
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js");
  }

  const voiceModal = document.getElementById("voiceModal");
  document.getElementById("open-voice-modal")?.addEventListener("click", () => {
    voiceModal.hidden = false;
  });
  document.querySelectorAll("[data-close-voice-modal]").forEach((item) => {
    item.addEventListener("click", () => {
      voiceModal.hidden = true;
    });
  });

  document.getElementById("parse-text-btn")?.addEventListener("click", parseVoiceText);
  document.getElementById("clear-draft-btn")?.addEventListener("click", () => {
    document.getElementById("voice-text").value = "";
    document.getElementById("draft-message").hidden = true;
    document.getElementById("draft-list").hidden = true;
  });
  setupVoiceInput();
})();
