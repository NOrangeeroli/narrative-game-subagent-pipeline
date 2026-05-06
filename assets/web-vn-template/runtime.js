(function () {
  const story = window.NARRATIVE_GAME_STORY;
  const state = Object.assign({}, story.initial_state || {});
  const nodes = new Map((story.nodes || []).map((node) => [node.id, node]));
  const assets = new Map((story.assets || []).map((asset) => [asset.asset_id, asset]));
  const characters = new Map((story.characters || []).map((character) => [character.id, character]));
  const displayNameToCharacterId = new Map((story.characters || []).map((character) => [normalizeKey(character.display_name), character.id]));
  const portraitAssetToCharacterId = new Map();
  (story.assets || []).forEach((asset) => {
    if (asset.kind === "portrait" && asset.character_id) {
      portraitAssetToCharacterId.set(asset.asset_id, asset.character_id);
    }
  });

  let currentNodeId = story.start_node_id;
  let beatIndex = 0;
  let activitySession = null;
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
    setBackground(node.background_id || node.id);
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
    if (!command || command.type !== "command") return;
    const args = command.args || {};
    if (command.command === "show_bg") {
      const assetId = commandArg(command, "asset_id", "bg");
      if (assetId) setBackground(assetId);
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
    }
  }

  function advancePastCommands(beats) {
    while (beatIndex < beats.length && beats[beatIndex] && beats[beatIndex].type === "command") {
      executeCommand(beats[beatIndex]);
      beatIndex += 1;
    }
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

  function enterNode(nodeId) {
    currentNodeId = nodeId;
    beatIndex = 0;
    activitySession = null;
    lastVoiceKey = null;
    stopVoice();
    stopAllSfx();
    const node = nodes.get(currentNodeId);
    if (node) resetNodeScene(node);
    render();
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
    const choices = (node.choices || []).filter(choicePasses);
    if (choices.length === 0 && node.is_terminal) {
      continueButton.hidden = true;
      return;
    }
    choices.forEach((choice) => {
      choicesEl.appendChild(makeButton(choice.label || "Continue", () => {
        applyWrites(choice.state_writes);
        enterNode(choice.target);
      }));
    });
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

  function labelForRuntimeItem(spec, itemId) {
    const item = (spec.items || []).find((candidate) => candidate && candidate.id === itemId);
    return (item && (item.label || item.name)) || itemId;
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
    const itemDefs = new Map((spec.items || []).filter((item) => item && item.id).map((item) => [item.id, item]));
    const budget = spec.action_budget && typeof spec.action_budget === "object" ? spec.action_budget : null;
    const session = ensureSession(node, () => ({
      visited: new Set(),
      revealed: new Set(),
      items: new Set((spec.items || []).filter((item) => item && item.initially_owned === true).map((item) => item.id)),
      completedCombinations: new Set(),
      selectedItemId: null,
      budget: budget ? Number(budget.initial ?? 0) : null,
      log: [unit.entry_text || "Inspect the scene."],
    }));
    const completion = spec.completion || {};
    const requiredHotspots = completion.required_hotspots || [];
    const requiredItems = completion.required_items || [];
    const complete = requiredHotspots.every((id) => session.visited.has(id))
      && requiredItems.every((id) => session.items.has(id))
      && (completion.conditions || []).every(conditionPasses);

    function addLog(text) {
      if (text) session.log.push(text);
    }

    function collectItems(itemIds, label) {
      (itemIds || []).forEach((itemId) => {
        if (!itemId || session.items.has(itemId)) return;
        session.items.add(itemId);
        addLog(`${label || "Collected"}: ${labelForRuntimeItem(spec, itemId)}`);
      });
    }

    function numericCost(source, key, fallback) {
      if (!budget) return 0;
      if (source && typeof source.cost === "number") return Math.max(0, Number(source.cost));
      if (source && typeof source[key] === "number") return Math.max(0, Number(source[key]));
      if (typeof budget[key] === "number") return Math.max(0, Number(budget[key]));
      if (typeof budget.default_cost === "number") return Math.max(0, Number(budget.default_cost));
      return fallback;
    }

    function spendBudget(cost, failureText) {
      if (!budget || !cost) return true;
      if (Number(session.budget || 0) < cost) {
        addLog(failureText || budget.depleted_text || "You cannot focus on that now.");
        return false;
      }
      session.budget = Number(session.budget || 0) - cost;
      return true;
    }

    function revealHotspots(hotspotIds) {
      (hotspotIds || []).forEach((hotspotId) => {
        if (!hotspotId || session.revealed.has(hotspotId)) return;
        session.revealed.add(hotspotId);
        const hotspot = (spec.hotspots || []).find((candidate) => candidate && candidate.id === hotspotId);
        addLog(`New lead: ${(hotspot && (hotspot.label || hotspot.id)) || hotspotId}`);
      });
    }

    function hotspotVisible(hotspot) {
      return hotspot.initially_visible !== false || session.revealed.has(hotspot.id) || session.visited.has(hotspot.id);
    }

    function hotspotUnlocked(hotspot) {
      const requiredVisited = [...(hotspot.requires || []), ...(hotspot.requires_hotspots || [])];
      const requiredLocalItems = hotspot.requires_items || [];
      return requiredVisited.every((id) => session.visited.has(id)) && requiredLocalItems.every((id) => session.items.has(id));
    }

    function applyInteractionResult(result, fallbackText) {
      addLog(result.text || result.reveal_text || result.feedback || fallbackText);
      const writes = result.state_writes || [];
      if (!result.outcome_id) {
        applyWrites(writes);
      }
      collectItems(result.collects);
      collectItems(result.creates_items, "Added evidence");
      revealHotspots(result.reveals_hotspots);
      if (result.sfx_asset_id) playSfx(result.sfx_asset_id);
      if (result.outcome_id) {
        completeActivity(result.outcome_id, writes);
        return true;
      }
      return false;
    }

    function inspectHotspot(hotspot) {
      if (!hotspotUnlocked(hotspot)) {
        const blockedCost = numericCost(hotspot, "blocked_cost", numericCost(hotspot, "wrong_use_cost", 0));
        if (!spendBudget(blockedCost, hotspot.blocked_text || budget && budget.depleted_text)) {
          render();
          return;
        }
        addLog(hotspot.blocked_text || "Something else needs attention first.");
        render();
        return;
      }
      if ((hotspot.use_results || []).length
        && !hotspot.reveal_text
        && !hotspot.description
        && !(hotspot.collects || []).length
        && !(hotspot.reveals_hotspots || []).length) {
        addLog(hotspot.use_prompt || "Select an item to use here.");
        render();
        return;
      }
      if (!spendBudget(numericCost(hotspot, "inspect_cost", 1), hotspot.depleted_text || budget && budget.depleted_text)) {
        render();
        return;
      }
      session.visited.add(hotspot.id);
      addLog(hotspot.reveal_text || hotspot.description || "You notice something useful.");
      const writes = hotspot.state_writes || [];
      if (!hotspot.outcome_id) {
        applyWrites(writes);
      }
      collectItems(hotspot.collects);
      revealHotspots(hotspot.reveals_hotspots);
      if (hotspot.sfx_asset_id) playSfx(hotspot.sfx_asset_id);
      if (hotspot.outcome_id) {
        completeActivity(hotspot.outcome_id, writes);
        return;
      }
      render();
    }

    function useSelectedItem(hotspot) {
      const selectedItemId = session.selectedItemId;
      if (!selectedItemId) {
        inspectHotspot(hotspot);
        return;
      }
      const result = (hotspot.use_results || []).find((candidate) => candidate && candidate.item_id === selectedItemId);
      if (!result) {
        const wrongCost = numericCost(hotspot, "wrong_use_cost", 1);
        if (!spendBudget(wrongCost, hotspot.default_use_text || spec.default_use_text || budget && budget.depleted_text)) {
          render();
          return;
        }
        addLog(hotspot.default_use_text || spec.default_use_text || `${labelForRuntimeItem(spec, selectedItemId)} does not help there.`);
        render();
        return;
      }
      if (!hotspotUnlocked(hotspot)) {
        const blockedCost = numericCost(hotspot, "blocked_cost", numericCost(hotspot, "wrong_use_cost", 0));
        if (!spendBudget(blockedCost, hotspot.blocked_text || budget && budget.depleted_text)) {
          render();
          return;
        }
        addLog(hotspot.blocked_text || "Something else needs attention first.");
        render();
        return;
      }
      if (!spendBudget(numericCost(result, "use_cost", numericCost(hotspot, "use_cost", 1)), result.depleted_text || budget && budget.depleted_text)) {
        render();
        return;
      }
      session.visited.add(hotspot.id);
      session.selectedItemId = null;
      if (!applyInteractionResult(result, "That worked.")) {
        render();
      }
    }

    function presentSelectedItem(target) {
      if (!session.selectedItemId) {
        addLog(target.prompt || "Select an item first.");
        render();
        return;
      }
      const accepted = (target.accepted_items || []).find((candidate) => candidate && candidate.item_id === session.selectedItemId);
      if (!accepted) {
        addLog(target.default_text || `${labelForRuntimeItem(spec, session.selectedItemId)} does not change the conversation.`);
        render();
        return;
      }
      session.selectedItemId = null;
      if (!applyInteractionResult(accepted, "The evidence lands.")) {
        render();
      }
    }

    function combinationAvailable(combo) {
      return !session.completedCombinations.has(combo.id)
        && (combo.item_ids || []).every((itemId) => session.items.has(itemId));
    }

    function runCombination(combo) {
      if (!combinationAvailable(combo)) {
        addLog(combo.blocked_text || "You do not have the right evidence for that.");
        render();
        return;
      }
      if (!spendBudget(numericCost(combo, "combine_cost", 1), combo.depleted_text || budget && budget.depleted_text)) {
        render();
        return;
      }
      session.completedCombinations.add(combo.id);
      if (!applyInteractionResult(combo, combo.text || combo.feedback || "The evidence fits together.")) {
        render();
      }
    }

    choicesEl.innerHTML = "";
    continueButton.hidden = true;
    speakerEl.textContent = "Inspect";
    lineEl.textContent = spec.prompt || unit.entry_text || "Choose what to inspect.";
    const scene = spec.scene || {};
    if (scene.background_asset_id) {
      setBackground(scene.background_asset_id);
    }

    const panel = makeEl("div", "gameplay-panel");
    if (budget) {
      const meter = makeEl("div", "budget-strip");
      meter.appendChild(makeEl("strong", "", budget.label || budget.id || "Focus"));
      meter.appendChild(makeEl("span", "budget-value", String(session.budget ?? 0)));
      panel.appendChild(meter);
    }
    const log = makeEl("div", "activity-log");
    session.log.slice(-5).forEach((entry) => log.appendChild(makeEl("p", "", entry)));
    panel.appendChild(log);

    if ((spec.items || []).length) {
      const inventory = makeEl("div", "inventory-strip");
      inventory.appendChild(makeEl("strong", "", "Inventory"));
      const itemButtons = makeEl("div", "inventory-items");
      if (session.items.size === 0) {
        itemButtons.appendChild(makeEl("span", "empty-inventory", "No items"));
      }
      Array.from(session.items).forEach((itemId) => {
        const item = itemDefs.get(itemId) || {};
        const button = makeButton(item.label || itemId, () => {
          session.selectedItemId = session.selectedItemId === itemId ? null : itemId;
          render();
        }, session.selectedItemId === itemId ? "inventory-item selected" : "inventory-item");
        if (item.description) button.title = item.description;
        itemButtons.appendChild(button);
      });
      inventory.appendChild(itemButtons);
      panel.appendChild(inventory);
    }

    const availableCombinations = (spec.evidence_combinations || []).filter((combo) => combo && combo.id && combinationAvailable(combo));
    if (availableCombinations.length) {
      const combine = makeEl("div", "combine-panel");
      combine.appendChild(makeEl("strong", "", "Connect Evidence"));
      const comboGrid = makeEl("div", "gameplay-actions");
      availableCombinations.forEach((combo) => {
        comboGrid.appendChild(makeButton(combo.label || combo.id, () => runCombination(combo)));
      });
      combine.appendChild(comboGrid);
      panel.appendChild(combine);
    }

    const scenePanel = makeEl("div", "interaction-scene");
    const backgroundAsset = assets.get(scene.background_asset_id);
    if (backgroundAsset && backgroundAsset.runtime_path) {
      scenePanel.style.backgroundImage = `linear-gradient(180deg, rgba(8, 9, 12, 0.1), rgba(8, 9, 12, 0.74)), url("${backgroundAsset.runtime_path}")`;
      scenePanel.classList.add("has-scene-image");
    }
    const visibleHotspots = (spec.hotspots || []).filter((hotspot) => hotspot && hotspot.id && hotspotVisible(hotspot));
    const useOverlay = scene.layout === "overlay" && visibleHotspots.some((hotspot) => hotspot.bounds);
    if (useOverlay) {
      scenePanel.classList.add("overlay-mode");
      scenePanel.classList.add(`labels-${scene.show_hotspot_labels || "hover"}`);
    }
    const overlayHotspots = useOverlay ? visibleHotspots.filter((hotspot) => hotspot.bounds) : [];
    const gridHotspots = useOverlay ? visibleHotspots.filter((hotspot) => !hotspot.bounds) : visibleHotspots;

    function renderHotspotButton(hotspot, overlay) {
      const unlocked = hotspotUnlocked(hotspot);
      const done = session.visited.has(hotspot.id);
      const label = `${hotspot.label || hotspot.id}${done ? " (done)" : ""}`;
      let button;
      if (overlay) {
        button = document.createElement("button");
        button.type = "button";
        button.className = unlocked ? "hotspot-button hotspot-region" : "hotspot-button hotspot-region locked";
        button.addEventListener("click", () => useSelectedItem(hotspot));
      } else {
        button = makeButton(label, () => useSelectedItem(hotspot), unlocked ? "hotspot-button" : "hotspot-button locked");
      }
      if (overlay) {
        button.setAttribute("aria-label", label);
        const bounds = hotspot.bounds || {};
        button.style.left = `${Number(bounds.x || 0) * 100}%`;
        button.style.top = `${Number(bounds.y || 0) * 100}%`;
        button.style.width = `${Number(bounds.w || 0.12) * 100}%`;
        button.style.height = `${Number(bounds.h || 0.1) * 100}%`;
        button.appendChild(makeEl("span", "hotspot-label", label));
      }
      if (hotspot.description) button.title = hotspot.description;
      const asset = assets.get(hotspot.asset_id);
      if (asset && asset.runtime_path) {
        const image = document.createElement("img");
        image.src = asset.runtime_path;
        image.alt = "";
        button.prepend(image);
      }
      return button;
    }

    overlayHotspots.forEach((hotspot) => {
      scenePanel.appendChild(renderHotspotButton(hotspot, true));
    });
    const grid = makeEl("div", "hotspot-grid interaction-hotspots");
    gridHotspots.forEach((hotspot) => {
      grid.appendChild(renderHotspotButton(hotspot, false));
    });
    if (gridHotspots.length) {
      scenePanel.appendChild(grid);
    }
    panel.appendChild(scenePanel);

    if ((spec.present_targets || []).length) {
      const present = makeEl("div", "present-targets");
      present.appendChild(makeEl("strong", "", "Present"));
      const targetGrid = makeEl("div", "hotspot-grid");
      (spec.present_targets || []).forEach((target) => {
        targetGrid.appendChild(makeButton(target.label || target.id || "Present", () => presentSelectedItem(target)));
      });
      present.appendChild(targetGrid);
      panel.appendChild(present);
    }

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
      choicesEl.innerHTML = "";
      return;
    }
    titleEl.textContent = story.title || "Narrative Game";
    nodeTitleEl.textContent = node.title || node.id;
    stage.classList.toggle("gameplay-active", Boolean(node.gameplay));
    choicesEl.innerHTML = "";
    if (node.gameplay) {
      renderGameplay(node);
      return;
    }
    const beats = node.beats && node.beats.length ? node.beats : [{ speaker: "Narrator", text: "..." }];
    advancePastCommands(beats);
    if (beatIndex >= beats.length) {
      renderChoices(node);
      return;
    }
    const beat = beats[Math.min(beatIndex, beats.length - 1)];
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
    beatIndex += 1;
    render();
  });

  restartButton.addEventListener("click", () => {
    currentNodeId = story.start_node_id;
    beatIndex = 0;
    activitySession = null;
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
