function pad(num) {
  return String(num).padStart(2, "0");
}

function formatDate(d) {
  const y = d.getFullYear();
  const m = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  return `${y}-${m}-${day}`;
}

window.setQuickRange = function setQuickRange(type) {
  const fromInput = document.querySelector('input[name="date_from"]');
  const toInput = document.querySelector('input[name="date_to"]');
  if (!fromInput || !toInput) return;

  const now = new Date();
  let fromDate = null;
  let toDate = null;

  if (type === "today") {
    fromDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    toDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }
  if (type === "this_month") {
    fromDate = new Date(now.getFullYear(), now.getMonth(), 1);
    toDate = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  }
  if (type === "last_month") {
    fromDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    toDate = new Date(now.getFullYear(), now.getMonth(), 0);
  }
  if (type === "this_year") {
    fromDate = new Date(now.getFullYear(), 0, 1);
    toDate = new Date(now.getFullYear(), 11, 31);
  }

  if (fromDate && toDate) {
    fromInput.value = formatDate(fromDate);
    toInput.value = formatDate(toDate);
    fromInput.form.submit();
  }
};

(() => {
  const batchPrintForm = document.getElementById("batch-print-form");
  if (batchPrintForm) {
    const selectAllPrint = document.getElementById("select-all-print");
    const batchPrintBtn = document.getElementById("batch-print-btn");
    const batchPrintHint = document.getElementById("batch-print-hint");
    const checkboxes = Array.from(document.querySelectorAll(".print-order-checkbox"));

    function getSelectedOrderIds() {
      return new Set(checkboxes.filter((item) => item.checked).map((item) => item.value));
    }

    function updateBatchPrintState() {
      const selectedCount = getSelectedOrderIds().size;
      batchPrintBtn.disabled = selectedCount === 0;
      batchPrintHint.textContent = selectedCount
        ? `已选择 ${selectedCount} 单，提交后会生成 A4 三联出货单。`
        : "请选择要打印 A4 三联出货单的订单。";
    }

    selectAllPrint.addEventListener("click", () => {
      const shouldCheck = checkboxes.some((item) => !item.checked);
      checkboxes.forEach((item) => {
        item.checked = shouldCheck;
      });
      updateBatchPrintState();
    });

    checkboxes.forEach((item) => item.addEventListener("change", updateBatchPrintState));
    updateBatchPrintState();
  }

  const queryVoiceModal = document.getElementById("queryVoiceModal");
  const openQueryButton = document.getElementById("open-query-voice-modal");
  if (!queryVoiceModal || !openQueryButton) return;

  openQueryButton.addEventListener("click", () => {
    queryVoiceModal.hidden = false;
  });
  document.querySelectorAll("[data-close-query-modal]").forEach((item) => {
    item.addEventListener("click", () => {
      queryVoiceModal.hidden = true;
    });
  });

  const queryFieldMap = {
    keyword: "filter-keyword",
    payment_status: "filter-payment-status",
    production_status: "filter-production-status",
    print_status: "filter-print-status",
    date_from: "filter-date-from",
    date_to: "filter-date-to",
    sort_by: "filter-sort-by",
  };

  const queryLabels = {
    keyword: "关键词",
    payment_status: "付款状态",
    production_status: "生产状态",
    print_status: "打印状态",
    date_from: "开始日期",
    date_to: "结束日期",
    sort_by: "排序",
  };

  const sortLabels = {
    priority_due: "默认：优先级+截至日期",
    payment_first: "未结款优先",
    order_new: "订单号：新到旧",
    order_old: "订单号：旧到新",
    customer: "客户名",
    item: "商品名",
    amount_desc: "总金额：高到低",
    amount_asc: "总金额：低到高",
    unpaid_desc: "待结金额：高到低",
  };

  function renderQueryDraft(data) {
    const pendingQueryDraft = data.draft || {};
    const fields = document.getElementById("query-draft-fields");
    const entries = Object.entries(queryLabels).map(([key, label]) => {
      let value = pendingQueryDraft[key] || "不限";
      if (key === "sort_by") value = sortLabels[pendingQueryDraft[key]] || "默认：优先级+截至日期";
      return `<span><strong>${label}</strong>${value}</span>`;
    });
    fields.innerHTML = entries.join("");

    const message = document.getElementById("query-draft-message");
    const issueText = data.issues && data.issues.length ? `执行时有提示：${data.issues.join("；")}` : "已执行只读筛选，不会修改任何订单。";
    const confidenceText = data.confidence !== undefined ? ` 置信度：${Math.round(data.confidence * 100)}%` : "";
    message.textContent = `${issueText} 来源：${data.source_model}${confidenceText}`;
    document.getElementById("query-draft-card").hidden = false;
  }

  function submitQueryDraft(draft) {
    Object.entries(queryFieldMap).forEach(([key, id]) => {
      const el = document.getElementById(id);
      if (el) el.value = draft[key] || "";
    });
    document.getElementById("order-filter-form").submit();
  }

  async function parseQueryVoiceText() {
    const input = document.getElementById("query-voice-text");
    const status = document.getElementById("query-voice-status");
    const text = input.value.trim();
    if (!text) {
      status.textContent = "先说一句或输入一段查询条件。";
      return;
    }

    status.textContent = "正在生成查询草稿...";
    const resp = await fetch("/api/voice-order-query-draft", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text}),
    });
    const data = await resp.json();
    if (!data.ok) {
      status.textContent = data.message || "查询解析失败";
      return;
    }
    renderQueryDraft(data);
    status.textContent = "已解析，正在执行筛选。";
    submitQueryDraft(data.draft || {});
  }

  function setupQueryVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const voiceBtn = document.getElementById("query-voice-btn");
    const status = document.getElementById("query-voice-status");
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
      document.getElementById("query-voice-text").value = text;
      status.textContent = "已识别，正在生成查询草稿。";
      parseQueryVoiceText();
    });

    recognition.addEventListener("end", () => {
      voiceBtn.classList.remove("recording");
    });

    recognition.addEventListener("error", (event) => {
      voiceBtn.classList.remove("recording");
      status.textContent = `语音识别失败：${event.error || "请重试"}`;
    });
  }

  document.getElementById("parse-query-text-btn").addEventListener("click", parseQueryVoiceText);
  document.getElementById("clear-query-draft-btn").addEventListener("click", () => {
    document.getElementById("query-voice-text").value = "";
    document.getElementById("query-draft-card").hidden = true;
    document.getElementById("query-voice-status").textContent = "点麦克风说查询条件，识别后会直接执行筛选。";
  });
  setupQueryVoiceInput();
})();
