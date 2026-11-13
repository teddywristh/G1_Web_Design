const demoViews = [...document.querySelectorAll("[data-demo-view]")];
const demoPanels = [...document.querySelectorAll("[data-demo-panel]")];
const demoForm = document.querySelector("[data-demo-form]");
const demoInput = document.querySelector("#landing-demo-question");
const demoAnswer = document.querySelector("[data-demo-answer]");
const demoReset = document.querySelector("[data-demo-reset]");
let animationStopped = false;
let animationRun = 0;

function selectDemoView(view) {
  demoViews.forEach((button) => {
    button.classList.toggle("preview-active", button.dataset.demoView === view);
  });
  demoPanels.forEach((panel) => {
    panel.hidden = panel.dataset.demoPanel !== view;
  });
}

function stopAnimation() {
  animationStopped = true;
  animationRun += 1;
}

function delay(milliseconds, run) {
  return new Promise((resolve) => {
    window.setTimeout(() => resolve(!animationStopped && run === animationRun), milliseconds);
  });
}

async function typeDemoQuestion(text, run) {
  if (!demoInput) return false;
  demoInput.value = "";
  demoInput.classList.add("is-typing");
  for (const character of text) {
    if (animationStopped || run !== animationRun) {
      demoInput.classList.remove("is-typing");
      return false;
    }
    demoInput.value += character;
    await new Promise((resolve) => window.setTimeout(resolve, 42));
  }
  demoInput.classList.remove("is-typing");
  return true;
}

async function playDemoAnimation() {
  const run = animationRun;
  const question = "Hợp đồng lao động cần có những nội dung gì?";
  while (!animationStopped && run === animationRun) {
    selectDemoView("chat");
    if (demoAnswer) demoAnswer.hidden = true;
    if (demoForm) demoForm.hidden = false;
    if (!(await delay(700, run))) return;
    if (!(await typeDemoQuestion(question, run))) return;
    if (!(await delay(500, run))) return;
    if (demoAnswer) demoAnswer.hidden = false;
    if (demoForm) demoForm.hidden = true;
    if (!(await delay(2600, run))) return;
    selectDemoView("library");
    if (!(await delay(2200, run))) return;
    selectDemoView("settings");
    if (!(await delay(2200, run))) return;
  }
}

demoViews.forEach((button) => {
  button.addEventListener("click", () => {
    stopAnimation();
    selectDemoView(button.dataset.demoView);
  });
});

demoForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  stopAnimation();
  if (!demoInput?.value.trim()) {
    demoInput?.focus();
    return;
  }
  if (demoAnswer) demoAnswer.hidden = false;
  if (demoForm) demoForm.hidden = true;
});

demoReset?.addEventListener("click", () => {
  stopAnimation();
  if (demoInput) {
    demoInput.value = "";
    demoInput.focus();
  }
  if (demoAnswer) demoAnswer.hidden = true;
  if (demoForm) demoForm.hidden = false;
});

demoInput?.addEventListener("focus", stopAnimation, { once: true });
demoInput?.addEventListener("input", stopAnimation, { once: true });
playDemoAnimation();
