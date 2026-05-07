public static class BuildAutomation
{
    public static void BuildDesktop()
    {
#if UNITY_EDITOR
        UnityEditor.BuildPipeline.BuildPlayer(new UnityEditor.BuildPlayerOptions
        {
            scenes = new string[0],
            locationPathName = "Builds/AdventureDesktop",
            target = UnityEditor.BuildTarget.StandaloneOSX,
            options = UnityEditor.BuildOptions.None
        });
#endif
    }
}
