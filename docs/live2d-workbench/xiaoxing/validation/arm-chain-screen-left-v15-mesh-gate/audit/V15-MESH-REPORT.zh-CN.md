# V15 画面左侧手臂 ArtMesh 网格

状态：`engineering_pass_pending_user_visual_approval`。数值网格检查不能替代用户视觉批准。

- V14 冻结输入：24/24；
- 四层均使用真实 alpha 边界；越界三角、退化三角、UV 越界均为 0；
- 手指负空间通过边界内采样保留；
- 节点合同只声明候选父级，不创建实际 Deformer；
- 当前不进入主动参数、Physics 或 Runtime。

请审查 `qa/V15-MESH-USER-REVIEW.zh-CN.png` 的线框是否跨出轮廓、是否有过长
细三角、手指间隙是否被桥接。批准后再建立节点并做父级级联验证。
