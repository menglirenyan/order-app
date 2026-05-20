async function bindSuggest(inputId, boxId, fieldName) {
  const input = document.getElementById(inputId);
  const box = document.getElementById(boxId);
  if (!input || !box) return;

  async function fetchSuggestions() {
    const q = input.value.trim();
    const resp = await fetch(`/api/suggest?field=${fieldName}&q=${encodeURIComponent(q)}`);
    const data = await resp.json();
    const items = data.items || [];

    if (!items.length) {
      box.innerHTML = "";
      box.style.display = "none";
      return;
    }

    box.innerHTML = items.map((item) => `<button type="button" class="suggest-item">${item}</button>`).join("");
    box.style.display = "block";

    box.querySelectorAll(".suggest-item").forEach((btn) => {
      btn.addEventListener("click", () => {
        input.value = btn.textContent;
        box.innerHTML = "";
        box.style.display = "none";
        input.focus();
      });
    });
  }

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(fetchSuggestions, 120);
  });

  input.addEventListener("blur", () => {
    setTimeout(() => {
      box.style.display = "none";
    }, 150);
  });

  input.addEventListener("focus", fetchSuggestions);
}

const fieldMap = {
  customer: "customer-input",
  phone: "phone-input",
  item_name: "item-input",
  size: "size-input",
  quantity: "quantity-input",
  unit_price: "unit-price-input",
  paid_amount: "paid-amount-input",
  priority_color: "priority-input",
  due_date: "due-date-input",
  remark: "remark-input",
};

function updateAmountPreview() {
  const quantityInput = document.getElementById("quantity-input");
  const unitPriceInput = document.getElementById("unit-price-input");
  const preview = document.getElementById("amount-preview");
  if (!quantityInput || !unitPriceInput || !preview) return;
  const quantity = Number(quantityInput.value || 0);
  const unitPrice = Number(unitPriceInput.value || 0);
  preview.textContent = `合计 ${(quantity * unitPrice).toFixed(2)}`;
}

function applyDraft(draft) {
  Object.entries(fieldMap).forEach(([key, id]) => {
    const el = document.getElementById(id);
    if (el && draft[key] !== undefined && draft[key] !== null && draft[key] !== "") {
      el.value = draft[key];
    }
  });
  updateAmountPreview();
}

async function fillRecentPriceIfNeeded() {
  const itemInput = document.getElementById("item-input");
  const sizeInput = document.getElementById("size-input");
  const unitPriceInput = document.getElementById("unit-price-input");
  if (!itemInput || !sizeInput || !unitPriceInput) return;

  const itemName = itemInput.value.trim();
  const size = sizeInput.value.trim();
  if (!itemName || Number(unitPriceInput.value || 0) > 0) return;

  const resp = await fetch(`/api/recent-price?item_name=${encodeURIComponent(itemName)}&size=${encodeURIComponent(size)}`);
  const data = await resp.json();
  if (data.ok && data.unit_price) {
    unitPriceInput.value = data.unit_price;
    updateAmountPreview();
    const message = document.getElementById("draft-message");
    if (message) {
      message.hidden = false;
      message.textContent = `已按历史订单 ${data.order_no} 带入最近单价，可修改。`;
    }
  }
}

(() => {
  bindSuggest("customer-input", "customer-suggest", "customer");
  bindSuggest("item-input", "item-suggest", "item_name");
  bindSuggest("size-input", "size-suggest", "size");

  document.getElementById("quantity-input")?.addEventListener("input", updateAmountPreview);
  document.getElementById("unit-price-input")?.addEventListener("input", updateAmountPreview);
  document.getElementById("item-input")?.addEventListener("blur", fillRecentPriceIfNeeded);
  document.getElementById("size-input")?.addEventListener("blur", fillRecentPriceIfNeeded);

  updateAmountPreview();
})();
