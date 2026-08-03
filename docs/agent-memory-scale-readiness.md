# 阶段 6：规模化进入条件评估与同步契约硬化

状态：完成本地范围评估；结论为 **Go：继续使用本地方案**，**No-Go：现在引入云端、向量库或队列**。

评估日期：2026-08-02；2026-08-03 增补删除优先恢复回归。所有数字来自 `src/storage/agentMemoryScaleReadiness.test.ts` 的隔离 fixture；没有读取或修改用户真实数据，没有网络请求，也没有远程上传。fixture 结果只说明当前实现对这组边界样本的行为和耗时，不能外推为生产容量承诺。

## 1. 同步契约硬化结果

当前 Outbox 事件包含 `eventId`、`entityType`、`entityId`、`operation`、`schemaVersion`、`deviceId`、`createdAt`、`syncVersion`，以及经过安全投影的 `updatedAt`、`deletedAt` 和 payload。`deviceId + syncVersion` 只表示单设备顺序。

- delete 事件先到且本地没有实体时，`applyOutboxEvent(null, delete)` 会物化 `data: null` 的 Tombstone。
- 同设备的旧 upsert，以及无法证明因果关系的跨设备 upsert，都不能让该 Tombstone 复活。
- 相同 `deviceId` 的版本可以按单调序列判断 stale/newer；不同 `deviceId` 的 `syncVersion` 返回 `incomparable`，不能直接做大小比较。
- 同一 `eventId` 重复应用是幂等的。

相关证据在 `src/storage/localRepository.test.ts` 和测量 fixture 的 delete-first 回归用例中；本地 Repository 另有主记录、Outbox、同步计数器、journal 清理中断和损坏 journal 的删除守卫测试。当前实现仍然没有跨设备冲突合并、因果元数据、远程 ack/cursor、重试传输、RLS/TLS/审计或删除传播服务，因此这不是“云同步已可接入”的声明。

云同步前置阻塞保持明确：在定义跨设备的冲突/重建语义、远端删除确认和权限审计前，不得把 `RepositorySyncTransport` 当作可用网络能力；本阶段只冻结 Provider-neutral wire boundary。

## 2. 实测事实

测量命令：

```text
npx vitest run src/storage/agentMemoryScaleReadiness.test.ts --reporter=verbose --silent=false
```

本次运行的 fixture 时钟为 `2026-08-02T12:00:00.000Z`，测量输出时间为 `2026-08-02T15:16:40.558Z`。p50/p95 是单次运行中完成预热后的样本分位数，不是线上 SLA。

| 指标 | Fixture | 实测结果 |
|---|---|---:|
| Memory 条目数 | 200 条，达到当前 Memory 上限 | 200 |
| Memory 存储大小 | Repository 主记录，UTF-8 序列化字节 | 86,866 bytes |
| Memory Outbox | 同一批 fixture 的安全投影 | 200 events / 135,955 bytes |
| 关键词检索 | 200 条 Memory；1,000 次查询；当前宠物可见作用域 | p50 1.3230 ms；p95 2.2991 ms |
| Outbox 数量与大小 | 独立 fixture，追加 256 个事件 | 256 events / 83,167 bytes |
| Outbox 增长速度 | 内存 Map storage，逐事件追加并序列化 | 4,515.7 events/s；1,467,010 bytes/s |
| Task 扫描 | 1,000 tasks、1,000 reminders、1,000 instances；得到 500 个候选 | p50 3.4906 ms；p95 5.3915 ms |
| 主动触发评估 | 500 个候选，创建独立本地 gate fixture | p50 61.7660 ms；p95 71.3288 ms |

恢复/失败 fixture 的结果全部符合预期：

| 场景 | 结果 |
|---|---|
| 损坏实体 JSON 与损坏 Outbox | 安全降级为空实体/空队列，未抛出阻断异常 |
| 主记录写入失败 | 返回失败；主记录和 Outbox 均未留下半成品 |
| Outbox 写入失败且回滚中断 | journal 被保留；下一次初始化回滚主记录、清理 journal，实体保持不存在 |
| delete-first + 跨设备旧 upsert | Tombstone 保持不变，旧 upsert 未应用 |

“增长速度”是隔离内存 fixture 的序列化循环速度，不是磁盘、WebView 配额或真实用户机器的吞吐证据；它仅用于发现当前数组式 Outbox 的增长形态。

## 3. 候选阈值（不是实测事实）

这些是下一轮压测/遥测前的保护性候选值，不是本次 fixture 推导出的硬结论：

| 观察项 | 候选本地告警线 | 超过后的动作 |
|---|---:|---|
| Active Memory | 150 条，或主记录序列化超过 256 KiB | 先做本地索引/分片/归档设计；不自动引入向量库 |
| 关键词检索 p95 | 50 ms | 优先优化本地检索和读取次数；只有真实工作负载持续超线才评估 Embedding |
| Outbox backlog | 1,000 events，或 1 MiB | 增加本地压缩/ack 前保留策略和可见告警；不等同于需要 Kafka |
| Task 扫描或主动评估 p95 | 100 ms（以 1,000 tasks 级 fixture 为一档） | 先定位算法/序列化热点；只有单 Worker 可靠性或吞吐仍不足才评估队列 |
| 恢复可靠性 | 任一损坏、写失败或 journal 恢复场景失败 | No-Go：先修复本地可靠性，不进入云端扩展 |

本次样本低于 Memory、检索和 Task 的候选告警线；主动评估的 p95 低于 100 ms 候选线。由于样本是人工 fixture，不能据此声称已覆盖更大数据量或所有 WebView 配额情况。

## 4. 是否有必须引入云端、向量库或队列的证据

没有。

- 没有跨设备同步的已实现需求或远端消费方；不同设备版本仍不可比较，冲突合并契约尚未定义。
- 关键词检索在当前 200 条边界 fixture 上 p95 为 2.2991 ms，没有出现必须使用 Embedding 或独立向量库的延迟证据。
- 1,000 条任务 fixture 的扫描和主动评估没有超过候选本地告警线；当前单 Worker 规则评估也没有可靠性失败证据。
- 损坏数据、写入失败和 journal 恢复 fixture 均通过，说明本地边界可继续使用；这不是对所有规模的可靠性保证。

因此现在不引入 PostgreSQL、pgvector、Qdrant、Milvus、Kafka、Temporal、云端同步或远程队列。未来若出现真实多设备、远程推送、跨天强审计工作流，或代表性本地工作负载持续越过候选阈值，应先重新测量，再单独验收对应基础设施。

## 5. 留在本地的理由与下一阶段必要条件

继续本地方案的理由：

- 当前数据规模有明确上限，且检索使用简单可解释的关键词/标签/时间排序。
- Task 事实源、Reminder 生命周期、主动触发门禁和 Outbox 都能在本机保持同一数据边界；引入远程组件会扩大故障面和删除传播责任。
- 当前 Outbox 是迁移准备，不是网络队列；在没有远端 ack/cursor 和冲突协议前，保持本地更诚实也更容易验证。
- SOUL 继续是宠物包内只读资产；Memory Outbox 只保存安全投影，不保存完整聊天、原始证据、密码、Token、医疗信息或精确地址。

进入下一阶段至少需要同时具备：

1. 明确的跨设备/远程产品需求，以及用户对同步范围、删除和保留期的选择。
2. 代表性 fixture 或真实的、经用户同意的匿名遥测持续超过候选性能/容量线，而不是一次偶然慢测量。
3. 跨设备因果顺序、冲突合并、重建/删除语义、幂等、远端 ack/cursor、离线重试和 schema 演进协议。
4. 云端身份、最小权限、RLS、TLS、审计、备份恢复、区域/保留策略和隐私删除流程的设计与验证。

若仅是语义检索变慢，先评估本地倒排/分片/缓存；只有确认关键词方案无法满足代表性工作负载，才评估本地 Embedding 或受控的 PostgreSQL + pgvector。Qdrant/Milvus 不属于当前默认升级路径。若仅是事件积压，先做本地压缩和恢复；只有单 Worker 的吞吐或可靠性经证据证明不足，才评估队列。

## 6. 成本、模型额度、Embedding 与隐私风险

- 当前本地关键词检索不产生云 API、Embedding、网络流量或模型额度成本，主要成本是本机 CPU、内存、localStorage 配额和故障恢复维护。
- 云端事实源会增加存储、备份、网络出站、身份认证、监控、审计、TLS/RLS 和运维成本；跨设备同步还会增加冲突处理、删除传播和客服解释成本。
- 远程 Embedding 会按新增/更新内容产生模型调用、重试和额度消耗，并增加向量存储与索引成本；本地 Embedding 则交换为模型包体积、CPU/内存、电量和升级成本。当前没有必要为此引入成本。
- 把 Memory 或 Event 上传远端会扩大敏感数据暴露面，即使当前安全投影已过滤密码、Token、医疗信息、精确地址和原始聊天，也仍需处理用户同意、数据最小化、跨境/区域、保留期、访问审计、备份删除和供应商合规。localStorage 也不应被描述成加密数据库。
- Provider 可替换不等于数据可以自动外发；任何远端 Provider 或同步服务都必须另设授权、范围和删除契约。

## 7. Go / No-Go

**Go：** 保持 Task、Memory、Outbox、Tombstone、关键词检索和主动触发评估在本地继续演进；保留当前 fixture 测量与恢复测试作为进入条件基线。

**No-Go：** 本阶段不接入 PostgreSQL、pgvector、Qdrant、Milvus、Kafka、Temporal、云端同步或远程上传；也不宣称当前 `RepositorySyncTransport` 已经可以接云。

阶段 6 的结论是“本地方案通过当前边界评估，规模化基础设施暂不进入”，而不是“系统已证明可以无限规模运行”。

## 8. 本次验证记录

- 相关测试：2 个文件、11/11 通过。
- 历史记录（2026-08-02）：全量 npm 为 55 个文件、488/488 通过。
- `npm run build`：通过；Vite 仍报告已有的主 chunk 超过 500 kB 优化提示。
- `cargo test`：10/10 通过。
- `cargo check`：通过。

## 9. 2026-08-03 修复轮验证

- `npm test`：59 个测试文件、575/575 个测试通过。
- `src/storage/agentMemoryScaleReadiness.test.ts`：2/2 通过，包含删除优先恢复回归。
- `npm run build`、`cargo test` 10/10、`cargo check` 和 `git diff --check` 均通过。
