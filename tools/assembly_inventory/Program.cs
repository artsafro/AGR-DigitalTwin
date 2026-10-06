// Read metadata only. Never load or invoke the inspected assembly.
using System.Collections.Immutable;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;
using System.Security.Cryptography;
using System.Text.Json;

if (args.Length == 0)
{
    Console.Error.WriteLine("Usage: assembly_inventory <PE file> [PE file ...]");
    return 2;
}
var results = new List<object>();
foreach (string path in args)
{
    using var stream = File.OpenRead(path);
    var hash = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    stream.Position = 0;
    using var pe = new PEReader(stream);
    if (!pe.HasMetadata)
    {
        results.Add(new { path = Path.GetFullPath(path), sha256 = hash, managed = false });
        continue;
    }
    var reader = pe.GetMetadataReader();
    var provider = new TypeNames();
    var types = new List<object>();
    foreach (var handle in reader.TypeDefinitions)
    {
        var type = reader.GetTypeDefinition(handle);
        var methods = new List<object>();
        foreach (var mh in type.GetMethods())
        {
            var m = reader.GetMethodDefinition(mh);
            var signature = m.DecodeSignature(provider, (object?)null);
            methods.Add(new {
                name = reader.GetString(m.Name), attributes = m.Attributes.ToString(),
                returns = signature.ReturnType, parameter_types = signature.ParameterTypes,
                parameters = m.GetParameters().Select(ph => {
                    var p = reader.GetParameter(ph);
                    return new { sequence = p.SequenceNumber, name = reader.GetString(p.Name), attributes = p.Attributes.ToString() };
                }).ToArray(),
                il_bytes = m.RelativeVirtualAddress == 0 ? 0 : pe.GetMethodBody(m.RelativeVirtualAddress).GetILBytes()!.Length
            });
        }
        types.Add(new { name = provider.GetTypeFromDefinition(reader, handle, 0), attributes = type.Attributes.ToString(), methods });
    }
    var references = reader.AssemblyReferences.Select(h => {
        var a = reader.GetAssemblyReference(h);
        return new { name = reader.GetString(a.Name), version = a.Version.ToString() };
    }).ToArray();
    var members = reader.MemberReferences.Select(h => {
        var m = reader.GetMemberReference(h);
        return new { owner = provider.EntityName(reader, m.Parent), name = reader.GetString(m.Name) };
    }).ToArray();
    var definition = reader.GetAssemblyDefinition();
    results.Add(new { path = Path.GetFullPath(path), sha256 = hash, managed = true,
        assembly = reader.GetString(definition.Name), version = definition.Version.ToString(),
        references, members, types });
}
Console.WriteLine(JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = true }));
return 0;

sealed class TypeNames : ISignatureTypeProvider<string, object?>
{
    static string Qualified(string ns, string name) => ns.Length == 0 ? name : ns + "." + name;
    public string GetTypeFromDefinition(MetadataReader r, TypeDefinitionHandle h, byte kind)
    {
        var t = r.GetTypeDefinition(h);
        return Qualified(r.GetString(t.Namespace), r.GetString(t.Name));
    }
    public string GetTypeFromReference(MetadataReader r, TypeReferenceHandle h, byte kind)
    {
        var t = r.GetTypeReference(h);
        return Qualified(r.GetString(t.Namespace), r.GetString(t.Name));
    }
    public string EntityName(MetadataReader r, EntityHandle h) => h.Kind switch {
        HandleKind.TypeDefinition => GetTypeFromDefinition(r, (TypeDefinitionHandle)h, 0),
        HandleKind.TypeReference => GetTypeFromReference(r, (TypeReferenceHandle)h, 0),
        HandleKind.TypeSpecification => GetTypeFromSpecification(r, null, (TypeSpecificationHandle)h, 0),
        _ => h.Kind.ToString()
    };
    public string GetTypeFromSpecification(MetadataReader r, object? context, TypeSpecificationHandle h, byte kind) => r.GetTypeSpecification(h).DecodeSignature(this, context);
    public string GetPrimitiveType(PrimitiveTypeCode code) => code.ToString();
    public string GetSZArrayType(string element) => element + "[]";
    public string GetArrayType(string element, ArrayShape shape) => element + "[" + new string(',', shape.Rank - 1) + "]";
    public string GetByReferenceType(string element) => element + "&";
    public string GetPointerType(string element) => element + "*";
    public string GetPinnedType(string element) => element + " pinned";
    public string GetModifiedType(string modifier, string element, bool required) => element + (required ? " modreq(" : " modopt(") + modifier + ")";
    public string GetGenericInstantiation(string type, ImmutableArray<string> args) => type + "<" + string.Join(",", args) + ">";
    public string GetGenericMethodParameter(object? context, int index) => "!!" + index;
    public string GetGenericTypeParameter(object? context, int index) => "!" + index;
    public string GetFunctionPointerType(MethodSignature<string> sig) => "fn(" + string.Join(",", sig.ParameterTypes) + ")->" + sig.ReturnType;
}
