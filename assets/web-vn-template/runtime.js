(function () {
  const story = window.NARRATIVE_GAME_STORY;
  const state = Object.assign({}, story.initial_state || {});
  const nodes = new Map((story.nodes || []).map((node) => [node.id, node]));
  const assets = new Map((story.assets || []).map((asset) => [asset.asset_id, asset]));
  const characters = new Map((story.characters || []).map((character) => [character.id, character]));
  const nodeCompletionRules = story.node_completion_rules || [];
  const displayNameToCharacterId = new Map((story.characters || []).map((character) => [normalizeKey(character.display_name), character.id]));
  const portraitAssetToCharacterId = new Map();
  (story.assets || []).forEach((asset) => {
    if (asset.kind === "portrait" && asset.character_id) {
      portraitAssetToCharacterId.set(asset.asset_id, asset.character_id);
    }
  });

  let currentNodeId = story.start_node_id;
  let beatIndex = 0;
  let overlayBeats = null;
  let overlayBeatIndex = 0;
  let overlayReturnIndex = 0;
  let overlayExitChoice = null;
  let activitySession = null;
  let pendingRouteChoice = null;
  let terminalVariantPlayed = false;
  let activeEndingVariant = null;
  let nodeCompletionApplied = false;
  let sceneBackgroundId = null;
  let currentBgmId = null;
  let currentBgm = null;
  let currentVoice = null;
  let lastVoiceKey = null;
  let activeSfx = [];
  const pendingAudio = [];
  const activePortraits = new Map();
  const characterAliases = new Map();
  const BGM_VOLUME = 0.28;
  const BGM_DUCKED_VOLUME = 0.12;
  const SFX_VOLUME = 0.36;
  const VOICE_VOLUME = 1.0;
  const SFX_MAX_SECONDS = 2.2;

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

  function normalizeKey(value) {
    return String(value || "").trim().replace(/[^a-zA-Z0-9.]+/g, "_").toLowerCase();
  }

  function inferCharacterIdFromPortrait(assetId) {
    if (portraitAssetToCharacterId.has(assetId)) {
      return portraitAssetToCharacterId.get(assetId);
    }
    const parts = String(assetId || "").split(".");
    return parts[0] === "portrait" && parts[1] ? `char.${parts[1]}` : "char.unknown";
  }

  function resolveCharacterId(characterHint, assetId) {
    if (characterHint) {
      const raw = String(characterHint).trim();
      if (characterAliases.has(raw)) return characterAliases.get(raw);
      if (characters.has(raw)) return raw;
      if (displayNameToCharacterId.has(normalizeKey(raw))) return displayNameToCharacterId.get(normalizeKey(raw));
      if (assetId && portraitAssetToCharacterId.has(assetId)) return portraitAssetToCharacterId.get(assetId);
      const charId = raw.startsWith("char.") ? raw : `char.${raw.replace(/^portrait\./, "").split(".")[0]}`;
      if (characters.has(charId)) return charId;
      if (charId !== "char.") return charId;
    }
    return inferCharacterIdFromPortrait(assetId);
  }

  function resolvePortraitAssetId(characterId, assetHint) {
    const character = characters.get(characterId);
    if (assetHint) {
      const raw = String(assetHint);
      if (assets.has(raw)) return raw;
      const emotion = raw.split(".").pop();
      const match = (character && character.portrait_assets || []).find((portrait) => {
        return portrait.emotion === raw || portrait.emotion === emotion || portrait.asset_id === raw || portrait.asset_id.endsWith(`.${raw}`);
      });
      if (match) return match.asset_id;
      if (!raw.startsWith("portrait.") && characterId && characterId.startsWith("char.")) {
        const slug = characterId.slice(5);
        const candidate = `portrait.${slug}.${raw}`;
        if (assets.has(candidate)) return candidate;
      }
      return raw;
    }
    return character && character.base_portrait_asset_id;
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

  function renderActivePortraits() {
    portraitsEl.innerHTML = "";
    const seenPortraitIds = new Set();
    const portraitIds = Array.from(activePortraits.values()).filter((id) => {
      const asset = assets.get(id);
      if (!asset || !asset.runtime_path || seenPortraitIds.has(id)) return false;
      seenPortraitIds.add(id);
      return true;
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

  function resetNodeScene(node) {
    sceneBackgroundId = node.background_id || node.id;
    setBackground(sceneBackgroundId);
    activePortraits.clear();
    const beats = node.beats || [];
    const hasPresentationCommands = beats.some((beat) => {
      return beat && beat.type === "command" && ["show_char", "set_expression", "hide_char"].includes(beat.command);
    });
    if (!hasPresentationCommands) {
      (node.portrait_ids || []).forEach((assetId) => {
        const characterId = inferCharacterIdFromPortrait(assetId);
        activePortraits.set(characterId, assetId);
      });
    }
    renderActivePortraits();
  }

  function commandArg(command, key, fallbackKey) {
    const args = command.args || {};
    return args[key] || (fallbackKey ? args[fallbackKey] : undefined) || args["0"];
  }

  function audioPath(assetId) {
    const asset = assets.get(assetId);
    return asset && asset.runtime_path;
  }

  function attemptPlay(audio) {
    const playback = audio.play();
    if (playback && typeof playback.catch === "function") {
      playback.catch(() => {
        if (!audio.__pipelineStopped && !pendingAudio.includes(audio)) {
          pendingAudio.push(audio);
        }
      });
    }
  }

  function resumePendingAudio() {
    const waiting = pendingAudio.splice(0, pendingAudio.length);
    waiting.forEach((audio) => {
      if (!audio.__pipelineStopped) {
        attemptPlay(audio);
      }
    });
  }

  function playAudioAsset(assetId, options) {
    const path = audioPath(assetId);
    if (!path) return null;
    const audio = new Audio(path);
    audio.loop = Boolean(options && options.loop);
    audio.volume = Number((options && options.volume) ?? 1);
    audio.__pipelineStopped = false;
    attemptPlay(audio);
    return audio;
  }

  function stopAudio(audio) {
    if (!audio) return;
    audio.__pipelineStopped = true;
    audio.pause();
    try {
      audio.currentTime = 0;
    } catch (_error) {
      // Some browsers disallow resetting a not-yet-loaded audio element.
    }
  }

  function setBgmDucked(ducked) {
    if (currentBgm) {
      currentBgm.volume = ducked ? BGM_DUCKED_VOLUME : BGM_VOLUME;
    }
  }

  function pruneSfx() {
    activeSfx = activeSfx.filter((audio) => audio && !audio.ended && !audio.__pipelineStopped);
  }

  function stopAllSfx() {
    activeSfx.forEach(stopAudio);
    activeSfx = [];
  }

  function playBgm(assetId) {
    if (!assetId) return;
    if (currentBgmId === assetId && currentBgm) return;
    stopAudio(currentBgm);
    currentBgmId = assetId;
    currentBgm = playAudioAsset(assetId, { loop: true, volume: currentVoice ? BGM_DUCKED_VOLUME : BGM_VOLUME });
  }

  function stopBgm() {
    stopAudio(currentBgm);
    currentBgm = null;
    currentBgmId = null;
  }

  function playSfx(assetId) {
    if (!assetId) return;
    pruneSfx();
    activeSfx
      .filter((audio) => audio.__assetId === assetId)
      .forEach(stopAudio);
    activeSfx = activeSfx.filter((audio) => audio.__assetId !== assetId && !audio.__pipelineStopped);
    const audio = playAudioAsset(assetId, { loop: false, volume: SFX_VOLUME });
    if (!audio) return;
    audio.__assetId = assetId;
    audio.addEventListener("playing", () => {
      window.setTimeout(() => stopAudio(audio), SFX_MAX_SECONDS * 1000);
    }, { once: true });
    audio.addEventListener("ended", pruneSfx, { once: true });
    activeSfx.push(audio);
  }

  function stopVoice() {
    stopAudio(currentVoice);
    currentVoice = null;
    setBgmDucked(false);
  }

  function playVoiceForBeat(beat) {
    const assetId = beat && beat.voice_asset_id;
    if (!assetId) {
      stopVoice();
      lastVoiceKey = null;
      return;
    }
    const key = `${currentNodeId}:${beatIndex}:${assetId}`;
    if (key === lastVoiceKey) return;
    stopVoice();
    lastVoiceKey = key;
    currentVoice = playAudioAsset(assetId, { loop: false, volume: VOICE_VOLUME });
    if (currentVoice) {
      currentVoice.addEventListener("playing", () => setBgmDucked(true), { once: true });
      currentVoice.addEventListener("ended", () => setBgmDucked(false), { once: true });
    }
  }

  function executeCommand(command) {
    if (!command || command.type !== "command") return false;
    const args = command.args || {};
    if (command.command === "show_bg") {
      const assetId = commandArg(command, "asset_id", "bg");
      if (assetId) {
        sceneBackgroundId = assetId;
        setBackground(assetId);
      }
    } else if (command.command === "show_cg") {
      const assetId = commandArg(command, "asset_id", "cg");
      if (assetId) setBackground(assetId);
    } else if (command.command === "hide_cg") {
      setBackground(sceneBackgroundId || currentNodeId);
    } else if (command.command === "show_char") {
      const assetId = args.asset_id || args.expression_asset_id || args.portrait;
      const characterHint = args.character_id || args.character || args.name;
      const characterId = resolveCharacterId(characterHint, assetId);
      const resolvedAssetId = resolvePortraitAssetId(characterId, assetId);
      if (resolvedAssetId) {
        if (characterHint) characterAliases.set(String(characterHint).trim(), characterId);
        activePortraits.set(characterId, resolvedAssetId);
        renderActivePortraits();
      }
    } else if (command.command === "set_expression") {
      const currentAssetId = activePortraits.get(args.character_id);
      const characterId = resolveCharacterId(args.character_id || args.character || args.name, currentAssetId || args.expression_asset_id);
      const resolvedAssetId = resolvePortraitAssetId(characterId, args.expression_asset_id || args.asset_id || args.expression || args.expr || args.emotion);
      if (resolvedAssetId) {
        activePortraits.set(characterId, resolvedAssetId);
        renderActivePortraits();
      }
    } else if (command.command === "hide_char") {
      const characterId = resolveCharacterId(args.character_id || args.character || args.name);
      activePortraits.delete(characterId);
      renderActivePortraits();
    } else if (command.command === "play_bgm") {
      playBgm(commandArg(command, "asset_id", "track"));
    } else if (command.command === "stop_bgm") {
      stopBgm();
    } else if (command.command === "play_sfx") {
      playSfx(commandArg(command, "asset_id", "track"));
    } else if (command.command === "set") {
      applyWrites([args]);
    } else if (command.command === "complete_activity") {
      return completeActivity(args.outcome || args.outcome_id || args.edge_id, []);
    }
    return false;
  }

  function advancePastCommands(beats) {
    while (beatIndex < beats.length && beats[beatIndex] && beats[beatIndex].type === "command") {
      if (executeCommand(beats[beatIndex])) return true;
      beatIndex += 1;
    }
    return false;
  }

  function applyWrites(writes) {
    (writes || []).forEach((write) => {
      if (!write || typeof write !== "object") {
        if (typeof console !== "undefined" && console.warn) console.warn("Ignoring invalid state write", write);
        return;
      }
      const id = write.state_variable_id || write.state_id || write.id;
      if (!id) {
        if (typeof console !== "undefined" && console.warn) console.warn("Ignoring state write without id", write);
        return;
      }
      const value = normalizeStateValue(write.value);
      const operation = write.operation || write.op || "set";
      if (operation === "increment") {
        state[id] = Number(state[id] || 0) + Number(value || 1);
      } else if (operation === "decrement") {
        state[id] = Number(state[id] || 0) - Number(value || 1);
      } else if (operation === "append") {
        state[id] = Array.isArray(state[id]) ? state[id].concat([value]) : [value];
      } else if (operation === "remove") {
        state[id] = Array.isArray(state[id]) ? state[id].filter((item) => item !== value) : state[id];
      } else {
        state[id] = value;
      }
    });
  }

  function normalizeStateValue(value) {
    if (value === "true") return true;
    if (value === "false") return false;
    if (value === "null") return null;
    if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
      return Number(value);
    }
    return value;
  }

  function conditionPasses(condition) {
    const id = condition && (condition.state_variable_id || condition.state_id || condition.id);
    if (!condition || !id) return true;
    const actual = state[id];
    const expected = normalizeStateValue(condition.value);
    switch (condition.operator) {
      case "!=":
      case "not_equals": return actual !== expected;
      case ">":
      case "greater_than": return Number(actual) > Number(expected);
      case ">=":
      case "greater_than_or_equal": return Number(actual) >= Number(expected);
      case "<":
      case "less_than": return Number(actual) < Number(expected);
      case "<=":
      case "less_than_or_equal": return Number(actual) <= Number(expected);
      case "==":
      case "equals":
      default: return actual === expected;
    }
  }

  function choicePasses(choice) {
    return (choice.conditions || []).every(conditionPasses);
  }

  function applyNodeCompletionRules(nodeId) {
    if (nodeCompletionApplied) return;
    nodeCompletionApplied = true;
    nodeCompletionRules.forEach((rule) => {
      if (!rule || rule.source_node_id !== nodeId) return;
      if ((rule.conditions || []).every(conditionPasses)) {
        applyWrites(rule.effects);
      }
    });
  }

  function isVisibleChoice(choice) {
    return (choice.condition_type || "player_choice") === "player_choice";
  }

  function enterNode(nodeId) {
    currentNodeId = nodeId;
    beatIndex = 0;
    overlayBeats = null;
    overlayBeatIndex = 0;
    overlayReturnIndex = 0;
    overlayExitChoice = null;
    activitySession = null;
    pendingRouteChoice = null;
    terminalVariantPlayed = false;
    activeEndingVariant = null;
    nodeCompletionApplied = false;
    lastVoiceKey = null;
    stopVoice();
    stopAllSfx();
    const node = nodes.get(currentNodeId);
    if (node) resetNodeScene(node);
    render();
  }

  function commitChoice(choice, extraWrites) {
    if (!choice || !choice.target) return;
    applyWrites(choice.effects);
    applyWrites(choice.state_writes);
    applyWrites(extraWrites);
    applyNodeCompletionRules(currentNodeId);
    enterNode(choice.target);
    return true;
  }

  function startOverlay(beats, options) {
    overlayBeats = beats || [];
    overlayBeatIndex = 0;
    overlayReturnIndex = options && Number.isInteger(options.returnIndex) ? options.returnIndex : beatIndex;
    overlayExitChoice = options && options.exitChoice ? options.exitChoice : null;
    beatIndex = 0;
    render();
  }

  function followChoice(choice) {
    if (!choice || !choice.target) return;
    const beats = choice.beats || [];
    if (beats.length) {
      startOverlay(beats, { exitChoice: choice });
      return;
    }
    commitChoice(choice, []);
  }

  function chooseInline(choice) {
    const returnIndex = beatIndex + 1;
    applyWrites(choice.effects);
    applyWrites(choice.state_writes);
    startOverlay(choice.beats || [], { returnIndex });
  }

  function finishOverlay() {
    const exitChoice = overlayExitChoice;
    const returnIndex = overlayReturnIndex;
    overlayBeats = null;
    overlayBeatIndex = 0;
    overlayReturnIndex = 0;
    overlayExitChoice = null;
    if (exitChoice) {
      commitChoice(exitChoice, []);
    } else {
      beatIndex = returnIndex;
      render();
    }
  }

  function selectEndingVariant(node) {
    const variants = (node.ending_variants || []).filter((variant) => {
      return (variant.conditions || []).every(conditionPasses);
    });
    if (!variants.length) return null;
    variants.sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0));
    return variants[0];
  }

  function startTerminalVariant(node) {
    if (!node || terminalVariantPlayed) return false;
    const variant = selectEndingVariant(node);
    if (!variant) return false;
    terminalVariantPlayed = true;
    activeEndingVariant = variant;
    applyWrites(variant.state_writes);
    if (variant.ending_id && state["state.game.ending_id"] == null) {
      state["state.game.ending_id"] = variant.ending_id;
    }
    if ((variant.beats || []).length) {
      startOverlay(variant.beats, { returnIndex: beatIndex });
      return true;
    }
    render();
    return true;
  }

  function completeActivity(outcomeId, writes) {
    const node = nodes.get(currentNodeId);
    if (!node) return false;
    const choice = (node.choices || []).find((candidate) => {
      return candidate.outcome_id === outcomeId || candidate.edge_id === outcomeId || (candidate.source_rule_ids || []).includes(outcomeId);
    }) || (node.choices || [])[0];
    if (!choice || !choicePasses(choice)) return false;
    return commitChoice(choice, writes);
  }

  function followPendingRouteChoice() {
    const choice = pendingRouteChoice;
    pendingRouteChoice = null;
    if (choice) followChoice(choice);
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
    const displayedChoices = choices.concat(routeChoices.length > 1 || choices.length > 0 ? routeChoices : []);
    displayedChoices.forEach((choice) => {
      choicesEl.appendChild(makeButton(choice.label || "Continue", () => followChoice(choice), isVisibleChoice(choice) ? "" : "route-choice"));
    });
    if (choices.length === 0 && routeChoices.length === 1) {
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

  function renderInlineChoice(beat) {
    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = beat.speaker || "Choose";
    lineEl.textContent = beat.text || "";
    const availableChoices = (beat.choices || []).filter(choicePasses);
    if (!availableChoices.length) {
      beatIndex += 1;
      render();
      return;
    }
    availableChoices.forEach((choice) => {
      choicesEl.appendChild(makeButton(choice.label || "Continue", () => chooseInline(choice)));
    });
  }

  function renderBeatList(beats, onComplete) {
    if (advancePastCommands(beats)) return true;
    if (beatIndex >= beats.length) {
      onComplete();
      return true;
    }
    const beat = beats[Math.min(beatIndex, beats.length - 1)];
    if (beat && beat.type === "choice") {
      renderInlineChoice(beat);
      return true;
    }
    speakerEl.textContent = beat.speaker || "Narrator";
    lineEl.textContent = beat.text || "";
    playVoiceForBeat(beat);
    return false;
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
    nodeTitleEl.textContent = (activeEndingVariant && activeEndingVariant.title) || node.title || node.id;
    choicesEl.innerHTML = "";
    continueButton.textContent = "Continue";
    pendingRouteChoice = null;
    if (overlayBeats) {
      if (!renderBeatList(overlayBeats, finishOverlay)) {
        continueButton.hidden = false;
      }
      return;
    }
    if (node.gameplay) {
      renderGameplay(node);
      return;
    }
    const beats = node.beats && node.beats.length ? node.beats : [{ speaker: "Narrator", text: "..." }];
    if (advancePastCommands(beats)) return;
    if (beatIndex >= beats.length) {
      if (node.is_terminal) applyNodeCompletionRules(node.id);
      if (node.is_terminal && startTerminalVariant(node)) return;
      renderChoices(node);
      return;
    }
    const beat = beats[Math.min(beatIndex, beats.length - 1)];
    if (beat && beat.type === "choice") {
      renderInlineChoice(beat);
      return;
    }
    speakerEl.textContent = beat.speaker || "Narrator";
    lineEl.textContent = beat.text || "";
    playVoiceForBeat(beat);
    if (beatIndex < beats.length - 1) {
      continueButton.hidden = false;
    } else {
      renderChoices(node);
    }
  }

  continueButton.addEventListener("click", () => {
    if (pendingRouteChoice) {
      followPendingRouteChoice();
      return;
    }
    beatIndex += 1;
    render();
  });

  restartButton.addEventListener("click", () => {
    currentNodeId = story.start_node_id;
    beatIndex = 0;
    overlayBeats = null;
    overlayBeatIndex = 0;
    overlayReturnIndex = 0;
    overlayExitChoice = null;
    activitySession = null;
    pendingRouteChoice = null;
    terminalVariantPlayed = false;
    activeEndingVariant = null;
    nodeCompletionApplied = false;
    stopBgm();
    stopVoice();
    pendingAudio.length = 0;
    activePortraits.clear();
    Object.keys(state).forEach((key) => delete state[key]);
    Object.assign(state, story.initial_state || {});
    enterNode(currentNodeId);
  });

  document.addEventListener("pointerdown", resumePendingAudio, true);
  document.addEventListener("keydown", resumePendingAudio, true);

  enterNode(currentNodeId);
})();
