using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace XiongdaImporter
{
    public static class XiongdaRunImporter
    {
        private const string DefaultExtractRoot = "/home/kaifeng/extra/Downloads/fudan/IC_competition/unity/extracted_xiongda_run";
        private const string DefaultAssetRoot = "Assets/XiongdaImported";
        private const string AutoImportTriggerFileName = ".xiongda_auto_import";

        [InitializeOnLoadMethod]
        private static void RegisterAutoImportHook()
        {
            EditorApplication.delayCall += TryRunAutoImport;
        }

        [MenuItem("Tools/Xiongda/Import Left Variant")]
        private static void ImportLeftVariant()
        {
            ImportKnownVariant("xiongda_left_slide_variant");
        }

        [MenuItem("Tools/Xiongda/Import Base Default")]
        private static void ImportBaseDefault()
        {
            ImportKnownVariant("xiongda_base_default");
        }

        [MenuItem("Tools/Xiongda/Import Main Menu Showcase")]
        private static void ImportMainMenuShowcase()
        {
            ImportKnownVariant("xiongda_main_menu_showcase");
        }

        public static void ImportBaseDefaultBatch()
        {
            ImportKnownVariant("xiongda_base_default");
        }

        public static void ImportMainMenuShowcaseBatch()
        {
            ImportKnownVariant("xiongda_main_menu_showcase");
        }

        [MenuItem("Tools/Xiongda/Import Xionger Base Default")]
        private static void ImportXiongerBaseDefault()
        {
            ImportKnownVariant("xionger_base_default");
        }

        public static void ImportXiongerBaseDefaultBatch()
        {
            ImportKnownVariant("xionger_base_default");
        }

        [MenuItem("Tools/Xiongda/Import Guangtouqiang Base Default")]
        private static void ImportGuangtouqiangBaseDefault()
        {
            ImportKnownVariant("guangtouqiang_base_default");
        }

        public static void ImportGuangtouqiangBaseDefaultBatch()
        {
            ImportKnownVariant("guangtouqiang_base_default");
        }

        public static void ImportLeftVariantBatch()
        {
            ImportKnownVariant("xiongda_left_slide_variant");
        }

        [MenuItem("Tools/Xiongda/Import Right Variant")]
        private static void ImportRightVariant()
        {
            ImportKnownVariant("xiongda_right_slide_variant");
        }

        public static void ImportRightVariantBatch()
        {
            ImportKnownVariant("xiongda_right_slide_variant");
        }

        [MenuItem("Tools/Xiongda/Import Variant From Folder...")]
        private static void ImportVariantFromFolder()
        {
            var folder = EditorUtility.OpenFolderPanel("Select extracted xiongda variant folder", DefaultExtractRoot, string.Empty);
            if (string.IsNullOrEmpty(folder))
            {
                return;
            }

            ImportVariant(folder);
        }

        private static void ImportKnownVariant(string variantName)
        {
            ImportVariant(Path.Combine(DefaultExtractRoot, variantName));
        }

        private static void TryRunAutoImport()
        {
            if (EditorApplication.isCompiling || EditorApplication.isUpdating)
            {
                EditorApplication.delayCall += TryRunAutoImport;
                return;
            }

            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            var triggerPath = Path.Combine(projectRoot, AutoImportTriggerFileName);
            if (!File.Exists(triggerPath))
            {
                return;
            }

            string variantName;
            try
            {
                variantName = File.ReadAllText(triggerPath).Trim();
                File.Delete(triggerPath);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                return;
            }

            if (string.IsNullOrEmpty(variantName))
            {
                variantName = "xiongda_left_slide_variant";
            }

            if (VariantAlreadyImported(variantName))
            {
                Debug.Log($"Xiongda auto-import skipped because prefab already exists for {variantName}");
                TryRunPostImportSetup(variantName);
                return;
            }

            Debug.Log($"Xiongda auto-import trigger detected: {variantName}");
            ImportKnownVariant(variantName);
            TryRunPostImportSetup(variantName);
        }

        private static bool VariantAlreadyImported(string variantName)
        {
            var prefabPath = $"{DefaultAssetRoot}/{variantName}/Prefabs/熊大@蒙皮.prefab";
            return File.Exists(Path.Combine(Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath, prefabPath));
        }

        private static void ImportVariant(string sourceVariantDirectory)
        {
            var summaryPath = Path.Combine(sourceVariantDirectory, "summary.json");
            if (!File.Exists(summaryPath))
            {
                if (!Application.isBatchMode)
                {
                    EditorUtility.DisplayDialog("Xiongda Import", $"summary.json not found in:\n{sourceVariantDirectory}", "OK");
                }
                return;
            }

            var variantName = Path.GetFileName(sourceVariantDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
            var importer = new VariantImporter(sourceVariantDirectory, $"{DefaultAssetRoot}/{variantName}");

            try
            {
                importer.Import();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                if (!Application.isBatchMode)
                {
                    EditorUtility.DisplayDialog("Xiongda Import Failed", ex.Message, "OK");
                }
            }
        }

        private static void TryRunPostImportSetup(string variantName)
        {
            if (variantName != "xiongda_main_menu_showcase")
            {
                return;
            }

            try
            {
                // Keep the scene synchronized with the imported showcase prefab.
                XiongdaSceneSetup.CreateMainMenuShowcaseSceneBatch();
                Debug.Log("Xiongda auto-import also refreshed the main menu showcase scene.");
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
        }

        private sealed class VariantImporter
        {
            private readonly string sourceVariantDirectory;
            private readonly string extractRootDirectory;
            private readonly string targetAssetRoot;
            private readonly string projectRootDirectory;

            private readonly Dictionary<string, Transform> transformByPath = new Dictionary<string, Transform>();
            private readonly Dictionary<string, Texture2D> textureCache = new Dictionary<string, Texture2D>();
            private readonly Dictionary<string, Material> materialCache = new Dictionary<string, Material>();
            private readonly Dictionary<string, Mesh> meshCache = new Dictionary<string, Mesh>();
            private readonly Dictionary<string, AnimationClip> clipCache = new Dictionary<string, AnimationClip>();

            private Dictionary<string, object> summary;
            private GameObject rootObject;

            public VariantImporter(string sourceVariantDirectory, string targetAssetRoot)
            {
                this.sourceVariantDirectory = sourceVariantDirectory;
                extractRootDirectory = Directory.GetParent(sourceVariantDirectory)?.FullName ?? sourceVariantDirectory;
                this.targetAssetRoot = targetAssetRoot;
                projectRootDirectory = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            }

            public void Import()
            {
                summary = LoadJsonObject(Path.Combine(sourceVariantDirectory, "summary.json"));

                EnsureAssetFolder(string.Empty);
                EnsureAssetFolder("Textures");
                EnsureAssetFolder("Materials");
                EnsureAssetFolder("Meshes");
                EnsureAssetFolder("Animations");
                EnsureAssetFolder("Prefabs");
                AssetDatabase.Refresh();

                BuildHierarchy();
                ImportRenderers();
                ImportAnimationsAndConfigureRoot();
                AssetDatabase.SaveAssets();
                AssetDatabase.Refresh();

                CreatePreviewIfNeeded();
                SavePrefabAndSelect();
            }

            private void BuildHierarchy()
            {
                var hierarchyPath = Path.Combine(sourceVariantDirectory, "hierarchy.json");
                var nodes = LoadJsonArray(hierarchyPath);
                nodes.Sort((a, b) => GetPathDepth(GetString(AsDict(a), "path")).CompareTo(GetPathDepth(GetString(AsDict(b), "path"))));

                foreach (var nodeObject in nodes)
                {
                    var node = AsDict(nodeObject);
                    var name = GetString(node, "name");
                    var path = GetString(node, "path");
                    var parentPath = GetString(node, "parent_path");

                    GameObject go;
                    if (string.IsNullOrEmpty(path))
                    {
                        go = new GameObject(name);
                        rootObject = go;
                    }
                    else
                    {
                        var parent = FindTransform(parentPath);
                        go = new GameObject(name);
                        go.transform.SetParent(parent, false);
                    }

                    ApplyLocalTransform(go.transform, node);
                    transformByPath[path] = go.transform;
                }

                if (rootObject == null)
                {
                    throw new InvalidOperationException("Failed to build hierarchy root.");
                }
            }

            private void ImportRenderers()
            {
                var rendererEntries = GetList(summary, "renderers");
                foreach (var rendererEntry in rendererEntries)
                {
                    var rendererSummary = AsDict(rendererEntry);
                    var rendererJsonPath = ResolveExtractPath(GetString(rendererSummary, "mesh_json"));
                    var rendererData = LoadJsonObject(rendererJsonPath);
                    AttachRenderer(rendererData);
                }
            }

            private void ImportAnimationsAndConfigureRoot()
            {
                var animationInfo = AsDict(summary["animation_component"]);
                var animationComponent = EnsureComponent<Animation>(rootObject);
                animationComponent.playAutomatically = false;
                animationComponent.wrapMode = WrapMode.Loop;
                animationComponent.animatePhysics = GetBool(animationInfo, "animate_physics");

                var clipEntries = GetList(animationInfo, "clips");
                AnimationClip defaultClip = null;

                foreach (var clipEntry in clipEntries)
                {
                    var clipSummary = AsDict(clipEntry);
                    var clip = ImportClip(clipSummary);
                    animationComponent.AddClip(clip, clip.name);
                    if (clip.name == "Run")
                    {
                        defaultClip = clip;
                    }
                }

                if (defaultClip == null && clipEntries.Count > 0)
                {
                    defaultClip = ImportClip(AsDict(clipEntries[0]));
                }

                if (defaultClip != null)
                {
                    animationComponent.clip = defaultClip;
                }

                var player = EnsureComponent<XiongdaPlayOnStart>(rootObject);
                EditorUtility.SetDirty(player);
                EditorUtility.SetDirty(animationComponent);
            }

            private void AttachRenderer(Dictionary<string, object> rendererData)
            {
                var transform = FindTransform(GetString(rendererData, "gameobject_path"));
                var renderer = EnsureComponent<SkinnedMeshRenderer>(transform.gameObject);
                var mesh = ImportMesh(rendererData);
                renderer.sharedMesh = mesh;
                renderer.sharedMaterials = ImportMaterials(GetList(rendererData, "materials"));
                renderer.rootBone = FindOptionalTransform(GetString(rendererData, "root_bone_path"));
                renderer.bones = ImportBones(GetList(rendererData, "bones"));
                renderer.updateWhenOffscreen = true;
                renderer.localBounds = ExpandBounds(mesh.bounds, 1.05f);

                EditorUtility.SetDirty(renderer);
            }

            private Mesh ImportMesh(Dictionary<string, object> rendererData)
            {
                var key = $"{GetString(rendererData, "mesh_file")}_{GetInt(rendererData, "mesh_path_id")}";
                if (meshCache.TryGetValue(key, out var cached))
                {
                    return cached;
                }

                var meshName = $"{SafeFileName(GetString(rendererData, "mesh_name"))}_{key}.asset";
                var assetPath = $"{targetAssetRoot}/Meshes/{meshName}";
                var mesh = AssetDatabase.LoadAssetAtPath<Mesh>(assetPath);
                if (mesh == null)
                {
                    mesh = new Mesh();
                    AssetDatabase.CreateAsset(mesh, assetPath);
                }

                mesh.Clear();
                mesh.name = GetString(rendererData, "mesh_name");

                var vertices = ToVector3Array(GetList(rendererData, "vertices"));
                var normals = ToVector3Array(GetList(rendererData, "normals"));
                var tangents = ToVector4Array(GetList(rendererData, "tangents"));
                var uv = ToVector2Array(GetList(rendererData, "uv0"));
                var indices = ToIntArray(GetList(rendererData, "indices"));
                var boneIndices = GetList(rendererData, "bone_indices");
                var boneWeights = GetList(rendererData, "bone_weights");
                var bindPoses = ToMatrixArray(GetList(rendererData, "bind_poses"));

                mesh.indexFormat = vertices.Length > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
                mesh.vertices = vertices;
                if (normals.Length == vertices.Length)
                {
                    mesh.normals = normals;
                }

                if (tangents.Length == vertices.Length)
                {
                    mesh.tangents = tangents;
                }

                if (uv.Length == vertices.Length)
                {
                    mesh.uv = uv;
                }

                mesh.triangles = indices;
                if (bindPoses.Length > 0)
                {
                    mesh.bindposes = bindPoses;
                }

                if (boneIndices.Count == vertices.Length && boneWeights.Count == vertices.Length)
                {
                    mesh.boneWeights = ToBoneWeights(boneIndices, boneWeights);
                }

                if (normals.Length != vertices.Length)
                {
                    mesh.RecalculateNormals();
                }

                mesh.RecalculateBounds();
                EditorUtility.SetDirty(mesh);
                meshCache[key] = mesh;
                return mesh;
            }

            private Material[] ImportMaterials(List<object> materialEntries)
            {
                var materials = new Material[materialEntries.Count];
                for (var i = 0; i < materialEntries.Count; i++)
                {
                    materials[i] = ImportMaterial(AsDict(materialEntries[i]));
                }

                return materials;
            }

            private Material ImportMaterial(Dictionary<string, object> materialData)
            {
                var key = $"{GetString(materialData, "file")}_{GetInt(materialData, "path_id")}";
                if (materialCache.TryGetValue(key, out var cached))
                {
                    return cached;
                }

                var materialName = $"{SafeFileName(GetString(materialData, "name"))}_{key}.mat";
                var assetPath = $"{targetAssetRoot}/Materials/{materialName}";
                var material = AssetDatabase.LoadAssetAtPath<Material>(assetPath);
                if (material == null)
                {
                    material = new Material(FindBestShader());
                    AssetDatabase.CreateAsset(material, assetPath);
                }

                material.shader = FindBestShader();
                var textures = GetList(materialData, "textures");
                foreach (var textureEntry in textures)
                {
                    var textureSlot = AsDict(textureEntry);
                    var slotName = GetString(textureSlot, "slot");
                    var texture = ImportTexture(AsDict(textureSlot["texture"]));
                    ApplyTexture(material, slotName, texture);
                }

                var colors = GetList(materialData, "colors");
                foreach (var colorEntry in colors)
                {
                    var colorData = AsDict(colorEntry);
                    if (GetString(colorData, "slot") != "_Color")
                    {
                        continue;
                    }

                    var color = ToColor(GetList(colorData, "rgba"));
                    ApplyColor(material, color);
                }

                ConfigureImportedMaterial(material);
                EditorUtility.SetDirty(material);
                materialCache[key] = material;
                return material;
            }

            private Texture2D ImportTexture(Dictionary<string, object> textureData)
            {
                var key = $"{GetString(textureData, "file")}_{GetInt(textureData, "path_id")}";
                if (textureCache.TryGetValue(key, out var cached))
                {
                    return cached;
                }

                var sourcePath = ResolveExtractPath(GetString(textureData, "png"));
                var textureName = $"{SafeFileName(Path.GetFileNameWithoutExtension(sourcePath))}_{key}.png";
                var assetPath = $"{targetAssetRoot}/Textures/{textureName}";
                var absoluteTargetPath = AbsoluteAssetPath(assetPath);

                Directory.CreateDirectory(Path.GetDirectoryName(absoluteTargetPath) ?? projectRootDirectory);
                File.Copy(sourcePath, absoluteTargetPath, true);
                AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
                ConfigureImportedTexture(assetPath);

                var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(assetPath);
                if (texture == null)
                {
                    throw new InvalidOperationException($"Failed to import texture: {assetPath}");
                }

                textureCache[key] = texture;
                return texture;
            }

            private AnimationClip ImportClip(Dictionary<string, object> clipSummary)
            {
                var key = $"{GetString(clipSummary, "file")}_{GetInt(clipSummary, "path_id")}";
                if (clipCache.TryGetValue(key, out var cached))
                {
                    return cached;
                }

                var clipData = LoadJsonObject(ResolveExtractPath(GetString(clipSummary, "json")));
                var clipName = GetString(clipSummary, "name");
                var assetPath = $"{targetAssetRoot}/Animations/{SafeFileName(clipName)}_{key}.anim";
                var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(assetPath);
                if (clip == null)
                {
                    clip = new AnimationClip();
                    AssetDatabase.CreateAsset(clip, assetPath);
                }

                clip.name = clipName;
                clip.legacy = true;
                clip.frameRate = GetFloat(clipSummary, "sample_rate", 30f);
                clip.wrapMode = (WrapMode)GetInt(clipSummary, "wrap_mode", (int)WrapMode.Loop);
                ClearClipCurves(clip);

                ApplyQuaternionCurves(clip, GetList(clipData, "m_RotationCurves"), "m_LocalRotation");
                ApplyVectorCurves(clip, GetList(clipData, "m_PositionCurves"), "m_LocalPosition");
                ApplyVectorCurves(clip, GetList(clipData, "m_ScaleCurves"), "m_LocalScale");
                clip.EnsureQuaternionContinuity();
                SetLoop(clip, clip.wrapMode == WrapMode.Loop);

                EditorUtility.SetDirty(clip);
                clipCache[key] = clip;
                return clip;
            }

            private static void ClearClipCurves(AnimationClip clip)
            {
                foreach (var binding in AnimationUtility.GetCurveBindings(clip))
                {
                    AnimationUtility.SetEditorCurve(clip, binding, null);
                }

                foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
                {
                    AnimationUtility.SetObjectReferenceCurve(clip, binding, null);
                }
            }

            private static void ApplyQuaternionCurves(AnimationClip clip, List<object> curves, string propertyPrefix)
            {
                foreach (var curveEntry in curves)
                {
                    var entry = AsDict(curveEntry);
                    var path = GetString(entry, "path");
                    var curve = AsDict(entry["curve"]);
                    var keys = GetList(curve, "m_Curve");

                    SetCurve(clip, path, $"{propertyPrefix}.x", BuildFloatCurve(keys, "x"));
                    SetCurve(clip, path, $"{propertyPrefix}.y", BuildFloatCurve(keys, "y"));
                    SetCurve(clip, path, $"{propertyPrefix}.z", BuildFloatCurve(keys, "z"));
                    SetCurve(clip, path, $"{propertyPrefix}.w", BuildFloatCurve(keys, "w"));
                }
            }

            private static void ApplyVectorCurves(AnimationClip clip, List<object> curves, string propertyPrefix)
            {
                foreach (var curveEntry in curves)
                {
                    var entry = AsDict(curveEntry);
                    var path = GetString(entry, "path");
                    var curve = AsDict(entry["curve"]);
                    var keys = GetList(curve, "m_Curve");

                    SetCurve(clip, path, $"{propertyPrefix}.x", BuildFloatCurve(keys, "x"));
                    SetCurve(clip, path, $"{propertyPrefix}.y", BuildFloatCurve(keys, "y"));
                    SetCurve(clip, path, $"{propertyPrefix}.z", BuildFloatCurve(keys, "z"));
                }
            }

            private static void SetCurve(AnimationClip clip, string path, string propertyName, AnimationCurve curve)
            {
                var binding = EditorCurveBinding.FloatCurve(path, typeof(Transform), propertyName);
                AnimationUtility.SetEditorCurve(clip, binding, curve);
            }

            private static AnimationCurve BuildFloatCurve(List<object> keyEntries, string component)
            {
                var keys = new Keyframe[keyEntries.Count];
                for (var i = 0; i < keyEntries.Count; i++)
                {
                    var data = AsDict(keyEntries[i]);
                    var value = AsDict(data["value"]);
                    var inSlope = AsDict(data["inSlope"]);
                    var outSlope = AsDict(data["outSlope"]);
                    var inWeight = AsDict(data["inWeight"]);
                    var outWeight = AsDict(data["outWeight"]);

                    var key = new Keyframe(
                        GetFloat(data, "time", 0f),
                        GetFloat(value, component, 0f),
                        GetFloat(inSlope, component, 0f),
                        GetFloat(outSlope, component, 0f));

#if UNITY_2018_1_OR_NEWER
                    key.weightedMode = (WeightedMode)GetInt(data, "weightedMode", 0);
                    key.inWeight = GetFloat(inWeight, component, 0.33333334f);
                    key.outWeight = GetFloat(outWeight, component, 0.33333334f);
#endif
                    keys[i] = key;
                }

                return new AnimationCurve(keys);
            }

            private static void SetLoop(AnimationClip clip, bool loop)
            {
                var serializedObject = new SerializedObject(clip);
                var settings = serializedObject.FindProperty("m_AnimationClipSettings");
                if (settings == null)
                {
                    return;
                }

                var loopProperty = settings.FindPropertyRelative("m_LoopTime");
                if (loopProperty == null)
                {
                    return;
                }

                loopProperty.boolValue = loop;
                serializedObject.ApplyModifiedPropertiesWithoutUndo();
            }

            private Transform[] ImportBones(List<object> boneEntries)
            {
                var bones = new Transform[boneEntries.Count];
                for (var i = 0; i < boneEntries.Count; i++)
                {
                    if (!(boneEntries[i] is Dictionary<string, object> boneData))
                    {
                        bones[i] = null;
                        continue;
                    }

                    bones[i] = FindOptionalTransform(GetString(boneData, "path"));
                }

                return bones;
            }

            private void SavePrefabAndSelect()
            {
                var prefabPath = $"{targetAssetRoot}/Prefabs/{SafeFileName(rootObject.name)}.prefab";
                var prefab = PrefabUtility.SaveAsPrefabAssetAndConnect(rootObject, prefabPath, InteractionMode.UserAction);
                if (!Application.isBatchMode)
                {
                    Selection.activeGameObject = rootObject;
                    EditorGUIUtility.PingObject(prefab != null ? (Object)prefab : rootObject);
                    if (SceneView.lastActiveSceneView != null)
                    {
                        SceneView.lastActiveSceneView.FrameSelected();
                    }
                }

                Debug.Log($"Xiongda imported to {prefabPath}");
            }

            private void CreatePreviewIfNeeded()
            {
                if (Camera.main == null)
                {
                    var cameraObject = new GameObject("Xiongda Preview Camera");
                    var camera = cameraObject.AddComponent<Camera>();
                    cameraObject.transform.position = new Vector3(0f, 1.3f, -4.5f);
                    cameraObject.transform.LookAt(rootObject.transform.position + new Vector3(0f, 1.0f, 0f));
                    camera.clearFlags = CameraClearFlags.Skybox;
                }

                if (Object.FindObjectOfType<Light>() == null)
                {
                    var lightObject = new GameObject("Xiongda Preview Light");
                    var light = lightObject.AddComponent<Light>();
                    light.type = LightType.Directional;
                    light.intensity = 1.2f;
                    lightObject.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
                }
            }

            private void ApplyLocalTransform(Transform transform, Dictionary<string, object> node)
            {
                transform.localPosition = ToVector3(GetList(node, "local_position"));
                transform.localRotation = ToQuaternion(GetList(node, "local_rotation"));
                transform.localScale = ToVector3(GetList(node, "local_scale"));
            }

            private static T EnsureComponent<T>(GameObject gameObject) where T : Component
            {
                var component = gameObject.GetComponent<T>();
                if (component == null)
                {
                    component = gameObject.AddComponent<T>();
                }

                return component;
            }

            private static Bounds ExpandBounds(Bounds bounds, float multiplier)
            {
                if (bounds.size == Vector3.zero)
                {
                    return new Bounds(Vector3.zero, Vector3.one);
                }

                return new Bounds(bounds.center, bounds.size * multiplier);
            }

            private Transform FindTransform(string path)
            {
                if (!transformByPath.TryGetValue(path, out var transform))
                {
                    throw new InvalidOperationException($"Transform path not found: {path}");
                }

                return transform;
            }

            private Transform FindOptionalTransform(string path)
            {
                if (string.IsNullOrEmpty(path))
                {
                    return null;
                }

                transformByPath.TryGetValue(path, out var transform);
                return transform;
            }

            private string ResolveExtractPath(string relativePath)
            {
                if (Path.IsPathRooted(relativePath))
                {
                    return relativePath;
                }

                var normalized = relativePath.Replace('/', Path.DirectorySeparatorChar);
                return Path.Combine(extractRootDirectory, normalized);
            }

            private void EnsureAssetFolder(string child)
            {
                var assetPath = string.IsNullOrEmpty(child) ? targetAssetRoot : $"{targetAssetRoot}/{child}";
                Directory.CreateDirectory(AbsoluteAssetPath(assetPath));
            }

            private string AbsoluteAssetPath(string assetPath)
            {
                return Path.Combine(projectRootDirectory, assetPath);
            }

            private static Shader FindBestShader()
            {
                return Shader.Find("Standard")
                    ?? Shader.Find("Universal Render Pipeline/Lit")
                    ?? Shader.Find("HDRP/Lit")
                    ?? Shader.Find("Sprites/Default");
            }

            private static void ApplyTexture(Material material, string slotName, Texture texture)
            {
                if (texture == null)
                {
                    return;
                }

                if (slotName == "_MainTex" && material.HasProperty("_MainTex"))
                {
                    material.SetTexture("_MainTex", texture);
                }

                if (slotName == "_MainTex" && material.HasProperty("_BaseMap"))
                {
                    material.SetTexture("_BaseMap", texture);
                }

                if (material.mainTexture == null)
                {
                    material.mainTexture = texture;
                }
            }

            private static void ApplyColor(Material material, Color color)
            {
                if (material.HasProperty("_Color"))
                {
                    material.SetColor("_Color", color);
                }

                if (material.HasProperty("_BaseColor"))
                {
                    material.SetColor("_BaseColor", color);
                }
            }

            private static void ConfigureImportedTexture(string assetPath)
            {
                var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
                if (importer == null)
                {
                    return;
                }

                importer.textureType = TextureImporterType.Default;
                importer.textureCompression = TextureImporterCompression.Uncompressed;
                importer.alphaIsTransparency = false;
                importer.mipmapEnabled = true;

                var settings = new TextureImporterSettings();
                importer.ReadTextureSettings(settings);
                settings.filterMode = FilterMode.Trilinear;
                settings.aniso = 8;
                settings.mipmapEnabled = true;
                importer.SetTextureSettings(settings);
                importer.SaveAndReimport();
            }

            private static void ConfigureImportedMaterial(Material material)
            {
                var hasMainTexture = material.mainTexture != null;
                if (hasMainTexture)
                {
                    // The source material multiplies albedo by gray; white preserves the full texture detail.
                    ApplyColor(material, Color.white);
                }
                else if (material.HasProperty("_Color"))
                {
                    material.SetColor("_Color", new Color(0.92f, 0.92f, 0.92f, 1f));
                }

                if (material.HasProperty("_Glossiness"))
                {
                    material.SetFloat("_Glossiness", hasMainTexture ? 0.08f : 0.18f);
                }

                if (material.HasProperty("_SpecularHighlights"))
                {
                    material.SetFloat("_SpecularHighlights", 0f);
                }

                if (material.HasProperty("_GlossyReflections"))
                {
                    material.SetFloat("_GlossyReflections", 0f);
                }
            }

            private static BoneWeight[] ToBoneWeights(List<object> indexEntries, List<object> weightEntries)
            {
                var weights = new BoneWeight[indexEntries.Count];
                for (var i = 0; i < indexEntries.Count; i++)
                {
                    var indices = GetList(indexEntries[i]);
                    var values = GetList(weightEntries[i]);
                    var total = Mathf.Max(0.0001f,
                        GetFloat(values[0]) + GetFloat(values[1]) + GetFloat(values[2]) + GetFloat(values[3]));

                    weights[i] = new BoneWeight
                    {
                        boneIndex0 = GetInt(indices[0]),
                        boneIndex1 = GetInt(indices[1]),
                        boneIndex2 = GetInt(indices[2]),
                        boneIndex3 = GetInt(indices[3]),
                        weight0 = GetFloat(values[0]) / total,
                        weight1 = GetFloat(values[1]) / total,
                        weight2 = GetFloat(values[2]) / total,
                        weight3 = GetFloat(values[3]) / total,
                    };
                }

                return weights;
            }

            private static Matrix4x4[] ToMatrixArray(List<object> entries)
            {
                var matrices = new Matrix4x4[entries.Count];
                for (var i = 0; i < entries.Count; i++)
                {
                    var values = GetList(entries[i]);
                    var matrix = new Matrix4x4();
                    for (var row = 0; row < 4; row++)
                    {
                        for (var column = 0; column < 4; column++)
                        {
                            matrix[row, column] = GetFloat(values[row * 4 + column]);
                        }
                    }

                    matrices[i] = matrix;
                }

                return matrices;
            }

            private static Vector3[] ToVector3Array(List<object> entries)
            {
                var result = new Vector3[entries.Count];
                for (var i = 0; i < entries.Count; i++)
                {
                    result[i] = ToVector3(GetList(entries[i]));
                }

                return result;
            }

            private static Vector4[] ToVector4Array(List<object> entries)
            {
                var result = new Vector4[entries.Count];
                for (var i = 0; i < entries.Count; i++)
                {
                    var values = GetList(entries[i]);
                    result[i] = new Vector4(
                        GetFloat(values[0]),
                        GetFloat(values[1]),
                        GetFloat(values[2]),
                        GetFloat(values[3]));
                }

                return result;
            }

            private static Vector2[] ToVector2Array(List<object> entries)
            {
                var result = new Vector2[entries.Count];
                for (var i = 0; i < entries.Count; i++)
                {
                    var values = GetList(entries[i]);
                    result[i] = new Vector2(GetFloat(values[0]), GetFloat(values[1]));
                }

                return result;
            }

            private static int[] ToIntArray(List<object> entries)
            {
                var result = new int[entries.Count];
                for (var i = 0; i < entries.Count; i++)
                {
                    result[i] = GetInt(entries[i]);
                }

                return result;
            }

            private static Vector3 ToVector3(List<object> values)
            {
                return new Vector3(GetFloat(values[0]), GetFloat(values[1]), GetFloat(values[2]));
            }

            private static Quaternion ToQuaternion(List<object> values)
            {
                return new Quaternion(GetFloat(values[0]), GetFloat(values[1]), GetFloat(values[2]), GetFloat(values[3]));
            }

            private static Color ToColor(List<object> values)
            {
                return new Color(GetFloat(values[0]), GetFloat(values[1]), GetFloat(values[2]), GetFloat(values[3]));
            }

            private static int GetPathDepth(string path)
            {
                return string.IsNullOrEmpty(path) ? 0 : path.Split('/').Length;
            }

            private static Dictionary<string, object> LoadJsonObject(string path)
            {
                var parsed = MiniJson.Deserialize(File.ReadAllText(path));
                return AsDict(parsed);
            }

            private static List<object> LoadJsonArray(string path)
            {
                var parsed = MiniJson.Deserialize(File.ReadAllText(path));
                return GetList(parsed);
            }

            private static Dictionary<string, object> AsDict(object value)
            {
                if (value is Dictionary<string, object> dict)
                {
                    return dict;
                }

                throw new InvalidOperationException("Expected object dictionary.");
            }

            private static List<object> GetList(Dictionary<string, object> dict, string key)
            {
                return GetList(dict[key]);
            }

            private static List<object> GetList(object value)
            {
                if (value is List<object> list)
                {
                    return list;
                }

                if (value == null)
                {
                    return new List<object>();
                }

                throw new InvalidOperationException("Expected list value.");
            }

            private static string GetString(Dictionary<string, object> dict, string key, string fallback = "")
            {
                if (!dict.TryGetValue(key, out var value) || value == null)
                {
                    return fallback;
                }

                return Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture) ?? fallback;
            }

            private static bool GetBool(Dictionary<string, object> dict, string key, bool fallback = false)
            {
                if (!dict.TryGetValue(key, out var value) || value == null)
                {
                    return fallback;
                }

                return GetBool(value, fallback);
            }

            private static bool GetBool(object value, bool fallback = false)
            {
                switch (value)
                {
                    case bool b:
                        return b;
                    case long l:
                        return l != 0;
                    case double d:
                        return Math.Abs(d) > double.Epsilon;
                    default:
                        return fallback;
                }
            }

            private static int GetInt(Dictionary<string, object> dict, string key, int fallback = 0)
            {
                return dict.TryGetValue(key, out var value) ? GetInt(value, fallback) : fallback;
            }

            private static int GetInt(object value, int fallback = 0)
            {
                switch (value)
                {
                    case int i:
                        return i;
                    case long l:
                        return (int)l;
                    case float f:
                        return Mathf.RoundToInt(f);
                    case double d:
                        return (int)Math.Round(d);
                    case string s when int.TryParse(s, out var parsed):
                        return parsed;
                    default:
                        return fallback;
                }
            }

            private static float GetFloat(Dictionary<string, object> dict, string key, float fallback = 0f)
            {
                return dict.TryGetValue(key, out var value) ? GetFloat(value, fallback) : fallback;
            }

            private static float GetFloat(object value, float fallback = 0f)
            {
                switch (value)
                {
                    case float f:
                        return f;
                    case double d:
                        return (float)d;
                    case int i:
                        return i;
                    case long l:
                        return l;
                    case string s when float.TryParse(s, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var parsed):
                        return parsed;
                    default:
                        return fallback;
                }
            }

            private static string SafeFileName(string value)
            {
                var invalidChars = Path.GetInvalidFileNameChars();
                var chars = value.ToCharArray();
                for (var i = 0; i < chars.Length; i++)
                {
                    for (var j = 0; j < invalidChars.Length; j++)
                    {
                        if (chars[i] == invalidChars[j])
                        {
                            chars[i] = '_';
                            break;
                        }
                    }
                }

                return new string(chars).Replace(' ', '_');
            }
        }
    }
}
