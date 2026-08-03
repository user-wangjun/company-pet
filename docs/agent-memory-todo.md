# Agent Memory / Soul / Task To-do

> 状态：阶段 0.1--6 的本地边界已实现并重验；聊天入口已接入，内置 App 固定本地 Provider；云端同步和远程 Key 配置仍未接入
>
> 研究依据：`D:\Users\Downloads\deep-research-report.md`
>
> 目标：把 Memory、Soul、Search、Task 和主动陪伴拆成可独立验收的阶段，避免一次性引入云端数据库、向量库、多 Agent 和复杂调度系统。

## 进度快照

验收日期：2026-08-03

| 阶段 | 状态 | 证据 / 说明 |
|---|---|---|
| 阶段 0：边界与数据契约 | ✅ 已补齐 | `docs/agent-memory-data-contract.md`：保存位置、可见性、过期/删除、边界和 10+ 个对话样例 |
| 阶段 0.1：远程 Provider 外发策略与隐私边界 | ✅ 已验收 | 统一远程 Context 过滤、无标签健康/用药/地址样例、密码策略/医疗科普误报样例、Provider 提示和数据契约已通过相关测试与构建 |
| 阶段 1：Soul 与 Context Assembler | ✅ 已验收 | 5 个相关测试文件 58/58 通过；完整测试 46/46 文件、417/417 测试通过；`npm run build` 成功 |
| 阶段 2：Session 与 Memory v1 | ✅ 已验收 | `companionMemory.ts`、Context 注入、设置页管理入口；相关测试 6 个文件 71/71、全量测试 47 个文件 430/430 通过；`npm run build` 成功 |
| 阶段 3：任务识别与任务事实源 | ✅ 已验收 | 聊天操作、候选生命周期和取消表达已修复并重验 |
| 阶段 4：主动触发与多宠物交付 | ✅ 已验收 | 无标题控制语句已绑定最近主动投递上下文；非当前宠物目标采用显式切换，相关测试和全量验证通过 |
| 阶段 5：本地持久化与云端迁移准备 | ✅ 本地范围已验收 | Task 与 Memory 已迁移到 Provider 无关本地 Repository；Outbox、Tombstone、删除优先守卫、损坏 journal 和写入失败恢复已验证；云端能力未实现 |
| 阶段 6：规模化进入条件与同步契约硬化 | ✅ 本地范围评估完成 | `docs/agent-memory-scale-readiness.md`；fixture 性能/恢复证据通过；云端、向量库和队列 No-Go |

## 2026-08-03 审计修复记录

- 敏感边界补齐无标签的健康自述、用药、中文/英文地址形状，并保留密码策略、医疗科普等无具体数据讨论的误报回归测试；当前输入、历史、Preference、Memory、Task、Soul、平台策略和 Outbox 继续共用 fail-closed 规则。
- Repository 增加最小删除守卫。主记录、Outbox、同步计数器、journal 清理中断、损坏 journal 和回滚再次失败时，Memory/Task 均不会把已删除事实或提醒重新暴露。
- `writeTaskDatabase` 现在返回真实成功结果；App 和 TaskWorkspace 只在写入成功后更新 UI、显示成功反馈、关闭提醒或清理动作。失败只显示通用重试提示。
- `ignoredStreak` 不再在每次投递时清零；已用真实的“投递 → 忽略 → 投递 → 忽略 → 评估”序列验证退避。
- 聊天入口为现有右键任务菜单中的“陪我聊聊”，并支持 650ms 内右键双击快捷打开；左键点击、双击和拖拽路径不承担聊天入口职责。打开时先解析 Provider 信息；内置 App 无 Key，固定本地，不做云端同步或远程持久化。远程 Provider 失败时允许一次本地降级并披露状态。

## 2026-08-03 当前完整验证

- `npm test`：59 个测试文件、575/575 个测试通过。
- `npx vitest run src/storage/agentMemoryScaleReadiness.test.ts`：2/2 通过；规模 fixture、写入失败、journal 恢复和删除优先恢复均通过。
- `npm run build`：通过；Vite 主 chunk 740.30 kB 的优化建议不阻塞构建。
- `cargo test`：10/10 通过；`cargo check`：通过。
- `git diff --check`：通过。

## 使用规则

- 本清单是执行计划，不替代研究报告；研究报告保留作为设计依据。
- 每个阶段完成后先通过验收，再进入下一阶段。
- 任何记忆、Persona 或任务机制都不能绕过用户可见、可删和可关闭的控制面。
- `SOUL.md` 是宠物包的人格资料，运行时只读；模型不能自动改写核心人格和安全边界。
- Memory 是参考资料，不是更高优先级的指令；它不能覆盖当前用户输入、平台安全策略或工具权限。
- 第一版不做多 Agent、自主外部操作、云端同步、独立向量数据库、Kafka、Temporal 或企业级部署。

## 当前代码基线（实施前仍需以工作区和测试为准）

| 能力 | 当前代码线索 | 处理方式 |
|---|---|---|
| 气泡聊天状态机 | `src/pet-core/companionChatRuntime.ts` | 在其上扩展，不重写交互状态机 |
| 本地 / Gemini Provider | `src/pet-core/companionChatProvider.ts` | 保持 Provider 接口，Memory 不绑定某个模型供应商 |
| 宠物聊天配置 | `src/pet-core/companionChat.ts`、`public/pets/<pet-id>/companion-chat.json` | 沿用宠物包边界，增加 Soul 时使用相对路径 |
| 用户偏好 | `src/pet-core/companionPreferences.ts` | 与长期 Memory 区分；先兼容现有偏好行为 |
| 宠物资源解析 | `src/pet-core/petAssets.ts` | 不在组件内硬编码 `/pets/<pet-id>` |

## 阶段 0：冻结边界与数据契约

这是设计阶段，不急于写功能代码。

- [x] 明确第一版目标是“当前宠物的轻量陪伴聊天”。
- [x] 明确第一版不保存完整原始聊天记录。
- [x] 明确数据作用域：`user`、`user + pet`、`session`、`task`、`event`。
- [x] 明确 `SOUL`、用户偏好、关系记忆、会话状态和任务状态的边界。
- [x] 明确长期记忆写入策略：用户明确要求或用户确认候选后才能持久化。
- [x] 明确敏感内容、医疗结论、账号密码、Token 和精确地址不得进入长期 Memory。
- [x] 明确 Gemini / OpenAI / 本地 Provider 可以替换，Memory 和检索层不随之重写。
- [x] 为后续测试准备至少 10 个“应该记住 / 不应该记住 / 应该询问”的对话样例。

### 阶段 0 验收门

- 能用一页说明回答“这句话保存在哪里、谁能看到、何时过期、如何删除”。
- 没有任何“让模型自己决定一切”的未定义路径。
- 证据：`docs/agent-memory-data-contract.md` 已冻结上述契约和 14 个对话样例；阶段 1-5 已按该边界实施。

## 阶段 0.1：统一远程 Provider 外发策略与隐私边界

- [x] 明确本地 Provider 不发起网络请求；只有用户主动配置 API Key 才启用远程 Provider；无 Key 不静默回退到远程服务。
- [x] 以 Provider 无关的共享隐私规则过滤当前输入、历史、Memory、Preference、Evidence、Soul、平台策略和其他用户可控字段。
- [x] 当前输入命中敏感规则时不调用远程 fetcher；历史敏感消息整条删除，不保留原文、片段或证据；安全历史仍保留。
- [x] 覆盖密码、Token、API Key、私钥、身份证、银行卡、信用卡、精确地址、医疗诊断、病史、用药信息及常见英文表达。
- [x] 在聊天气泡显示本地/远程 Provider、目标服务和本轮上下文外发说明；不显示完整 API Key，不承诺服务商绝不保存数据。
- [x] 在数据契约中冻结远程模式、本地模式、允许/禁止外发数据、Memory 删除/Tombstone、服务商条款边界和 API Key 存放边界。

### 阶段 0.1 验收记录

- 实现范围：`src/pet-core/companionPrivacy.ts`、`src/pet-core/companionContext.ts`、`src/pet-core/companionChatProvider.ts`、`src/pet-core/companionChatRuntime.ts`、`src/pet-core/CompanionChatBubble.tsx`、`src/App.tsx` 及 `src/App.css`；没有新增云端数据库、同步服务、向量库、队列或账号系统。
- 契约更新：`docs/agent-memory-data-contract.md` 新增“远程 Provider 外发策略”章节。
- 历史记录（2026-08-02）：相关测试 `src/pet-core/companionChatProvider.test.ts`、`src/pet-core/companionContext.test.ts`、`src/pet-core/companionChatRuntime.test.ts`、`src/pet-core/companionMemory.test.ts`、`src/pet-core/CompanionChatBubble.test.tsx`；5 个文件、39/39 通过。
- 历史记录（2026-08-02）：全量 `npm test` 为 55 个文件、494/494 通过。
- 历史记录（2026-08-02）：`npm run build` 成功；Vite 报告主 JS chunk 727.08 kB、超过 500 kB 建议值，但不阻塞本阶段。当前轮结果见上方“当前完整验证”。
- 已知风险：规则仍采用保守匹配，未命中规则的变体可能需要后续迭代；密码策略、医疗科普和通用保护讨论已有明确误报回归样例。服务商的数据保留、训练和区域政策不由本应用保证。
- 当前边界：本地模式不外发；远程模式只发送经过过滤的必要上下文；当前项目没有云端同步能力。

## 阶段 1：Soul 与 Context Assembler

这是第一个实施阶段，也是新对话应该先做的范围。

- [x] 为 `PetManifest` 增加可选的宠物 Soul 相对路径字段，例如 `soulPath`。
- [x] 实现宠物包内 `SOUL.md` 的只读加载，并复用现有安全相对路径解析。
- [x] 定义 `SOUL.md` 的固定章节：`Identity`、`Expression`、`Behavior`、`Safety Boundary`。
- [x] 对缺失、超长或加载失败的 Soul 提供中性回退，不影响其他宠物。
- [x] 不允许运行时写入、合并或自动修改 `SOUL.md`。
- [x] 新增 Provider 无关的 Context Assembler，负责组合：平台策略、Soul、现有偏好、近期会话和当前用户输入。
- [x] 明确上下文优先级：平台安全与工具权限 > 当前用户意图 > Soul 边界 > 用户偏好 > 普通记忆参考。
- [x] 给 Soul、偏好和近期会话设置明确长度预算，避免完整文件无限注入。
- [x] 将当前 Provider 中的系统指令组装逻辑逐步迁入可测试的纯函数；保持现有 Gemini 和本地回复行为。
- [x] 增加 Soul 缺失、路径安全、宠物切换、上下文优先级和 Provider 兼容测试。
- [x] 仅为需要验证的宠物增加最小 Soul 示例，不要在没有依据时替所有宠物编造人格。

### 阶段 1 验收门

- 同一用户输入切换不同宠物后，事实上下文不串台、表达风格会变化。
- Soul 不能覆盖隐私策略、Provider 错误处理或当前用户输入。
- 缺失 Soul 时聊天仍能使用现有中性配置。
- 通过相关单元测试、`npm run build`，且没有修改无关宠物素材或发行文件。

### 阶段 1 验收记录

- 相关测试：`npm test -- src/pet-core/petSoul.test.ts src/pet-core/companionContext.test.ts src/pet-core/companionChatProvider.test.ts src/pet-core/petAssets.test.ts src/pet-core/companionChatRuntime.test.ts`
- 相关测试结果：5 个文件、58 个测试全部通过。
- 全量测试：46 个文件、417 个测试全部通过。
- 构建：`npm run build` 成功；`dist/pets/xiaoju-cat/SOUL.md` 已进入产物。
- 构建提示：Vite 报告主 JS chunk 超过 500 kB；这是已有构建优化提示，不阻塞本阶段验收。

## 阶段 2：Session 与 Memory v1

- [x] 定义结构化 Memory 条目：`id`、`scope`、`type`、`content`、`source`、`evidence`、`confidence`、`createdAt`、`updatedAt`、`expiresAt`、`status`。
- [x] 区分共享用户事实与用户—宠物关系记忆。
- [x] 设计 Provider 无关的 `MemoryRepository` 接口。
- [x] 将当前有限聊天窗口与长期 Memory 分离。
- [x] 第一版实现本地关键词 / 标签 / 时间检索，不先引入向量数据库。
- [x] 检索默认限制作用域、相关度阈值和 Top-K 数量。
- [x] 检索结果以“参考记忆”注入，不能被当作系统指令执行。
- [x] 实现“建议记住 → 用户确认 → 保存”的写入流程；明确低风险记住表达可直接保存，未确认候选不会保存。
- [x] 保留来源证据，支持 `superseded`、过期和冲突处理。
- [x] 提供查看、编辑、删除、禁用和导出入口。
- [x] 增加记忆注入、冲突、删除、作用域隔离和敏感信息过滤测试。

### 阶段 2 验收门

- 删除的记忆不会再次被检索。
- A 宠物的关系记忆不会被 B 宠物检索到。
- 当前用户明确指令不会被旧记忆覆盖。
- 记忆检索失败时聊天仍能正常回复。

### 阶段 2 验收记录

- 本地键：`yuxin-companion-memory-v1`；完整聊天窗口仍只在 `companionChatRuntime.ts` 会话状态中存在，不写入长期 Memory。
- 相关测试：`npm test -- src/pet-core/companionMemory.test.ts src/pet-core/companionContext.test.ts src/pet-core/companionChatProvider.test.ts src/pet-core/petSoul.test.ts src/pet-core/petAssets.test.ts src/pet-core/companionChatRuntime.test.ts`；6 个文件、71 个测试全部通过。
- 全量测试：`npm test`；47 个文件、430 个测试全部通过。
- 构建：`npm run build` 成功；Vite 仍提示主 JS chunk 为 676.02 kB、超过 500 kB 建议值，但不阻塞本阶段。
- 验收结论：删除/禁用条目不会进入检索；`global` 可被当前宠物使用，`pet:<id>` 已隔离；当前用户输入仍位于 Memory 之前；检索异常会降级为空记忆而不阻塞聊天。
- 已知边界：当前聊天入口启用的是明确低风险“记住/以后叫我”直接保存；通用候选确认 API 已具备，但推断型候选的实际对话确认 UI 尚未启用。检索仍是本地关键词/时间排序，不包含向量或 Embedding。
- 未实施：向量检索、Embedding、云同步、任务识别、主动提醒、多 Agent、PostgreSQL、Qdrant、Milvus、Kafka、Temporal。

## 阶段 3：任务识别与任务事实源

- [x] 先支持明确表达：`提醒我`、`记一下`、`明天做`。
- [x] Provider 无关 Task Extractor 输出任务标题、时间、时区、证据、置信度和风险等级。
- [x] 区分明确任务、模糊愿望、假设、玩笑和否定表达；模糊或没有日期的事项不会被默认为今天。
- [x] 遵循现有 `TaskStatus` 与 Reminder 状态，不新增 `unscheduled`、`scheduled` 或 `expired` 任务状态；未确认事项停留在内存候选中。
- [x] 实现任务更新、完成、取消、延期和去重；完成/取消不依赖 `dueAt`，延期/改期需要明确新时间。
- [x] 保存任务来源消息、原始证据和来源宠物，不把任务混入普通 Memory。
- [x] 高影响、时间歧义或涉及敏感领域时要求简短确认。
- [x] 与现有任务模块对接，不创建平行的第二套任务事实源。

### 阶段 3 验收门

- [x] “最近该学习了”不会自动生成提醒。
- [x] “明天下午三点提醒我交报告”能生成结构化任务并进入现有 Task/Reminder 事实源。
- [x] 重复表达不会创建重复任务。
- [x] 完成或取消表达通过聊天入口等价集成路径实际改变任务状态，并不会继续进入普通提醒候选。

### 阶段 3 验收记录

- 纯逻辑模块：`src/pet-core/companionTaskExtractor.ts`、`companionTaskOperations.ts`、`companionTaskSession.ts`；候选只在聊天会话内等待确认，显式退出、宠物切换、外部点击和自动超时都会清空。
- Task 最小来源字段：`sourceMessageId`、`evidence`、`createdByPetId`；旧 schema 1/2 数据读取时补齐为 `null`，仍使用 `yuxin.tasks.v1`。
- 阶段 3 相关测试：5 个文件、60/60 通过；覆盖完成/取消/延期/改期、超时清理、显式退出/换宠/外部点击和“`不用记`/`不用了`/`别记`/`取消`”。
- 全量测试：`npm test`；52 个文件、463/463 测试通过。
- 构建：`npm run build` 成功；Vite 主 chunk 超过 500 kB 的提示仍是已有优化建议，不阻塞本阶段。
- 当前结论：✅ 已通过聊天入口等价验收，允许进入阶段 4。
- 已修复：`App.tsx` 仅对延期/改期检查新 `dueAt`；`pendingCompanionTaskRef` 与所有退出路径同步清空；确认解析器识别四种取消表达。
- 未实施：云同步、向量检索、多 Agent 和新的调度器。

## 阶段 4：主动触发与多宠物交付

- [x] Scheduler 只产生到期、错过或需要重新评估的候选。
- [x] Proactive Trigger Engine 独立决定 `send`、`suppress`、`delay` 或 `aggregate`。
- [x] 加入用户级主动次数上限。
- [x] 加入单任务冷却、同类聚合、安静时段和忽略退避。
- [x] 记录每次触发的理由、分数、抑制原因和最终结果。
- [x] 支持“别再提醒这件事”“少提醒”“换一只宠物提醒”；无标题表达优先绑定最近一次可靠的主动投递上下文，没有可靠上下文时明确要求任务名称，不写入普通 Memory。
- [x] 将任务事实与宠物表达分离，由 Delivery / Persona 层生成短气泡、动作或声音。
- [x] 使用幂等键避免多 Worker 或多宠物重复投递。

### 阶段 4 验收门

- [x] 同一任务在同一时间窗口最多产生一次实际投递。
- [x] 安静时段和频率上限确实能抑制提醒。
- [x] 连续忽略后提醒频率降低，而不是增加。
- [x] 每次主动提醒都能解释“为什么现在提醒”。
- [x] 无标题控制语句能作用于当前相关任务，并且多宠物交付行为有实际集成证据。

### 阶段 4 验收记录

- `src/pet-core/proactiveTriggerEngine.ts` 将到期、错过和 `triggered/missed` 重评候选转换为可测试的本地规则决策；不调用 Gemini，不创建第二套任务事实源或调度器。
- `src/pet-core/proactiveExpressionGate.ts` 的同一 `yuxin-proactive-expression-gate-v1` 存储键承载任务主动次数、全局气泡门禁、冷却、幂等键、偏好和决策日志；旧状态缺少 `task_reminder` 计数时按 0 兼容读取。
- `src/pet-core/proactiveDelivery.ts` 只负责将决策转换为最终宠物的短气泡文案；任务事实仍由 `TaskDatabase` / `Reminder` 保存，正式系统任务提醒保留原有手动通道。
- 已实现 `send`、`suppress`、`delay`、`aggregate`；包括每日上限、单任务冷却、同类聚合、安静时段、连续忽略退避，以及带标题或可靠最近上下文的 `别再提醒`、`少提醒` 和换宠偏好。无标题且上下文缺失、聚合或过期时明确要求任务名称。
- `proactiveTaskControl.ts` 将聊天控制解析与 TaskDatabase/最近主动投递上下文绑定；控制分支早于普通 Memory 候选提取，控制表达不会写入普通 Memory。
- 多宠物交付采用显式切换策略：目标宠物不是当前宠物时先切换，队列保留同一个幂等投递；切换完成前不渲染，目标宠物不可用时丢弃交付，不退化为当前宠物的另一身份文案。`canRenderProactiveTaskDelivery` 进一步校验宠物身份。
- 阶段 4 相关测试：`proactiveExpressionGate.test.ts`、`proactiveTriggerEngine.test.ts`、`proactiveDelivery.test.ts`、`proactiveTaskControl.test.ts`；覆盖无标题上下文、普通 Memory 隔离、幂等、安静时段、每日上限、忽略退避、聚合、终态任务过滤、重启恢复、决策解释和多宠物路由；忽略退避另有真实投递/忽略序列回归测试。
- 验证：`npm test` 54 个文件、484/484 通过；`npm run build` 成功；`cargo test` 10/10 通过；`cargo check` 成功。
- 当前结论：✅ 阶段 4 已通过完整重验，允许进入并完成阶段 5 的本地范围。
- 已知边界：正式 OS/任务栈提醒仍是用户明确建立的手动任务提醒；Trigger Engine 控制新增的主动宠物表达，不用主动策略覆盖正式提醒事实。

## 阶段 5：本地持久化与云端迁移准备

- [x] 先为本地存储抽象 Repository，不把 UI 直接绑定到 localStorage 或 SQLite API。
- [x] 为实体预留 UUID、`deviceId`、`schemaVersion`、`syncVersion`、`deletedAt`。
- [x] 本地事务和 Outbox Event 同时写入。
- [x] 设计 Provider 无关的未来同步事件契约和 `event_id` 幂等机制；本阶段不上传云端。
- [ ] 需要跨设备时再引入 PostgreSQL 作为事实源。
- [ ] 需要大量语义检索时再加入 PostgreSQL + pgvector。
- [x] 在本地事实实体上用 Tombstone 表示删除，并为未来传播保留删除事件；摘要、缓存和向量派生数据的云端传播尚未实现。
- [ ] 云端部署时增加 RLS、TLS、审计和最小权限角色。

### 阶段 5 实施与验收记录

- 新增 Provider 无关边界：`src/storage/localRepository.ts`；UI 通过 Task/Memory Repository 或既有领域 API 读写，`App.tsx` 的当前宠物本地设置也不再直接调用 `localStorage`。
- 事实实体：Task 仍以 `yuxin.tasks.v1` 为兼容入口，TaskDatabase 信封和每个 Task Outbox 事件补齐 `id`、`deviceId`、`schemaVersion`、`syncVersion`、`updatedAt`、`deletedAt`；Memory 仍以 `yuxin-companion-memory-v1` 为兼容入口并补齐 `deletedAt`。Proactive 表达门控、用户偏好、Care Reminder 和当前宠物选择仍是独立的派生/设置边界，未被错误串写进 Task 或 Memory 事实。
- `syncVersion` 使用同一设备级单调计数器；`deviceId` 首次生成后持久化并跨 Repository 初始化保持稳定；`schemaVersion` 保留实体/事件版本，旧 Task schema 1/2 和旧 Memory 条目可兼容读取，缺失字段安全补默认值。
- Outbox 事件至少包含 `eventId`、`entityType`、`entityId`、`operation`、`schemaVersion`、`deviceId`、`createdAt`、`syncVersion`，并可携带脱敏后的 `updatedAt`、`deletedAt` 和 payload。事件 ID 按设备、实体、操作和同步版本确定，重复追加按 ID 幂等；`applyOutboxEvent` 通过已见事件 ID 和版本顺序避免重复应用。
- localStorage 不是完整事务数据库：Repository 用写入 journal、回滚、删除守卫和下次初始化恢复处理主记录、Outbox、同步计数器的中途异常；写入失败、配额/权限异常、损坏 JSON、journal 异常、journal 清理中断和多次初始化均 fail-safe。Task/Memory 旧数据不会因信封迁移丢失；物理清理后的事实仍通过 delete Outbox 事件保留 Tombstone 语义，删除守卫不会保存原始内容。
- Memory Outbox 仅保存安全投影，不保存完整聊天记录；密码、Token、银行卡、医疗信息、精确地址和原始聊天/证据字段会被过滤。`SOUL.md` 继续作为宠物包内只读资产，不进入同步数据。
- 阶段 5 相关测试：`src/storage/localRepository.test.ts`、`src/task-core/taskStore.test.ts`、`src/pet-core/companionMemory.test.ts`，覆盖主记录/Outbox/同步计数器中断、journal 清理中断、损坏 journal、删除守卫和 Task 提醒停止。
- 全量验证结果以本次 2026-08-03 运行记录为准；不要沿用本节历史的旧测试数量。
- 尚未实现：PostgreSQL/SQLite 云端事实源、远程上传、跨设备同步、冲突合并、RLS/TLS/审计/权限服务、向量数据库、Embedding、Kafka、Temporal 和多 Agent。

### 阶段 5 云端扩展进入条件

本地 Repository 和迁移准备已经完成；只有出现明确需求或测量证据时才实施云端扩展：多设备同步、远程推送、记忆量增长、检索延迟或本地容量成为瓶颈。

## 阶段 6：规模化进入条件评估与同步契约硬化

- [x] 用隔离 fixture 测量 Memory、Outbox、关键词检索、Task 扫描、主动触发评估和本地恢复。
- [x] 验证 delete-first Tombstone 不被旧 upsert 复活，且不同 `deviceId` 的 `syncVersion` 不直接比较。
- [x] 明确当前跨设备冲突合并、远端 ack/cursor、权限审计和删除传播仍是云同步前置阻塞。
- [x] 新增 `docs/agent-memory-scale-readiness.md`，区分实测事实、候选阈值、成本/隐私风险和 Go/No-Go。
- [ ] 只有 PostgreSQL + pgvector 出现明确瓶颈后，评估 Qdrant 或 Milvus。
- [ ] 只有异步任务量和可靠性要求超过单 Worker 后，评估队列系统。
- [ ] 只有跨天、可恢复、强审计工作流成为核心需求后，评估 Temporal。

### 阶段 6 实施与验收记录

- `src/storage/agentMemoryScaleReadiness.test.ts` 只使用内存 fixture：200 条 Memory、256 个 Outbox 事件、1,000 条 Task/500 个主动候选；包含损坏数据、写入失败、journal 重启恢复和 delete-first 回归。
- 本次 fixture 实测：Memory 关键词检索 p50 1.3230 ms / p95 2.2991 ms；Task 扫描 p50 3.4906 ms / p95 5.3915 ms；主动评估 p50 61.7660 ms / p95 71.3288 ms；恢复场景全部通过。
- 相关测试命令和完整结果记录在 `docs/agent-memory-scale-readiness.md`；这些是当前边界样本证据，不是生产容量承诺。
- 当前结论：✅ Go 留在本地；❌ No-Go 引入云端同步、PostgreSQL/pgvector、独立向量库、Kafka、Temporal 或远程上传。

## 每阶段通用完成标准

- [x] 只修改当前阶段涉及的文件和逻辑。
- [x] 保留用户已有工作区改动，不使用破坏性 Git 命令。
- [x] 为新增纯逻辑补单元测试。
- [x] 运行相关测试和 `npm run build`。
- [x] 记录未完成项、已知限制和下一阶段入口。
- [x] 不把临时调试文件、密钥、Prompt 日志或生成资产混入项目。
