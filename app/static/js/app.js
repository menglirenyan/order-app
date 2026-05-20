(() => {
  const dialog = document.getElementById("confirmDialog");
  let pendingForm = null;
  let pendingButton = null;

  function closeDialog() {
    if (dialog) {
      dialog.hidden = true;
    }
    pendingForm = null;
    pendingButton = null;
  }

  function submitConfirmedForm() {
    if (!pendingForm) {
      closeDialog();
      return;
    }
    pendingForm.dataset.confirmed = "true";
    if (pendingButton && pendingButton.name) {
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = pendingButton.name;
      hidden.value = pendingButton.value;
      pendingForm.appendChild(hidden);
    }
    pendingForm.requestSubmit ? pendingForm.requestSubmit() : pendingForm.submit();
    closeDialog();
  }

  if (dialog) {
    dialog.querySelector("[data-confirm-ok]").addEventListener("click", submitConfirmedForm);
    dialog.querySelectorAll("[data-confirm-cancel]").forEach((item) => {
      item.addEventListener("click", closeDialog);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !dialog.hidden) {
        closeDialog();
      }
    });
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.confirmed === "true") {
      return;
    }

    const message = form.dataset.confirm;
    if (!message || !dialog) {
      return;
    }

    event.preventDefault();
    pendingForm = form;
    pendingButton = event.submitter instanceof HTMLButtonElement ? event.submitter : null;
    document.getElementById("confirmDialogMessage").textContent = message;
    dialog.hidden = false;
    dialog.querySelector("[data-confirm-cancel]").focus();
  });
})();
