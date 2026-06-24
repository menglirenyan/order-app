const printDocument = document.querySelector("[data-print-document]");
document.getElementById("printDeliveryButton")?.addEventListener("click", () => window.print());
if (printDocument?.dataset.autoPrint === "true") {
  window.addEventListener("load", () => window.print());
}
