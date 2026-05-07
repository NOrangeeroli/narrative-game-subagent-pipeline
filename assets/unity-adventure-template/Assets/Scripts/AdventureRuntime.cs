using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public sealed class AdventureRuntime : MonoBehaviour
{
    [Serializable] public class RuntimeManifest { public string start_node_id; public string start_level_id; public RuntimeLevel[] levels; public RuntimeInteraction[] interactions; public NodeLevel[] node_levels; public EndingEntry[] endings; }
    [Serializable] public class RuntimeLevel { public string level_id; public string title; public string summary; public float width; public float height; public float spawn_x; public float spawn_y; public bool is_terminal; }
    [Serializable] public class RuntimeInteraction { public string interaction_id; public string level_id; public string kind; public string label; public float x; public float y; public string edge_id; public string target_node_id; }
    [Serializable] public class NodeLevel { public string node_id; public string level_id; }
    [Serializable] public class EndingEntry { public string ending_id; public string terminal_node_id; public string level_id; public string title; }

    private RuntimeManifest manifest;
    private readonly Dictionary<string, RuntimeLevel> levels = new Dictionary<string, RuntimeLevel>();
    private readonly Dictionary<string, string> nodeToLevel = new Dictionary<string, string>();
    private readonly List<GameObject> spawned = new List<GameObject>();
    private GameObject player;
    private RuntimeLevel currentLevel;
    private string currentLevelId;
    private string currentNodeId;
    private string message;
    private bool showHelp = true;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Bootstrap()
    {
        if (FindObjectOfType<AdventureRuntime>() != null) return;
        var runtime = new GameObject("AdventureRuntime");
        runtime.AddComponent<AdventureRuntime>();
        DontDestroyOnLoad(runtime);
    }

    private void Awake()
    {
        LoadManifest();
        BuildLookup();
        var cameraObject = Camera.main != null ? Camera.main.gameObject : new GameObject("Main Camera");
        if (Camera.main == null) cameraObject.AddComponent<Camera>();
        cameraObject.tag = "MainCamera";
        Camera.main.orthographic = true;
        Camera.main.orthographicSize = 5.5f;
        GoToNode(manifest != null ? manifest.start_node_id : null);
    }

    private void LoadManifest()
    {
        var path = Path.Combine(Application.streamingAssetsPath, "adventure-runtime.json");
        if (!File.Exists(path))
        {
            Debug.LogError("Missing StreamingAssets/adventure-runtime.json");
            message = "Missing adventure runtime manifest.";
            return;
        }
        manifest = JsonUtility.FromJson<RuntimeManifest>(File.ReadAllText(path));
    }

    private void BuildLookup()
    {
        levels.Clear();
        nodeToLevel.Clear();
        if (manifest == null) return;
        if (manifest.levels != null)
        {
            foreach (var level in manifest.levels)
            {
                if (level != null && !string.IsNullOrEmpty(level.level_id)) levels[level.level_id] = level;
            }
        }
        if (manifest.node_levels != null)
        {
            foreach (var binding in manifest.node_levels)
            {
                if (binding != null && !string.IsNullOrEmpty(binding.node_id) && !string.IsNullOrEmpty(binding.level_id))
                {
                    nodeToLevel[binding.node_id] = binding.level_id;
                }
            }
        }
    }

    private void GoToNode(string nodeId)
    {
        if (manifest == null) return;
        currentNodeId = string.IsNullOrEmpty(nodeId) ? manifest.start_node_id : nodeId;
        string levelId;
        if (!nodeToLevel.TryGetValue(currentNodeId, out levelId)) levelId = manifest.start_level_id;
        GoToLevel(levelId);
    }

    private void GoToLevel(string levelId)
    {
        currentLevelId = levelId;
        foreach (var obj in spawned) if (obj != null) Destroy(obj);
        spawned.Clear();
        RuntimeLevel level;
        if (!levels.TryGetValue(levelId, out level))
        {
            message = "Missing level: " + levelId;
            return;
        }
        currentLevel = level;
        message = string.IsNullOrEmpty(level.summary) ? level.title : level.summary;
        BuildLevel(level);
        SpawnInteractions(level.level_id);
    }

    private void BuildLevel(RuntimeLevel level)
    {
        var floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
        floor.name = "Floor";
        floor.transform.position = new Vector3(level.width * 0.5f, level.height * 0.5f, 0.35f);
        floor.transform.localScale = new Vector3(level.width, level.height, 0.1f);
        floor.GetComponent<Renderer>().material.color = new Color(0.24f, 0.33f, 0.24f);
        Destroy(floor.GetComponent<Collider>());
        spawned.Add(floor);

        player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        player.name = "Player";
        player.transform.position = new Vector3(level.spawn_x, Mathf.Clamp(level.spawn_y, 1.0f, Mathf.Max(1.0f, level.height - 1.0f)), -0.1f);
        player.transform.localScale = new Vector3(0.7f, 1.1f, 0.7f);
        player.GetComponent<Renderer>().material.color = new Color(0.78f, 0.32f, 0.28f);
        Destroy(player.GetComponent<Collider>());
        spawned.Add(player);
    }

    private void SpawnInteractions(string levelId)
    {
        if (manifest == null || manifest.interactions == null) return;
        foreach (var interaction in manifest.interactions)
        {
            if (interaction == null || interaction.level_id != levelId) continue;
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            obj.name = "Interaction:" + interaction.interaction_id;
            obj.transform.position = new Vector3(interaction.x, interaction.y, -0.2f);
            obj.transform.localScale = InteractionScale(interaction.kind);
            obj.GetComponent<Renderer>().material.color = ColorForKind(interaction.kind);
            Destroy(obj.GetComponent<Collider>());
            obj.AddComponent<AdventureInteractionMarker>().interaction = interaction;
            spawned.Add(obj);
        }
    }

    private Vector3 InteractionScale(string kind)
    {
        switch (kind)
        {
            case "talk": return new Vector3(0.55f, 1.0f, 0.55f);
            case "open": return new Vector3(0.85f, 1.15f, 0.45f);
            case "tend_garden": return new Vector3(1.05f, 0.55f, 0.45f);
            default: return new Vector3(0.62f, 0.62f, 0.62f);
        }
    }

    private Color ColorForKind(string kind)
    {
        switch (kind)
        {
            case "listen": return new Color(0.3f, 0.5f, 0.9f);
            case "talk": return new Color(0.8f, 0.65f, 0.2f);
            case "open": return new Color(0.45f, 0.28f, 0.14f);
            case "tend_garden": return new Color(0.18f, 0.65f, 0.28f);
            default: return new Color(0.72f, 0.72f, 0.72f);
        }
    }

    private void Update()
    {
        if (player != null)
        {
            var move = ReadMovement();
            if (move.sqrMagnitude > 1f) move.Normalize();
            var pos = player.transform.position + new Vector3(move.x, move.y, 0) * 4.0f * Time.deltaTime;
            if (currentLevel != null)
            {
                pos.x = Mathf.Clamp(pos.x, 0.6f, Mathf.Max(0.6f, currentLevel.width - 0.6f));
                pos.y = Mathf.Clamp(pos.y, 1.0f, Mathf.Max(1.0f, currentLevel.height - 0.6f));
            }
            player.transform.position = pos;
            if (Camera.main != null)
            {
                var cam = Camera.main.transform.position;
                cam.x = Mathf.Lerp(cam.x, player.transform.position.x, Time.deltaTime * 5f);
                cam.y = Mathf.Lerp(cam.y, player.transform.position.y + 1.2f, Time.deltaTime * 5f);
                cam.z = -10f;
                Camera.main.transform.position = cam;
            }
        }
        if (Input.GetKeyDown(KeyCode.E) || Input.GetKeyDown(KeyCode.Space)) ActivateNearestInteraction();
    }

    private Vector2 ReadMovement()
    {
        var x = 0f;
        var y = 0f;
        if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) x -= 1f;
        if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) x += 1f;
        if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) y += 1f;
        if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) y -= 1f;
        return new Vector2(x, y);
    }

    private void ActivateNearestInteraction()
    {
        var nearest = FindNearestInteraction();
        if (nearest == null)
        {
            message = "No interaction nearby.";
            return;
        }
        message = string.IsNullOrEmpty(nearest.label) ? nearest.kind : nearest.label;
        if (!string.IsNullOrEmpty(nearest.target_node_id)) GoToNode(nearest.target_node_id);
    }

    private RuntimeInteraction FindNearestInteraction()
    {
        if (player == null || manifest == null || manifest.interactions == null) return null;
        RuntimeInteraction best = null;
        var bestDistance = 2.2f;
        foreach (var interaction in manifest.interactions)
        {
            if (interaction == null || interaction.level_id != currentLevelId) continue;
            var distance = Vector2.Distance(new Vector2(player.transform.position.x, player.transform.position.y), new Vector2(interaction.x, interaction.y));
            if (distance <= bestDistance)
            {
                bestDistance = distance;
                best = interaction;
            }
        }
        return best;
    }

    private void OnGUI()
    {
        GUI.Box(new Rect(16, 16, Screen.width - 32, 104), "");
        GUI.Label(new Rect(32, 28, Screen.width - 64, 24), currentLevelId ?? "No level");
        GUI.Label(new Rect(32, 54, Screen.width - 64, 54), message ?? "");
        if (showHelp) GUI.Label(new Rect(32, 92, Screen.width - 64, 24), "Keyboard: WASD/arrows move, E/Space interact. Mobile: use buttons below.");

        var buttonY = Screen.height - 88;
        if (GUI.RepeatButton(new Rect(24, buttonY, 64, 56), "<")) MoveTouch(new Vector2(-1, 0));
        if (GUI.RepeatButton(new Rect(96, buttonY, 64, 56), ">")) MoveTouch(new Vector2(1, 0));
        if (GUI.RepeatButton(new Rect(168, buttonY - 60, 64, 56), "^")) MoveTouch(new Vector2(0, 1));
        if (GUI.RepeatButton(new Rect(168, buttonY, 64, 56), "v")) MoveTouch(new Vector2(0, -1));
        if (GUI.Button(new Rect(Screen.width - 124, buttonY, 96, 56), "Action")) ActivateNearestInteraction();
        if (GUI.Button(new Rect(Screen.width - 232, buttonY, 96, 56), "Help")) showHelp = !showHelp;
    }

    private void MoveTouch(Vector2 direction)
    {
        if (player == null) return;
        if (direction.sqrMagnitude > 1f) direction.Normalize();
        var pos = player.transform.position + new Vector3(direction.x, direction.y, 0) * 4.0f * Time.deltaTime;
        if (currentLevel != null)
        {
            pos.x = Mathf.Clamp(pos.x, 0.6f, Mathf.Max(0.6f, currentLevel.width - 0.6f));
            pos.y = Mathf.Clamp(pos.y, 1.0f, Mathf.Max(1.0f, currentLevel.height - 0.6f));
        }
        player.transform.position = pos;
    }
}

public sealed class AdventureInteractionMarker : MonoBehaviour
{
    public AdventureRuntime.RuntimeInteraction interaction;
}
