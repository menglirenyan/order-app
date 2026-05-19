(() => {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) {
    return;
  }

  const mobileQuery = window.matchMedia("(max-width: 768px)");
  const menuButton = document.createElement("button");
  const overlay = document.createElement("div");

  menuButton.type = "button";
  menuButton.className = "mobile-menu-button";
  menuButton.setAttribute("aria-label", "打开导航");
  menuButton.setAttribute("aria-expanded", "false");
  menuButton.innerHTML = '<span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>';

  overlay.className = "mobile-nav-overlay";
  document.body.prepend(overlay);
  document.body.prepend(menuButton);

  function setNavOpen(isOpen) {
    document.body.classList.toggle("mobile-nav-open", isOpen);
    menuButton.setAttribute("aria-expanded", String(isOpen));
    menuButton.setAttribute("aria-label", isOpen ? "关闭导航" : "打开导航");
  }

  menuButton.addEventListener("click", () => {
    setNavOpen(!document.body.classList.contains("mobile-nav-open"));
  });

  overlay.addEventListener("click", () => setNavOpen(false));

  sidebar.addEventListener("click", (event) => {
    if (event.target.closest("a") && mobileQuery.matches) {
      setNavOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setNavOpen(false);
    }
  });

  mobileQuery.addEventListener("change", (event) => {
    if (!event.matches) {
      setNavOpen(false);
    }
  });

  const path = window.location.pathname;
  const shouldShowNewOrder = (
    path === "/dashboard"
    || path === "/orders"
    || /^\/orders\/\d+/.test(path)
  ) && !path.includes("/edit");

  if (shouldShowNewOrder) {
    const newOrderButton = document.createElement("a");
    newOrderButton.className = "mobile-new-order-fab";
    newOrderButton.href = "/orders/new";
    newOrderButton.textContent = "+ 新建";
    document.body.appendChild(newOrderButton);
  }

  document.querySelectorAll("[data-mobile-toggle-card]").forEach((card) => {
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "button");
    card.setAttribute("aria-expanded", "false");

    function toggleCard() {
      const isOpen = card.classList.toggle("is-expanded");
      card.setAttribute("aria-expanded", String(isOpen));
    }

    card.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, label, select, textarea")) {
        return;
      }
      toggleCard();
    });

    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      toggleCard();
    });
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) {
      return;
    }
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    const submitter = event.submitter;
    if (submitter && submitter instanceof HTMLButtonElement) {
      submitter.dataset.originalText = submitter.textContent || "";
      submitter.textContent = "处理中...";
      submitter.disabled = true;
    }
  });
})();
