# 小星 Left｜大臂 AA + 人体轮廓候选 v5

当前状态：`UPPER_ARM_AA_ANATOMICAL_CANDIDATE / WAITING_USER_VISUAL_APPROVAL`。

本候选只重建大臂的 hidden/complete 几何和正式 display Alpha：肩根短而有体积，中段保留不对称软组织轮廓，肘部以斜向短收束连接共享支点，不使用周期 B-spline 胶囊端或圆形补丁。路径在 32×高分辨率画布直接栅格化，逻辑 mask 与 formal display Alpha 均只做一次 BOX coverage downsample。

当前 R2 的 upper_arm、sleeve、forearm、bracelet、hand 和骨架文件没有被覆盖。请先审查 `qa/upper-arm-aa-anatomical-review.png`，视觉批准后再决定是否提升正式层。
