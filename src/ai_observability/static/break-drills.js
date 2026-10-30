const controls = document.querySelectorAll("[data-panel-target]");
const panels = document.querySelectorAll("[data-evidence-panel]");

controls.forEach((control) => {
  control.addEventListener("click", () => {
    const target = control.dataset.panelTarget;
    panels.forEach((panel) => {
      panel.hidden = panel.id !== target;
    });
    controls.forEach((button) => {
      button.classList.toggle("button-primary", button === control);
      button.classList.toggle("button-quiet", button !== control);
      button.setAttribute("aria-pressed", String(button === control));
    });
  });
});
