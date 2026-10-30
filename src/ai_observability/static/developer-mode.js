const form = document.querySelector("#knowledge-check");
const feedback = document.querySelector("#form-feedback");
const tools = document.querySelector("#developer-tools");
const answers = { q1: "step", q2: "contract", q3: "policy" };

function showTools() {
  form.hidden = true;
  tools.hidden = false;
}

if (sessionStorage.getItem("veyepr-developer-mode") === "granted") {
  showTools();
}

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  const values = new FormData(form);
  const complete = Object.keys(answers).every((key) => values.get(key));
  const correct = Object.entries(answers).every(([key, value]) => values.get(key) === value);

  if (!complete) {
    feedback.textContent = "Answer all three questions before continuing.";
    return;
  }
  if (!correct) {
    feedback.textContent = "Review the assurance model and try again. The goal is to make the boundary explicit.";
    return;
  }

  sessionStorage.setItem("veyepr-developer-mode", "granted");
  showTools();
});
