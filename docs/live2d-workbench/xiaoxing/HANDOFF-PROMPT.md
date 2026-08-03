# 小星 Live2D 当前权威交接

更新时间：2026-07-27

## 当前权威结论

V11 旧冻结经独立复核发现：最终汇总发生在目录切换后，旧输出备份又在最终汇总前
删除，因此原先的“完整候选原子发布与全程回滚保护”声明不成立。用户已授权修复，
当前候选已完成事务边界重构、故障注入验证和真实双运行复核，并获用户明确批准
重新冻结，状态为：

`V11 发布事务修复版已通过并重新冻结`

批准记录与冻结清单已按当前修复工件重建；修复前冻结清单哈希仅作为被替代记录保留。
V10 单侧手臂工程粗绑继续保持 `38/38` 冻结一致。V11 只证明能够在冻结输入上自动
复核并确定性复现当前单臂工程结果，不代表能够从新原图自动生成材料，也不代表正式
纹理模型、完整角色 Cubism、Physics、Runtime、平台接入、双臂或全身完成。

## V11 当前冻结入口

V11 根目录：

`validation/arm-chain-screen-right-v11-automation-prototype/`

当前批准、冻结与结果：

- `validation/arm-chain-screen-right-v11-automation-prototype/audit/v11-user-approval-and-freeze-authorization-2026-07-27.json`
- `validation/arm-chain-screen-right-v11-automation-prototype/audit/v11-freeze-manifest-2026-07-27.json`
- `validation/arm-chain-screen-right-v11-automation-prototype/run_v11.py`
- `validation/arm-chain-screen-right-v11-automation-prototype/README.md`
- `validation/arm-chain-screen-right-v11-automation-prototype/output/audit/v11-result.json`
- `validation/arm-chain-screen-right-v11-automation-prototype/output/audit/V11-AUTOMATION-REPORT.zh-CN.md`

当前 V11 冻结清单 SHA-256：

`1f530904431be0945778d029af4c620490bbb4c7250f9114015acc35cc40e378`

被替代的修复前冻结清单 SHA-256：

`4414d4956bd66c19a685d72016c61f36a86fee70e699a3ec1c86d3388be06321`；
它不再是当前冻结依据。

V10 根目录：

`validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/`

当前批准与冻结文件：

- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-user-visual-approval-and-freeze-authorization-2026-07-27.json`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-freeze-manifest-2026-07-27.json`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-cubism-validation-report.md`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-cubism-rough-rig-evidence-manifest.json`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-final-closeout-audit.json`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit/v10-cubism-return-determinism.json`

冻结清单 SHA-256：

`6a5ff7c38b709efb7ff6991901a46f136b6b97c412f5dfcd36e04c1a549f5db7`

最终 CMO3：

`validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/cubism/xiaoxing-arm-chain-v10-rough-rig.cmo3`

CMO3 SHA-256：

`6b3c6d5682eec1a019dc7f14c6ebe185bb1cdeca24f3fcd3d93b502e8aa60bf0`

冻结清单锁定 38 项工件；冻结时逐项复核路径、文件长度和 SHA-256，结果为
`38/38` 一致。

此前冻结后 CMO3 在长度不变的情况下发生哈希变化，旧冻结曾降为 `37/38` 并已
判定失效。当前哈希对应的 CMO3 已在真实 Cubism GUI 中重新完成肩、肘、腕、
taper、接缝和 `0→1→0` 最小复核；审计、审批记录和冻结清单随后按依赖顺序
重建，上述 `38/38` 只指当前重新生成的冻结。

## 已证明范围

- V11 统一入口能够在两个独立干净目录中完整运行。
- 两次运行比较 7 个确定性文件的长度与 SHA-256，结果为 `7/7` 一致。
- 最终机器结果和报告在候选目录中完整写入并校验后，才执行带回滚保护的事务式
  目录切换；切换成功后不再写入 `output/`。
- 候选校验失败和候选目录切换失败均完成旧输出恢复；备份清理失败会保留可恢复
  备份并返回明确告警。
- 自动复核 41 个 FK 样本、6 个组合极值和共 47 个姿态。
- 骨长、三处相邻接缝、整链连通与回程检查全部通过。
- 运行前、双运行之间、发布后 V10 冻结工件均为 `38/38`。
- V11 是冻结输入上的自动复核与复现工具；材料与 PSD 为哈希锁定的确定性复制，
  网格检查复核冻结数值记录，不重新生成素材或解析 CMO3。
- Cubism Editor GUI 实际可用，最终 CMO3 已真实保存。
- 工程导入 PSD 可用；当前四个 ArtMesh 为 sleeve、upper_arm、forearm、hand。
- 肩—肘—腕 Deformer 层级、参数关键形与固定 Draw Order 已建立。
- Draw Order 保持为 upper_arm 100、hand 200、forearm 300、sleeve 400。
- 最终静态肘根边界最大位移为 `4.27 px`，不超过 `4.3737707666 px`。
- `ParamV7ForearmRootTaper` 已形成有效、连续的局部动态关键形；最大位移
  `4.202 px`，沿轮廓最大影响范围 `20.66129 px`，不超过 `22 px`。
- 四个 ArtMesh 已完成数值网格检查和 GUI 视觉检查。
- 肩、肘、腕及必要组合完成真实连续慢速 `0→1→0` 运动验证。
- 回程前后可见像素差为 `0`，回零具有确定性。
- 用户已确认当前肘部外观，并最终批准整个 V10 工程粗绑。

## 证据入口

优先查看：

- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/qa/v10-closeout-review-board.png`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/qa/v10-closeout-engineering-board.png`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/qa/v10-continuous-parameter-motion.mp4`
- `validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/qa/evidence/`

证据的逐项角色、哈希和解释以冻结清单及证据清单为准。

## 冻结边界

不得就地改写当前 V11 冻结清单锁定的入口、配置、输出、报告、批准记录或证据，也
不得改写 V10 冻结工程。任一锁定文件发生字节变化都必须重新打开对应门禁、重新
验证并重新取得用户批准。

不得恢复或派生此前已否决的旧材料链。V4、袖子、V6、V7、V8、V9 的冻结输入继续
受各自清单约束。

## 后续停止条件

当前没有被自动授权的下一生产阶段。进入正式纹理、正式 PSD、完整 Cubism、
Physics、Runtime、平台集成、另一侧手臂或全身制作前，必须由用户另行选择范围并
明确授权。不得把 V10 工程粗绑或 V11 自动复核冻结解释为这些下游范围已经批准。
