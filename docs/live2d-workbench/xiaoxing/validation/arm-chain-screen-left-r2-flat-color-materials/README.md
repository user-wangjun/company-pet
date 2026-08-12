# 小星 Left｜R2 全画布平色正式收口

本目录对应 `character=xiaoxing`、`view=front`、`screenSide=left`、`anatomicalSide=right`。

## 当前状态

`R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED`。最新整只手视觉批准与冻结 manifest 已通过字节/SHA256/尺寸/identity 复核；`engineeringPass=true`、`userVisualApproval=true`、`formalR2Promotion=true`、`overallGatePass=true`、`R2-GATE=passed`。

## 允许范围与保护

正式范围：小星 Left = 正面屏幕左侧、解剖右臂；`candidates/upper-arm-aa-anatomical-v8/` 是唯一正式 R2 upper-arm 来源，sleeve/forearm/bracelet/hand 使用冻结输入。builder 只在已登记的 forearm seam/U-cap、语义 topology、正式 Alpha、合同、报告和中文 QA 范围内写入；最新批准记录和历史冻结记录均不被改写。

shaft visible ownership 直接来自 front-line master 的 4-connected skin-side enclosed component；腕部 seam 直接取 source free components 与 source barrier pixels，注册 corridor 只作选择 guard，不能单独发出色块。shaft formal Alpha 在固定 supersample 后保留 fractional edge，并在 source ownership 内重新裁切；U-cap formal Alpha 则以最新蓝线为唯一显示边界，旧源线只保留为逻辑连接与审计诊断，不能再次把顶部裁成台阶。U-cap 使用 source-space float periodic C2 cubic Bézier；在 32×画布完成高分辨率布尔运算，逻辑 mask 只在一次 BOX coverage 下采样后阈值化；formal display Alpha 由注册 cubic coverage 生成，并在下采样后执行蓝线边界 guard。禁止低分辨率 NEAREST 几何、矩形/尖锐多边形/固定圆/全局 hull/radial patch、blur、dilate、erode、LANCZOS ringing。

## 输出

逻辑输出：四个主层 visible/hidden/complete 与 forearm 子区域；正式显示 Alpha 与 flat layer 保持 512×1086 identity。`forearm_skin` 必须单组件/0 孔洞；`forearm` 的 6 个孔洞必须逐坐标匹配冻结 bracelet legal negative spaces。旧 zero-hole forearm checks 只作历史并明确 superseded。

## 门禁与后续

审查入口：`qa/R2-小星Left-全画布平色材料-中文审查图.png`、`audit/r2-formal-promotion-report.json`、`audit/machine-report.json`、`contracts/topology-expectations.json`。抬手序列仍是 R2 diagnostic-only：03/04/06/07 的 hand 小岛来自 BICUBIC + Alpha>=128 低分辨率变换阈值；没有声称 R3 通过，未来 R3 需要至少 41 个高分辨率 floating-boundary coverage 点。本任务明确未进入 R3、纹理、网格、节点、Physics、Cubism 或 Runtime。
