# 小橘 Gate 3 材料尝试复盘

当前结论：`Gate 3 未通过`。现有输出是完整隐藏解剖与分层技术试验，不是最终 Live2D 模型，也不允许据此进入 Cubism 绑定。

## 候选结论

- `v1-v4`：拒绝。主要问题是站立感、柱状前肢、躯干压扁或与登录场景支撑关系冲突。
- `v5 fullbody`：仅接受为隐藏解剖、完整四肢和毛发纹理来源。它的坐姿与镜头不是最终登录姿势，禁止整只替换原始小橘。
- `v5 no-forelegs`：接受为胸腔、腹部和前肢下方隐藏区域的补全来源。
- `v6 limbless`：整只轮廓拒绝。躯干呈团块化、压缩生物体积；只允许使用尾根与后肢原遮挡区内的小范围补洞像素。

## 当前已证明

- 画布统一为 `1370 x 1148`，21 个试验部件均存在。
- 头部仍使用批准的登录场景小橘来源，没有用 v5 生成脸替换身份。
- 两条前肢已有完整肢体层和肩、上臂、前臂、爪的独立试验层。
- 上臂与前臂已从方形多边形切片改成沿骨段的圆头胶囊遮罩，大角度旋转时不再暴露矩形纹理板。
- 眼部新增 12 个独立材料层：左右干净虹膜、瞳孔、反光、闭眼线、原眼安全层和眼眶裁剪层。干净虹膜中心黑色残留为 `0`；目光极限移动在 clipping 后越界为 `0`。
- 眨眼已生成 `ParamEyeOpen=1.00/0.72/0.42/0.16/0.00` 五档视觉检查，使用连续纵向网格压缩与闭眼线渐入，不切换整张眼睛图片。
- 近侧后肢与爪有独立材料；原图完全遮挡的远侧后肢按猫的双侧对称解剖推断，并应用 `0.82` 远景缩放与 `-3°/-4°` 平面旋转，明确标记为 `INFERRED` 且默认隐藏在身体后方。
- 身体隐藏底层已进一步拆成胸腔、腹部和骨盆三个宽重叠体积区，后续可以分别承担呼吸、接触压缩和后躯配重。
- v6 整体没有混入最终身体轮廓，只在原本被尾和近侧后肢遮住的局部区域参与补洞。

## Gate 3 阻塞项

- 远侧后肢的双侧解剖、缩短透视和后置层级已经确定，但仍需在展开姿势中确认髋部连接；不可仅凭静止遮挡宣告通过。
- 胸腔、腹部、骨盆已经独立，但重叠边界仍需在展开姿势中验证，不能只看静止合成图。
- 前肢旋转骨段已改为圆头胶囊遮罩，但肩根、腕部的最终毛边和动态 draw order 仍需在 Cubism 中检查。
- v5 部件尚未写入新的可编辑分层 PSD；旧 working PSD 中的 `TODO_HIDDEN_*` 不能算完成。
- 尚未完成展开姿势、遮眼往返和四分之一速度视频验收。
- 当前刚体压力测试在 rest/expanded/cover 三姿态中保持骨段长度漂移 `0 px`、相邻关节断开 `0`；这只证明技术连通，遮眼视觉仍标记为 `visualPass=false`，不能当成 Gate 3 通过。
- 已生成一次 `3.967 s` 的遮眼—停留—回落预览。底层按 `60 Hz` 采样，最大单帧关节变化 `3.3715°`，低于合同上限 `3.5°`；抬起采用近端到远端延迟，回落采用远端到近端释放。该结果为 `technicalPass=true / visualPass=false`，仍需检查动态遮挡切换和真实 Cubism 网格形变。

机器审计见 `qa/gate3-v5-parts-audit.json`、`qa/gate3-v5-eye-parts-audit.json`、`qa/gate3-v5-joint-motion-report.json` 和 `qa/gate3-v5-cover-roundtrip-report.json`；动态预览为 `qa/gate3-v5-cover-roundtrip-20fps-preview.gif`。视觉审计另见 `qa/gate3-v5-gaze-extremes-contact-sheet.png`、`qa/gate3-v5-blink-contact-sheet.png`、`qa/gate3-v5-joint-motion-contact-sheet.png`、`qa/gate3-v5-segmented-expanded.png`、`qa/gate3-v5-body-volume-zones.png`、`qa/gate3-v5-foreleg-segments-contact-sheet.png` 和 `qa/gate3-v5-hindlimbs-contact-sheet.png`。推断的远侧后肢只出现在 `qa/gate3-v5-inferred-full-anatomy.png`，不混进默认自然合成图。

PSD 导入已准备为 `import_v5_parts_into_working_psd.jsx`。脚本会创建独立的 `GATE3_V5_IMPORT_TRIAL`，不会覆盖旧 `GATE3_RIG_PARTS`；完成 Photoshop 实际导入、保存和重新导出清单之前，仍视为未验证。
