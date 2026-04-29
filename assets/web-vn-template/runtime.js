(function () {
  const story = window.NARRATIVE_GAME_STORY;
  const state = Object.assign({}, story.initial_state || {});
  const nodes = new Map((story.nodes || []).map((node) => [node.id, node]));
  const assets = new Map((story.assets || []).map((asset) => [asset.asset_id, asset]));
  let currentNodeId = story.start_node_id;
  let beatIndex = 0;
  let activitySession = null;
  let pendingRouteChoice = null;

  const titleEl = document.getElementById("title");
  const nodeTitleEl = document.getElementById("node-title");
  const speakerEl = document.getElementById("speaker");
  const lineEl = document.getElementById("line");
  const choicesEl = document.getElementById("choices");
  const continueButton = document.getElementById("continue");
  const restartButton = document.getElementById("restart");
  const stage = document.getElementById("stage");
  const portraitsEl = document.getElementById("portraits");

  function hashColor(value, offset) {
    let hash = offset;
    for (let i = 0; i < value.length; i += 1) {
      hash = (hash * 31 + value.charCodeAt(i)) % 360;
    }
    return hash;
  }

  function setBackground(assetId) {
    const asset = assets.get(assetId);
    if (asset && asset.runtime_path) {
      stage.style.setProperty("--scene-image", `url("${asset.runtime_path}")`);
      stage.classList.add("has-asset-bg");
      return;
    }
    const a = hashColor(assetId || "default", 17);
    const b = hashColor(assetId || "default", 137);
    stage.classList.remove("has-asset-bg");
    stage.style.setProperty("--scene-gradient", `linear-gradient(135deg, hsl(${a} 34% 32%), hsl(${b} 28% 18%) 58%, hsl(${(a + b) % 360} 38% 28%))`);
  }

  function renderPortraits(node) {
    portraitsEl.innerHTML = "";
    const portraitIds = (node.portrait_ids || []).filter((id) => {
      const asset = assets.get(id);
      return asset && asset.runtime_path;
    });
    portraitIds.forEach((id, index) => {
      const asset = assets.get(id);
      const image = document.createElement("img");
      image.src = asset.runtime_path;
      image.alt = "";
      image.className = `portrait portrait-${index}`;
      portraitsEl.appendChild(image);
    });
  }

  function applyWrites(writes) {
    (writes || []).forEach((write) => {
      const id = write.state_variable_id;
      if (!id) return;
      if (write.operation === "increment") {
        state[id] = Number(state[id] || 0) + Number(write.value || 1);
      } else if (write.operation === "decrement") {
        state[id] = Number(state[id] || 0) - Number(write.value || 1);
      } else if (write.operation === "append") {
        state[id] = Array.isArray(state[id]) ? state[id].concat([write.value]) : [write.value];
      } else if (write.operation === "remove") {
        state[id] = Array.isArray(state[id]) ? state[id].filter((item) => item !== write.value) : state[id];
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

  function isVisibleChoice(choice) {
    return (choice.condition_type || "player_choice") === "player_choice";
  }

  function enterNode(nodeId) {
    currentNodeId = nodeId;
    beatIndex = 0;
    activitySession = null;
    pendingRouteChoice = null;
    render();
  }

  function followChoice(choice) {
    if (!choice || !choice.target) return;
    applyWrites(choice.state_writes);
    enterNode(choice.target);
  }

  function completeActivity(outcomeId, writes) {
    const node = nodes.get(currentNodeId);
    if (!node) return;
    const choice = (node.choices || []).find((candidate) => {
      return candidate.outcome_id === outcomeId || candidate.edge_id === outcomeId;
    }) || (node.choices || [])[0];
    if (!choice || !choicePasses(choice)) return;
    applyWrites(choice.state_writes);
    applyWrites(writes);
    enterNode(choice.target);
  }

  function makeButton(label, onClick, className) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label || "Continue";
    if (className) button.className = className;
    button.addEventListener("click", onClick);
    return button;
  }

  function makeEl(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function renderChoices(node) {
    choicesEl.innerHTML = "";
    pendingRouteChoice = null;
    continueButton.textContent = "Continue";
    const availableChoices = (node.choices || []).filter(choicePasses);
    const choices = availableChoices.filter(isVisibleChoice);
    const routeChoices = availableChoices.filter((choice) => !isVisibleChoice(choice));
    if (choices.length === 0 && routeChoices.length === 0 && node.is_terminal) {
      continueButton.hidden = true;
      return;
    }
    choices.forEach((choice) => {
      choicesEl.appendChild(makeButton(choice.label || "Continue", () => followChoice(choice)));
    });
    if (choices.length === 0 && routeChoices.length > 0) {
      pendingRouteChoice = routeChoices[0];
      continueButton.hidden = false;
      return;
    }
    continueButton.hidden = true;
  }

  function ensureSession(node, factory) {
    if (!activitySession || activitySession.nodeId !== node.id) {
      activitySession = Object.assign({ nodeId: node.id }, factory());
    }
    return activitySession;
  }

  function statValue(stats, statId, fallback) {
    return Object.prototype.hasOwnProperty.call(stats, statId) ? stats[statId] : fallback;
  }

  function makeStats(statDefs) {
    const values = {};
    (statDefs || []).forEach((stat) => {
      values[stat.id] = Number(stat.initial ?? stat.value ?? 0);
    });
    return values;
  }

  function applyStatEffects(session, effects) {
    (effects || []).forEach((effect) => {
      const side = effect.side === "opponent" ? "opponentStats" : "playerStats";
      const id = effect.stat_id;
      if (!id) return;
      const current = Number(session[side][id] || 0);
      const value = Number(effect.value || 0);
      if (effect.operation === "increment") {
        session[side][id] = current + value;
      } else if (effect.operation === "set") {
        session[side][id] = value;
      } else {
        session[side][id] = current - value;
      }
    });
  }

  function statConditionPasses(session, condition) {
    if (!condition) return false;
    const side = condition.side === "opponent" ? "opponentStats" : "playerStats";
    const actual = Number(session[side][condition.stat_id] || 0);
    const expected = Number(condition.value || 0);
    switch (condition.operator) {
      case "greater_than": return actual > expected;
      case "greater_than_or_equal": return actual >= expected;
      case "less_than": return actual < expected;
      case "equals": return actual === expected;
      case "less_than_or_equal":
      default: return actual <= expected;
    }
  }

  function firstOutcome(unit, fallback) {
    const bindings = unit.exit_bindings || [];
    return (bindings[0] && bindings[0].outcome_id) || fallback;
  }

  function renderBattle(node) {
    const unit = node.gameplay || {};
    const spec = unit.runtime_spec || {};
    const player = spec.player || { label: "Player", stats: [] };
    const opponent = spec.opponent || { label: "Opponent", stats: [] };
    const session = ensureSession(node, () => ({
      playerStats: makeStats(player.stats),
      opponentStats: makeStats(opponent.stats),
      round: 0,
      log: [unit.entry_text || "The confrontation begins."],
    }));

    function checkOutcome() {
      const win = (spec.win_conditions || []).find((condition) => statConditionPasses(session, condition));
      if (win) return win.outcome_id || "victory";
      const loss = (spec.lose_conditions || []).find((condition) => statConditionPasses(session, condition));
      if (loss) return loss.outcome_id || "defeat";
      const maxRounds = Number(spec.max_rounds || 0);
      if (maxRounds && session.round >= maxRounds) {
        return (unit.fail_forward && unit.fail_forward.outcome_id) || firstOutcome(unit, "continue");
      }
      return null;
    }

    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = opponent.label || "Opponent";
    lineEl.textContent = spec.prompt || unit.entry_text || "Choose how to respond.";

    const panel = makeEl("div", "gameplay-panel");
    const stats = makeEl("div", "stat-grid");
    [player, opponent].forEach((owner, ownerIndex) => {
      const sideStats = ownerIndex === 0 ? session.playerStats : session.opponentStats;
      const card = makeEl("div", "stat-card");
      card.appendChild(makeEl("strong", "", owner.label || (ownerIndex === 0 ? "Player" : "Opponent")));
      (owner.stats || []).forEach((stat) => {
        const row = makeEl("div", "stat-row");
        row.appendChild(makeEl("span", "", stat.label || stat.id));
        row.appendChild(makeEl("b", "", String(statValue(sideStats, stat.id, stat.initial || 0))));
        card.appendChild(row);
      });
      stats.appendChild(card);
    });
    panel.appendChild(stats);

    const log = makeEl("div", "activity-log");
    session.log.slice(-3).forEach((entry) => log.appendChild(makeEl("p", "", entry)));
    panel.appendChild(log);

    const actions = makeEl("div", "choices gameplay-actions");
    (spec.player_actions || spec.actions || []).forEach((action) => {
      actions.appendChild(makeButton(action.label || action.id, () => {
        applyStatEffects(session, action.effects);
        session.log.push(action.feedback || action.description || `${action.label || action.id} lands.`);
        let outcome = action.outcome_id || checkOutcome();
        if (!outcome) {
          const enemyPattern = spec.enemy_pattern || [];
          const enemyAction = enemyPattern[session.round % Math.max(enemyPattern.length, 1)];
          if (enemyAction) {
            applyStatEffects(session, enemyAction.effects);
            session.log.push(enemyAction.feedback || enemyAction.description || "The opponent presses back.");
          }
          session.round += 1;
          outcome = checkOutcome();
        }
        if (outcome) {
          completeActivity(outcome, action.state_writes || []);
        } else {
          render();
        }
      }));
    });
    panel.appendChild(actions);
    choicesEl.appendChild(panel);
  }

  function renderInteraction(node) {
    const unit = node.gameplay || {};
    const spec = unit.runtime_spec || {};
    const session = ensureSession(node, () => ({ visited: new Set(), log: [unit.entry_text || "Inspect the scene."] }));
    const completion = spec.completion || {};
    const required = completion.required_hotspots || [];
    const complete = required.every((id) => session.visited.has(id));

    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = "Inspect";
    lineEl.textContent = spec.prompt || unit.entry_text || "Choose what to inspect.";

    const panel = makeEl("div", "gameplay-panel");
    const log = makeEl("div", "activity-log");
    session.log.slice(-4).forEach((entry) => log.appendChild(makeEl("p", "", entry)));
    panel.appendChild(log);

    const grid = makeEl("div", "hotspot-grid");
    (spec.hotspots || []).forEach((hotspot) => {
      const requires = hotspot.requires || [];
      const unlocked = requires.every((id) => session.visited.has(id));
      const label = session.visited.has(hotspot.id) ? `${hotspot.label || hotspot.id} [done]` : (hotspot.label || hotspot.id);
      const button = makeButton(label, () => {
        if (!unlocked) {
          session.log.push(hotspot.blocked_text || "Something else needs attention first.");
        } else {
          session.visited.add(hotspot.id);
          applyWrites(hotspot.state_writes);
          session.log.push(hotspot.reveal_text || hotspot.description || "You notice something useful.");
        }
        render();
      });
      button.disabled = !unlocked;
      grid.appendChild(button);
    });
    panel.appendChild(grid);
    if (complete) {
      panel.appendChild(makeButton(completion.label || "Continue", () => {
        completeActivity(completion.outcome_id || firstOutcome(unit, "complete"), completion.state_writes || []);
      }, "primary-action"));
    }
    choicesEl.appendChild(panel);
  }

  function renderPuzzle(node) {
    const unit = node.gameplay || {};
    const spec = unit.runtime_spec || {};
    const session = ensureSession(node, () => ({ input: [], attempts: 0, message: unit.entry_text || "Solve the puzzle." }));
    const solution = spec.solution || [];

    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = "Puzzle";
    lineEl.textContent = spec.prompt || unit.entry_text || "Choose the correct sequence.";

    const panel = makeEl("div", "gameplay-panel");
    panel.appendChild(makeEl("div", "sequence-display", session.input.length ? session.input.join(" -> ") : "No input yet"));
    panel.appendChild(makeEl("p", "activity-message", session.message));
    (spec.clues || []).forEach((clue) => panel.appendChild(makeEl("p", "clue", clue)));

    const grid = makeEl("div", "hotspot-grid");
    (spec.options || []).forEach((option) => {
      grid.appendChild(makeButton(option.label || option.id, () => {
        session.input.push(option.id);
        session.message = option.feedback || "Input added.";
        render();
      }));
    });
    panel.appendChild(grid);
    const controls = makeEl("div", "choices gameplay-actions");
    controls.appendChild(makeButton("Back", () => {
      session.input.pop();
      render();
    }));
    controls.appendChild(makeButton("Clear", () => {
      session.input = [];
      render();
    }));
    controls.appendChild(makeButton(spec.submit_label || "Submit", () => {
      const solved = solution.length === session.input.length && solution.every((id, index) => id === session.input[index]);
      if (solved) {
        completeActivity(spec.solved_outcome_id || "solved", spec.solved_state_writes || []);
        return;
      }
      session.attempts += 1;
      const hints = spec.hints || [];
      session.message = hints[Math.min(session.attempts - 1, hints.length - 1)] || spec.wrong_feedback || "That sequence does not fit.";
      if (spec.max_attempts && session.attempts >= Number(spec.max_attempts)) {
        const failOutcome = spec.failed_outcome_id || (unit.fail_forward && unit.fail_forward.outcome_id);
        if (failOutcome) {
          completeActivity(failOutcome, spec.failed_state_writes || []);
          return;
        }
      }
      session.input = [];
      render();
    }, "primary-action"));
    panel.appendChild(controls);
    choicesEl.appendChild(panel);
  }

  function renderExploration(node) {
    const unit = node.gameplay || {};
    const spec = unit.runtime_spec || {};
    const areas = new Map((spec.areas || []).map((area) => [area.id, area]));
    const session = ensureSession(node, () => ({
      areaId: spec.start_area_id || ((spec.areas || [])[0] || {}).id,
      visitedAreas: new Set([spec.start_area_id]),
      discoveries: new Set(),
      log: [],
    }));
    const area = areas.get(session.areaId) || (spec.areas || [])[0] || {};
    const completion = spec.completion || {};
    const requiredAreas = completion.required_areas || [];
    const requiredDiscoveries = completion.required_discoveries || [];
    const complete = requiredAreas.every((id) => session.visitedAreas.has(id)) && requiredDiscoveries.every((id) => session.discoveries.has(id));

    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = area.label || "Explore";
    lineEl.textContent = area.description || spec.prompt || unit.entry_text || "Choose where to go.";

    const panel = makeEl("div", "gameplay-panel");
    if (session.log.length) {
      const log = makeEl("div", "activity-log");
      session.log.slice(-3).forEach((entry) => log.appendChild(makeEl("p", "", entry)));
      panel.appendChild(log);
    }
    const discoveries = makeEl("div", "hotspot-grid");
    (area.discoveries || []).forEach((discovery) => {
      const label = session.discoveries.has(discovery.id) ? `${discovery.label || discovery.id} [done]` : (discovery.label || discovery.id);
      discoveries.appendChild(makeButton(label, () => {
        session.discoveries.add(discovery.id);
        applyWrites(discovery.state_writes);
        session.log.push(discovery.text || "You found something.");
        render();
      }));
    });
    panel.appendChild(discoveries);
    const exits = makeEl("div", "choices gameplay-actions");
    (area.exits || []).forEach((localExit) => {
      exits.appendChild(makeButton(localExit.label || "Go", () => {
        const needs = localExit.requires_discoveries || [];
        if (!needs.every((id) => session.discoveries.has(id))) {
          session.log.push(localExit.blocked_text || "The way is not open yet.");
        } else {
          session.areaId = localExit.target_area_id;
          session.visitedAreas.add(session.areaId);
          session.log.push(localExit.travel_text || "You move on.");
        }
        render();
      }));
    });
    panel.appendChild(exits);
    if (complete) {
      panel.appendChild(makeButton(completion.label || "Finish exploration", () => {
        completeActivity(completion.outcome_id || firstOutcome(unit, "complete"), completion.state_writes || []);
      }, "primary-action"));
    }
    if (spec.retreat_outcome_id) {
      panel.appendChild(makeButton(spec.retreat_label || "Retreat", () => completeActivity(spec.retreat_outcome_id, [])));
    }
    choicesEl.appendChild(panel);
  }

  function renderGameplay(node) {
    const adapter = node.gameplay && node.gameplay.adapter_id;
    if (adapter === "battle.choice_duel") {
      renderBattle(node);
    } else if (adapter === "interaction.inspect_scene") {
      renderInteraction(node);
    } else if (adapter === "puzzle.sequence_lock") {
      renderPuzzle(node);
    } else if (adapter === "exploration.room_nav") {
      renderExploration(node);
    } else {
      speakerEl.textContent = "Unsupported";
      lineEl.textContent = `No Web VN adapter exists for ${adapter}.`;
      renderChoices(node);
    }
  }

  function render() {
    const node = nodes.get(currentNodeId);
    if (!node) {
      nodeTitleEl.textContent = "Missing Scene";
      speakerEl.textContent = "";
      lineEl.textContent = `No node exists for ${currentNodeId}.`;
      continueButton.hidden = true;
      pendingRouteChoice = null;
      choicesEl.innerHTML = "";
      return;
    }
    titleEl.textContent = story.title || "Narrative Game";
    nodeTitleEl.textContent = node.title || node.id;
    setBackground(node.background_id || node.id);
    renderPortraits(node);
    choicesEl.innerHTML = "";
    continueButton.textContent = "Continue";
    pendingRouteChoice = null;
    if (node.gameplay) {
      renderGameplay(node);
      return;
    }
    const beats = node.beats && node.beats.length ? node.beats : [{ speaker: "Narrator", text: "..." }];
    const beat = beats[Math.min(beatIndex, beats.length - 1)];
    speakerEl.textContent = beat.speaker || "Narrator";
    lineEl.textContent = beat.text || "";
    if (beatIndex < beats.length - 1) {
      continueButton.hidden = false;
    } else {
      renderChoices(node);
    }
  }

  continueButton.addEventListener("click", () => {
    if (pendingRouteChoice) {
      followChoice(pendingRouteChoice);
      return;
    }
    beatIndex += 1;
    render();
  });

  restartButton.addEventListener("click", () => {
    currentNodeId = story.start_node_id;
    beatIndex = 0;
    activitySession = null;
    pendingRouteChoice = null;
    Object.keys(state).forEach((key) => delete state[key]);
    Object.assign(state, story.initial_state || {});
    render();
  });

  render();
})();
