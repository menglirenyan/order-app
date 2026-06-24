(() => {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) {
    return;
  }

  const mobileQuery = window.matchMedia("(max-width: 768px)");
  const menuButton = document.querySelector("[data-mobile-menu]");
  const overlay = document.querySelector("[data-mobile-overlay]");
  if (!menuButton || !overlay) return;

  function setNavOpen(isOpen) {
    document.body.classList.toggle("mobile-nav-open", isOpen);
    menuButton.setAttribute("aria-expanded", String(isOpen));
    menuButton.setAttribute("aria-label", isOpen ? "关闭导航" : "打开导航");
    overlay.hidden = !isOpen;
    if (isOpen) {
      sidebar.querySelector("a")?.focus();
    }
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

  document.querySelectorAll("[data-mobile-toggle-card]").forEach((card) => {
    const toggleButton = card.querySelector("[data-mobile-card-toggle]");
    if (!toggleButton) return;

    function toggleCard() {
      const isOpen = card.classList.toggle("is-expanded");
      toggleButton.setAttribute("aria-expanded", String(isOpen));
      toggleButton.textContent = isOpen ? "收起详细信息" : toggleButton.dataset.closedLabel;
    }

    toggleButton.dataset.closedLabel = toggleButton.textContent;
    toggleButton.addEventListener("click", toggleCard);
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
