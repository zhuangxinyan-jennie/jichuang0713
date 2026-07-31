using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace XiongdaImporter
{
    public static class XiongdaAssetCollector
    {
        private const string BaseDefaultAnimationFolder = "Assets/XiongdaImported/xiongda_base_default/Animations";
        private const string LeftVariantAnimationFolder = "Assets/XiongdaImported/xiongda_left_slide_variant/Animations";
        private const string RightVariantAnimationFolder = "Assets/XiongdaImported/xiongda_right_slide_variant/Animations";
        private const string StandaloneAnimationFolder = "Assets/XiongdaImported/standalone_clips/Animations";

        private const string FullPrefabPath = "Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大.prefab";
        private const string LeftVariantPrefabPath = "Assets/XiongdaImported/xiongda_left_slide_variant/Prefabs/熊大@蒙皮.prefab";
        private const string RightVariantPrefabPath = "Assets/XiongdaImported/xiongda_right_slide_variant/Prefabs/熊大@蒙皮.prefab";
        private const string PurePrefabPath = "Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大@纯毛版.prefab";

        private const string CollectionFolderName = "XiongdaCollected";
        private const string ActionsFolderName = "Actions";
        private const string ExpressionsFolderName = "Expressions";
        private const string ExpressionsOnlyFolderName = "ExpressionsOnly";
        private const string ObjFolderName = "OBJ";
        private const string ReportFileName = "animation_validation_report.txt";
        private const string ReadmeFileName = "README.txt";
        private const string ExpressionOnlyAssetFolder = "Assets/XiongdaImported/expression_only/Animations";

        private const string ExtractRoot = "/home/kaifeng/extra/Downloads/fudan/IC_competition/unity/extracted_xiongda_run";
        private const string StandaloneBear2RunJson = ExtractRoot + "/standalone_clips/Bear2Run_B__Bear2Run__26a942382c8d86c4a9891ef631897c00_1.json";
        private const string StandaloneBear2RunAssetPath = StandaloneAnimationFolder + "/Bear2Run_26a942382c8d86c4a9891ef631897c00_1.anim";
        private const string PureObjSourcePath = ExtractRoot + "/xiongda_base_default/mesh_exports/xiongda_xinban/xiongda_xinban.obj";
        private const string PureObjTexturePath = ExtractRoot + "/xiongda_base_default/textures/xiongda2017.png";

        [MenuItem("Tools/Xiongda/Collect Motions And Validate")]
        private static void CollectMotionsAndValidateMenu()
        {
            CollectMotionsAndValidateBatch();
        }

        public static void CollectMotionsAndValidateBatch()
        {
            XiongdaRunImporter.ImportBaseDefaultBatch();
            XiongdaRunImporter.ImportLeftVariantBatch();
            XiongdaRunImporter.ImportRightVariantBatch();
            XiongdaSkinVariants.CreateDefaultPureSkinPrefabBatch();

            var standaloneClip = ImportStandaloneBear2Run();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            var clips = GatherUniqueClips(standaloneClip);
            var expressionOnlyClips = GenerateExpressionOnlyClips(clips);
            ValidateClips(clips);

            var projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            var collectionRoot = Path.Combine(projectRoot, CollectionFolderName);
            var actionsRoot = Path.Combine(collectionRoot, ActionsFolderName);
            var expressionsRoot = Path.Combine(collectionRoot, ExpressionsFolderName);
            var expressionsOnlyRoot = Path.Combine(collectionRoot, ExpressionsOnlyFolderName);
            var objRoot = Path.Combine(collectionRoot, ObjFolderName);

            Directory.CreateDirectory(collectionRoot);
            Directory.CreateDirectory(actionsRoot);
            Directory.CreateDirectory(expressionsRoot);
            Directory.CreateDirectory(expressionsOnlyRoot);
            Directory.CreateDirectory(objRoot);

            CopyClipFiles(clips, actionsRoot, expressionsRoot, projectRoot);
            CopyExpressionOnlyClipFiles(expressionOnlyClips, expressionsOnlyRoot, projectRoot);
            ExportPureObj(objRoot);
            WriteReadme(collectionRoot, clips, expressionOnlyClips);
            WriteValidationReport(collectionRoot, clips);

            Debug.Log($"Xiongda collection generated at {collectionRoot}");
        }

        private static List<CollectedClip> GatherUniqueClips(AnimationClip standaloneClip)
        {
            var folders = new[]
            {
                BaseDefaultAnimationFolder,
                LeftVariantAnimationFolder,
                RightVariantAnimationFolder,
            };

            var collected = new List<CollectedClip>();
            var seenNames = new HashSet<string>(StringComparer.Ordinal);

            foreach (var folder in folders)
            {
                if (!AssetDatabase.IsValidFolder(folder))
                {
                    continue;
                }

                var guids = AssetDatabase.FindAssets("t:AnimationClip", new[] { folder });
                var assetPaths = new List<string>(guids.Length);
                foreach (var guid in guids)
                {
                    assetPaths.Add(AssetDatabase.GUIDToAssetPath(guid));
                }

                assetPaths.Sort(StringComparer.Ordinal);
                foreach (var assetPath in assetPaths)
                {
                    var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(assetPath);
                    if (clip == null || string.IsNullOrEmpty(clip.name) || !seenNames.Add(clip.name))
                    {
                        continue;
                    }

                    collected.Add(new CollectedClip
                    {
                        Name = clip.name,
                        SourceAssetPath = assetPath,
                        SourceLabel = folder,
                        Clip = clip,
                        HasExpressionBindings = ClipHasExpressionBindings(clip),
                    });
                }
            }

            if (standaloneClip != null && seenNames.Add(standaloneClip.name))
            {
                collected.Add(new CollectedClip
                {
                    Name = standaloneClip.name,
                    SourceAssetPath = StandaloneBear2RunAssetPath,
                    SourceLabel = "standalone_clips/Bear2Run_B",
                    Clip = standaloneClip,
                    HasExpressionBindings = ClipHasExpressionBindings(standaloneClip),
                });
            }

            return collected.OrderBy(item => item.Name, StringComparer.Ordinal).ToList();
        }

        private static void ValidateClips(List<CollectedClip> clips)
        {
            var fullGroups = new Dictionary<string, List<CollectedClip>>(StringComparer.Ordinal);
            foreach (var clip in clips)
            {
                var fullPrefabPath = GetFullValidationPrefabPath(clip);
                if (!fullGroups.TryGetValue(fullPrefabPath, out var bucket))
                {
                    bucket = new List<CollectedClip>();
                    fullGroups.Add(fullPrefabPath, bucket);
                }

                bucket.Add(clip);
            }

            foreach (var pair in fullGroups)
            {
                ValidateClipsAgainstPrefab(pair.Key, pair.Value, false);
            }

            ValidateClipsAgainstPrefab(PurePrefabPath, clips, true);
        }

        private static void ValidateClipsAgainstPrefab(string prefabPath, List<CollectedClip> clips, bool usePureResult)
        {
            var prefabRoot = PrefabUtility.LoadPrefabContents(prefabPath);
            if (prefabRoot == null)
            {
                throw new InvalidOperationException($"Failed to load prefab for validation: {prefabPath}");
            }

            try
            {
                var animationComponent = prefabRoot.GetComponent<Animation>();
                if (animationComponent == null)
                {
                    animationComponent = prefabRoot.AddComponent<Animation>();
                }

                var transformByPath = BuildTransformMap(prefabRoot.transform);
                foreach (var collectedClip in clips)
                {
                    var result = ValidateSingleClip(prefabRoot, animationComponent, transformByPath, collectedClip.Clip, collectedClip.HasExpressionBindings);
                    result.PrefabPath = prefabPath;
                    if (usePureResult)
                    {
                        collectedClip.PureValidation = result;
                    }
                    else
                    {
                        collectedClip.FullValidation = result;
                    }
                }
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        private static ValidationResult ValidateSingleClip(
            GameObject prefabRoot,
            Animation animationComponent,
            Dictionary<string, Transform> transformByPath,
            AnimationClip clip,
            bool requireExpression)
        {
            var result = new ValidationResult
            {
                RequiresExpression = requireExpression,
                ExpressionChanged = !requireExpression,
            };
            var bindingPaths = GetBindingPaths(clip);
            result.BindingPathCount = bindingPaths.Count;

            var availableMotionProbePaths = new List<string>();
            var availableExpressionProbePaths = new List<string>();
            foreach (var path in bindingPaths)
            {
                if (!transformByPath.ContainsKey(path))
                {
                    result.MissingPaths.Add(path);
                    continue;
                }

                if (IsExpressionPath(path))
                {
                    availableExpressionProbePaths.Add(path);
                }
                else
                {
                    availableMotionProbePaths.Add(path);
                }
            }

            result.PathsFound = result.MissingPaths.Count == 0;

            try
            {
                if (animationComponent.GetClip(clip.name) == null)
                {
                    animationComponent.AddClip(clip, clip.name);
                }

                animationComponent.clip = clip;
                result.SampleSucceeded = true;
                result.MotionChanged = DetectPoseChange(prefabRoot, clip, transformByPath, availableMotionProbePaths);
                if (requireExpression)
                {
                    result.ExpressionChanged = DetectPoseChange(prefabRoot, clip, transformByPath, availableExpressionProbePaths);
                }
            }
            catch (Exception ex)
            {
                result.ErrorMessage = ex.Message;
            }

            return result;
        }

        private static string GetFullValidationPrefabPath(CollectedClip clip)
        {
            if (clip.SourceAssetPath.IndexOf("/xiongda_left_slide_variant/", StringComparison.Ordinal) >= 0)
            {
                return LeftVariantPrefabPath;
            }

            if (clip.SourceAssetPath.IndexOf("/xiongda_right_slide_variant/", StringComparison.Ordinal) >= 0)
            {
                return RightVariantPrefabPath;
            }

            return FullPrefabPath;
        }

        private static Dictionary<string, Transform> BuildTransformMap(Transform root)
        {
            var result = new Dictionary<string, Transform>(StringComparer.Ordinal)
            {
                { string.Empty, root }
            };

            foreach (var child in root.GetComponentsInChildren<Transform>(true))
            {
                if (child == root)
                {
                    continue;
                }

                result[GetRelativePath(root, child)] = child;
            }

            return result;
        }

        private static string GetRelativePath(Transform root, Transform current)
        {
            var names = new Stack<string>();
            var cursor = current;
            while (cursor != null && cursor != root)
            {
                names.Push(cursor.name);
                cursor = cursor.parent;
            }

            return string.Join("/", names.ToArray());
        }

        private static List<string> GetBindingPaths(AnimationClip clip)
        {
            var paths = new HashSet<string>(StringComparer.Ordinal);
            foreach (var binding in AnimationUtility.GetCurveBindings(clip))
            {
                paths.Add(binding.path ?? string.Empty);
            }

            foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
            {
                paths.Add(binding.path ?? string.Empty);
            }

            var result = paths.ToList();
            result.Sort(StringComparer.Ordinal);
            return result;
        }

        private static bool DetectPoseChange(
            GameObject prefabRoot,
            AnimationClip clip,
            Dictionary<string, Transform> transformByPath,
            List<string> probePaths)
        {
            if (probePaths.Count == 0)
            {
                return false;
            }

            var baselineTime = 0f;
            clip.SampleAnimation(prefabRoot, baselineTime);
            var baseline = CapturePoseSnapshot(transformByPath, probePaths);

            foreach (var sampleTime in BuildSampleTimes(clip))
            {
                if (Mathf.Approximately(sampleTime, baselineTime))
                {
                    continue;
                }

                clip.SampleAnimation(prefabRoot, sampleTime);
                if (HasPoseDifference(baseline, CapturePoseSnapshot(transformByPath, probePaths)))
                {
                    return true;
                }
            }

            return false;
        }

        private static List<float> BuildSampleTimes(AnimationClip clip)
        {
            var length = Mathf.Max(clip.length, 0f);
            var result = new List<float> { 0f };
            if (length <= 0f)
            {
                return result;
            }

            AddSampleTime(result, length * 0.2f);
            AddSampleTime(result, length * 0.4f);
            AddSampleTime(result, length * 0.6f);
            AddSampleTime(result, length * 0.8f);
            AddSampleTime(result, Mathf.Max(0f, length - (1f / Mathf.Max(clip.frameRate, 30f))));
            return result;
        }

        private static void AddSampleTime(List<float> samples, float value)
        {
            foreach (var existing in samples)
            {
                if (Mathf.Abs(existing - value) <= 0.0001f)
                {
                    return;
                }
            }

            samples.Add(value);
        }

        private static Dictionary<string, PoseSnapshot> CapturePoseSnapshot(
            Dictionary<string, Transform> transformByPath,
            List<string> probePaths)
        {
            var snapshot = new Dictionary<string, PoseSnapshot>(probePaths.Count, StringComparer.Ordinal);
            foreach (var path in probePaths)
            {
                if (!transformByPath.TryGetValue(path, out var transform))
                {
                    continue;
                }

                snapshot[path] = new PoseSnapshot
                {
                    LocalPosition = transform.localPosition,
                    LocalRotation = transform.localRotation,
                    LocalScale = transform.localScale,
                };
            }

            return snapshot;
        }

        private static bool HasPoseDifference(
            Dictionary<string, PoseSnapshot> baseline,
            Dictionary<string, PoseSnapshot> current)
        {
            foreach (var pair in baseline)
            {
                if (!current.TryGetValue(pair.Key, out var other))
                {
                    continue;
                }

                if ((pair.Value.LocalPosition - other.LocalPosition).sqrMagnitude > 0.000001f)
                {
                    return true;
                }

                if ((pair.Value.LocalScale - other.LocalScale).sqrMagnitude > 0.000001f)
                {
                    return true;
                }

                if (Quaternion.Angle(pair.Value.LocalRotation, other.LocalRotation) > 0.05f)
                {
                    return true;
                }
            }

            return false;
        }

        private static bool IsExpressionPath(string path)
        {
            return !string.IsNullOrEmpty(path)
                && path.IndexOf("Bone_xdbq", StringComparison.Ordinal) >= 0;
        }

        private static bool ClipHasExpressionBindings(AnimationClip clip)
        {
            foreach (var binding in AnimationUtility.GetCurveBindings(clip))
            {
                if (IsExpressionPath(binding.path))
                {
                    return true;
                }
            }

            foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(clip))
            {
                if (IsExpressionPath(binding.path))
                {
                    return true;
                }
            }

            return false;
        }

        private static List<ExpressionOnlyClip> GenerateExpressionOnlyClips(List<CollectedClip> clips)
        {
            EnsureAssetFolder("Assets", "XiongdaImported");
            EnsureAssetFolder("Assets/XiongdaImported", "expression_only");
            EnsureAssetFolder("Assets/XiongdaImported/expression_only", "Animations");

            var result = new List<ExpressionOnlyClip>();
            foreach (var collectedClip in clips.Where(item => item.HasExpressionBindings))
            {
                var targetFileName = SafeFileName(collectedClip.Name) + "_expression_only.anim";
                var assetPath = ExpressionOnlyAssetFolder + "/" + targetFileName;
                var expressionClip = AssetDatabase.LoadAssetAtPath<AnimationClip>(assetPath);
                if (expressionClip == null)
                {
                    expressionClip = new AnimationClip();
                    AssetDatabase.CreateAsset(expressionClip, assetPath);
                }

                expressionClip.name = collectedClip.Name + "_expression_only";
                expressionClip.legacy = true;
                expressionClip.frameRate = collectedClip.Clip.frameRate;
                expressionClip.wrapMode = collectedClip.Clip.wrapMode;
                ClearClipCurves(expressionClip);

                foreach (var binding in AnimationUtility.GetCurveBindings(collectedClip.Clip))
                {
                    if (!IsExpressionPath(binding.path))
                    {
                        continue;
                    }

                    AnimationUtility.SetEditorCurve(
                        expressionClip,
                        binding,
                        AnimationUtility.GetEditorCurve(collectedClip.Clip, binding));
                }

                foreach (var binding in AnimationUtility.GetObjectReferenceCurveBindings(collectedClip.Clip))
                {
                    if (!IsExpressionPath(binding.path))
                    {
                        continue;
                    }

                    AnimationUtility.SetObjectReferenceCurve(
                        expressionClip,
                        binding,
                        AnimationUtility.GetObjectReferenceCurve(collectedClip.Clip, binding));
                }

                expressionClip.EnsureQuaternionContinuity();
                SetLoop(expressionClip, collectedClip.Clip.wrapMode == WrapMode.Loop);
                EditorUtility.SetDirty(expressionClip);

                result.Add(new ExpressionOnlyClip
                {
                    Name = expressionClip.name,
                    SourceName = collectedClip.Name,
                    SourceAssetPath = assetPath,
                    Clip = expressionClip,
                });
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            return result.OrderBy(item => item.Name, StringComparer.Ordinal).ToList();
        }

        private static void CopyClipFiles(List<CollectedClip> clips, string actionsRoot, string expressionsRoot, string projectRoot)
        {
            foreach (var collectedClip in clips)
            {
                var sourceAbsolutePath = Path.Combine(projectRoot, collectedClip.SourceAssetPath);
                var targetFileName = SafeFileName(collectedClip.Name) + ".anim";
                File.Copy(sourceAbsolutePath, Path.Combine(actionsRoot, targetFileName), true);

                if (collectedClip.HasExpressionBindings)
                {
                    File.Copy(sourceAbsolutePath, Path.Combine(expressionsRoot, targetFileName), true);
                }
            }
        }

        private static void CopyExpressionOnlyClipFiles(List<ExpressionOnlyClip> clips, string expressionsOnlyRoot, string projectRoot)
        {
            foreach (var clip in clips)
            {
                var sourceAbsolutePath = Path.Combine(projectRoot, clip.SourceAssetPath);
                File.Copy(sourceAbsolutePath, Path.Combine(expressionsOnlyRoot, SafeFileName(clip.Name) + ".anim"), true);
            }
        }

        private static void ExportPureObj(string objRoot)
        {
            var objTargetPath = Path.Combine(objRoot, "xiongda_pure.obj");
            var mtlTargetPath = Path.Combine(objRoot, "xiongda_pure.mtl");
            var textureTargetPath = Path.Combine(objRoot, "xiongda2017.png");

            var sourceObjText = File.ReadAllText(PureObjSourcePath);
            var builder = new StringBuilder();
            builder.AppendLine("mtllib xiongda_pure.mtl");
            builder.AppendLine("usemtl xiongda_body");
            builder.Append(sourceObjText);
            File.WriteAllText(objTargetPath, builder.ToString(), Encoding.UTF8);

            var mtlBuilder = new StringBuilder();
            mtlBuilder.AppendLine("newmtl xiongda_body");
            mtlBuilder.AppendLine("Ka 1.000000 1.000000 1.000000");
            mtlBuilder.AppendLine("Kd 1.000000 1.000000 1.000000");
            mtlBuilder.AppendLine("Ks 0.000000 0.000000 0.000000");
            mtlBuilder.AppendLine("d 1.000000");
            mtlBuilder.AppendLine("illum 2");
            mtlBuilder.AppendLine("map_Kd xiongda2017.png");
            File.WriteAllText(mtlTargetPath, mtlBuilder.ToString(), Encoding.UTF8);

            File.Copy(PureObjTexturePath, textureTargetPath, true);
        }

        private static void WriteReadme(string collectionRoot, List<CollectedClip> clips, List<ExpressionOnlyClip> expressionOnlyClips)
        {
            var readmePath = Path.Combine(collectionRoot, ReadmeFileName);
            var builder = new StringBuilder();
            builder.AppendLine("熊大资源整理说明");
            builder.AppendLine();
            builder.AppendLine("目录说明：");
            builder.AppendLine("- Actions: 熊大模型可用的动作动画文件");
            builder.AppendLine("- Expressions: 含表情骨 Bone_xdbq 的动作子集");
            builder.AppendLine("- ExpressionsOnly: 从表情动作里剥离出来的纯表情版动画，仅保留 Bone_xdbq 曲线");
            builder.AppendLine("- OBJ: 纯净熊大主体 OBJ、配套 MTL、主体贴图");
            builder.AppendLine();
            builder.AppendLine("OBJ 说明：");
            builder.AppendLine("- xiongda_pure.obj 来自 xiongda_xinban 主体网格");
            builder.AppendLine("- 已去掉鞋子、蜂蜜罐等单独网格");
            builder.AppendLine("- OBJ 不带骨骼；动作验证使用 Unity prefab 完成");
            builder.AppendLine();
            builder.AppendLine($"动作总数: {clips.Count}");
            builder.AppendLine($"表情动作数: {clips.Count(item => item.HasExpressionBindings)}");
            builder.AppendLine($"纯表情导出数: {expressionOnlyClips.Count}");
            builder.AppendLine();
            builder.AppendLine("详细验证结果见 animation_validation_report.txt");
            File.WriteAllText(readmePath, builder.ToString(), Encoding.UTF8);
        }

        private static void WriteValidationReport(string collectionRoot, List<CollectedClip> clips)
        {
            var reportPath = Path.Combine(collectionRoot, ReportFileName);
            var builder = new StringBuilder();
            builder.AppendLine("熊大动作验证报告");
            builder.AppendLine();
            builder.AppendLine("验证方法:");
            builder.AppendLine("- 完整验证会按动作来源自动匹配熊大 prefab：基础版、左滑铲版、右滑铲版");
            builder.AppendLine("- 纯毛版验证统一使用熊大@纯毛版 prefab，判断去掉配件后主体动作还能不能播");
            builder.AppendLine("- 通过标准不是“所有绑定路径都必须存在”，而是 SampleAnimation 成功，并且检测到主体骨骼实际发生位姿变化");
            builder.AppendLine("- 对表情动作，额外要求检测到 Bone_xdbq 表情骨发生变化");
            builder.AppendLine();

            var fullPassCount = clips.Count(item => item.FullValidation != null && item.FullValidation.Passed);
            var purePassCount = clips.Count(item => item.PureValidation != null && item.PureValidation.Passed);

            builder.AppendLine($"完整熊大通过: {fullPassCount}/{clips.Count}");
            builder.AppendLine($"纯毛版熊大通过: {purePassCount}/{clips.Count}");
            builder.AppendLine();

            foreach (var clip in clips)
            {
                builder.AppendLine($"[{clip.Name}]");
                builder.AppendLine($"source={clip.SourceAssetPath}");
                builder.AppendLine($"expression={clip.HasExpressionBindings}");
                builder.AppendLine($"full_prefab={DescribeValidation(clip.FullValidation)}");
                builder.AppendLine($"pure_prefab={DescribeValidation(clip.PureValidation)}");
                builder.AppendLine();
            }

            File.WriteAllText(reportPath, builder.ToString(), Encoding.UTF8);
        }

        private static string DescribeValidation(ValidationResult result)
        {
            if (result == null)
            {
                return "NOT_RUN";
            }

            var builder = new StringBuilder();
            builder.Append(result.Passed ? "PASS" : "FAIL");
            builder.Append($" bindings={result.BindingPathCount}");
            builder.Append($" sample={(result.SampleSucceeded ? "yes" : "no")}");
            builder.Append($" motion={(result.MotionChanged ? "yes" : "no")}");
            if (result.RequiresExpression)
            {
                builder.Append($" expression={(result.ExpressionChanged ? "yes" : "no")}");
            }

            if (!string.IsNullOrEmpty(result.PrefabPath))
            {
                builder.Append($" prefab={result.PrefabPath}");
            }

            if (result.MissingPaths.Count > 0)
            {
                builder.Append($" missing={result.MissingPaths.Count}");
                builder.Append(" [");
                builder.Append(string.Join(", ", result.MissingPaths.Take(6).ToArray()));
                if (result.MissingPaths.Count > 6)
                {
                    builder.Append(", ...");
                }

                builder.Append("]");
            }

            if (!string.IsNullOrEmpty(result.ErrorMessage))
            {
                builder.Append($" error={result.ErrorMessage}");
            }

            return builder.ToString();
        }

        private static AnimationClip ImportStandaloneBear2Run()
        {
            EnsureAssetFolder("Assets", "XiongdaImported");
            EnsureAssetFolder("Assets/XiongdaImported", "standalone_clips");
            EnsureAssetFolder("Assets/XiongdaImported/standalone_clips", "Animations");

            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(StandaloneBear2RunAssetPath);
            if (clip == null)
            {
                clip = new AnimationClip();
                AssetDatabase.CreateAsset(clip, StandaloneBear2RunAssetPath);
            }

            var clipData = LoadJsonObject(StandaloneBear2RunJson);
            clip.name = GetString(clipData, "m_Name", "Bear2Run");
            clip.legacy = true;
            clip.frameRate = 30f;
            clip.wrapMode = WrapMode.Loop;
            ClearClipCurves(clip);
            ApplyQuaternionCurves(clip, GetList(clipData, "m_RotationCurves"), "m_LocalRotation");
            ApplyVectorCurves(clip, GetList(clipData, "m_PositionCurves"), "m_LocalPosition");
            ApplyVectorCurves(clip, GetList(clipData, "m_ScaleCurves"), "m_LocalScale");
            clip.EnsureQuaternionContinuity();
            SetLoop(clip, true);
            EditorUtility.SetDirty(clip);
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

                SetCurve(clip, path, propertyPrefix + ".x", BuildFloatCurve(keys, "x"));
                SetCurve(clip, path, propertyPrefix + ".y", BuildFloatCurve(keys, "y"));
                SetCurve(clip, path, propertyPrefix + ".z", BuildFloatCurve(keys, "z"));
                SetCurve(clip, path, propertyPrefix + ".w", BuildFloatCurve(keys, "w"));
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

                SetCurve(clip, path, propertyPrefix + ".x", BuildFloatCurve(keys, "x"));
                SetCurve(clip, path, propertyPrefix + ".y", BuildFloatCurve(keys, "y"));
                SetCurve(clip, path, propertyPrefix + ".z", BuildFloatCurve(keys, "z"));
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

        private static Dictionary<string, object> LoadJsonObject(string path)
        {
            return AsDict(MiniJson.Deserialize(File.ReadAllText(path)));
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

        private static void EnsureAssetFolder(string parent, string child)
        {
            var path = parent + "/" + child;
            if (!AssetDatabase.IsValidFolder(path))
            {
                AssetDatabase.CreateFolder(parent, child);
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

        private sealed class CollectedClip
        {
            public string Name;
            public string SourceAssetPath;
            public string SourceLabel;
            public AnimationClip Clip;
            public bool HasExpressionBindings;
            public ValidationResult FullValidation;
            public ValidationResult PureValidation;
        }

        private sealed class ExpressionOnlyClip
        {
            public string Name;
            public string SourceName;
            public string SourceAssetPath;
            public AnimationClip Clip;
        }

        private sealed class ValidationResult
        {
            public string PrefabPath;
            public int BindingPathCount;
            public bool RequiresExpression;
            public bool PathsFound;
            public bool SampleSucceeded;
            public bool MotionChanged;
            public bool ExpressionChanged;
            public string ErrorMessage;
            public readonly List<string> MissingPaths = new List<string>();

            public bool Passed
            {
                get
                {
                    return SampleSucceeded
                        && MotionChanged
                        && ExpressionChanged
                        && string.IsNullOrEmpty(ErrorMessage);
                }
            }
        }

        private struct PoseSnapshot
        {
            public Vector3 LocalPosition;
            public Quaternion LocalRotation;
            public Vector3 LocalScale;
        }
    }
}
