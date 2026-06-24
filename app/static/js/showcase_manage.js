const selectedItems = new Map();
const grid = document.getElementById("manageGrid");
const quoteModal = document.getElementById("quoteModal");
const quoteBody = document.getElementById("quoteBody");
const quoteCount = document.getElementById("quoteCount");
const quoteStatus = document.getElementById("quoteStatus");
const showcaseDetailModal = document.getElementById("showcaseDetailModal");
const showcaseDetailTitle = document.getElementById("showcaseDetailTitle");
const showcaseDetailSummary = document.getElementById("showcaseDetailSummary");
const showcaseDetailImage = document.getElementById("showcaseDetailImage");
const showcaseDetailEmpty = document.getElementById("showcaseDetailEmpty");
const showcaseDetailCategory = document.getElementById("showcaseDetailCategory");
const showcaseDetailCode = document.getElementById("showcaseDetailCode");
const showcaseDetailVisible = document.getElementById("showcaseDetailVisible");
const showcaseDetailDescription = document.getElementById("showcaseDetailDescription");
const selectionActions = Array.from(document.querySelectorAll(".selection-action"));
const newItemBtn = document.getElementById("newItemBtn");
const startSelectBtn = document.getElementById("startSelectBtn");
let selectionMode = false;
let detailTrigger = null;

function getCardData(card) {
    return {
        id: card.dataset.itemId,
        name: card.dataset.title || "",
        image_url: card.dataset.imageUrl || "",
        size: "",
        quantity: "1",
        price: ""
    };
}

function setSelectionMode(enabled) {
    selectionMode = enabled;
    document.body.classList.toggle("selection-mode", enabled);
    selectionActions.forEach(item => item.hidden = !enabled);
    newItemBtn.hidden = enabled;
    startSelectBtn.hidden = enabled;
    if (!enabled) {
        selectedItems.clear();
        document.querySelectorAll(".manage-select-card.selected").forEach(card => {
            card.classList.remove("selected");
            card.setAttribute("aria-pressed", "false");
        });
    }
    updateSelectionButtons();
}

function updateSelectionButtons() {
    const count = selectedItems.size;
    document.getElementById("openQuoteBtn").textContent = count ? `生成资料清单（${count}）` : "生成资料清单";
    document.getElementById("openQuoteBtn").disabled = count === 0;
    document.getElementById("deleteItemsBtn").disabled = count === 0;
}

function toggleCard(card, forceSelected = null) {
    const row = getCardData(card);
    const shouldSelect = forceSelected === null ? !selectedItems.has(row.id) : forceSelected;
    if (shouldSelect) {
        selectedItems.set(row.id, row);
        card.classList.add("selected");
        card.setAttribute("aria-pressed", "true");
    } else {
        selectedItems.delete(row.id);
        card.classList.remove("selected");
        card.setAttribute("aria-pressed", "false");
    }
    updateSelectionButtons();
}

function openShowcaseDetail(card) {
    detailTrigger = card;
    const imageUrl = card.dataset.imageUrl || "";
    showcaseDetailTitle.textContent = card.dataset.title || "资料详情";
    showcaseDetailSummary.textContent = card.dataset.description ? "图片与描述" : "";
    showcaseDetailCategory.textContent = card.dataset.category || "未分类";
    showcaseDetailCode.textContent = card.dataset.code || "";
    showcaseDetailVisible.textContent = card.dataset.visible || "";
    showcaseDetailDescription.textContent = card.dataset.description || "暂无描述";
    if (imageUrl) {
        showcaseDetailImage.hidden = false;
        showcaseDetailImage.src = imageUrl;
        showcaseDetailImage.alt = card.dataset.title || "";
        showcaseDetailEmpty.hidden = true;
    } else {
        showcaseDetailImage.hidden = true;
        showcaseDetailImage.removeAttribute("src");
        showcaseDetailEmpty.hidden = false;
    }
    showcaseDetailModal.hidden = false;
    showcaseDetailModal.querySelector("[data-close-detail-modal]")?.focus();
}

function renderQuoteRows() {
    const rows = Array.from(selectedItems.values());
    quoteBody.innerHTML = "";
    quoteCount.textContent = rows.length;
    rows.forEach(row => {
        const tr = document.createElement("tr");
        const nameTd = document.createElement("td");
        nameTd.textContent = row.name;
        tr.appendChild(nameTd);

        const imageTd = document.createElement("td");
        if (row.image_url) {
            const img = document.createElement("img");
            img.className = "quote-thumb";
            img.src = row.image_url;
            img.alt = row.name;
            imageTd.appendChild(img);
        } else {
            imageTd.textContent = "无图";
        }
        tr.appendChild(imageTd);

        [["size", "text"], ["quantity", "number"], ["price", "text"]].forEach(([field, type]) => {
            const td = document.createElement("td");
            const input = document.createElement("input");
            input.type = type;
            input.value = row[field];
            input.dataset.id = row.id;
            input.dataset.field = field;
            if (field === "quantity") {
                input.min = "0";
                input.step = "1";
            }
            input.addEventListener("input", event => {
                const current = selectedItems.get(event.target.dataset.id);
                if (current) {
                    current[event.target.dataset.field] = event.target.value;
                }
            });
            td.appendChild(input);
            tr.appendChild(td);
        });

        const actionTd = document.createElement("td");
        const removeBtn = document.createElement("button");
        removeBtn.className = "quote-remove-btn";
        removeBtn.type = "button";
        removeBtn.textContent = "移除";
        removeBtn.addEventListener("click", () => {
            selectedItems.delete(row.id);
            const card = document.querySelector(`.manage-select-card[data-item-id="${row.id}"]`);
            if (card) {
                card.classList.remove("selected");
            }
            renderQuoteRows();
            updateSelectionButtons();
            if (!selectedItems.size) {
                quoteModal.hidden = true;
            }
        });
        actionTd.appendChild(removeBtn);
        tr.appendChild(actionTd);
        quoteBody.appendChild(tr);
    });
}

function quotePayload() {
    return Array.from(selectedItems.values()).map(row => ({
        name: row.name,
        image_url: row.image_url,
        size: row.size,
        quantity: row.quantity,
        price: row.price
    }));
}

async function downloadQuote(format) {
    const rows = quotePayload();
    if (!rows.length) {
        return;
    }
    quoteStatus.textContent = "生成中...";
    const endpoint = format === "excel" ? "/showcase/quotation/excel" : "/showcase/quotation/image";
    const response = await fetch(endpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({rows})
    });
    if (!response.ok) {
        let message = "生成失败";
        try {
            const data = await response.json();
            message = data.error || message;
        } catch (error) {}
        quoteStatus.textContent = message;
        return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
    link.href = url;
    link.download = format === "excel" ? `material-list-${stamp}.xlsx` : `material-list-${stamp}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    quoteStatus.textContent = "已生成";
}

if (grid) {
    document.querySelectorAll(".manage-select-card").forEach(card => {
        let pressTimer = null;
        let longPressed = false;
        const startPress = () => {
            longPressed = false;
            pressTimer = window.setTimeout(() => {
                longPressed = true;
                setSelectionMode(true);
                toggleCard(card, true);
            }, 520);
        };
        const stopPress = () => {
            window.clearTimeout(pressTimer);
        };

        card.addEventListener("mousedown", startPress);
        card.addEventListener("touchstart", startPress, {passive: true});
        card.addEventListener("mouseup", stopPress);
        card.addEventListener("mouseleave", stopPress);
        card.addEventListener("touchend", stopPress);
        card.addEventListener("click", event => {
            if (longPressed) {
                event.preventDefault();
                return;
            }
            if (selectionMode) {
                toggleCard(card);
                return;
            }
            openShowcaseDetail(card);
        });
        card.addEventListener("keydown", event => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            if (selectionMode) {
                toggleCard(card);
            } else {
                openShowcaseDetail(card);
            }
        });
    });
}

startSelectBtn.addEventListener("click", () => setSelectionMode(true));
document.getElementById("cancelSelectBtn").addEventListener("click", () => setSelectionMode(false));
document.getElementById("openQuoteBtn").addEventListener("click", () => {
    if (!selectedItems.size) {
        return;
    }
    renderQuoteRows();
    quoteStatus.textContent = "";
    quoteModal.hidden = false;
});
document.getElementById("deleteItemsBtn").addEventListener("click", async () => {
    const ids = Array.from(selectedItems.keys());
    if (!ids.length || !confirm(`确认删除 ${ids.length} 条资料？`)) {
        return;
    }
    const response = await fetch("/showcase/manage/delete", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ids})
    });
    if (!response.ok) {
        alert("删除失败");
        return;
    }
    window.location.reload();
});
document.getElementById("downloadImageBtn").addEventListener("click", () => downloadQuote("image"));
document.getElementById("downloadExcelBtn").addEventListener("click", () => downloadQuote("excel"));
document.querySelectorAll("[data-close-modal]").forEach(item => {
    item.addEventListener("click", () => quoteModal.hidden = true);
});
document.querySelectorAll("[data-close-detail-modal]").forEach(item => {
    item.addEventListener("click", () => {
        showcaseDetailModal.hidden = true;
        detailTrigger?.focus();
    });
});
