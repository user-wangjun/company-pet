# 小星 Left R3：运动压力测试与几何冻结候选

> 历史失败候选：本目录保留一次未通过工程门禁的 R3 尝试及其回归证据，不代表当前 R3
> 已开始。当前权威状态是 `R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED`；重新启动 R3 需要
> 另行授权并从当前 R2 冻结输入重新执行。

状态：R3_ENGINEERING_FAILED / RETURN_TO_EARLIEST_FAILED_STAGE

engineeringPass=false；overallGatePass=false；R3-GATE 保持未勾选。

## 身份与边界

- character=xiaoxing，view=front，screenSide=left，anatomicalSide=right。
- 本目录是本阶段唯一写入目录；R1、R2、旧 arm-chain-screen-left-v12-* 至 v38-* 全部只读。
- 只使用 R2 冻结的 512×1086 complete flat-layers 做运动 alpha；源线/源彩仅作固定背景审查，不参与 alpha 或 layer-only 拼装。
- R2 的 11 帧 -52° shoulder / 155° elbow 已记录为 qa_only_not_R3，没有继承角度、姿态或结果。

## 物理求解

- shoulder=(166,270)，elbow=(149,399)，wrist=(110,538)，palmRoot=(104,552)。
- upper_arm=130.115333 px，forearm=144.367586 px，wrist→palmRoot=15.231546 px。
- upper_arm 绕 shoulder；forearm 绕 elbow 后继承 shoulder；hand 绕 wrist 后继承 elbow 与 shoulder。
- bracelet、bracelet_back、bracelet_front 都只继承 forearm；没有独立关节、节点或运动通道。
- sleeve 只在 R3 压力测试中使用双锚连续几何变形：A=(166,228) 为 torso/scapular 支撑锚，袖口锚点跟随 upper_arm/elbow；无缩放、无平移补偿、无 blur/dilate、无 R5 mesh/deformer/node。

## 采样与证据

- 5 条独立压力轨迹和 2 条人体顺序组合轨迹，每条 41 个完整 0→1→0 样本。组合路径按 shoulder lead → elbow follow → wrist refinement 分阶段，不把三处关节同步当作刚杆旋转。
- 极值矩阵共 18 个组合：1 个 in_contract_valid、8 个 in_contract_failed、9 个 excluded_by_contract；合同示例另列 5 条。
- 逐样本记录写入 audit/sample-metrics.json，共 287 个轨迹/极值采样记录。
- 慢速 GIF：qa/shoulder-negative-0-1-0.gif、qa/shoulder-positive-0-1-0.gif、qa/elbow-0-1-0.gif、qa/wrist-negative-0-1-0.gif、qa/wrist-positive-0-1-0.gif、qa/coupled-motion-0-1-0.gif、qa/coupled-motion-alt-0-1-0.gif。
- 中文总审查图：qa/R3-小星Left-运动压力测试-中文审查图.png。
- 其他视觉证据：单关节与组合极值接触表、三处关节最近邻放大图、bracelet 移除/前后深度检查、袖子双锚点审查图。
- R3-local 手掌修复候选：qa/手掌边界修复候选-中文审查图.png 与 audit/hand-palm-repair-candidate.json；候选不覆盖 R2，需单独视觉批准后才能提升为新的上游材料修订。

## 自动门禁结论

- PASS r2_manifest_expected_sha256：R2 artifact-manifest SHA-256=FEA721AD3F6EB9576DD14D847A97FA17C712D7CCBA2B3DEDA7E09CA8EFD8EE8A matches expected FEA721…EE8A
- PASS r2_formal_masks_and_flat_layers_frozen：all 43 formal R2 masks/flat-layers verified against manifest
- PASS protected_r1_r2_v12_v38_unchanged：protected snapshot 936 files digest before=d1025edb42df897379ad6c88fca726a907d27f5ff9282f5507836f6d8ea374e1 after=d1025edb42df897379ad6c88fca726a907d27f5ff9282f5507836f6d8ea374e1
- PASS all_required_tracks_at_least_41_samples：7 tracks have 41 samples each
- FAIL continuous_parent_child_fk_chain：upper_arm→forearm→hand transforms use physical shoulder/elbow/wrist pivots and deterministic out-and-back samples
- PASS bone_length_drift_le_0_25px：maximum absolute float bone-length drift=0.000000454593px
- PASS return_angles_pivots_and_output_alpha_exact：all track start/end angles, joints, composite alpha and RGBA return exactly to neutral
- PASS return_correspondence_deterministic：every mirrored out/back sample pair has identical alpha and RGBA hashes
- PASS no_branch_flip_or_angle_jump：elbow remains on preferred branch; per-sample angle step is bounded and continuous
- PASS hidden_overlap_minimums：maximum R1 hidden-overlap deficit=0.000000px
- PASS joint_width_guards：maximum measured local joint width=56.799811px; guards shoulder=58/elbow=48/wrist=48px
- FAIL local_area_drift_le_5pct：maximum absolute alpha-area drift=40.360610%
- FAIL full_canvas_material_containment：50 samples clip transformed R2 material at the 512x1086 canvas boundary; examples=[{"trackId":"shoulder-positive-0-1-0","sampleIndex":8,"anglesDeg":{"shoulder":11.755705,"elbow":0.0,"wrist":0.0},"layers":["hand"]},{"trackId":"shoulder-positive-0-1-0","sampleIndex":9,"anglesDeg":{"shoulder":12.988961,"elbow":0.0,"wrist":0.0},"layers":["hand"]},{"trackId":"shoulder-positive-0-1-0","sampleIndex":10,"anglesDeg":{"shoulder":14.142136,"elbow":0.0,"wrist":0.0},"layers":["hand"]},{"trackId":"shoulder-positive-0-1-0","sampleIndex":11,"anglesDeg":{"shoulder":15.208119,"elbow":0.0,"wrist":0.0},"layers":["hand"]},{"trackId":"shoulder-positive-0-1-0","sampleIndex":12,"anglesDeg":{"shoulder":16.18034,"elbow":0.0,"wrist":0.0},"layers":["hand"]}]
- FAIL no_joint_transparent_gap_or_disconnect：joint centerline gap samples are zero and arm union stays one connected component
- FAIL unique_visible_ownership：no duplicate visible skin ownership across four primary layers
- FAIL bracelet_forearm_owner_and_depth_order：bracelet stays in forearm transform, hand has no visible owner pixels, and removal leaves a continuous wrist bridge
- PASS arm_only_alpha_has_no_whole_body_fallback：all composites are made only from R2 complete flat-layers
- PASS sleeve_dual_anchor_continuity：R3-only sleeve dual-anchor deformation records fixed support and cuff following upper_arm
- PASS visual_review_artifacts_present：Chinese total board, GIFs, extrema contact sheet, joint zooms, bracelet depth/removal, and sleeve dual-anchor review are generated
- PASS r3_gate_not_closed：R3-GATE remains unchecked; no user approval record and no final geometry freeze checklist were created

## 用户批准边界

本构建没有创建用户视觉批准记录，也没有生成最终几何冻结清单。
只有用户明确批准完整活动包络且工程门禁为 true 后，才允许关闭 R3-GATE 并生成冻结清单与哈希。
当前工程门禁未通过；不得把本轮图像当作可批准的完整活动包络，必须回到最早失效阶段修正后重跑。

构建器：tools/build_r3_motion_stress.py。建议连续运行两次，并比较 audit/artifact-manifest.json 与 R2/R1/旧链保护快照。
