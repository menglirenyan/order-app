document.querySelectorAll(".category-quick-btn").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.querySelector('input[name="category"]');
    if (input) input.value = button.dataset.category || "";
  });
});
