(function () {
  const story = window.NARRATIVE_GAME_STORY;
  const state = Object.assign({}, story.initial_state || {});
  const nodes = new Map((story.nodes || []).map((node) => [node.id, node]));
  let currentNodeId = story.start_node_id;
  let beatIndex = 0;

  const titleEl = document.getElementById("title");
  const nodeTitleEl = document.getElementById("node-title");
  const speakerEl = document.getElementById("speaker");
  const lineEl = document.getElementById("line");
  const choicesEl = document.getElementById("choices");
  const continueButton = document.getElementById("continue");
  const restartButton = document.getElementById("restart");
  const stage = document.getElementById("stage");

  function hashColor(value, offset) {
    let hash = offset;
    for (let i = 0; i < value.length; i += 1) {
      hash = (hash * 31 + value.charCodeAt(i)) % 360;
    }
    return hash;
  }

  function setBackground(assetId) {
    const a = hashColor(assetId || "default", 17);
    const b = hashColor(assetId || "default", 137);
    stage.style.setProperty("--scene-gradient", `linear-gradient(135deg, hsl(${a} 34% 32%), hsl(${b} 28% 18%) 58%, hsl(${(a + b) % 360} 38% 28%))`);
  }

  function applyWrites(writes) {
    (writes || []).forEach((write) => {
      const id = write.state_variable_id;
      if (!id) return;
      if (write.operation === "increment") {
        state[id] = Number(state[id] || 0) + Number(write.value || 1);
      } else if (write.operation === "decrement") {
        state[id] = Number(state[id] || 0) - Number(write.value || 1);
      } else {
        state[id] = write.value;
      }
    });
  }

  function conditionPasses(condition) {
    if (!condition || !condition.state_variable_id) return true;
    const actual = state[condition.state_variable_id];
    const expected = condition.value;
    switch (condition.operator) {
      case "not_equals": return actual !== expected;
      case "greater_than": return Number(actual) > Number(expected);
      case "greater_than_or_equal": return Number(actual) >= Number(expected);
      case "less_than": return Number(actual) < Number(expected);
      case "less_than_or_equal": return Number(actual) <= Number(expected);
      case "equals":
      default: return actual === expected;
    }
  }

  function choicePasses(choice) {
    return (choice.conditions || []).every(conditionPasses);
  }

  function renderChoices(node) {
    choicesEl.innerHTML = "";
    const choices = (node.choices || []).filter(choicePasses);
    if (choices.length === 0 && node.is_terminal) {
      continueButton.hidden = true;
      return;
    }
    choices.forEach((choice) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = choice.label || "Continue";
      button.addEventListener("click", () => {
        applyWrites(choice.state_writes);
        currentNodeId = choice.target;
        beatIndex = 0;
        render();
      });
      choicesEl.appendChild(button);
    });
    continueButton.hidden = true;
  }

  function render() {
    const node = nodes.get(currentNodeId);
    if (!node) {
      nodeTitleEl.textContent = "Missing Scene";
      speakerEl.textContent = "";
      lineEl.textContent = `No node exists for ${currentNodeId}.`;
      continueButton.hidden = true;
      choicesEl.innerHTML = "";
      return;
    }
    titleEl.textContent = story.title || "Narrative Game";
    nodeTitleEl.textContent = node.title || node.id;
    setBackground(node.background_id || node.id);
    const beats = node.beats && node.beats.length ? node.beats : [{ speaker: "Narrator", text: "..." }];
    const beat = beats[Math.min(beatIndex, beats.length - 1)];
    speakerEl.textContent = beat.speaker || "Narrator";
    lineEl.textContent = beat.text || "";
    choicesEl.innerHTML = "";
    if (beatIndex < beats.length - 1) {
      continueButton.hidden = false;
    } else {
      renderChoices(node);
    }
  }

  continueButton.addEventListener("click", () => {
    beatIndex += 1;
    render();
  });

  restartButton.addEventListener("click", () => {
    currentNodeId = story.start_node_id;
    beatIndex = 0;
    Object.keys(state).forEach((key) => delete state[key]);
    Object.assign(state, story.initial_state || {});
    render();
  });

  render();
})();

