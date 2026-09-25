using UnrealBuildTool;
using System.IO;

public class GISGame : ModuleRules
{
    public GISGame(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bEnableExceptions = true; // The portable solver rejects invalid time steps with std::invalid_argument.

        PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
        PrivateDependencyModuleNames.AddRange(new string[] { "Json", "ProceduralMeshComponent" });

        // This project sits beside ../sim_core so Unreal and the command-line tests compile one solver.
        PublicIncludePaths.Add(Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "..", "sim_core")));
    }
}
