# CLR metadata inventory

Own diagnostic for local DLL/EXE files. Requires .NET SDK10; no NuGet packages.
It reads signatures and member references with PEReader, without loading or
executing the target assembly. It is not a decompiler, security sandbox or full
IL audit. JSON includes local paths and SHA-256; review before sharing.

From repository root:

```powershell
dotnet build tools/assembly_inventory -o tmp/geoagr-inspector --configfile tools/assembly_inventory/NuGet.Config
dotnet tmp/geoagr-inspector/assembly_inventory.dll <input.dll> <input.exe>
```

Native PE files return `managed: false`. Malformed/non-PE input fails with nonzero
exit. No assemblies from the inspected distribution are copied to the project.
