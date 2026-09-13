# Companion Harness V1 TODO

> 状态：Phase 8-R4-H 真实 Windows 200% DPI Tauri Settings A-G 复验通过，当前 H 结论为 `TAURI_SETTINGS_PASS`；本轮全量 Vitest 另受工作树既有 pet manifest/test 参数不一致阻断。pre-QA 原始资料未知，真实 Provider、打包、发布和 Git 发布仍未完成
> 审查日期：2026-08-20
> 产品：愈心
> 输入文档：`Companion Harness PRD v1.2`、`Companion Harness Technical Design v1.2`

## 1. 审查结论

两份 v1.2 输入文档已经与当前桌宠高度契合，产品方向和技术边界均无阻塞项：统一 AI 入口、Local First、One Call First、模型只提候选、真实执行后再确认、共享用户事实并隔离宠物关系、Task / Reminder 远程零外发、主动提醒先过本地策略，这些都与现有实现和数据契约一致。

下表保留 v1.1 审查时发现的问题及其处理依据；这些适配决定已经写入两份 v1.2 源文档。本 TODO 只负责把已冻结设计拆成实施、验收和发布门禁，不再充当源文档冲突的补丁层。

| v1.1 审查发现（已在 v1.2 修正） | 当前项目事实 | v1.2 / TODO 决定 |
|---|---|---|
| Harness 可能被理解成 Agent Runner / Tool Loop | 旧路线中仍有最多 4 次 Provider 调用与 Tool Call 循环的规划 | v1.2 已明确 Harness V1 是单次请求编排层；不做 Tool Loop、ReAct、Planner、Critic 或二次“修文案”调用 |
| Service 后面默认是 SQLite | 当前 Memory、Task、Outbox 已有经过恢复与删除保护验证的本地 Repository / `localStorage` 事实源 | v1.2 已改为复用现有本机持久化；不迁移 SQLite，不建立第二套 Repository |
| Provider 是 Local / Gemini / Custom Gemini | 当前已统一为 `local`、`gemini-native`、`openai-compatible` 协议，Custom Gemini 是 Profile/Endpoint 配置问题 | v1.2 已采用现有 Provider Profile + Protocol + Adapter，不退回写死厂商枚举 |
| 技术设计把 Action/Memory 提取能力和领域 Envelope 放进 Provider | 阶段 7 已冻结最小、供应商中立的传输合同；Task、Memory、Soul 不能反向耦合到 Adapter | v1.2 已将领域语义收回 Harness 自有 `CompanionModelPort` / Codec；Provider Adapter 只实现通用传输与结构化输出能力 |
| Memory scope 为 `user_global` / `pet_relationship`，类型为 profile/person/project 等 | 当前持久化契约是 `global` / `pet:<id>`，类型为 fact/relationship/episode/preference | v1.2 已直接复用现有 Memory schema，并记录产品语义映射，不复制数据 |
| 普通模型回复可产生 Memory Candidate | 当前正式契约只允许“用户明确要求”或“用户确认后”的低风险长期写入 | v1.2 已冻结候选默认不落盘；只有 explicit / confirmed 且通过隐私、作用域、重复、冲突、时效检查后才保存 |
| TaskService 与 ReminderService 看似是两个事实源 | 当前 Reminder 是 `TaskDatabase` 中绑定 Task 的子实体，Task 是唯一任务事实源 | v1.2 已明确 Reminder facade 复用现有 Task Store，不新建 Reminder 数据库 |
| Context 可选择“相关或近期到期”Task | 正式远程白名单没有 Task/Reminder；现行 Context/Provider 请求也不携带这些事实 | v1.2 已冻结不向远程 Context 注入任何 Task/Reminder 投影；相关性、近期到期或优先级均不是外发理由 |
| Context 可包含 User Profile 与 Conversation History | 当前个人资料中的性别、邮箱、电话明确不得进入远程 Provider；完整原始聊天默认不长期保存 | v1.2 已改为穷举白名单、当前运行时 Session 安全片段，且不新增完整聊天持久化 |
| 技术设计 Action 示例缺少 PRD 中的 `update_reminder` | PRD 必做项包含它，现有代码已具备延期/改期能力 | v1.2 Action 合同已补齐 `update_reminder`；现有 cancel/postpone/reschedule 继续作为受控本地兼容动作 |
| `CompanionInput` 只有业务字段 | 当前 UI 已有 request id、`AbortSignal`、停止回复、切宠物和迟到结果保护 | v1.2 已补入 request/session/source-message identity、当前时间与取消信号；取消后不得产生新副作用 |

### 本 TODO 的范围权威

- 本文件是 Companion Harness V1 唯一有效的实施、验收和发布门禁清单；V1 的所有后续开工项只从本文件领取。
- [Agent / Memory / Task TODO](agent-memory-todo.md) 阶段 0--7 继续作为已验收底座的权威记录，正文不由本文件改写；[数据与隐私合同](agent-memory-data-contract.md) 继续有效。
- [Agent / Memory / Task TODO](agent-memory-todo.md) 原阶段 8--11 已被本文件整体替代，只保留历史路线背景，不再提供可执行勾选项；其中多次 Provider Tool Loop、Tool Registry 和 `pet.express` 均不是 Harness V1 要求。
- 输入文档中的推荐目录只是参考。V1 不做大规模搬目录；新增纯逻辑继续放在 `src/pet-core/`，复用 `src/task-core/`、`src/storage/` 和现有 Tauri 模块。

## 2. V1 冻结边界

### 必须成立

- 所有聊天发送最终只走 `UI -> CompanionHarness -> Harness-owned CompanionModelPort / Local Domain -> UI`。
- 模型边界固定为 `CompanionHarness -> Harness-owned CompanionModelPort -> Provider Adapter`；领域 Envelope 的组装、解析和校验属于 Harness，Provider Adapter 不认识 Action、Memory、Task 或 Soul 语义。
- 能由本地确定性规则完成的请求使用 0 次外部模型调用。
- 需要远程模型的普通聊天最多 1 次外部调用。
- Reply、Action Candidates、Memory Candidates 在同一次远程响应中返回；不再调用模型修正回复。
- Model 只能提出候选；Schema、权限、明确意图、业务规则、去重、执行和最终成功确认都归 Harness / Domain Service。
- Action 只有在领域写入成功后才能显示成功；写入失败、目标歧义、重复、取消和超时均不得包装成成功。
- V1 的 `REMINDER_DUE` 与 `TASK_DUE_SOON` 始终使用本地宠物文案，0 次模型调用；AI Enhanced 仅保留为未来非 Task / Reminder 事件的扩展边界，不在 V1 接远程路径。
- Scheduler 只产生事件，现有 Proactive Gate 决定是否允许表达，Harness 不能绕过勿扰、冷却、次数、幂等和宠物路由。
- API Key 仍只从系统安全存储进入 Provider Adapter 的短生命周期调用参数，不进入 Prompt、Harness Response、普通日志或持久化对象。
- 当前用户输入、历史、Soul、Preference 和已确认 Memory 在远程调用前继续经过统一 fail-closed 隐私过滤；Task、Reminder、ReminderInstance 及其派生投影不进入 V1 远程 Context。

### 明确不做

- 不做 Agent Loop、Tool Calling 循环、Decision LLM、Planner、Critic、Multi-Agent 或后台自由思考。
- 不做 Browser、Email、Calendar、文件、Shell、系统控制或任意外部工具。
- 不新增 SQLite、Vector DB、Embedding Pipeline、云同步、远程 Outbox Transport 或账号系统。
- 不持久化完整 Prompt、完整原始聊天、模型原始响应或敏感 Context。
- 不用 Harness 重写现有 Task Scheduler、Memory Repository、Task Store、Provider 安全存储或宠物资源边界。

## 3. 目标运行流程

```text
CompanionInput
  -> Turn / cancellation guard
  -> LocalRequestHints + current deterministic route
  -> local-only request? -> Action/Memory Domain -> ResponseFinalizer
  -> ContextBuilder + ContextBudget + privacy projection
  -> Harness-owned CompanionModelPort
     -> Harness Model Codec
     -> domain-neutral Provider Adapter -> one Provider request
  -> normalized CompanionModelResponse
  -> ActionPolicy -> existing Domain Service -> ExecutionResult
  -> MemoryPolicy -> existing MemoryRepository
  -> ResponseFinalizer (local, deterministic)
  -> current runtime Session + UI
```

主动事件固定为：

```text
TaskDatabase / ReminderInstance
  -> existing Scheduler / scan
  -> stable CompanionEvent
  -> existing Proactive Gate
  -> ignore | local expression
  -> existing pet delivery route
```

## 4. 核心合同 TODO

### 4.1 Harness 输入输出

- [ ] 新增 `src/pet-core/companionHarnessTypes.ts`，定义由 Harness 拥有且与 Provider Adapter 解耦的 `CompanionInput`、`CompanionResponse`、`CompanionEvent`、`CompanionModelResponse`、`ActionCandidate`、`ActionExecutionResult` 和 `MemoryPolicyResult`。
- [ ] `CompanionInput` 至少携带 `requestId`、`sessionId`、`sourceMessageId`、`petId`、`message`、`source`、当前时间、IANA timezone（可得时）、offset 和 `AbortSignal`。
- [ ] 当前产品是单机单用户，不为满足设计稿而虚构账号系统；如合同保留 `userId`，V1 只能使用稳定的本地默认值，不能据此声称已支持多账号隔离。
- [ ] `CompanionResponse` 返回最终文本、Provider 披露、Action/Memory 结果摘要、是否降级和本轮外部调用次数；不得返回 Key、完整 Prompt 或原始敏感参数。
- [ ] Action Result 使用可表达真实领域结果的状态：`succeeded`、`duplicate`、`not_found`、`ambiguous`、`confirmation_required`、`rejected`、`failed`、`cancelled`，不只使用一个含糊的 boolean。

### 4.2 Harness 编排器

- [ ] 新增 `src/pet-core/companionHarness.ts`，以依赖注入方式接收 Context、`CompanionModelPort`、Task、Memory、Proactive 和安全日志接口；文件本身不读写 SQL / `localStorage`，不直接依赖 Provider Adapter，也不发 HTTP。
- [ ] 暴露 `respond(input)` 与 `handleEvent(event)`；两条路径共享安全、Provider 和可观测性边界，但主动事件不得进入聊天 Action 执行路径。
- [ ] 每个 Session 同时只允许一个活动 Turn；新发送、停止、退出、换宠物时取消旧 Turn。
- [ ] Provider 返回后、每个副作用执行前、写入最终 UI 前都检查 request identity 与 `AbortSignal`。
- [ ] 为已开始的写操作定义明确边界：写入前取消则不执行；写入已经成功则记录真实结果，不能伪装成“未发生”或重复执行。
- [ ] 本地显式路由与模型候选使用统一去重键，保证同一句话不会被本地 Extractor 和模型各执行一次。

### 4.3 LocalRequestHints

- [ ] 保留并复用 `resolveCompanionChatPipelineRoute()`、Task/Memory/Preference Extractor 和主动偏好解析器，把结果规范化为 hints / local candidate，而不是再写一套中文意图识别。
- [ ] 本地路由只提供确定性证据和本地完成能力；不得因为关键词存在就提升模型候选权限。
- [ ] 明确低风险、时间完整的 Task/Reminder 继续 0 API 创建；含糊时间、敏感内容、高风险或目标不唯一时进入确认/拒绝，不交给模型越过门禁。
- [ ] 对本地路由、模型候选和 Provider text-only fallback 增加“唯一所有者”测试，确保每轮最多执行一条等价写操作。

## 5. 分阶段实施

### Phase 1：纯 Harness 骨架与 Turn 安全

目标：先建立不依赖 React 的单次编排器，不改 UI 行为。

- [x] 完成 Harness 类型、依赖接口和最小 `respond()` 骨架。
- [x] 复用当前 Provider 错误分类、15 秒超时、远程失败后至多一次本地降级与降级披露。
- [x] 加入 request/session/message identity、取消、迟到结果丢弃和调用次数计数。
- [x] 建立 Fake `CompanionModelPort` / Fake Domain Services，覆盖纯文本成功、超时、取消、畸形回复、领域失败与本地降级；Phase 1 不修改 Provider 协议。
- [x] 普通聊天允许无 Action、无 Memory Candidate 直接结束。

验收门：

- [x] 纯文本远程聊天恰好 1 次 Provider 调用；本地聊天 0 次外部调用。
- [x] 取消后的迟到响应不能写 UI、Memory 或 Task。
- [x] Harness 纯逻辑测试通过后才进入 App 接线。

### Phase 1 实施记录（2026-08-11，严格收口复验）

- 进度：5/5；验收门：3/3。
- 新增纯逻辑 Harness、Harness-owned `CompanionModelPort` 合同和 Fake 测试；Turn 以 request/session/source-message/user/pet identity 绑定，支持取消、15 秒超时、迟到丢弃、0/1 外部调用计数和至多一次本地降级。
- 严格收口：fallback 只有 `info.kind === "local"` 才允许调用；通用 Model Attempt 边界把 remote 外部调用硬限制为每 Turn 1 次；异步 Sink 必须通过 Harness Turn Guard 在最后一刻提交，Harness 在 `await commit()` 后再次检查有效性。
- 对抗证据：主远程失败且 fallback 为 remote 时，fallback `generate()` 0 次、`external=1`、结果非成功降级；合法 Local fallback 为 `external=1/local=1/fallback=1`；旧 Turn 被 supersede 或取消后 Sink 写入数为 0。
- 证据（Phase 1 收口时）：Harness 定向测试 24/24；相关 Companion Provider/Runtime/Pipeline/Context/Privacy 回归 74/74；`npm run build` 通过；`git diff --check` 通过。
- 范围声明：本轮没有接入 `App.tsx` 或 React UI，没有修改 Gemini-native、OpenAI-compatible 或 Local Provider 协议，没有实现真实 Task、Reminder、Memory Action，没有实现 Context Budget 或 Proactive Event，也没有进入 Phase 2。
- Fake/纯逻辑测试不等同于真实 Provider、Tauri 实机或可发布验证；本记录不表示整个 Harness V1 已完成。

### Phase 2：ContextBuilder 与全局 Budget

目标：扩展现有 `companionContext.ts`，不重写已有 Soul、Preference、Memory 和隐私过滤。

Phase 2 前置门禁（2026-08-11 已完成）：

- [x] 正式数据合同已把远程允许内容改为穷举白名单，并明确排除 Task、Reminder、ReminderInstance、Task 派生摘要和 Outbox Task Event。
- [x] 现行 `CompanionContextAssemblerInput`、Provider 输入和 Gemini-native / OpenAI-compatible 请求体均未携带 Task/Reminder 字段，未发现需要保留的既有外发兼容行为。
- [x] Context 与双远程协议请求体 fixture 已覆盖相关、近期到期、无关、已完成、已取消、已删除 Task 以及 Reminder/ReminderInstance sentinel；当前边界通过后才允许实施以下 Budget 工作。

- [x] 新增可测试的全局 Context Budget；以字符数/保守 token 估算控制总量，而不是只靠各数组固定条数。
- [x] 新增纯逻辑 ContextBuilder；可注入 Harness、遵守 AbortSignal，并在 Context 完成后保持 provider-neutral 的最终隐私门禁。
- [x] 固定优先级：平台安全与权限 > 当前用户输入 > 当前宠物 Soul > 当前运行时 Session > 相关已确认 Memory；Task/Reminder 不参与远程 Context Budget。
- [x] 保留 `global` 与 `pet:<id>` 检索；宠物关系 Memory 只进入对应宠物 Context。
- [x] Harness V1 不读取 `TaskDatabase` 来构造远程 Context，也不发送 Task、Reminder、ReminderInstance、Task 摘要或 Outbox Task Event；“相关”“近期到期”“高优先级”均不能触发例外。
- [x] 用户明确讨论某个任务时，当前用户输入仍按普通输入白名单处理，但不得据此 join 本地 Task 事实；现有明确 Task/Reminder 本地确定性路由保持不变，本轮未改动其领域执行。
- [ ] 未来如确需最小 Task 投影，必须先修订 `docs/agent-memory-data-contract.md`，冻结明确讨论条件、逐字段 allowlist、终态/删除语义和用户披露，并先完成双远程协议隐私 fixture；不得只修改本 TODO 或先写实现。
- [x] `currentTime`、IANA timezone（可得时）和当前 offset 只进入 `CompanionInput` 的本地 Task Extractor / Handler；V1 Model Codec 不把它们编码进远程 Context，也不直接信任模型时间。
- [x] User Profile 只允许昵称等已经授权的低风险投影；邮箱、电话、性别和其他未授权字段不进入 Provider Context。
- [x] 远程发送前执行最终 privacy pass；当前输入命中敏感规则时不发起远程请求。
- [x] Budget 裁剪产生可测试的非敏感摘要元数据，但不记录被裁掉的原文。

验收门：

- [x] Global Memory 跨宠物可见，Relationship Memory 不跨宠物。
- [x] 超预算时按固定优先级裁剪，永不裁掉安全规则和当前用户输入。
- [x] 密码、Token、Key、证件、卡号、精确地址、医疗/用药及历史敏感消息均不进入远程请求 fixture。
- [x] 相关、近期到期、无关、已完成/取消和已删除 Task，以及 Reminder/ReminderInstance sentinel，均不出现在 Gemini-native 或 OpenAI-compatible 请求体；已有确定性 Task 路由测试保持 Provider 分支之外。

### Phase 2 实施记录（2026-08-11）

- 进度：Phase 2 实施项 10/10；验收门 4/4。条件性的未来 Task 最小投影门禁未触发，继续保留为未勾选的变更前置条件。
- 新增 provider-neutral 全局 Budget：默认上限为 12,000 Unicode code points 与 8,000 个保守 token 估算；保护平台安全规则和当前输入，按 Memory → 旧 History → Preference → 可选系统指令 → Soul 的固定顺序裁剪，Soul 只在 code-point 边界裁剪，超出必需内容预算则 fail closed。
- 新增纯逻辑 ContextBuilder：可注入 Soul、Preference、Memory、History 或现有 `MemoryRepository.search` 边界；在构建前后检查 `AbortSignal`，Memory 按 `global` / 当前 `pet:<id>` 隔离，global relationship fail closed；最终远程 privacy pass 在两种协议之前再次执行。
- 隐私与时间证据：昵称等低风险 Profile 投影可保留；性别、邮箱、电话以及密码、Bearer Token、Key、证件、卡号、精确地址、医疗/用药和历史敏感内容均在远程发送前拒绝或过滤。`currentTime`、timezone、offset 只保留在本地输入边界，Budget metadata 仅含计数、枚举和裁剪原因，不含原文。
- Task/Reminder 证据：ContextBuilder 与 Budget 无 Task/Reminder import 或读取；相关、近期到期、无关、已完成、已取消、软删除、物理删除 Task，Reminder、ReminderInstance、Task projection、Tombstone、Outbox 和时间 sentinel 均未进入 Gemini-native 或 OpenAI-compatible body。现有确定性 Task 路由测试仍在 Provider 分支之前；本轮未改动 Task 领域执行。
- 测试与构建：Harness `27/27`；Context/Budget/Privacy 定向组 `51/51`；Provider/Pipeline 定向组 `35/35`；全量 `npm test` 为 `69` 个文件、`660` 个测试全部通过；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 与本轮 10 个范围文件的空白/冲突标记检查通过。
- 范围声明：本轮只修改 Companion Harness、Context/Budget/Privacy 相关逻辑、测试和本 TODO；未接入 `App.tsx` 或 React UI，未开始 Phase 3，没有真实远程凭据/网络冒烟、Tauri 实机或视觉 QA，没有 Rust 改动或 Cargo 验证，没有 commit、push 或发布。

### Phase 2 强制收口复验（2026-08-11）

- 进度确认：Phase 2 实施项 10/10；验收门 4/4；此前条件性的 Task 最小投影门禁仍未触发，继续保持未勾选。
- A1 允许列表：远程 Preference / Profile 改为 exact allowlist；只保留已授权的全局昵称、replyStyle、companionStyle、eyeCare，以及当前宠物的 nickname / favorite / relationshipStyle；未知 key、其他宠物 scope、邮箱、电话、性别和伪装后的 Profile 敏感值均在最终门禁丢弃。完整 `CompanionUserProfile` 不进入 ContextBuilder 或 Provider 请求。
- A2 Trusted Context：正式 `assembleCompanionContext()` 输出带运行时 trust marker 并冻结；远程 `filterCompanionContextForRemote()`、Model Codec 和 Model Port 对手写/伪造/不匹配 Context fail closed，未通过时 Adapter / fetch 调用数为 0；本地 Adapter 仍可只接收当前用户输入。
- A3 token / CJK / emoji：`estimateCompanionTokens()` 使用 UTF-8 byte 数作为 provider-neutral 的保守代理，不假装等同厂商 tokenizer；`A=1`、`你=3`、`🙂=4`、`A你🙂=8`、组合字符 `e\u0301=3` 均有断言，字符上限与 token 上限分别计数并记录裁剪原因。
- 证据：Phase 2 定向组 `113/113`；Phase 2 + Phase 3 定向组 `145/145`；全量 `npm test` 为 `73` 个文件、`699` 个测试全部通过；`npm run build` 通过；`git diff --check` 通过。
- 范围声明：本次收口没有修改 `App.tsx`、Task / Reminder / Memory 执行、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 凭据、网络冒烟、Tauri 实机或视觉 QA 证据，不表示 Harness V1 已完成或可发布。

### Phase 3：Harness-owned CompanionModelPort 与领域中立 Provider Adapter

目标：由 Harness 拥有领域响应合同；现有 Adapter 只负责协议与传输，不引入 Tool Loop，也不重新耦合 Task / Memory 语义。

- [x] 在 Harness 侧新增 `CompanionModelPort`；它接收 Harness 模型请求并返回 `CompanionModelResponse`，是 `replyDraft`、`actions[]`、`memoryCandidates[]` 和非敏感 metadata 的唯一领域边界。
- [x] 新增 Harness-owned Model Codec，把安全 Context 转成通用 Provider 请求，并把 text / structured payload 解码成 `CompanionModelResponse`；Envelope 的 Prompt、Schema、解析与校验都不得下沉到 Provider Adapter。
- [x] Provider 能力只允许描述通用协议/传输事实，例如 text generation、已验证的 structured output / JSON Schema、取消、超时和 usage metadata；不得增加 `actionCandidates`、`memoryCandidates`、`memoryExtraction` 或其他桌宠领域 capability flag。
- [x] 保留现有 `send()` 作为迁移期兼容入口；如新增通用 `generate()`，其输入输出只能包含 system/messages、通用输出格式、文本/结构化 payload 和传输 metadata，不能导入 `ActionCandidate`、`MemoryCandidate`、Task、Memory 或 Soul 类型。
- [x] 未知/自定义协议默认 text-only 并 fail closed；结构化能力必须由 Adapter 明确验证，不能从 Provider 名称、Endpoint 或 Model 名称猜测。
- [x] 对 Harness Envelope 做严格运行时校验、长度限制、枚举校验和多余字段丢弃；畸形 candidate 一律不执行。
- [x] `local` Adapter 明确只提供文本；Task/Memory 核心能力由本地 Extractor 保持可用，不伪造模型候选。
- [x] `gemini-native` 只在通用 Adapter 能力确认支持时请求 structured payload；厂商请求字段不泄漏到 `CompanionModelPort`。
- [x] `openai-compatible` 的自定义 Endpoint 不假定支持某个厂商专属 `response_format`；能力未知时退回 text-only，不把解析失败当 Action。
- [x] Provider 连接测试继续是用户主动操作，且不经过领域 Envelope，不触发 Memory/Action；本轮保留 App 既有连接测试入口，未进行 App 接线迁移。
- [x] Key 只作为短生命周期 Adapter 参数使用；错误对象、metadata 和测试快照不得包含凭据或完整请求体。

验收门：

- [x] Local、Gemini-native、OpenAI-compatible 共用一套只验证通用请求、协议映射、取消、超时、错误和安全 metadata 的 Provider Adapter 合同测试。
- [x] `CompanionModelPort` / Model Codec 单独覆盖 text-only、合法 Envelope、畸形 Envelope、超长字段、未知 Action 和结构化能力降级。
- [x] 增加 import/类型边界检查：Provider Adapter 模块不得依赖 Harness 的 `ActionCandidate`、Memory Candidate、Task、Memory 或 Soul 领域类型。
- [x] 超时、取消、401/403、429、5xx 和网络失败均有覆盖；普通远程 Turn 的 Provider 请求数始终 `<= 1`。

### Phase 3 实施记录（2026-08-11）

- 进度：Phase 3 实施项 11/11；验收门 4/4。这里的“完成”仅指本阶段的纯逻辑 Model Port / Codec / Provider Adapter / Resolver 合同，不表示 App 已接管聊天或 Harness V1 可发布。
- Model Port / Codec：新增 Harness-owned `CompanionModelPort` 与 `companionModelCodec`；安全 Context 只编码为通用 system/messages/output/timeout/generation，内部 request/session/source-message/pet/time/budget 元数据不进入 Provider 请求；text-only 不从普通文本猜 Action / Memory，structured Envelope 严格校验 source id、scope、枚举、长度、数量、敏感字段和多余字段，畸形 structured 只使用同响应安全文本降级，不发第二次请求。
- Adapter / Resolver：新增领域中立 `companionProviderAdapter.ts` 与 `companionProviderResolver.ts`，统一 Local、Gemini-native、OpenAI-compatible 的通用协议映射；Local 强制 text-only 且 0 网络调用，远程 structured 仅接受显式 verified capability，未知协议/能力 fail closed；Key 只在 Adapter 闭包和请求 Header 的短生命周期内存在。
- 兼容与连接边界：旧 `send()` 保留为迁移兼容入口并复用通用 Adapter / Codec 的 wire mapping；连接测试仍由用户主动触发，使用 text-only 请求，不进入领域 Action / Memory 执行；未修改 `App.tsx`，未宣称 App 已接线。
- 对抗证据：覆盖远程手写/伪造/输入不匹配 Context 的 0 Adapter 调用、本地不可信 Context 的当前输入最小路径、Provider 失败分类、Abort/timeout、401/403/429/5xx/network/malformed、凭据 sentinel 不出现在错误/metadata/快照，以及每个普通远程 Turn 仅 1 次 Adapter 调用。
- 测试与构建：Phase 3 新增定向组 `32/32`；Phase 2 + Phase 3 定向组 `145/145`；全量 `npm test` 为 `73` 个文件、`699` 个测试全部通过；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 通过。
- 范围声明：本轮未修改 `App.tsx`、Task / Reminder / Memory Action Pipeline、Proactive、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 凭据/网络冒烟、Tauri 实机或视觉 QA、`cargo test` / `cargo check`、commit、push 或发布证据。

### Phase 2 / Phase 3 继续收口复核（2026-08-11）

- ContextBuilder 的历史投影现在只保留 `id`、`speaker`、`text` 和合法的内部 `contextEpoch`；本地 `sound`、`status` 以及任意附加 Task / Reminder 字段不会进入受信 Context，也不会进入 Codec 映射。
- Preference allowlist 对运行时异常对象继续 fail closed；Model Codec 对 `MemoryCandidate.expiresAt` 和 Provider metadata 做类型、长度与安全投影，畸形字段只丢弃候选，不重试 Provider。
- Phase 2 / Phase 3 九文件定向矩阵：`9` 个文件、`155/155`；全量 `npm test`：`73` 个文件、`708` 个测试；`npm run build` 通过（仅保留既有大 chunk warning）；`git diff --check` 及未跟踪范围文件空白、冲突标记、非预期 secret sentinel 和 Adapter import 边界检查通过。
- 本轮新增的受信 Context 对抗测试把 `petId` 与已提供的 `contextEpoch` 绑定到当前 Turn；旧 `send()` 兼容入口与新 `CompanionModelPort` 都会在 Adapter/fetch 前拒绝跨宠物或 epoch 不匹配的上下文。Provider Resolver 读取安全存储异常时只返回静态安全错误，不回显底层错误或 credential sentinel。
- 本轮仍未接入 `App.tsx`，未开始 Phase 4，未执行真实 Action / Memory 写入、真实 Provider 网络冒烟、Tauri 实机或视觉 QA；未修改 Rust，无 Cargo 证据；未 commit、push 或发布。

### Phase 3 P1 最终收口复核（2026-08-11）

- per-Turn Provider Snapshot 合同：`CompanionModelPort` 构造阶段不解析 Resolver；有效 Turn 通过 `beginTurn()` 只解析一次，并返回冻结的 `ResolvedCompanionModelTurn`，其中 `adapter`、复制冻结的 `info`、复制冻结的 `capabilities` 和捕获该 Adapter 的 `generate()` 同源。Harness 在该 Turn 的隐私门禁、Context 路径、trusted Context 检查、调用计数、远程上限、fallback、错误与最终披露中只使用该 snapshot；下一 Turn 才读取 Provider 新配置。兼容 `port.generate()` 也只创建一个自己的 snapshot，不使用动态 `info` getter。
- Snapshot 对抗测试已覆盖：构造时不解析；Local→Remote（Remote Adapter 1 次、external=1、local=0、Remote disclosure）；Remote→Local（Remote Adapter/fetch=0、external=0、local=1、Local disclosure）；Turn 中途切换保持旧 snapshot、下一 Turn 使用新 Provider；不同 Provider 下两个并发 Session 的结果、metadata、计数与 disclosure 互不污染；Remote 失败后只解析一次 Local fallback，external=1、local=1、fallback=1，且 fallback 非 Local 时在调用前 fail closed。
- Fail-closed 对抗测试已覆盖敏感输入、不受信 Context、`petId` / `contextEpoch` 不匹配：Adapter generate 与 fetch 均为 0，返回安全分类，不把 Context、credential 或 sentinel 带入响应。
- 完整 response body 生命周期：`fetchJsonWithTimeout()` 用同一个 `AbortController` 和 timeout 覆盖 fetcher、响应头和 `response.json()`；成功必须消费 body 后才清理 timer/listener/controller。`json()` 执行时 signal 保持未 abort；body 延迟但在期限内完成可成功；body 永不完成分类为 `timeout`；body 等待期间 parent abort 分类为 `cancelled`；普通 JSON 解析失败为 `malformed-response`；HTTP 401/403/429/500 即使错误 body 非 JSON 仍按 HTTP 分类。每个场景 fetcher 只调用一次，未回显底层异常或凭据。
- 真实验证证据：第一组定向命令 `5` 个文件、`80/80`；第二组定向命令 `9` 个文件、`172/172`；全量 `npm test` 为 `73` 个文件、`725` 个测试；`npm run build` 通过（仅保留既有大 chunk warning）；本轮文档变更后的 `git diff --check` 通过（Git 仅提示既有工作区文件的 LF/CRLF 转换 warning）。
- 范围与未验证项：本轮没有进入 Phase 4，没有接入 `App.tsx`，没有修改 Task / Reminder / Memory 执行、Action Pipeline、ResponseFinalizer、宠物资源、Live2D、Rust 或发布产物；没有真实 Provider 网络冒烟、真实 API Key、App 接线、Tauri 实机、视觉 QA、`cargo test` / `cargo check`、commit、push 或发布验证。未创建临时交付文件；构建产生的 `dist/` 仅为既有构建输出目录。

### Phase 4：Action Pipeline 与 ResponseFinalizer

目标：把“候选”和“真实执行”彻底分开，消灭虚假成功。

- [x] Action discriminated union 至少覆盖 `create_task`、`create_reminder`、`complete_task`、`update_reminder`。
- [x] 将现有 `cancel`、`postpone`、`reschedule` 保留为受控本地兼容动作；主动提醒偏好独立为 Harness-owned 本地领域请求，不进入 ActionCandidate / Model Codec / Provider Schema；未授权模型不能借未知 Action 名称调用这些本地能力。
- [x] Candidate 必须携带原始 source message id、明确性、时间信息和可验证目标；Provider 给出的 `intent: explicit` 不能单独作为自动执行依据。
- [x] `ActionPolicy` 同时检查：本地明确意图证据、Schema、隐私、时间、权限、业务规则、目标唯一性、重复和取消状态。
- [x] `create_task` / `create_reminder` 复用 `taskDraftFromCandidate()`、`createTask()`、`writeTaskDatabase()` 和现有重复检测。
- [x] `complete_task` 复用 `findTaskReference()` / `completeTask()`；模型提供的 task id 或标题都必须在当前活动 Task snapshot 中重新解析。
- [x] `update_reminder` 映射到现有 Task/Reminder 改期能力；过去时间、缺时区、模糊时间、无目标和多目标必须拒绝或要求确认。
- [x] 所有 Handler 只调用现有事实源；不得直接操作 React state 作为成功依据。
- [x] Action 幂等键至少绑定 session/message/action type/规范化目标；重试、双击或相同模型候选不得重复创建。
- [x] `ResponseFinalizer` 使用本地模板处理 Action 结果，不再请求模型。
- [x] Action-bearing Turn 在失败、歧义、拒绝或取消时必须覆盖 draft 中任何“已经完成”表述；不能只在后面追加一句失败说明。
- [x] 写入成功后再生成成功文案；写入失败时 UI、pending state 和 Task/Reminder 状态保持可恢复。

验收门：

- [x] 明确低风险提醒成功创建；模糊表达不自动创建；过去时间拒绝；重复提醒不重复写入。
- [x] complete/update 的目标不存在或不唯一时不修改数据库。
- [x] 领域写入失败、Provider 乱报成功、取消和迟到候选的“虚假成功确认”均为 0。
- [x] 每个支持 Action 同时断言最终文案、数据库事实和 Provider 调用次数。

### Phase 4 实施记录（2026-08-11）

- 进度：实施项 `12/12`；验收门 `4/4`。本记录只覆盖 Phase 4 纯逻辑 Action Pipeline 与 ResponseFinalizer，不代表 App 已接线或 Phase 5--8 已完成。
- 新增/修改：`src/pet-core/companionActionTypes.ts`、`companionActionPolicy.ts`、`companionActionPipeline.ts`、`companionResponseFinalizer.ts`、`companionPrivacy.ts`；收紧 `companionHarnessTypes.ts`、`companionModelCodec.ts`、`companionHarness.ts`；新增 `companionProactivePreference.ts`；新增/扩展对应 Pipeline、Harness、Codec、Finalizer、主动偏好和联合验收测试，并调整 Phase 1 Action fake 使用正式四类合同。
- Action 合同：模型 Envelope 仅允许 `create_task`、`create_reminder`、`complete_task`、`update_reminder`；每种 payload 与 `additionalProperties: false` Schema 均为 discriminated union。`cancel_task`、`postpone_task`、`reschedule_task` 仅作为本地兼容 union，不进入 Codec/Provider Action 名单。
- 唯一所有权：Harness 先重跑 `resolveCompanionChatPipelineRoute()` 及现有 Task Extractor；明确低风险 Task/Reminder 在 Provider snapshot 前执行，成功路径 `model=0/external=0`。模型 intent/evidence 不填充 Local Evidence；ActionPolicy 在 Schema、隐私、时间、时区、目标状态、重复和幂等检查任一失败时 fail closed。
- 主动提醒偏好唯一所有权：`mute`、`reduce`、`switch_pet` 复用 `parseProactivePreferenceCommand()`、`resolveProactiveTaskControlTarget()`、最近一次主动投递上下文、既有 TaskDatabase 和 Trigger Engine `setTaskPreference()`；通过注入的本地服务执行一次写入，不创建第二套偏好 Store，不进入四类模型 Action 合同。唯一目标、缺失/多目标、无最近上下文、无可切换宠物、依赖缺失、写入失败和取消分别返回真实的本地结果，并在所有这些路径保持 Provider / model begin / model generate 为 `0`。
- 事实与幂等：Handler 通过注入的 `CompanionTaskRepository.read/write` 使用现有 `readTaskDatabase()`、`writeTaskDatabase()`、`createTask()`、`updateTask()`、`completeTask()`、`taskDraftFromCandidate()`、`findTaskReference()`、`findDuplicateTask()` 和 `applyCompanionTaskOperationToDatabase()`；Handler Registry 串行执行，成功写入后才记录 `sessionId + sourceMessageId + action type + 规范化目标/时间` 幂等键。未引入第二套 Task/Reminder Store。
- 文案与长回复联合断言：ResponseFinalizer 完全本地且 `0` 次模型调用；Action-bearing Turn 忽略模型成功 draft，依据 `succeeded/duplicate/not_found/ambiguous/confirmation_required/rejected/failed/cancelled` 逐项生成诚实文案。普通无 Action 回复单独保留 Harness/Codec 已校验的最长 `2000` 字符，不再套用 Action 展示字段的 `120` 字符上限；Action 的 title/reference/triggerTime 继续严格限长和敏感过滤。写入失败、Handler throw、Policy reject、取消和 stale/late Turn 均不产生虚假成功文本；写入成功后取消保留数据库事实且阻止迟到 UI commit。
- 验证证据：`companionPhase4Acceptance.test.ts` 以同一场景联合覆盖 `create_task`、`create_reminder`、`complete_task`、`update_reminder`、`cancel_task`、`postpone_task`、`reschedule_task` 的最终文案、ExecutionResult、Task/Reminder/ReminderInstance 事实、Provider begin/generate、写入次数、重试/equivalent candidate 幂等、取消前不写和写入后迟到 UI commit；`companionProactivePreference.test.ts` 覆盖 mute/reduce/switch_pet、唯一/缺失/多目标、最近上下文、重试/双击、依赖缺失、写入失败、取消和 Provider 零调用；`companionResponseFinalizer.test.ts` 覆盖 121/2000 字符保留、超限/空回复 fail closed、Action-specific 文案和敏感展示过滤；`companionModelCodec.test.ts` 覆盖超限 malformed fail closed 及未知主动偏好 Action 不进入 Codec 合同。Phase 4 六文件定向组为 `111/111`；Harness / Codec / Task Extractor / Task Store / Proactive / Action 相关扩展定向组为 `12` 个文件、`194/194`；最终全量 `npm test` 为 `77` 个文件、`794` 个测试全部通过；`npm run build` 通过，仅有既有大 chunk warning。
- 未完成/未验证项：本轮未接线 `App.tsx`，未实现 Phase 5 Memory Candidate Policy，未开始 Phase 6 Proactive Event、Phase 7 App 收敛或 Phase 8 发布门禁；未接真实 Provider 网络/API Key，未做 Tauri 实机和视觉 QA，未做 Rust/Cargo 验证，未 commit、push 或 release。`update_reminder` 的正常 Task-bound Handler、主动提醒偏好和 ResponseFinalizer 均已有纯逻辑证据；真实 App 入口与未来明确 recurring-instance UI 解析仍留待后续阶段。

### Phase 4 P1 最终收口（2026-08-12）

- 状态：两个 P1 已修复并完成真实 storage 竞态复验；Phase 4 实施项 `12/12`、验收门 `4/4` 通过。此结论只覆盖纯逻辑 Action / ResponseFinalizer / 主动提醒偏好，不代表 App 接线或后续 Phase 已开始。
- Offset 约定已冻结：`CompanionInput.utcOffsetMinutes` 表示“当地时间减 UTC”（Asia/Shanghai `+480`、America/Los_Angeles 夏令时 `-420`）；旧 `TaskExtractorOptions.timezoneOffsetMinutes` 与 `TaskDatabase.settings.timezoneOffsetMinutes` 保留 JavaScript `Date#getTimezoneOffset()` 的“UTC 减当地时间”约定（上海 `-480`、洛杉矶夏令时 `+420`）。Harness 只在 `toLegacyTaskExtractorTimezoneOffsetMinutes()` 适配边界转换，不修改旧 Extractor / TaskDatabase 约定。
- 已检查 `buildLocalRequestHints()`、`TaskCandidate` / `TaskOperationCandidate` 构造、`localOperationFromCandidate()`、duplicate candidate、`currentLocalDateKey()` 和 create/update/postpone/reschedule Handler 输入；`currentLocalDateKey()` 继续直接使用 Harness 的当地时间减 UTC 约定，旧 offset 不再被直接赋给旧 Extractor。
- 精确时区证据：上海 `currentTime=2026-08-11T12:00:00.000Z`、`timezone=Asia/Shanghai`、`utcOffsetMinutes=480`，“明天下午四点”得到 `2026-08-12T08:00:00.000Z`，最终本地显示为 `8/12 16:00`（8 月 12 日 16:00）；UTC `utcOffsetMinutes=0` 得到 `2026-08-12T16:00:00.000Z`；洛杉矶 `currentTime=2026-08-12T06:30:00.000Z`、`utcOffsetMinutes=-420`（本地 8 月 11 日 23:30）下，“今天晚上十一点”得到 `2026-08-12T06:00:00.000Z` 并按过去时间拒绝，“明天早上八点”得到 `2026-08-12T15:00:00.000Z`，最终本地显示 `8/12 8:00`，日期-only “明天”得到 `2026-08-12`。
- writer 合同已冻结：`setProactiveTaskPreference()` 先计算 candidate，再调用现有 `writeProactiveExpressionState()`；只有其返回 `true` 才返回该 post-write state，返回 `false` 时抛出明确的 `ProactivePreferencePersistenceError`。因此服务层只把 writer 已确认的 state 当作 authoritative persisted state；writer 抛错或防御性 state 校验失败均为 `failed`，不会被 late abort 改写为成功。验证 read 抛错时保留已由 writer 确认的成功事实。
- 真实竞态矩阵已覆盖：A 写入前取消时 `setTaskPreference=0`、storage 写入不增加、Provider/model=0；B 实际 `storage.setItem()` 抛错时领域 `failed`、原偏好不变、无成功文案；C 实际 storage 抛错且 writer wrapper 在 `finally` abort 时仍为领域 `failed`，顶层 `cancelled`、`committed=false`、UI commit=0、无成功文案；D 实际写入成功后立即 abort 时领域 `succeeded`、顶层 `cancelled`、`committed=false`、UI commit=0，独立读取可见目标偏好；E 新 requestId 重试为 `duplicate` 且不增加写入；F writer 确认成功但 verification read 抛错仍保留 `succeeded`，独立 storage 读取可见目标偏好。A--F 的 Provider/model/external 调用均为 `0`。
- 新增/强化测试：`matrix A: aborts before the writer without invoking storage or Provider`、`matrix B: reports failed when the real storage writer throws`、`matrix C: keeps a storage failure failed when the writer aborts in finally`、`matrix D ... matrix E ...`、`matrix F: keeps writer-confirmed success when verification read fails`，并增加 Trigger Engine writer rejection 的直接断言；A 直接断言实际 `setTaskPreference()` 调用为 `0`，B--F 覆盖实际 writer 调用、storage 原始事实、写入次数、领域/顶层状态、UI commit、成功文案和 Provider/model 调用次数。
- 本轮验证：目标要求的 Phase 4 定向组 `7` 个文件、`127/127`；全量 `npm test` 为 `77` 个文件、`800` 个测试全部通过；`npm run build` 通过，仅保留既有大 chunk warning。
- 范围与未验证项：本轮未修改 `App.tsx`，未实现 Memory Candidate Policy，未开始 Phase 5--8；未接真实 Provider/API Key，未做 App 接线、Tauri 实机、视觉 QA、Rust/Cargo、commit、push 或 release。上述纯逻辑测试和构建不等同于运行时或可发布验证。

### Phase 5：Memory Candidate Policy

目标：在同一模型响应中接收候选，但继续遵守当前显式/确认写入契约。

- [x] Candidate 增加 source/evidence、scope、candidate category、lifetime、expiresAt、confidence、importance、explicitness 和 confirmation 状态。
- [x] Candidate 直接使用现有 `global` / `pet:<activePetId>` 作用域；模型不得指定另一只宠物的关系作用域，也不得引入 `user_global` / `pet_relationship` 第二套持久化值。
- [x] 将 PRD category 映射到现有持久化类型：profile/person/project/goal -> fact，event -> episode，preference -> preference，宠物共同经历 -> relationship。
- [x] 只有当前输入明确要求“记住”或用户确认后的候选才可保存；普通聊天推断、情绪、假设、敏感信息和模型自行提高 confidence 均不落盘。
- [x] 在 `MemoryPolicy` 中实现规范化、隐私检查、scope 检查、精确/近似重复、冲突、temporal 过期和 insert/update/ignore 决策。
- [x] 冲突只有在当前用户明确纠正或确认时才能 supersede/update；模型不能凭自己的推断覆盖旧事实。
- [x] 复用现有 `MemoryRepository`、Tombstone、Outbox 和删除保护；不创建第二个 Memory Store。
- [x] Memory 保存失败不阻塞正常聊天或已完成 Action，但必须给出诚实且不含原文的安全结果。

验收门：

- [x] 覆盖 global、pet relationship、duplicate、conflict、temporal expiration、敏感拒绝和保存失败。
- [x] “我今天好累”不保存；“我喜欢桂花茶，请记住”只保存一条；跨宠物关系不泄漏。
- [x] Memory Candidate 数量不能改变本轮 Provider 调用次数。

### Phase 5 基础实施记录（2026-08-12，已由 P1 最终收口记录取代）

- 进度：这是 P1 最终收口复验前的基础实现记录，不作为当前 Phase 5 最终通过数字。本轮只完成 Memory Candidate Policy 纯逻辑实现与验收，没有进入 Phase 6。
- Candidate/Codec：收紧 `MemoryCandidate` 合同，加入 source/evidence/sourceMessageId、scope、category/candidateCategory、lifetime/expiresAt、confidence/importance、explicitness 和 confirmationStatus；Schema 使用 `additionalProperties: false`、枚举/长度/数量/有限数值范围，并拒绝跨消息、跨宠物、category/type 不一致、非法 ISO、敏感字段和矛盾布尔确认。非法候选按原始 index 丢弃，不补发 Provider 请求；text-only 回复不猜测 Memory。
- MemoryPolicy：模型字段只作为候选，不构成授权；Policy 重新分析当前 `CompanionInput.message` 的本地显式“记住”证据，或接受由注入式 verifier 绑定当前确认消息、原 sourceMessageId、稳定候选 id、session/pet 的可信 proof。类别在本地映射为现有 `fact` / `episode` / `preference` / `relationship`，关系只写当前 `pet:<input.petId>`，不创建第二个 Store。
- 领域与持久化：使用现有 `MemoryRepository`、`yuxin-companion-memory-v1`、Tombstone 和 Local Repository journal/Outbox；新增同一 `writeState` 事务内的 atomic `supersede`，冲突替换失败时旧事实保持 active。精确/保守近似 duplicate 不新增 Outbox，过期 temporal 不参与写入、重复或冲突，删除后的 Tombstone 不可被重试复活。Outbox 只保留安全投影，不含敏感信息、完整聊天、原始 evidence 或错误文本。
- Harness/Finalizer：明确本地 Memory 路由先于 Provider snapshot，Provider begin/model/generate/external 均为 `0`；普通远程回复的 `0/1/4` 个候选共用一次模型响应和一次远程调用。真实 Memory 写入成功后才报告 succeeded；保存失败只使领域结果 failed/degraded，不撤销已成功 Action；模型伪造“已经记住”由本地结果覆盖；cancelled/stale 不提交 UI 文案，写入成功后的 late abort 保留领域事实但 `committed=false`，重试得到 duplicate。
- 验证证据：这是 P1 复验前的基线结果；最终数字与 P1-A 至 P1-D 的新增对抗证据见下方收口记录。
- 范围声明：本轮未触碰 `App.tsx` 的旧 Memory 分支，未做 App 接线或 Phase 6--8；未接真实 Provider/API Key，未做 Tauri 实机、视觉 QA、Rust/Cargo、commit、push、package 或 release。纯逻辑测试和 Web 构建不等同于真实 Provider、Tauri 或可发布验证。

### Phase 5 P1 最终收口（2026-08-12）

- 状态：P1-A 至 P1-D 已完成实现并复验；Phase 5 实施项 `8/8`、验收门 `3/3` 恢复为已通过。本记录仍只覆盖纯逻辑 Memory Candidate Policy，不代表 App 接线或可发布完成。
- P1-A 容量边界：`supersede()` 在任何 Repository 写入前检查 `MAX_COMPANION_MEMORY_ENTRIES=200`；`198 -> 199`、`199 -> 200` 成功，`200 -> supersede` 返回失败。失败时旧事实仍为 active，主记录、Outbox、journal、删除守卫和 sync counter 均不变；原始状态不超过 200 条，重新创建 Repository 后 200 条仍可读。
- P1-B 冲突槽位：Preference 使用规范化对象和正/负极性，覆盖 `喜欢/不喜欢`、`爱吃/不吃`、`爱喝/不喝`、`爱/不爱` 等现有 extractor 表达；Profile name 统一为 `profile:name`，支持“我叫”和“我的昵称是”。同对象反极性、同 profile 槽位不同名字才 supersede；同极性等价表达为 duplicate，咖啡/茶、香菜/芹菜、不同 person/project/shared experience 不误判。只有当前输入 explicit 或可信 confirmation proof 才能更正。
- P1-C 身份与版本：Candidate confirmation 使用不回显原文的 SHA-256 opaque fingerprint；Memory Entry 使用独立、由 candidate fingerprint 与 `supersedesId` 派生的 revision id。Repository 对相同 ID 的不同 scope/type/content fail closed，正常重试不新增写入，删除 Tombstone 不复活；已知 32 位碰撞对 `用户我叫i6adqy1cr8o0r` / `用户我叫1jpie37tfrvh` 得到不同 Candidate ID。`A -> B -> A` 生成不同 revision，最终只有最后一个 A active，且每次 `supersedesId` 正确指向前一版本。
- P1-D 混合结果：Finalizer 按 inserted/superseded/updated、duplicate、confirmation_required、failed、rejected、expired 分别计数；例如 `1 inserted + 1 confirmation_required` 为“已记住 1 条；另有 1 条尚未保存，需要你确认。”，`1 inserted + 1 failed` 为“已记住 1 条；另有 1 条保存失败。”。Action 成功文案保留，Memory failed 使顶层 degraded；模型 draft 不再覆盖逐项本地结果，也不回显 candidate content、evidence、sourceMessageId 或底层错误。
- 验证证据：Phase 5 定向组为 `8` 个文件、`160/160`；全量 `npm test` 为 `79` 个文件、`844/844`；`npx tsc --noEmit` 通过；`npm run build` 通过，仅保留既有 Vite 大 chunk warning；最终 `git diff --check` 通过。新增证据覆盖 200 条容量和重启、Outbox/journal/delete guard 稳定性、Preference/Profile conflict slot、已知碰撞对、A→B→A revision chain、Tombstone、ID collision fail-closed、mixed-result Finalizer 和 Action+Memory partial success。
- 范围声明：没有进入 Phase 6；没有修改 `App.tsx`、真实 Provider、Tauri/Rust、Live2D、宠物资源或发布产物；没有 commit、push、package 或 release。纯逻辑测试、类型检查和 Web 构建不等同于真实 Provider、Tauri 实机或可发布验证。

### Phase 6：Proactive Event 适配

目标：让 Harness 接管“允许后的表达”，不接管或复制 Scheduler。

- [x] 将现有 `TriggeredReminder` / due-soon candidate 适配为带稳定 id 的 `REMINDER_DUE` / `TASK_DUE_SOON` 事件。
- [x] 复用 `proactiveTriggerEngine.ts`、`proactiveExpressionGate.ts`、`proactiveDelivery.ts` 的勿扰、冷却、每日上限、聚合、幂等、忽略退避和宠物路由。
- [x] 明确 formal system notification、Task reminder stack 和宠物主动表达的职责，避免同一事件被当成两个新事实或重复气泡。
- [x] 默认使用宠物包本地模板，0 API；没有 Provider 也能提醒。
- [x] V1 不接 AI Enhanced Provider 路径；如已有相关设置，仅保留不外发的兼容读取与用户说明，未来非 Task / Reminder 事件必须另行修订 PRD、隐私合同和测试后才能启用。
- [x] Task/Reminder 触发的主动表达在 V1 始终使用本地模板；即使用户开启 AI Enhanced，也不发送任务标题、时间、状态或其他 Task/Reminder 投影，不为此发起远程调用。
- [x] 主动 AI 响应中的 Action / Memory Candidate 一律忽略；主动表达不能创建任务、改设置或绕过用户关闭状态。
- [x] Provider 失败时回到本地文案，不影响 Reminder 的 triggered / handled 事实，不重复触发。

验收门：

- [x] 覆盖正常到期、due soon、重复事件、DND、关闭主动、每日上限、聚合、App Restart、Sleep/Resume 和目标宠物不可用。
- [x] 所有 V1 主动事件外部调用数为 0，且每个有效事件只投递一次本地表达。

### Phase 6 实施记录（2026-08-12）

- 状态：这是 P1 收口前记录；既有实施项 `8/8` 与验收门 `2/2` 仅表示原始实现基线，暂不作为 Phase 6 最终通过证据。本记录只覆盖 Phase 6 纯逻辑主动事件适配，不代表 App 已接线、Tauri 已运行或已进入 Phase 7。
- 独立行为探针随后复现了 P1-A 至 P1-E：不同事件并发可绕过全局门禁、超过 256 条确认后幂等失效、eligible fallback 伪造 `lastDeliveryContext`、唯一 Harness 入口丢失聚合/宠物路由，以及 legacy `evaluate/deliveries` 被固定为空。P1 全部闭环前不得恢复本记录的最终状态或开始 Phase 7。
- 事件与边界：新增严格的 `CompanionEvent` 联合（`REMINDER_DUE`、`TASK_DUE_SOON`），通过 `companionProactiveEvent.ts` 生成基于 Reminder/Instance 或 Task/规范化 scheduledAt 的稳定 SHA-256 id；解析器拒绝未知字段、非法时间窗口和不完整事件。`CompanionHarness.handleEvent()` 只转发合法事件到注入的本地主动事件服务，不创建聊天 Turn，不调用 `CompanionModelPort`，不生成 Action/Memory Candidate。
- 唯一所有权：`Scheduler`/既有 Task Store 继续负责 ReminderInstance 的 triggered/missed/handled 事实；formal system notification 与 `TaskReminderStack` 继续负责可操作提醒；Phase 6 服务只负责一次非操作型宠物表达。没有新 Task/Reminder/Proactive 事实源，也没有修改 `App.tsx`、Provider 或 Tauri/Rust。
- 投递事务：策略评估只产生 `eligibleDeliveries`，不再把允许误报为已投递；`reserveDelivery()` 先写入持久化 reservation，随后才调用本地 sink；只有 sink 明确返回 `true` 才由 `confirmDelivery()` 增加计数、记录 delivered key 和 last delivery context。失败、异常、不可用宠物、重复、重启和确认写失败均 fail closed，并保留可恢复/不可重复的 reservation 语义。
- 本地降级：任务/提醒事件始终使用宠物包本地 `TaskFeedbackPackage`，不向 Provider 或远程 Context 发送 Task/Reminder 投影；模板读取失败时使用安全本地文案。AI Enhanced、远程 Model、Action、Memory 的 throwing spy 联合测试均保持 `0` 次调用。
- 验证证据（P1 收口前基线，非最终通过证据）：`companionProactiveEvent.test.ts` 覆盖稳定 id、正常/due-soon、重复、DND、关闭主动、每日上限、聚合、App Restart、Sleep/Resume、目标宠物不可用、writer/sink/confirmation failure 和外部调用隔离；Phase 6 相关定向组为 `8` 个文件、`152/152`；全量 `npm test` 为 `80` 个文件、`855/855`；`npx tsc --noEmit` 和 `npm run build` 均通过，仅保留既有 Vite 大 chunk warning。新增 P1 对抗测试与最终数字待收口后补录。
- 范围声明：未修改 `App.tsx`，未接真实 Provider/API Key，未做浏览器/Tauri 实机、视觉 QA、Rust/Cargo、commit、push、package 或 release。纯逻辑测试、类型检查和 Web 构建不等同于 App/Tauri 运行时或可发布验证；P1-A 至 P1-E 全部通过前不得开始 Phase 7。

### Phase 6 P1 实现侧验证（2026-08-24，P1-F 额度单位、跨日生命周期与损坏 schema 收口）

- 状态：Phase 6 的纯逻辑/Web 验收门恢复通过。P1-A 至 P1-F 的反例与回归均通过；Phase 6 实施项 `8/8`、验收门 `2/2` 仅表示本地纯逻辑与 Web build 门，不代表 App 接线、浏览器/Tauri 实机或可发布完成。
- P1-A 至 P1-E 保持既有收口：微批事务仍统一处理并发解析/聚合、dailyLimit、全局气泡冷却、durable receipt、终态证明清理、权威 confirmed context、Harness preferred-pet 路由和 legacy `evaluate().deliveries` 兼容；新 Harness 事件路径仍不消费 legacy deliveries，Provider、Model、Context、Action、Memory 均为 `0` 次调用。
- P1-F 额度单位：`ProactiveTaskDeliveryReceipt` 携带稳定 `reservationGroupId` 与 `reservationLocalDate`；同一聚合投递的 N 个 event receipt 共享 group，只计一个当前本地日期 reservation group。`evaluateEligibility()` 与 `reserveDelivery()` 共用 `countCurrentProactiveReservationGroups()`，confirmed receipt 不再重复计入 bubble quota。
- P1-F 旧 schema 迁移规则：schema v1 先校验每个 receipt 的状态和 canonical `updatedAt`，再读取 `deliveryReservationTaskIds`；task ID 集合先去空重、排序规范化。只有状态、`updatedAt` 和完整规范化 task 集合都相同的旧 receipt 才共享确定性 `legacy-reservation:v2:<SHA-256>` group；缺少证据或证据不一致时按 event key 保守隔离。receipt、event key、旧 reservationLocalDate 均保留，迁移写回后再次读取 group/date 不变。
- P1-F A/D/E 真实行为：`dailyLimit=2` 的两事件聚合只调用一次 sink；confirmation persistence 故意失败后两个 receipt 都保持 `reserved`、共享同一 group/date、`bubbleCounts.task_reminder=0`；超过 45 分钟后第三个独立事件再调用一次 sink 并成功确认，最终 bubble count 为 `1`，第三个 receipt 使用独立 group。确认成功的独立 group 只增加一个 bubble；`dailyLimit=2` 下第二个独立投递仍可成功，最终 sink 为 `2`、bubble count 为 `2`、reservation map 为空。
- P1-F B/C 真实行为：第一天 sink 成功但 confirmation 写失败时 sink 为 `1`，原 event receipt 在当天保持 `reserved`；同一 event 在跨日、服务重建/重启前后均不再次调用 sink。第二天的新 event 成功投递，重启后的新 sink 为 `1`，旧 receipt 保留第一天 `reservationLocalDate`，新 receipt 为 confirmed 且属于第二天，bubble count 为 `1`。
- P1-F 旧迁移反例：`proactiveExpressionGate.test.ts` 的 `reconstructs one stable legacy group from equivalent normalized task sets` 与 `companionProactiveEvent.test.ts` 的 `P1-F legacy migration: shares quota for proven old aggregation and stays idempotent after rebuild`。两条旧 receipt 代表一个实际 group（receipt 数 `2`、当日 quota 计数 `1`）；独立第三事件获得第二个 group 并成功投递。旧 event 重放在重建前后 sink `0` 次，新 event sink `1` 次；没有重复 confirmed receipt 或重复 bubble，写回再读 group/date 保持稳定。
- P1-F F/H 回归：两个不同 event 并发且 `dailyLimit=1` 仍只有一个 sink 和一个 confirmed receipt/bubble；主动事件继续不创建聊天 Turn，Provider、Model、Context、Action、Memory spy 均为 `0`。
- P1-F G schema/时间：嵌套 task-state schema 从 `1` 保守迁移到 `2`，旧 reserved/blocked/confirmed receipt 不丢弃并可靠获得 legacy group/date；schema round-trip、非法 group/date 和时钟回拨均 fail closed。新增 `proactiveTriggerEngine.test.ts` 的 `does not rewrite a damaged reservation schema or reopen it after a local day changes`，先确认损坏 group/date 导致 `evaluationPersistenceConfirmed=false`、无 `setItem` 回写，跨日后仍无 eligible delivery；receipt 仍只能由既有 Task/Reminder 终态证明清理，不能按时间删除或重放开放。
- 定向证据（真实命令）：`npx vitest run src/pet-core/proactiveExpressionGate.test.ts src/pet-core/proactiveTriggerEngine.test.ts src/pet-core/companionProactiveEvent.test.ts`，真实文件清单为 `src/pet-core/proactiveExpressionGate.test.ts`、`src/pet-core/proactiveTriggerEngine.test.ts`、`src/pet-core/companionProactiveEvent.test.ts`，3 个文件、`73/73`；P1-F 行为聚焦（4 个命名 P1-F 反例 + 损坏 schema 反例）为 `5/5`。
- 全量证据（真实命令）：`npm test`，91 个文件、`1048/1048`。
- 类型/构建证据（真实命令）：`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `861` 个模块，保留既有 `>500 kB` chunk warning；`git diff --check` 退出码 `0`，仅有工作树既有 LF/CRLF 转换提示。
- 范围声明：本轮只补充损坏 reservation schema 的 fail-closed 回写防护和对抗测试，并保留当前 P1-F reservation gate/engine、Phase 6 纯逻辑测试及本 TODO 范围；未修改 `App.tsx`，未开始 Phase 7--8，未接真实 Provider/API Key，未做浏览器/Tauri 实机、视觉 QA、Rust/Cargo、commit、push、package 或 release。纯逻辑测试、类型检查和 Web build 不等同于 App/Tauri 运行时或可发布验证；本轮完成后停止，不启动 Phase 7。

### Phase 7：App 接线与旧分支收敛

目标：Harness 成为唯一聊天编排入口，同时保留现有桌宠体验。

- [x] 在纯逻辑阶段验收后，把 `App.tsx` 的聊天发送大分支收敛为构造 `CompanionInput`、调用 Harness、渲染 `CompanionResponse`。
- [x] React 继续负责气泡、输入、pending、停止、重试、Session UI 和 Provider 披露；领域判断、Provider 调用、Action/Memory 执行迁出组件。
- [x] 保留 `companionChatRuntime.ts` 的现有状态机与 90 秒退出规则，不重写聊天交互。
- [x] 保留当前运行时会话列表行为；本阶段不把完整原始聊天写入长期 Repository。
- [x] 切宠物时切换 Soul 和 `pet:<id>` Memory，取消旧 Turn；Task 仍为用户级唯一事实，`createdByPetId` 只作 provenance。
- [x] 远程失败允许一次已披露的本地降级；不能在本轮继续偷偷请求远程 Provider。
- [x] 接线完成后删除/收敛 App 内重复编排分支，不能长期同时保留两条会产生副作用的执行路径。
- [x] Provider 设置、连接测试、系统安全存储和现有兼容迁移不因 Harness 改写。

验收门：

- [x] 本地聊天、远程 text-only、远程 structured、明确 Task/Reminder、确认、Memory、forget、主动偏好、停止、重试、换宠物全部在 Harness/领域定向测试与 Web 本地运行路径中收敛到唯一入口；Tauri 聊天发送/停止仍未验证。
- [x] 退出、停止、换宠、超时和新请求覆盖旧请求的纯逻辑迟到保护通过；Web 已验证停止、重试和退出无幽灵回复，Tauri 端到端交互仍未验证。
- [x] 用户切 Provider 后 Soul、Preference、Memory、Task、主动设置和当前宠物身份的快照/动态 getter 与隔离测试通过；未使用真实远程 Provider，Tauri 设置切换 UI 未验证。

### Phase 7 实施与验收记录（2026-08-13）

- 状态：Phase 7 代码实现、纯逻辑硬门和 Web 运行时门通过；Tauri 聊天端到端运行验证未通过，保持为独立未验证层级。下方“未做事项”是 Phase 7 记录生成时的快照；当前 Phase 8 已完成纯逻辑与自动化门。
- App/Harness 组合根：新增 `src/pet-core/companionAppHarness.ts`。`App.tsx` 通过稳定 `useRef` 实例组合 Harness，Provider profile/credential/fallback、当前宠物、宠物 Soul、companion-chat package、Preference、history、Task Repository 和 Trigger Engine 均从动态 ref/getter 读取，不因 React render、切宠或 Provider 设置重建 Harness。
- 唯一聊天入口：`sendCompanionChatMessage()` 只构造 `CompanionInput` 并调用 `companionAppHarness.harness.respond()`；常规发送路径不再调用旧 Pipeline、Context、Task/Memory/Preference/Proactive 写入或 `provider.send()`。全局唯一直接 `provider.send()` 保留在用户主动连接测试 `testCompanionProvider()`，使用 text-only，不进入 Harness Action/Memory。
- `CompanionInput`：`requestId` 为每次发送尝试的唯一 opaque 序列，`sessionId` 在一次打开的陪伴会话内稳定、退出后清空并下次重建，`sourceMessageId` 对应 pending user message，`userId` 使用 `local-user`，`petId` 在发送开始时快照，`currentTime` 为 ISO 字符串，`timezone` 使用运行时 IANA timezone、失败回退 `UTC`，`utcOffsetMinutes` 为 `-Date#getTimezoneOffset()`，`source` 为 `chat`，`contextEpoch` 沿用当前 runtime，`signal` 绑定当前 AbortController。
- 本地生成快照：`CompanionModelPort` 增加 Harness-owned `localGenerate` 钩子；本地回复根据 `HarnessModelRequest.input.petId` 读取对应 companion-chat package 和同一 Turn Context，不会因 Turn 期间活动宠物改变而串用新宠物。新增 Phase 7 回归测试覆盖该边界。
- 领域迁移：Task/Reminder、确认/取消/过期/换宠、Preference、forget、Memory candidate、主动提醒偏好、Provider snapshot/fallback 和 ResponseFinalizer 均在 Harness/本地域 service 处理；真实 Task Repository 写入成功后才报告成功，失败不更新 React 事实状态。
- 取消与幽灵回复：停止、退出、90 秒自动退出、切宠、Provider 保存/清除、新请求 supersede、surface 互斥和卸载均调用 `Harness.cancel()`/AbortController；ResponseSink 使用 `commitIfCurrent()` 检查 active pet、session、pending source message 和 Turn identity，迟到结果不追加 UI 或领域副作用。`companionChatRuntime` 的 90 秒、stop 草稿恢复和 retry 规则保持不变。
- Provider/fallback：远程普通 Turn 每轮一个 frozen Provider snapshot、最多一次 remote adapter 调用；允许 fallback 时最多一次本地 fallback，fallback disclosure 来自 Harness；下一 Turn 才读取新设置。credential sentinel 不进入 Context、Response 或错误。
- 自动化证据：Phase 7 定向命令 7 个文件、`105/105`；Phase 6 防回退 3 个文件、`72/72`；Provider/Context/Privacy 定向 7 个文件、`104/104`；全量 `npm test` 为 81 个文件、`893/893`；`npm exec tsc -- --noEmit` 通过；`npm run build` 通过，Vite 转换 838 个模块，仅保留既有大 chunk warning；`git diff --check` 通过。
- Web 运行证据：当前代码在本地 Web App 实际打开陪伴房，使用本地 Provider 完成发送与单条回复；实际验证停止后输入恢复且无迟到回复/重复发送、重试、退出、切宠、Task/Reminder、Memory/forget、Preference、主动提醒偏好，以及平台聊天入口与桌宠气泡入口的互斥行为。
- Tauri 运行边界：工作区 debug 二进制可启动，并捕获平台 `860×590` 与桌宠 `105×97` 窗口；但当前机器在窗口互斥切换时出现前台进程识别失败、窗口最小化/进程退出和辅助功能 XML 错误，未可靠完成 Tauri 内聊天发送、停止、重试或双表面无重复回复。因此 Tauri 聊天端到端验证为“未验证”，不能以 Web、测试或 build 替代。
- 未做事项（Phase 7 记录快照）：未使用真实 Provider/API Key；未运行 Cargo/Rust；未打包、发布、commit 或 push；未修改 `src-tauri`、宠物资源、Live2D、release exe、package.json 或 lockfile。

### Phase 8：可观测性、评测与发布门禁

- [x] 只记录脱敏后的 request id、provider profile id、protocol、latency、call count、action type/result、memory candidate count、event type/decision 和 error kind。
- [x] 不记录完整 Prompt、用户消息、Memory content、Task note/evidence、API Key、原始 Provider body 或完整模型回复。
- [x] 建立固定评测集，至少覆盖普通陪伴、明确/模糊任务、提醒创建/改期、完成任务、记住/忘记、冲突 Memory、敏感内容、Provider 故障、取消和主动提醒。
- [x] 每个评测同时检查三层：用户最终文案、领域事实、外部调用/隐私副作用。
- [x] 将 Task/Reminder 远程零外发作为独立隐私矩阵：相关、近期到期、无关、完成/取消、软删除/物理删除和主动提醒均不得把本地事实放进请求体。
- [x] 为 Local、Gemini-native、OpenAI-compatible 跑相同的领域中立 Provider Adapter 合同测试，并单独运行 `CompanionModelPort` / Model Codec 合同测试；真实远程冒烟只在用户已经主动配置凭据后执行，不进入 CI，不记录正文。
- [x] 运行 Harness 相关测试、现有 Companion/Memory/Task/Proactive/Provider 回归、全量 `npm test`、`npm run build`、`cargo test`、`cargo check` 和 `git diff --check`。
- [x] Tauri 实机验证 Settings 本地完整路径；main/platform、Owner blocked/retry、隐藏/重开与 listener 生命周期已通过。
- [x] Settings 在当前真实 Windows 200%（GetScaleFactorForMonitor=200、main/platform GetDpiForWindow=192）下通过正常与 2x 显示/交互验收。
- [x] Tauri 聊天 UI 完整路径；保留 `tauri-chat-real-20260826-0034` 原始证据不改，并以当前源码完成独立审计 run `tauri-chat-root-fix-20260828-045500` 的真实 Tauri A-H、隔离启动防护、事实型 validator 与清理复核；新 run 证据目录为 `docs/companion-harness-evidence/phase-8-tauri-chat/tauri-chat-root-fix-20260828-045500/`。
- 审计说明（2026-08-25）：`final-rerun-20260825-0801` 标记为 `AUDIT_REJECTED`，不能作为通过证据；固定 Keyring service 使隔离应用仍访问正式凭据命名空间，A 将 Local Storage/LevelDB 等变化笼统归为缓存而不能证明正式数据只读，C 的 Stop 点击发生在超时/本地 fallback 已结束后而未证明真正取消，G 缺少 listener attach/detach 数量闭环，H 缺少同一运行时间线内的准确写入次数闭环。
- 最终真实验收记录（2026-08-26）：runId `tauri-chat-real-20260826-0034`；自动化全量为 92 个测试文件、1056 个测试，Cargo 测试 17 个；A-H 全部 PASS。A 正式业务目录差异为 0、formal Credential Manager set/delete 为 0；隔离 Keyring service 与正式 service 不同；B-H 仅使用隔离数据、隔离凭据和 127.0.0.1 loopback stub。
- 本轮审计说明（2026-08-27—2026-08-28）：0034 原始证据保留不改；已补齐 fail-closed 启动防护、事实型 validator 与隔离运行目录清理复核。新 run `tauri-chat-root-fix-20260828-045500` 的 A-H、正式数据零差异、凭据命名空间隔离、隐私扫描和独立清理复核均已通过；最终 validator 负责从原始证据重算结论。
- 验收边界：真实外部 Provider、正式 API Key 内容、打包、安装包、release、commit 和 push 均未纳入本轮通过范围。
- [x] 更新 README、正式数据契约和旧路线状态，明确支持能力、降级、隐私、未实现项和 Harness 已接管的入口。

### Phase 8 实施与验收记录（历史快照，2026-08-13）

- P2 先行修复（历史快照）：新增 `companionUserProfileSync.ts`，曾尝试让全局昵称 Preference 与个人资料的显示值、保存和失败回滚保持一致；Phase 8-R 已将昵称持久化权收敛到 `global.nickname` Preference，并补齐重启、冲突、失败和恢复矩阵。昵称仍是 Preference，不会被误写成 Memory。
- 可观测性：新增 `companionObservability.ts`。运行时只接受协议化 allowlist 字段，request/profile id 使用不透明 hash，记录上限为 256 条；未知值收敛为 `unknown`，不接收原始 Prompt、消息、Task、Reminder、Memory、Provider body、回复正文或凭据。`companionObservability.test.ts` 用 hostile sentinel 验证真实 Recorder 与 Harness 生命周期均不泄漏。
- 固定评测：`companionPhase8Acceptance.test.ts` 固定覆盖普通聊天、明确/模糊 Task、Reminder 创建/改期/完成、确认/取消、重试/双击幂等、Memory/forget/冲突修正、敏感内容、Provider 错误、取消/supersede、主动提醒偏好和本地降级；每个 fixture 同时检查最终文案、领域事实、调用次数、隐私和重复/取消副作用。中文 Task/Reminder 语料 `20/20`，成功率 `100%`（满足 `>=95%`）。
- Provider 隐私矩阵：Local、Gemini-native 与 OpenAI-compatible 共用领域中立 Adapter/Model Port 合同；远程零外发覆盖相关、近期到期、无关、完成/取消、软删除/物理删除和主动提醒事实，并对请求体做 sentinel 检查。没有用户主动配置的真实 API 凭据，因此未执行真实远程冒烟。
- 故障与假成功：401/403/429/5xx、malformed、network/timeout 均保持单次远程调用、无秘密回显，并按配置最多一次本地降级；远程结构化候选不能覆盖本地领域事实或直接写 Task。停止和 supersede 后迟到响应不产生 UI、Task、Reminder 或 Memory 副作用。
- 自动化证据（历史快照，已由下方 Phase 8-R 记录替代）：Phase 8/相关闭环 `31` 个文件、`445/445`；全量 `npm test` `84` 个文件、`911/911`；TypeScript 检查通过；`npm run build` 通过（Vite 转换 `840` 个模块，仅保留既有大 chunk warning）；`cargo test` `12/12`、`cargo check` 通过；最终 `git diff --check` 通过。
- Tauri 当前尝试：实际启动工作区 `src-tauri/target/debug/yuxin-desktop-pet.exe`，先观察到未启动开发服务器导致的 `ERR_CONNECTION_REFUSED`，随后启动 `http://localhost:1420` 并确认当前 debug 桌宠窗口成功加载（截图约 `105×97`）。平台窗口没有出现在当前可操作窗口集合，无法可靠完成聊天、停止、重试、退出、切宠、Task/Reminder、确认、偏好、forget、双表面及 `860×590`/`1720×1180` 的完整证据；Tauri 门保持未勾选，不能用 Web、测试或历史 exe 替代。
- 发布边界：本轮未使用真实 Provider/API Key，未打包、commit、push 或发布；未修改宠物包、Live2D、release exe、`package.json` 或 lockfile；没有用户视觉/美学验收。纯逻辑、Web 构建与 Cargo 证据不等于 Tauri 或发布通过。

### Phase 8-R2 持久化一致性与 Observability 收口（2026-08-14）

- 状态：实现侧验证通过，等待独立验收。该状态只覆盖本轮代码、纯逻辑测试、Web build 与 Cargo 检查；不表示 Tauri、真实 Provider、正常/2x DPI、打包、发布或用户视觉验收完成。Tauri 实机项继续保持未勾选。
- 修复前稳定失败的三个反例：双键保存返回失败但重启后新 Profile 残留被迁移、已删除 Profile 昵称被空 Preference 复活、`cancel_task` / `postpone_task` / `reschedule_task` 被 Recorder 记录为 `unknown`。修复前分别在 `companionUserProfileSync.test.ts`、`companionObservability.test.ts` 中失败；修复后反例均通过。
- 持久化协议：新增版本化 `yuxin-companion-user-profile-recovery-v1` 恢复记录。每次 Profile/Preference 联合写入先写入并读回 `prepared` 记录，再对两个业务 key 与 Preference-authority marker 写入并读回，最后验证 `committed` 记录；任一步失败都返回失败、不触发 `onCommitted`，并恢复旧快照。恢复失败保留记录并阻塞后续写入；启动先恢复记录，已提交但清理失败时保留新状态并按记录幂等修复。
- Nickname 与迁移：Profile 持久化时清空 `nickname`，有效昵称只由 `global.nickname` Preference 派生。Preference key 已存在但缺少 nickname 时明确表示无昵称；只有 Profile-only、无 marker、无未完成恢复记录时才执行一次 legacy migration。成功写入并读回 `yuxin-companion-user-profile-migration-v1` marker；迁移写入或 marker 验证失败不激活昵称。App 与测试共用 `initializeCompanionUserProfileState()`，不再在 `App.tsx` 组合迁移与解析。
- 事务故障矩阵：`companionUserProfileSync.test.ts` 为 `24/24`，覆盖 prepared 写入失败、Profile/Preference 首写失败、跨 key 中途失败与 Profile 恢复失败、committed 写入失败、marker 写入失败、cleanup 失败、恢复期间再次写入、聊天改昵称后资料保存、forget、冲突、legacy migration、迁移失败和多次重启。
- Observability：Recorder allowlist 覆盖七种正式 `CompanionActionType`，但后三种本地兼容 Action 仍不进入 Model Codec/Provider Schema；真实 Harness 本地路由保持 Provider/model `0` 次调用，观测只保留 type/status，不保存 payload、title、reference、Task/Reminder id 或时间正文。`companionObservability.test.ts` 与 Model Codec 防回退测试通过。
- 定向证据：Phase 8 固定组 `4` 个文件、`61/61`；pet-core/task-core/storage 核心回归 `69` 个文件、`887/887`；补丁三文件组 `51/51`。
- 默认全量证据：`npm test` 连续三次均为 `84` 个文件、`943/943`；Vitest 用时分别为 `8.38s`、`8.42s`、`8.51s`。`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `840` 个模块，仅保留既有大 chunk warning；`cargo test` `12/12`、`cargo check` 通过；随后 `git diff --check` 通过。
- 未验证边界：没有真实 API Key 或远程 Provider 冒烟，没有启动 Tauri 最终验收，没有检查正常/2x DPI 交互，没有打包、发布、commit 或 push。本轮没有修改无关 Live2D、宠物资源、动画、QA 素材、release exe、`src-tauri` 业务代码、`package.json` 或 lockfile。

### Phase 8-R 阻断项修复与自动化硬门（2026-08-14）

- 状态：本节记录三个自动化阻断项的当前修复和硬门结果；它不表示 Tauri、真实 Provider、打包、发布或用户视觉验收已完成。Tauri 实机验证项继续保持未勾选。
- Observability 失败隔离：`CompanionHarness.respond` 和 `handleEvent` 均通过非递归、无重试的安全观测边界调用 Recorder；Recorder 抛错不会改变成功回复、ResponseSink 提交、主动事件投递、领域错误或取消/失败结果。观测输入按 allowlist 投影，动作和调用计数在交给观测器前复制，hostile Recorder 不能改写领域返回值，也不会看到原始 Prompt、消息、Task/Reminder、Memory、Provider body、回复正文或凭据。
- 昵称单一事实源：`global.nickname` Preference 是唯一持久化权威；Profile 的 `nickname` 只是兼容显示镜像，加载和重启时始终由 Preference 派生。Profile-only 旧数据只通过显式迁移写入 Preference；缺失 Preference 不会被旧 Profile 反向复活。持久化写入使用写后读验证和失败恢复，覆盖聊天后设置页立即可见、邮箱/其他资料变更、清空、首次写入失败、Preference 失败、恢复失败、重启、旧数据迁移和 Preference/Profile 冲突。
- 默认测试超时：`companionProactiveEvent.test.ts` 的 257 条确认事件压力用例保留全部断言，只增加该单测的 `10_000ms` 局部超时；生产代码未改全局超时、并发参数或重试策略。该压力是有界本地收据快照的刻意规模测试，隔离运行通过。
- Phase 8 定向证据：`companionPhase8Acceptance.test.ts`、`companionObservability.test.ts`、`companionUserProfileSync.test.ts` 通过；观察与昵称新增/修复测试合计 `18/18`，固定中文评测仍为 `20/20`。
- Companion 回归证据：Harness、Action、Memory、Preference、Forget、Provider、Context/Privacy 和 Proactive 共 `11` 个文件、`206/206` 通过。
- 默认全量证据：原始 `npm test` 连续三次均通过，每次均为 `84` 个文件、`921/921`；Vitest 用时分别为 `12.38s`、`9.91s`、`8.43s`，墙钟分别为 `14.533s`、`12.112s`、`10.647s`。
- 其他硬门：`npx tsc --noEmit`、`npm run build`、`cargo test` `12/12`、`cargo check` 和 `git diff --check` 均通过。build 仍只有既有大 chunk warning；未使用真实 Provider/API Key，未打包、发布、commit 或 push。

### Phase 8-R2 读取失败阻断项修复（2026-08-14，最新快照）

- 状态：Phase 8-R2 读取失败阻断项实现侧验证通过，等待独立验收。该状态只表示本轮 Profile/Preference 持久化纯逻辑、自动化测试、TypeScript、Web build 和 Cargo 检查通过；不表示 Tauri、真实 Provider、正常/2x DPI、打包、发布或用户验收完成。Phase 8 的 Tauri 实机复选框继续保持未勾选。
- 修复前红灯证据：在未修改生产代码时新增的两个对称反例稳定失败，定向命令为 `npm test -- --run src/pet-core/companionUserProfileSync.test.ts -t "snapshot read failure"`，结果 `2 failed / 24 skipped`。Profile 快照读取异常后，旧 `gender/email/phone` 被折叠成空 Profile；Preferences 快照读取异常后，旧昵称被折叠为空 Preferences，随后回滚会把伪造空快照写回业务键并破坏重启事实。
- 读取协议：`Profile`、`Preferences`、migration marker 和 recovery record 现在都通过单次 raw `getItem` 得到 `present-valid`、`missing`、`read-error` 或 `invalid`；同一次读取同时决定 presence、raw value 和 typed value。事务写入 prepared recovery record 前必须取得完整可信快照；任何读取异常/无效内容/无法确认 presence 都 fail closed，返回失败、保持 persistence 内存态、不调用 `onCommitted`、不执行业务键或 marker/migration 写入，也不启动 legacy migration。
- 零业务写入与写后读：Profile/Preferences/marker/recovery 的写后读验证只接受明确的目标值；读回失败、缺失、不一致或异常都不是成功。事务开始前的快照失败不创建 recovery record、不调用 `removeItem` 清除旧业务键。恢复写入的任一读回失败会保留 prepared record 并阻止后续新事务；只有完整旧快照已恢复并且 recovery 删除后的 raw 读取明确为 `missing` 才清理 prepared record。已验证的 committed record 仍优先采用新状态，cleanup 失败不回滚新状态并继续保留可重放证据。
- Nickname/迁移边界保持不变：`global.nickname` 仍是唯一持久化昵称权威，Profile 持久化镜像的 `nickname` 仍为空；Preference key 存在但没有 `global.nickname` 时不复活旧 Profile 昵称。任何 Profile/Preferences/marker/recovery 读取错误或 malformed 内容都阻止迁移，不猜测为 missing/empty。
- 新增测试：`companionUserProfileSync.test.ts` 从 `24` 个增加到 `32` 个，新增 `8` 个测试块，覆盖两个对称快照反例、App raw storage Profile/Preferences 读失败、marker/recovery presence 读失败、legacy migration 读门禁、malformed Profile/Preferences、prepared recovery readback 失败和 rollback readback 失败；每个故障路径检查返回/回调、raw 业务事实、marker/recovery、内存态和重启态。
- 定向证据：`npm test -- --run src/pet-core/companionUserProfileSync.test.ts` 为 `1` 文件、`32/32`；Phase 8 固定组（`companionPhase8Acceptance.test.ts`、`companionObservability.test.ts`、`companionUserProfileSync.test.ts`、`companionModelCodec.test.ts`）为 `4` 文件、`69/69`；Companion/pet-core/task-core/storage 回归为 `69` 文件、`895/895`。
- 三轮默认全量：连续三次 `npm test` 均为 `84` 文件、`951/951`，Vitest duration 分别为 `10.06s`、`8.68s`、`9.14s`；三轮均通过，没有通过缩小测试范围或修改配置隐藏失败。
- 其他硬门：`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `840` 个模块，仅保留既有 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12` 通过；`cargo check --manifest-path src-tauri/Cargo.toml` 通过；`git diff --check` 通过，仅报告工作区既有的 LF/CRLF 转换 warning。
- 本轮修改与边界：只修改 `src/pet-core/companionUserProfileSync.ts`、`src/pet-core/companionUserProfileSync.test.ts` 和本 TODO；未修改 `App.tsx`、`companionObservability.ts`、`companionModelCodec.ts`、Provider/Harness/Task/Memory/Proactive 业务代码、`src-tauri` 业务代码、`package.json`/lockfile、宠物包、Live2D、动画、QA 素材或 release 文件。工作区其他脏改动和未跟踪素材均未触碰。
- 未执行：Tauri 实机启动/聊天验收、真实 Provider/API Key 或远程冒烟、正常尺寸/2x DPI 检查、打包、发布、commit、push；完成本轮实现侧验证后在此停止，等待独立验收。

### Phase 8-R3 Profile / Preferences 单写者与 App/Harness 接线（2026-08-14，最新快照）

- 状态：实现侧验证通过，等待独立验收。本状态只覆盖本轮 Settings Repository/Owner、typed bridge、Profile/Preferences UI、Harness preference/forget wiring、纯逻辑测试、TypeScript、Web build 与 Cargo 检查；自动化实现侧通过，Tauri 双窗口运行未验证；真实 Provider、正常/2x DPI、打包、发布或用户视觉验收也未完成。
- 修复前红灯证据：在未修改生产实现时，P0-1 四个一次性 raw `getItem` 失败路径和 P0-2 双客户端 stale Profile/Preference、逆序、删除、同字段冲突、owner restart 共 `6` 个反例稳定失败；旧 App-style full-state persistence 会用空 startup projection 覆盖已有资料，stale client 也能报告成功。该红灯基线已记录后移除，修复后由 `companionUserSettingsRepository.test.ts` 固定为绿灯回归。
- Settings 协议：`CompanionUserSettingsOwner` 是唯一本机 settings/recovery 写者；App 通过 `CompanionUserSettingsRepository` 提交 `updateProfile`、`upsertPreference`、`deletePreference` delta command，命令携带 expected generation/revision 与 correlation id。Owner 对 stale version fail closed，对 correlation replay 返回原结果，并在成功后广播带版本的 committed snapshot。
- Blocked 与 UI：Profile、Preferences、migration marker、recovery record 任一读取异常或恢复不可用都会返回无业务快照的 blocked 状态；App/Harness 不构造空写入状态，设置页显示读取失败并禁用保存，Context 的空 Preferences 只读 projection 不会进入写路径。forget 先读取 Settings 与 Memory，再执行 Preference/Memory 删除，Settings 不可用时不会触碰 Memory。
- Tauri bridge：非平台主窗口持有 Owner；平台窗口通过 `companion-settings-command`、`companion-settings-result`、`companion-settings-snapshot` typed events 请求和接收版本化状态。没有修改 `src-tauri` 业务命令；桥接运行证据仍需 Tauri 双窗口实机验收。
- 自动化证据：`companionUserSettingsRepository.test.ts` `6/6`、`companionUserProfileSync.test.ts` `32/32`、Phase 7/8 接线组 `57/57`；此前记录的 Phase 8/Observability/Model Codec 固定组保持通过。当前全量单轮为 `85` 个文件、`959/959`。
- 未执行与停止边界：继续不使用真实 API Key/Provider，不启动发布流程，不打包、commit 或 push；不修改宠物资源、Live2D、动画、QA 素材或 release exe。Tauri 双窗口运行、真实远程请求、正常/2x DPI 和用户视觉验收保留为独立验收项。

#### Bridge 阻断项修复（2026-08-14）

- 状态：Bridge 阻断项实现侧验证通过，等待独立验收。本记录只覆盖 typed event Bridge 的 Owner re-initialize、跨 generation 握手权威和自动化协议证据；Tauri 双窗口运行、真实 Provider、正常/2x DPI、打包、发布和用户视觉验收仍未验证。
- 修复前红灯：先新增 `src/pet-core/companionUserSettingsBridge.test.ts`，未修改生产代码执行 `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts`，结果为 `1` 个文件、`5 passed / 7 failed`。其中 `blocked Owner recovers through a platform retry...` 在 retry 后仍为 `blocked`；`Owner restart with a clock rollback...` 在 `generation-2 / issuedAt=900` 后仍保留 `generation-1`，两个核心阻断项均稳定失败。
- Bridge 权威规则：Owner Bridge 收到 `kind: "initialize"` 时等待 `owner.initialize()` 后返回新状态；平台的 correlation-matched initialize response 是当前 main Owner 的握手权威，generation 变化不比较 issuedAt，revision 只在相同 generation 内防回退；未经握手的异代 snapshot 不直接覆盖状态并触发去重握手；新 generation 建立后旧 generation 的 snapshot/command result 不得覆盖平台状态；blocked 不携带业务快照，blocked 时命令 fail closed。
- Bridge 自动化证据：真实经过 `companion-settings-command`、`companion-settings-result`、`companion-settings-snapshot`、`startCompanionUserSettingsOwnerBridge()` 和 `createCompanionUserSettingsBridge()` 的测试为 `12/12`。覆盖初始握手、阻塞恢复、Owner 正常/回拨重启、异代迟到 snapshot、同代低/高 revision、stale command、结果超时后的 committed snapshot 与 correlation replay、emitTo 失败、重复 initialize/snapshot 和 listener 解除。
- 本轮验证：Settings 定向组 `5` 个文件、`52/52`；Phase 7/8、Harness、Preference、forget、Context/Privacy、Proactive 固定回归 `19` 个文件、`327/327`；最终全量 `npm test` 连续三轮均为 `86` 个文件、`971/971`，Vitest duration 分别为 `9.60s`、`10.32s`、`10.06s`。
- 其他硬门：`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `841` 个模块，仅保留既有 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12` 通过；`cargo check --manifest-path src-tauri/Cargo.toml` 通过；`git diff --check` 通过，仅报告工作区已有的 LF/CRLF 转换 warning。
- 本轮修改范围：`src/pet-core/companionUserSettingsBridge.ts`、新增 `src/pet-core/companionUserSettingsBridge.test.ts` 和本 TODO；未修改 `companionUserProfileSync.ts` 事务内核、Repository delta/commit 核心、`App.tsx`、`companionLocalDataService.ts`、Provider/Task/Memory/Proactive 业务、`src-tauri`、`package.json`/lockfile、宠物资源、Live2D、动画、QA 素材或 release 文件。未使用真实 API Key/Provider，未 package、commit、push 或 release。
- 未验证事项：没有可靠完成 Tauri 双窗口运行验收，因此不能宣称 main/platform 真实 handshake、隐藏/重显、主窗口重启或跨窗口 Profile/Preference 更新已通过；当前结论只能是“Bridge 阻断项实现侧验证通过，等待独立验收”。

#### Bridge 迟到 blocked snapshot 修复（2026-08-14）

- 状态：实现侧验证通过，等待独立验收。
- 修复前稳定红灯：新增反例后，在未修改生产代码时连续两次执行 `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts -t "a late blocked snapshot from the old Owner cannot clear the newly established Owner"`，每次均为 `1` 个文件、`1 failed / 12 skipped`（共 `13` 个测试）。失败断言为平台在释放 generation-1 的迟到 blocked snapshot 后仍应为 ready，但旧实现实际变为 `blocked`。
- 根因：blocked snapshot 不携带可验证的 generation/Owner 身份，却在 snapshot listener 中被无条件 `applyInitialization(next, "snapshot")`；因此 generation-2 已由 correlation-matched initialize response 建立后，旧 generation-1 的迟到 blocked 事件仍可清空平台当前可用视图。
- 最终权威规则：snapshot 只表示状态变化提示，不承担跨 Owner 接管权威；未经明确握手确认的 blocked snapshot 不直接改变平台 ready/blocked 状态，而是触发现有 `handshakeInFlight` 去重的 initialize。只有当前 Owner 的 correlation-matched initialize response 才能应用最终 ready 或 blocked；重复 blocked 信号共享同一握手，不比较 issuedAt，不创建第二套 Settings 事实源。同 generation 的 revision 防回退、旧 generation 的 ready snapshot/command result fail closed 规则保持不变。
- 新增 Bridge 测试覆盖：迟到旧 Owner blocked snapshot 不得回滚新 Owner（A）；当前 Owner 真实 blocked 必须由 blocked initialize response 接纳、平台 getSnapshot 为 null、命令 fail closed 且零业务写入（B）；重复 blocked snapshot 只共享一个 in-flight initialize（C）；清除存储故障后重新 initialize 必须重读原 Profile/Preferences 而不是空状态（D）。原有新 Owner 正常/时钟回拨接管、迟到旧 ready、同 generation 低/高 revision、timeout、correlation replay、stale command、Owner unavailable 和 listener cleanup 回归仍保留（E）。所有新增证据均经过真实 `companion-settings-command`、`companion-settings-result`、`companion-settings-snapshot`、`startCompanionUserSettingsOwnerBridge()` 与 `createCompanionUserSettingsBridge()`。
- 验证结果：Bridge 定向 `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts` 为 `1` 个文件、`16/16`；Settings 定向（Bridge、Repository、Profile/Preferences sync、Profile settings UI、Preferences、Phase 7/8 接线）为 `7` 个文件、`81/81`；Companion 固定回归（Phase 7/8、Harness 相关链路、Preference、Forget、Context/Privacy、Proactive、Model Codec、Observability）为 `22` 个文件、`346/346`。原始 `npm test` 连续三轮均为 `86` 个文件、`975/975`。`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `841` 个模块，仅有既有 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12`；`cargo check --manifest-path src-tauri/Cargo.toml` 通过；`git diff --check` 通过，仅报告工作区已有的 LF/CRLF 转换 warning。
- Tauri 实机：未验证。未用 Vitest、Web build 或历史 exe 代替 main/platform 双窗口的真实握手、跨窗口更新、Owner blocked/恢复、Owner 重启或隐藏/重显 listener 验收。
- 未执行：真实 Provider/API Key 或远程请求、正常/2x DPI 验证、打包、发布、commit、push；也未修改 Provider、Task、Memory、Proactive、事务内核、Repository 核心、App、`src-tauri` 业务代码、宠物资源、Live2D、动画、QA 素材或 release 文件。

### Phase 8-R4 Settings Protocol V2（2026-08-14，上一轮基线，已被下节当前快照 supersede）

- 状态：上一轮 Settings Protocol V2 实现侧记录，随后独立验收发现 P1 显式 retry/reconcile 竞态与 P2 client Repository stop 接线缺口；当前结论以本节后的“独立验收失败与显式恢复 / Bridge 生命周期修复”快照为准，不表示 Phase 8 已完成。
- 第一性根因：问题不是单个 Bridge 反例，而是早期 SettingsService 缺少完整的 Owner 状态协议，在 Phase 7 App/Harness 接线后逐步显化。最近一轮 blocked snapshot 修复又引入了 P1 反馈回归：`blocked snapshot -> automatic initialize -> Owner.initialize() -> refresh() 无条件 notify() -> 同一 blocked snapshot -> 下一轮 initialize`。旧 `handshakeInFlight` 只能合并重叠请求，无法处理 result-before-snapshot 的串行排列。
- 修复前稳定红灯：在未修改生产实现时，两次运行
  `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts -t "result-before-snapshot consumes one blocked Owner version without a feedback loop"`
  均为 `1` 个文件、`1 failed / 16 skipped`（该文件共 `17` 个测试）。失败断言为有界释放 `4` 轮后延迟 blocked snapshot 队列应为空，旧实现实际仍残留一个同状态 snapshot，证明自动 initialize 在 result 先到后自激。该测试真实经过 `createCompanionUserSettingsOwner()`、`startCompanionUserSettingsOwnerBridge()`、`createCompanionUserSettingsBridge()`、`companion-settings-command`、`companion-settings-result` 和 `companion-settings-snapshot`。
- Owner Protocol V2：每个 Owner 实例生成随机 `ownerEpoch`；同一 Owner 的真实语义转换递增 `stateSeq`；只有 Profile/Preferences 成功提交递增 `dataRevision`。ready/blocked 都携带版本；blocked 不带伪造空 snapshot，保留 `lastKnownDataRevision`。相同 ready 和相同 reason 的 blocked retry 真实重读但不重复通知；ready↔blocked、blocked reason 变化各发一次；成功业务提交同时递增 `stateSeq` 与 `dataRevision`。initialize 与 command 共用串行 Owner 执行队列。
- Client Transport V2：Bridge 内部区分 `not-ready/connecting/owner-unavailable/bridge-timeout/synced`。transport failure 只生成 UI-facing projection，不冒充 Owner blocked，也不改变已确认 Owner 版本。Bridge 维护当前确认版本、retired epoch 集合、pending signal 集合和单一 bounded automatic reconcile runner；同 epoch 相同/更低 `stateSeq`、低 `dataRevision`、旧 epoch、重复 result/snapshot 都被吸收或拒绝；新 epoch 只有带目标 epoch 的 correlation-matched initialize result 才能接管。`issuedAt` 只作诊断，绝不排序。
- 权威关系：snapshot 现在只是版本化状态变化 signal；同一版本的 result-before-snapshot 与 snapshot-before-result 都只消费一次。自动 reconcile 只为未消费 signal 运行且最多一个 in-flight；显式 `initialize()/retry` 仍始终允许真实读取。command timeout 不伪装成功；correlation replay 不重复业务写；blocked/transport unavailable 时业务写入保持为零；stop 后平台 listener、pending runner 和迟到事件不再改变状态。
- 修改文件范围：
  - `src/pet-core/companionUserSettingsRepository.ts`
  - `src/pet-core/companionUserSettingsRepository.test.ts`
  - `src/pet-core/companionUserSettingsBridge.ts`
  - `src/pet-core/companionUserSettingsBridge.test.ts`
  - `src/pet-core/companionLocalDataService.ts`
  - `src/App.tsx`
  - `docs/companion-harness-todo.md`
  - `D:\Users\Downloads\Companion Harness PRD.md`
  - `D:\Users\Downloads\Companion Harness Technical Design.md`
  未修改 `companionUserProfileSync.ts` 事务恢复内核、Provider、Task/Reminder、Memory、Proactive、`src-tauri` 业务命令、`package.json`/lockfile、宠物资源、Live2D、动画、QA 素材、release exe。
- 新增/改写测试矩阵：
  - A result-before-snapshot：同版本迟到 signal 被吸收，自动命令计数停止，队列归零。
  - B snapshot-before-result：signal 先到、matched result 后到，仍只 reconcile 一次。
  - C 重复与排列：重复 blocked signal、重复 result、重复 snapshot、有限有界释放均不产生第二轮。
  - D 当前 Owner blocked：ready→blocked 版本化传播、blocked 命令 fail closed、业务写入 `0`、相同 blocked retry 不重复通知。
  - E 显式恢复：故障解除后显式 initialize 真实重读并恢复原 Profile/Preferences，blocked→ready 只产生一个新版本。
  - F Owner 重启：新 epoch 接管、时钟回拨不影响接管，旧 ready/blocked/result 不能覆盖新 Owner。
  - G revision/stateSeq：同 epoch 低版本拒绝、高版本只经匹配 Owner result 接纳；stateSeq 与 dataRevision 职责分离，恢复 retry 不增加 dataRevision。
  - H timeout/replay：transport projection、command timeout、迟到 committed signal、correlation replay 和零重复写入。
  - I stop/listener：Owner Bridge 与平台 Bridge stop 后 listener/pending runner 清理，迟到 result/snapshot 不再改变客户端。
- 实际验证数字：Settings Bridge + Repository 定向为 `2` 个文件、`27/27`；Settings/Profile/Preferences/Phase 7/8 定向为 `8` 个文件、`87/87`；固定 Harness/Context/Privacy/Action/Memory/Provider/Model/Observability/Proactive/Phase 7/8 回归为 `42` 个文件、`561/561`；全量 `npm test` 连续三轮均为 `86` 个文件、`980/980`。
- 其他硬门：`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `841` 个模块，仅保留既有 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12`；`cargo check --manifest-path src-tauri/Cargo.toml` 通过；`git diff --check` 退出码 `0`，仅报告工作树既有 LF/CRLF 转换 warning。
- Tauri 边界：**Tauri 双窗口未验证。** 没有用 Vitest、Web build、历史 exe 或模拟事件代替 main/platform 初始握手、隐藏/重显、跨窗口 Profile/Preferences 更新、Owner blocked/恢复、Owner 重启、时钟回拨、旧事件迟到或 listener 重建的真实实机验收。真实 Provider/API Key、视觉/正常与 2x DPI、打包、发布、commit、push 也未执行。

### Phase 8-R4 独立验收失败与显式恢复 / Bridge 生命周期修复（2026-08-14，当前快照）

- 状态：原 Phase 8-R4 独立验收未通过，不能进入下一阶段；本轮修复完成后最多记录为“Phase 8-R4 显式恢复与 Bridge 生命周期修复实现侧验证通过，等待独立复验。”不得写 Phase 8 已完成，也不得勾选 Tauri 实机门。
- 已确认保留：原 blocked snapshot 自激反馈环已修复；同一 blocked 版本的自动化计数为 `automaticCommands=0`、`queuedSnapshots=0`；`ownerEpoch/stateSeq/dataRevision`、版本化 signal、retired epoch、bounded reconcile 与 PRD / Technical Design Protocol V2 主体继续有效。
- 本次独立验收失败的两个边界：用户显式 retry 复用了正在执行且带 `expectedOwnerEpoch=B` 的 automatic reconcile，导致 `commandsAfterAuto=1`、`delayedBeforeRetry=1`、`commandsAddedByExplicitCall=0`、`totalCommandsAfterRetry=1`、`retryStatus=blocked`、`finalStatus=blocked`；App 组合根 cleanup 只执行 UI `unsubscribe()` 与 Owner `stopBridge?.()`，没有调用 platform client Repository 的 `stop()`。
- 修复前红灯证据：新增 P1 核心竞态测试后，在未修改生产代码时连续两次运行 `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts -t "an explicit retry queued behind a mismatched automatic reconcile performs one unrestricted Owner reread"`，每次均为 `1` 个文件、`1 failed / 20 skipped`，失败点为 retry/final state 仍为 `blocked`；P2 lifecycle contract 在未接线时为 `1` 个文件、`1 failed / 1`，缺少 `companionUserSettingsRepository.stop?.()`。
- P1 最终规则：explicit handshake 与 automatic reconcile 使用独立 Promise 语义；automatic in-flight 时多个用户 retry 只登记一个共享 queued explicit handshake，runner 结束后追加一个不带 `expectedOwnerEpoch` 的真实读取；explicit matched result 消费相同或更低 pending version；只有仍有新 signal 才恢复 automatic runner；stop 会有限结束 queued retry 并吸收迟到事件。
- P2 最终规则：App 通过 Settings runtime lifecycle helper 管理 client Repository；每次 setup 先调用可选 `start()` 以支持 React StrictMode 同 context 重演，cleanup 解除 UI subscription、停止 main Owner Bridge，并调用 platform client Repository `stop()`。client Bridge stop 后可安全 restart，重建后只保留一组 result/snapshot listener。
- 本轮新增/强化测试矩阵：P1 核心竞态、三次点击合并、explicit blocked→ready 的 signal-before-result、result-before-signal、automatic 已恢复后仍追加 explicit reread、stop 竞态；P2 platform cleanup、main Owner cleanup、同 context restart listener；原 result/snapshot 排列、duplicate、Owner restart、clock rollback、retired epoch、timeout/replay、stale revision 与零业务写入回归均保留。
- 当前实现侧固定结果：Bridge + Repository 聚焦组为 `2` 个文件、`34/34`；Settings/App 定向组为 `9` 个文件、`96/96`；Harness/Context/Privacy/Action/Memory/Provider/Model/Observability/Proactive/Phase 7/8 固定组为 `42` 个文件、`566/566`；三轮完整 `npm test` 均为 `87` 个文件、`989/989`，退出码 `0`，无 warning。`npx tsc --noEmit` 退出码 `0`；`npm run build` 退出码 `0`，Vite 转换 `842` 个模块，仅有既有单个 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12`、退出码 `0`；`cargo check --manifest-path src-tauri/Cargo.toml` 退出码 `0`；`git diff --check` 退出码 `0`，仅有工作树既有 LF/CRLF 转换 warning。上述自动化结果不替代 Tauri 双窗口实机、真实 Provider、视觉、DPI、打包或发布验收。
- 停止边界：本轮不使用真实 API Key，不修改 Profile/Preferences 事务内核，不修改 Provider / Task / Reminder / Memory / Proactive 业务、不打包、不发布、不 commit、不 push；完成实现侧验证后停止，等待独立复验。

### Phase 8-R4 P2 in-flight lifecycle 修复（2026-08-14，当前实现侧结果）

- 状态：Phase 8-R4 P2 in-flight lifecycle 修复实现侧验证通过，等待独立复验。P1 显式 retry/reconcile 已通过上一轮独立验收；本轮不能宣称 Phase 8 完成。
- 上一次独立验收的真实失败证据：`commandsBeforeCleanup = 1`、`heldBeforeCleanup = 1`、`sharedPromise = true`、`commandsAfterRestart = 1`、`secondStatus = blocked`、`secondReason = owner-unavailable`；restart 后 result/snapshot listener 数量为 `1/1`，但 `finalStatus = blocked`、`finalReason = owner-unavailable`。因此 listener 重建本身成立，缺陷是旧生命周期异步任务跨越 stop/start 后污染并被新生命周期复用。
- 根因：旧实现以全局 `stopped` 布尔值表示生命周期；`stop()` 以只有 `correlationId` 的伪响应结束 waiter，`start()` 又快速把 `stopped` 设回 `false`。旧 `runExplicitHandshake()` 恢复后把取消结果解释为 `owner-unavailable`，而 `initialize()` 直接返回旧 `explicitHandshakeInFlight`；旧 Promise 的 `finally` 还可以无条件清空或驱动新代 Promise/runner，形成 ABA 竞态。automatic reconcile 与 queued explicit retry 共享同样的跨代风险。
- 最终实现策略：每个 request/waiter、explicit handshake、automatic runner、queued retry、listener installation 和 `finally` 都绑定 lifecycle generation；`stop()` 先递增并使旧 generation 失效，再以明确的 `cancelled` outcome 有限结束旧 waiter、清空旧槽位/pending signal/queued retry、解除 listener；`start()` 再递增创建新 generation，先完成新 result/snapshot listener installation。explicit/reconcile Promise 槽位在清理时同时校验“槽位仍是自己创建的 Promise”和 generation 仍一致；旧 generation 只能返回 stop 时安全快照，不能设置新代 transport failure、清空新代 Promise、消费新代 signal、启动新代 runner 或通知新代 UI。取消与 `owner-unavailable` 保持不同语义。
- 核心修复前红灯命令（生产代码未修改）：
  `npm test -- --run src/pet-core/companionUserSettingsBridge.test.ts -t "an immediate restart during an in-flight explicit handshake creates a fresh lifecycle-scoped request"`
  连续两次均为 `1` 个文件、`1 failed / 29 skipped`（该文件共 `30` 个测试），失败断言为两轮 `initialize()` 仍共享同一个 Promise。两次退出码均为 `1`。
- 新增真实对抗矩阵（均使用 `createCompanionUserSettingsBridge()`、Owner Bridge 与 mocked Tauri event bus）：
  - `an immediate restart during an in-flight explicit handshake creates a fresh lifecycle-scoped request`：同步 stop/start 后两轮 Promise 不共享；第二轮新增且只新增一条不带 `expectedOwnerEpoch` 的 initialize；旧 result 迟到后状态仍 ready；listener `1/1`，业务写入 `0`。
  - `a stopped lifecycle finalizer cannot clear or schedule work in the restarted lifecycle`：旧 Promise 进入 `finally` 后不能清空新 Promise，也不能造成第三条 command 或 automatic reconcile；新代完成。
  - `restart invalidates an in-flight automatic reconcile and its queued explicit retry`：旧 automatic 与 queued explicit 在 stop/start 后失效；新代发出一条 unrestricted read；旧 automatic result/snapshot 迟到不改变新 ready 状态；无循环、无重复读取、业务写入 `0`。
  - 原 P1 retry/reconcile、result-before-snapshot、snapshot-before-result、Owner restart/clock rollback、retired epoch、timeout/replay、blocked fail-closed、listener cleanup 与 App runtime lifecycle 回归全部保留。
- 修复后核心时序结果：新 Bridge 对抗测试 `3/3`；核心 explicit restart 的 race command 在基线之后新增 `2` 条，第二条 `expectedOwnerEpoch` 未定义；两轮 Promise `false` 共享；最终状态 `ready`；result/snapshot listener 严格为 `1/1`；业务写入 `0`。Bridge 文件总计 `30/30` 通过。
- 实际验证结果（全部退出码 `0`）：Bridge/Repository/Lifecycle 聚焦组 `3` 个文件、`39/39`；Settings/App 固定组 `9` 个文件、`99/99`；按小写 `companion`、大写 `Companion` 或 `proactive` 文件名前缀及 `.test.ts`/`.test.tsx` 后缀生成的固定 Harness 文件数为 `42`，通过 `569/569`；完整 `npm test` 连续三轮均为 `87` 个文件、`992/992`。
- 其他硬门：`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `842` 个模块，仅有既有单个 `>500 kB` chunk warning；`cargo test --manifest-path src-tauri/Cargo.toml` 为 `12/12`；`cargo check --manifest-path src-tauri/Cargo.toml` 通过；`git diff --check` 退出码 `0`，仅有工作树既有 LF/CRLF 转换 warning。
- 未验证边界：Tauri 双窗口仍未实机验证；真实 Provider/API Key、正常与 2x DPI、视觉、打包、发布、commit、push 均未执行。不要把本轮 Vitest、Web build 或 Cargo 结果替代上述边界，也不要进入下一阶段。

### Phase 8-R4 Tauri Settings Bridge 实机验收（2026-08-15）

- 唯一结论：`TAURI_SETTINGS_PARTIAL`。A、B、C、D、E、G 通过；F 的时钟回拨/旧事件迟到对抗未在真实 Tauri 注入，H 的隔离真实 2x DPI 未执行，因此不勾选任何 Tauri 完成复选框，不进入下一阶段。
- 当前源码与运行方式：HEAD `242e148041911201f3ce2d978a193cdf4eaeb89c`；工作区 `D:\CodeWorkspace\电脑桌宠`；使用 `npm run tauri dev` 生成并运行 `src-tauri/target/debug/yuxin-desktop-pet.exe`。正常 run PID `20892`，DEV fault run PID `20680`；窗口证据明确标记为 `main` 与 `platform`。
- A 初始握手：`PASS`。platform 达到 ready；启动初始 initialize 只有一条，后续 initialize 均由明确提交/快照后的协议流程触发；最终 listener 为 `result=1/snapshot=1`，未观察到自激反馈循环。
- B 隐藏/重显：`PASS`。platform 关闭只隐藏窗口，main 桌宠菜单重新打开 platform；重显后路由和 Settings 状态仍可用，listener 未重复。
- C Profile 跨窗口：`PASS`（历史运行行为）。先读取并记录基线；真实 Tauri platform 保存一次，Owner 回投成功反馈可见；重复不改字段的保存显示 no-op，未产生新的 snapshot/dataRevision；旧记录的起止比较只证明本轮起止相等，不证明 pre-QA 原始资料。
- D Preferences 跨窗口：`PASS`（历史运行行为）。Local Provider 下真实提交一次 `upsertPreference`，只产生一次 snapshot/revision；Profile 仍是镜像而非第二事实源；旧记录的起止比较只证明本轮起止相等，不证明 pre-QA 原始资料。
- E Owner blocked→恢复：`PASS`（历史运行行为）。仅在 DEV 环境使用 `VITE_XIAOJU_SETTINGS_FAULT=read`；Settings 页进入 blocked、没有业务快照和保存控件，fault 段业务 command 为 `0`；用户点击一次“重新读取本机设置”后执行 unrestricted reread 并恢复 ready，没有自动 initialize 循环。旧记录的起止比较不证明 pre-QA 原始资料，该入口不进入生产/release 路径。
- F Owner 重启/时钟回拨：`UNVERIFIED`。真实重建 Owner 产生了新的 owner epoch，但本轮没有安全的真实时钟回拨与旧 ready/blocked/result/snapshot 迟到注入；不将自动化对抗测试升级为实机通过。
- G lifecycle/listener：`PASS`。真实源码生命周期边界中 stop 后 `resultListeners=0`、`snapshotListeners=0`、`pendingWaiters=0`；下一次 client attach 严格为 `1/1`，旧 Owner Bridge 清理后保持单一 active subscription。
- H DPI：`UNVERIFIED`。未修改系统全局缩放；没有隔离的真实 2x DPI Tauri 执行条件，因此不伪造字段、反馈条、按钮和滚动区的 2x 通过。
- 自动化实际结果：聚焦反馈 `1` 文件 `9/9`；Settings/Repository/Bridge/Lifecycle/Profile 聚焦组 `7` 文件 `90/90`；完整 `npm test` `87` 文件、`1000/1000`；`npx tsc --noEmit` 通过；`npm run build` 通过，仅有既有单个 Vite `>500 kB` chunk warning；`git diff --check` 退出码 `0`，仅有工作区已有 LF/CRLF warning。Rust 未修改，未运行 cargo。
- 历史数据记录（本轮已降级）：旧记录只证明当时运行起点与结束值的比较相等，不能证明起点是 pre-QA 原始资料；本轮不再使用“原始资料已找到”或“精确恢复”结论，按 `preQaOriginalStatus: UNKNOWN` 处理。
- 有效证据：
  - `docs/companion-harness-evidence/phase-8-r4-tauri-settings/phase-8-r4-tauri-matrix.json`
  - `docs/companion-harness-evidence/phase-8-r4-tauri-settings/tauri-interactions.log`
  - `docs/companion-harness-evidence/phase-8-r4-tauri-settings/platform-home-r4-current.jpg`（JPEG，860x590，非全零）
  - `docs/companion-harness-evidence/phase-8-r4-tauri-settings/platform-settings-blocked-r4.jpg`（JPEG，860x590，非全零）
  - `docs/companion-harness-evidence/phase-8-r4-tauri-settings/main-context-menu.jpg`（历史 JPEG；WebView 原生菜单，不能证明矩阵 B，已排除）
- 尚未验证边界：F 的真实时钟回拨/旧事件迟到、H 的真实隔离 2x DPI；此外真实 Provider/API Key、发布/打包和 release acceptance 仍不在本门范围。所有诊断 trace 已裁剪 correlationId/ownerEpoch，未记录完整 Profile、昵称、邮箱、电话、Key 或 Prompt。

### Phase 8-R4 当前修复与独立复验（2026-08-15）

- B 门单项标记：✅ `PASS`（真实 Tauri 自定义任务菜单、平台隐藏后主桌宠保留、从菜单重开平台均有当前源码证据）。这只是 B 门单项通过，不改变整门 `TAURI_SETTINGS_PARTIAL` 结论。
- 当前基线：修复前唯一结论为 `TAURI_SETTINGS_REJECTED`。上一节旧快照中的 `TAURI_SETTINGS_PARTIAL` 已被本轮独立复核推翻，不作为当前结论；它不能覆盖本轮发现的 Settings UI 并发缺陷。
- 真实红灯（生产实现未修改）：
  `npm test -- --run src/pet-core/CompanionUserProfileSettings.test.tsx -t "keeps one physical save request locked through a pending draft edit"`
  连续两次退出码均为 `1`；每次为 `1` failed / `14` skipped，失败语义均为同一 pending `onSave` 被第二次调用（期望调用数 `1`，实际 `2`）。
- 最小修复：`CompanionUserProfileSettings` 将同步不可重入的 `requestInFlightRef`、按钮 `busy`、保存 attempt/result、draft revision/dirty 标记、反馈关联和 lifecycle generation 分开；编辑不释放物理请求锁，result/projection 不覆盖编辑后的草稿，第一笔 Promise settle 后才允许下一次保存。新增真实 jsdom 挂载交互测试，覆盖同周期重复保存、pending 编辑、result/projection 两种排列、settle 后提交最新草稿、blocked→恢复和成功/失败/no-op 反馈。
- 自动化实际结果：组件核心 `1` 文件 `15/15`；Settings 定向组 `7` 文件 `96/96`；全量 `npm test -- --run` 为 `87` 文件 `1006/1006`；`npx tsc --noEmit` 退出码 `0`；`npm run build` 退出码 `0`（843 modules，只有既有单个 Vite 大 chunk warning）；产物 fault-marker 检查通过；`git diff --check` 退出码 `0`，仅有既有 LF/CRLF warning。Rust 未修改，`cargo`：`NOT RUN because Rust was not modified`。
- 当前源码 Tauri 复验：本轮启动 `npm run tauri dev`，仅停止本轮启动的进程；进程 PID `35132`，窗口 `main=854884`、`platform=396130`。main 自定义任务菜单通过真实可访问树确认包含“今日任务 / 新建任务 / 陪我聊聊 / 快捷提醒 / 提醒设置 / 暂时隐藏桌宠”；先隐藏 platform 并确认 main 仍在，再从该自定义菜单重新打开 platform。有效证据为 `main-task-menu-r4.jpg` 与 `platform-reopened-r4.jpg`；`main-context-menu.jpg` 明确标记为 WebView 原生菜单并排除矩阵 B。
- 数据保护：没有可信的 pre-QA 备份，未清空、猜测、替换或输出 Profile/Preferences 字段原值；`preQaOriginalStatus: UNKNOWN`、`startOfRunStateRestored: true`（仅表示本轮起止比较相等）、`priorQaMarkersRemain: true`、`ownerAuthorizationToMutate: false`。任何真正恢复原始资料的动作均等待 owner 提供备份或授权。
- 最新验收矩阵：`TAURI_SETTINGS_PARTIAL`。代码、红绿证据、构建和 B 菜单证据已纠正；F 的真实时钟回拨/旧事件迟到与 H 的隔离真实 2x DPI 仍为 `UNVERIFIED`，不升级为 accepted，不宣称 Phase 8/Harness V1/发布门完成，也不进入下一阶段。

### Phase 8-R4-F 真实 Tauri Owner 接管复验（2026-08-15）

- 状态：F `PASS`。总状态仍为 `TAURI_SETTINGS_PARTIAL — only isolated true 2x DPI remains`；H 仍为 `UNVERIFIED`，不进入 H、Provider、打包、发布或 Git 发布。
- 当前源码真实运行：`npm run tauri dev -- --no-watch`；选定 runId `f-owner-takeover-r4`；Tauri PID `37212`；main/platform 原生 HWND `28705644/62194748`。日志同时保留了早期控制器未就绪的两次 `UNVERIFIED` 尝试，最终判定只采用 `r4` 的完整时序。
- Owner A→B：A epoch 后缀 `…90bd6a2d`，B epoch 后缀 `…s8gazpfj`；A `issuedAt=1786808790945`，B `issuedAt=1786808790944`，`issuedAtB < issuedAtA=true`。A 停止时 command listener/owner subscription 为 `0/0`；B correlation-matched unrestricted initialize 后 platform 为 `ready`，result/snapshot listener 为 `1/1`。
- 真实迟到矩阵：ready/blocked snapshot、ready/blocked initialize result、duplicate result、duplicate snapshot、result-before-snapshot、snapshot-before-result 均经 `companion-settings-snapshot`/`companion-settings-result` 真实 Tauri event bus 注入。每项注入前后 authority/status/stateSeq/dataRevision 与 B 投影均相等；无 blocked UI projection、无旧 Profile/Preferences projection、无业务 command/write；automatic reconcile 总数为 `1` 且有界。
- drain/cleanup：bounded drain 为 `pendingWaiters=0`、`queuedSignals=0`、`automaticRunner=0`、result/snapshot listener `1/1`、业务 command `0`；stop client 后 listener `0/0`，迟到 snapshot 不改变状态；stop Owner B 后 command listener/owner subscription `0/0`。
- 安全 seam：复用 Owner 工厂已有 `ownerEpoch`/`issuedAt` seam；新增的仅为 `import.meta.env.DEV` 双重保护的 session-scoped controller、内存事件捕获/重放和去敏诊断计数。没有修改系统时间、localStorage、Profile/Preferences、业务写入或生产 `window` 全局。最终生产 absence 检查确认 scenario 环境变量、marker、scenario id、控制事件和 DEV fault 文案均不在 `dist`。
- 本轮硬门实际结果：Bridge/Repository/Lifecycle `3` 个文件 `39/39`；Settings 定向组 `7` 个文件 `96/96`；全量 `88` 个文件 `1007/1007`；`npx tsc --noEmit` 通过；`npm run build` 通过，Vite 转换 `844` 个模块，仅有既有单个 `>500 kB` chunk warning；`git diff --check` 退出码 `0`，仅有工作区既有 LF/CRLF 提示；Rust 未修改，`cargo`：`NOT RUN because Rust was not modified`。
- 有效证据：`docs/companion-harness-evidence/phase-8-r4-tauri-settings/tauri-f-owner-takeover.log`。日志只记录 epoch 后缀、协议版本、状态和计数，不记录完整 ownerEpoch/correlationId、snapshot、nickname、email、phone、API Key、Prompt 或聊天历史。

### Phase 8-R4-H 当前 Tauri Settings 2x DPI 验收（2026-08-20）

- 当前结论：`TAURI_SETTINGS_PASS`；Phase 8-R4-H `PASS`，Tauri Settings A-H 全部通过。该记录追加在 F 记录之后，不改写前序失败、部分通过或 `UNVERIFIED` 历史快照。
- 真实运行：当前 HEAD `242e148041911201f3ce2d978a193cdf4eaeb89c`；命令 `npm run tauri dev -- --no-watch`；Tauri exe `D:\CodeWorkspace\电脑桌宠\src-tauri\target\debug\yuxin-desktop-pet.exe`；最终 run launcher PID `39632`、Tauri PID `41036`；main HWND `15927612`、platform HWND `854706`；两者均为当前源码本轮原生窗口，完成后仅停止本轮 PID。
- DPI 硬证据：启动前和启动后只读 `GetScaleFactorForMonitor=200`；主显示器 `\\.\DISPLAY1`、primary、`1536×960`、work area `1536×912`；main/platform 均位于 `DISPLAY1`，`GetDpiForWindow=192`，等价 `scaleFactor=2.0`。没有修改系统全局缩放；没有用近似值替代原生结果。
- H 矩阵：A main 桌宠完整可见且点击区对齐；B platform 框架/home/真实任务菜单完整；C Profile 控件、焦点、no-op 保存和反馈状态正常；D Local Provider Preferences 区域正常且不使用真实 Key/请求；E Settings `scrollHeight=808`、`clientHeight=492`，可到底并回顶；F 仅使用既有 `VITE_XIAOJU_SETTINGS_FAULT=read`，blocked/retry 完整且业务写入 `0`；G platform 隐藏后 main 保留并由真实任务菜单重开，路由/布局/listener 正常；H 原生 200%/192 DPI 证据与完整 Settings 2x 视觉/交互矩阵通过。
- 截图证据：新增 `tauri-h-2x-proof.json`、`tauri-h-2x.log`、`main-2x-r4.jpg`、`main-task-menu-2x-r4.png`、`platform-home-2x-r4.jpg`、`platform-settings-2x-top-r4.jpg`、`platform-settings-2x-bottom-r4.jpg`、`platform-settings-blocked-2x-r4.jpg`、`platform-reopened-2x-r4.jpg`。所有新截图已检查签名、非零尺寸/内容与哈希；设置页截图使用去敏证据区域，未交付真实资料值。
- 缺陷与修复：先完成完整 H 矩阵，未发现 2x DPI 生产 UI/CSS、窗口布局或业务协议缺陷，因此没有生产修复批次。为完成本轮 TypeScript 硬门，仅移除三个测试文件内共六个已失效 `@ts-expect-error` 注释：`src/marketing/marketingStaticFile.test.ts`、`src/pet-core/platform.test.ts`、`src/pet-core/companionPhase7Acceptance.test.ts`；未修改生产实现或 Provider/Task/Reminder/Memory/Proactive/Settings 持久化协议/Bridge 权威协议/Rust/包锁/宠物资源/Live2D/release 文件。
- 自动化与隔离：聚焦命令 4 文件 `54/54`；全量 `npm test -- --run` 为 88 文件 `1011/1011`；`npx tsc --noEmit`、`npm run build`、`git diff --check` 通过；build 为 863 modules，仅既有单个 `>500 kB` warning；Rust 未修改，`NOT RUN because Rust was not modified`；dist 未发现 H/F 环境变量、fault marker/文案、控制事件、测试 sentinel、敏感 sentinel 或验收专用生产入口。
- 数据保护与边界：Profile/Preferences 原值、API Key、Prompt、聊天正文、完整 correlationId 和完整 ownerEpoch 均未记录；`preQaOriginalStatus` 保持 `UNKNOWN`；没有业务变更。该门只收口当前源码真实 Tauri Settings A-H，不代表 Harness V1 发布、真实 Provider/API Key、打包/安装包、release acceptance、commit、push 或 Git 发布。
- 本节证据索引：`docs/companion-harness-evidence/phase-8-r4-tauri-settings/tauri-h-2x-proof.json`、`tauri-h-2x.log`、更新后的 `phase-8-r4-tauri-matrix.json`。

### Phase 8-R4-H 修复后追加复验（2026-08-20）

- 当前 H 结论：`TAURI_SETTINGS_PASS`。本节追加在历史 F/H 记录之后，不覆盖前序红灯、部分通过、`UNVERIFIED` 或旧 H 记录；A-G 真实 Windows 200% DPI Tauri Settings 检查全部通过。
- 正常 run：当前源码 h11 使用独立 Vite `1434` 与 Tauri `com.yuxin.desktop.codexh11`；原生 proof 为主显示器 `\\.\DISPLAY1`、monitor scale `200%`、main/platform `GetDpiForWindow=192`。关闭 platform 后只剩 main；再用真实桌宠任务菜单重开 platform，进入 Settings 并完成底部/顶部滚动。重开后 platform 原生窗口仍为 200%，没有重复可见窗口，active settings listener 为 `1/1`。
- A-G 矩阵：A main 桌宠完整可见；B platform 品牌、导航、宠物入口、信箱、窗口控制和首页滚动通过；C Profile 字段、焦点外观、no-op 保存反馈通过；D Local Provider 底部控件可达且未触发连接/保存/网络请求；E Settings 顶到底再回顶通过；F 独立 fault bundle 的 blocked/重新读取面和重试恢复通过，业务写入标记为 `0`；G 隐藏后主宠保留、真实任务菜单重开、Settings 路由与滚动能力通过。
- F fault run：Vite 启动时设置既有 `VITE_XIAOJU_SETTINGS_FAULT=read`，日志为 `tauri-h-2x-fault-current-20260820-hfault2.log`；真实页面显示“本机设置正在等待恢复”与“重新读取本机设置”，点击重试后恢复 ready。该 run 已停止；第一次仅在 Tauri 子进程设置变量的无效配置 run 不计入 F。
- 本轮修复批次：
  - `src/App.tsx` 在平台导航后增加同一窗口的延迟 reveal/focus retry，覆盖真实隐藏/重开时的窗口显示竞态，不创建新窗口或 listener。
  - 新增 `src/pet-core/dedicatedPlatformWindow.ts` 与对应单测，锁定 `unminimize -> show -> setFocus` 顺序。
  - `src/pet-core/companionUserSettingsBridge.ts` 将 Settings DEV trace event prefix 做编译期 DEV 隔离；最终 dist 扫描不再包含 `settings_trace:` 控制事件。
- 当前自动化：聚焦组 `4` 文件 `54/54`；`npx tsc --noEmit`、`npm run build`、`git diff --check` 和 dist 隔离扫描通过；dist 不含 H/F 环境变量、DEV marker/error、控制事件、测试 sentinel 或验收入口；Rust 未修改，`NOT RUN because Rust was not modified`。
- 全量测试例外：本轮最终 `npm test -- --run` 为 `89` 文件、`1012/1013`，唯一失败是工作树既有 `public/pets/xiaoju-cat/pet.json` 当前 `loopFrameCount=14/landingFrameCount=5` 与既有 `src/pet-core/petInteractionManifest.test.ts` 断言 `12/7` 不一致；本轮没有修改宠物资源或该测试，保留该未授权范围的 dirty 状态，不把它包装成通过。
- 当前证据：`phase-8-r4-tauri-matrix.json` 的 `currentHAfterF`；`tauri-h-2x-dpi-proof-20260820-h11.json`、`tauri-h-2x-dpi-proof-20260820-h11-reopen.json`；`main-2x-current-20260820-h11.jpg`；`platform-home-2x-current-20260820-h11.jpg`；`platform-settings-top-2x-current-20260820-h11.jpg`；`platform-settings-bottom-2x-current-20260820-h11.jpg`；`platform-settings-reopened-2x-current-20260820-h11.jpg`；`platform-settings-blocked-current-20260820-hfault2.jpg`。设置截图使用脱敏区域，未交付真实资料值。
- 数据与独立门：`preQaOriginalStatus` 继续为 `UNKNOWN`；没有 Profile/Preferences 业务变更、真实 Provider/API Key、打包、安装包、commit、push 或发布。全量 Vitest 的宠物 manifest/test mismatch 仍是工作区独立自动化待处理项；Provider、打包/安装、release acceptance 与 Git 发布仍未完成。

### Phase 8-R4-H 当前源码证据追加（2026-08-20，最终本地收口）

- 当前结论：`TAURI_SETTINGS_PASS`；本节追加在历史 F/H 记录之后，不改写任何历史失败、部分通过或 `UNVERIFIED` 快照。
- 正常 current-source run：h13 使用真实 Tauri main/platform 双窗口；`DISPLAY1` 为 primary，原生 `GetScaleFactorForMonitor=200`，main/platform `GetDpiForWindow=192`；Profile、no-op 保存、Local Provider、Settings 顶到底再回顶、platform 隐藏/任务菜单重开均通过。证据：`tauri-h-2x-dpi-proof-20260820-h13.json`、`tauri-h-2x-current-run-20260820-h13.log` 及 h13 截图组。
- F current-source run：hFault5 在 Vite 启动时使用既有 `VITE_XIAOJU_SETTINGS_FAULT=read`；真实 Settings blocked/重试面显示正常，显式重试后恢复 ready；日志统计 `blocked=4`、`ready=5`、业务写入标记 `0`，平台关闭完成，run 已停止。证据：`tauri-h-2x-fault-current-20260820-hfault5.log`。
- Native blocked capture：hFault6 记录当前源码 native main/platform HWND、`210×224`/`1720×1180`、DPI `192`、scale `200%`；其 platform PrintWindow 候选为黑帧，已明确排除，不作为验收截图。hFault5 的真实 CUA blocked/retry 观察与 ready 去敏截图仍作为 F 证据。证据：`tauri-h-2x-fault-current-20260820-hfault5.log`、`platform-settings-retry-ready-cua-current-20260820-hfault5.jpg`、`tauri-h-2x-final-proof-20260820-h13-hfault5.json`。
- 自动化硬门（本次证据完成后重跑）：聚焦组 `54/54`；全量 `89` 文件、`1013/1013`；`npx tsc --noEmit`、`npm run build`（`861` modules）、`git diff --check` 和 dist 隔离扫描均通过；Rust：`NOT RUN because Rust was not modified`。
- 数据保护：没有输出或修改 Profile/Preferences 原值，没有 API Key/Provider 请求；没有完整 correlationId、ownerEpoch、Prompt 或聊天正文；`preQaOriginalStatus` 继续为 `UNKNOWN`。Provider、打包/安装、release acceptance、commit、push 和 Git 发布仍是独立未授权门。
- 证据索引：`docs/companion-harness-evidence/phase-8-r4-tauri-settings/tauri-h-2x-final-proof-20260820-h13-hfault5.json`、`phase-8-r4-tauri-matrix.json` 的 `currentHFinal`。

### Phase 8-R4-H 当前源码 H18 追加验收（2026-08-21）

- 当前结论：`TAURI_SETTINGS_PASS`；本节追加在全部历史 H 记录之后，不改写历史失败、部分通过或 `UNVERIFIED` 快照。H18 先完成完整 A-G 矩阵，再执行自动化与产物硬门。
- 真实运行：当前 HEAD `242e148041911201f3ce2d978a193cdf4eaeb89c`；正常与故障均使用 `npm run tauri dev -- --no-watch`；正常运行未设置 `VITE_XIAOJU_SETTINGS_FAULT`，故障运行单独设置既有 `VITE_XIAOJU_SETTINGS_FAULT=read`；两次运行均在证据采集后停止，目标 Tauri 进程与 `1420/9222` 监听均清零。
- DPI 硬证据：启动前及矩阵完成后的原生探针均显示 primary `\\.\DISPLAY1`、`1536×960`、work area `1536×912`、`GetScaleFactorForMonitor=200`；main/platform 原生窗口均为 `GetDpiForWindow=192`，WebView `devicePixelRatio=2`，未修改系统缩放、未强制 WebView scale、未使用浏览器模拟或截图放大。
- H 矩阵：A main 桌宠命中区通过；B platform 框架/home 与六项真实任务菜单通过；C Profile 四字段、Tab 焦点顺序、no-op 保存及无变化反馈通过；D Local Provider 区域可达且未测试连接、保存或请求；E Settings 到底、回顶且无裁切；F 独立 read fault 显示 blocked/retry，显式重试恢复 ready，故障日志业务 command type 为 `0`；G platform 隐藏后 main 保留，由任务菜单重开 platform 并重新到达 Settings；H 原生 200%/192 DPI 下 A-G 全部通过。
- 缺陷与修复：完整矩阵未发现当前源码的 2x UI、窗口布局、路由、滚动或设置桥接缺陷，因此没有生产修复批次；H14-H17 的中断/恢复尝试保留为历史，不提升为 H18 证据。工作树中与本门无关的 dirty/untracked 内容保持不动。
- 当前证据：`tauri-h-2x-proof-20260821-h18.json`、`tauri-h-2x-current-run-20260821-h18.log`、`tauri-h-2x-fault-current-20260821-h18.log`、`main-2x-20260821-h18.png`、`main-task-menu-2x-20260821-h18.png`、`platform-home-2x-20260821-h18.png`、`platform-settings-2x-top-20260821-h18.png`、`platform-settings-2x-bottom-20260821-h18.png`、`platform-settings-blocked-2x-20260821-h18.png`；Profile 顶部截图已去敏，blocked 截图不含 Profile 值。
- 自动化与隔离：聚焦命令 4 文件 `54/54`；全量 `npm test -- --run` 为 `91` 文件、`1047/1047`；`npx tsc --noEmit`、`npm run build`、`git diff --check` 通过；构建转换 `861` 个模块，仅有既有单个 `>500 kB` chunk warning；dist 未发现 H/F 环境变量、DEV fault/owner takeover marker、控制事件、测试 sentinel 或验收专用入口；Rust 未修改，`cargo`：`NOT RUN because Rust was not modified`。
- 数据保护与边界：`preQaOriginalStatus` 保持 `UNKNOWN`；没有 Profile/Preferences 业务写入、API Key、真实 Provider 请求、完整 correlationId/ownerEpoch、Prompt 或聊天正文进入交付证据；没有 Provider、Harness V1、打包、发布、commit 或 push 声明。
- 本节证据索引：`docs/companion-harness-evidence/phase-8-r4-tauri-settings/tauri-h-2x-proof-20260821-h18.json` 与 `phase-8-r4-tauri-matrix.json` 的 `currentHFinalH18`。

## 6. V1 最终验收指标

| 指标 | 通过标准 | 证据 |
|---|---:|---|
| 普通远程聊天外部请求 | 每 Turn `<= 1` | Fake Provider 计数 + Adapter 合同测试 |
| 可本地完成的明确操作 | 外部请求 `= 0` | Task/Memory 集成测试 |
| V1 主动提醒外部请求 | 每事件 `= 0` | Proactive 测试 |
| 明确 Task / Reminder 操作成功率 | 支持语料集 `>= 95%` | `companionPhase8Acceptance.test.ts` 固定中文 fixture `20/20` |
| 虚假成功确认 | `0` | Provider 乱报 + 各类领域失败矩阵 |
| 重复 Reminder / Action 写入 | `0` | 重试、双击、重复候选、重启 fixture |
| 业务层直接依赖具体厂商 | `0` | import/协议边界检查 |
| Provider Adapter 依赖 Harness / Task / Memory / Soul 领域类型 | `0` | import/类型边界检查 |
| 本机 Task / Reminder 事实或投影进入远程请求 | `0` | Context fixture + 双协议请求体快照 |
| 敏感 Context / Key 泄漏 | `0` | 请求快照、日志快照与隐私 fixture |
| 取消后的新副作用 | `0` | Abort / stale request 集成测试 |

## 7. 硬停线条件

出现以下任一情况时，不得进入下一 Phase，也不得宣称 Harness 已完成：

- 同一用户输入可能同时由旧 App 分支和 Harness 执行副作用。
- 普通聊天为了 Action、Memory、Finalizer 或自检发生第二次模型调用。
- 新建了第二套 Task、Reminder、Memory 或 Proactive 事实源。
- 模型输出未经本地明确意图、Schema、权限和领域验证就触发写操作。
- Action 失败或持久化失败后仍出现成功文案。
- 停止、换宠或退出后，迟到响应仍可写 Task / Memory / UI。
- Context 或日志中出现 Key、完整敏感字段、完整 Prompt 或未裁剪原始历史。
- 以相关、近期到期、优先级或主动提醒为理由，把任何本机 Task/Reminder 事实或投影放入远程 Context。
- Provider Adapter 增加 Action/Memory 领域能力标记，或直接依赖 Harness、Task、Memory、Soul 类型。
- 任一 V1 主动事件绕过 Proactive Gate，或产生 Provider 调用。
- 只通过单元测试而没有 App/Tauri 真实运行证据，却把状态写成可发布。

## 8. 建议的第一开工单元

第一轮只完成 Phase 1，不同时接 App、不改 Provider 协议、不动 Task/Memory schema：

1. 增加 Harness types 与依赖接口；
2. 实现纯 `respond()` 单次生命周期；
3. 用 Fake `CompanionModelPort` 验证 0/1 次调用、取消、超时、迟到结果和本地降级；
4. 通过 Phase 1 验收门后，再进入 Context Budget。

这样第一轮就能得到可验证的编排核心，同时不会碰用户当前未提交的 UI、宠物资产、发布产物或 Live2D 工作线。

## 9. 输入文档指纹

- `Companion Harness PRD.md`：SHA-256 `558D4D61958FC3425604A34EFE9E43EEBA4BA50D3AE44946F5533850B5787116`
- `Companion Harness Technical Design.md`：SHA-256 `89F63E87AADC7D8CB8A3D4CB54B86BCD7F3DAC288D09D9F66F8F32EBF196C8B2`

后续如果输入文档变化，先对比指纹并重新审查受影响条目，不默认沿用旧结论。

### Companion Harness 意图修复与 Release 复验（2026-08-31）

- 根因：`extractCompanionPreference()` 原先用裸 `安静|别太吵|少打扰` 匹配，把普通陪伴表达误写为 `global.companionStyle=quiet` 且标为 `inferred`；现改为“持久范围信号 + 明确安静控制信号”双门禁，写入来源为 `explicit`。
- 修改文件：`src/pet-core/companionPreferences.ts`、`src/pet-core/companionPreferences.test.ts`、`src/pet-core/companionChatPipeline.test.ts`、`src/pet-core/companionHarness.test.ts`。
- 验证：聚焦 `3` 文件 `74/74`；Companion 回归 `38` 文件 `551/551`；`tsc --noEmit`、`npm run build`、Tauri `build --no-bundle` 均通过；`git diff --check` 无错误。
- Release：`D:\CodeWorkspace\电脑桌宠\src-tauri\target\release\yuxin-desktop-pet.exe`；FileVersion `0.3.2`；构建文件时间 `2026-08-31 00:13:00`；SHA-256 `DF1885B448DC592E8B1249A833B5CD74F113B27058A058BD691CA138AE0F4F77`；运行 PID `19152`，唯一进程路径与 Release 一致。已确认并关闭误启动的旧注册 `0.2.5` 进程，未关闭当前 Release。
- 模型目录：通过 `https://api.deepseek.com/v1/models` 获取 `3` 个模型，当前仍选 `deepseek-v4-flash`。
- 真实 DS：当前 Release/Tauri 中发送原始普通聊天测试句，Provider `ds` 返回可见回复“好，那就安静待着吧，喵。我陪你坐会儿。”；单次远程请求成功，未出现本地回退或重复回复。
- 回退与敏感配置：验收前回退开关为开启；真实请求期间临时关闭，完成后已重新开启并保存。API Key 仅确认掩码状态“已配置”，未读取、输出、修改或清除。
- 副作用：普通句与完整原始句均未触发 Preference/Task/Reminder/Memory；明确持久化安静请求保持单次幂等写入。最终结论：`MINIMAL_REAL_DS_PASS`。

### Companion Harness 当前 Release 最小真实 DS 复验（2026-09-02）

- 最终结论：`CURRENT_RELEASE_MINIMAL_DS_PASS`。
- 版本隔离：仅运行 `D:\CodeWorkspace\电脑桌宠\src-tauri\target\release\yuxin-desktop-pet.exe`；FileVersion `0.3.2`；SHA-256 `5909E969F8147301CD388E114567D8AB27123D75D32D837D1A8889A97DBDC42B`；最终 PID `23596`，进程路径一致且 `Responding=True`。
- Provider：真实 Tauri 设置页确认当前使用 `ds`、协议 `openai-compatible`、模型 `deepseek-v4-flash`、Endpoint `https://api.deepseek.com`；API Key 仅确认掩码“已配置”，未读取、输出、修改或清除。模型目录曾从 `https://api.deepseek.com/v1/models` 成功获取 `3` 个模型。
- 真实 DS：临时关闭本地回退并保存后，在陪伴房远程模式发送一条最小普通陪伴测试；界面由 `ds` 返回可见回复“好的，我就在这儿陪你。安静坐一会儿就好。”，未出现本地回退或重复回复。
- 副作用与恢复：本轮回复未创建 Task、Reminder 或 Memory；测试后已重新开启本地回退并保存，设置页显示“已保存并使用ds。”；未修改源码、测试、构建产物或其他配置文件。
