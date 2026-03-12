今回の変更
#### refresh session handoff with missing tool-handler audit detail
`docs/imple_plan_0.1.0.md` と現在の repository state の比較作業をさらに進め、**workflow service methods は存在するが、対応する MCP tool-handler / stdio registration が visible implementation 上では確認できていない** という audit detail を整理しました。

今回の方針:
- 「service layer に機能がある」ことと、「public MCP surface に露出している」ことを明確に分離して整理する
- `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` について、単に stdio registration が見えていないだけでなく、対応する visible tool-handler definition も未確認であることを明記する
- 次の work loop が、抽象的な gap 確認ではなく、MCP exposure 実装に直接進めるようにする

---

### 今回の監査でさらに明確になったこと
#### 1. workflow service 側には主要操作が実装されている
`src/ctxledger/workflow/service.py` 上で、少なくとも以下の service methods が存在することを確認済み。

- `register_workspace`
- `start_workflow`
- `create_checkpoint`
- `complete_workflow`

これにより、implementation plan 上の主要 workflow operations については、少なくとも service/domain layer 側では実装が存在する、という評価は維持される。

---

#### 2. しかし visible MCP stdio surface には対応する tool exposure が見えていない
`src/ctxledger/server.py` の visible stdio runtime wiring では、少なくとも次の tool registrations が確認できている。

##### confirmed visible stdio tools
- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

一方で、implementation plan / README で required workflow tools とされる以下は、inspected stdio runtime wiring 上では visible registration が確認できていない。

##### not visibly registered as stdio tools in inspected runtime wiring
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

---

#### 3. visible MCP tool-handler definitions も未確認
今回の監査ではさらに、`src/ctxledger/server.py` に見えている server-side tool-handler definitions を確認した結果、少なくとも以下は visible tool-handler として確認できた。

##### confirmed visible tool-handler definitions
- `build_resume_workflow_tool_handler`
- `build_projection_failures_ignore_tool_handler`
- `build_projection_failures_resolve_tool_handler`
- `build_memory_remember_episode_tool_handler`
- `build_memory_search_tool_handler`
- `build_memory_get_context_tool_handler`

一方で、plan-required workflow tools に対応する以下の visible tool-handler definitions は確認できていない。

##### no corresponding visible MCP tool-handler definitions confirmed
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

これにより、未解決タスクは単なる registration 漏れの可能性だけでなく、
- tool-handler 自体の未実装
- または少なくとも inspected server surface では未確認
というレベルまで具体化された。

---

#### 4. 現在の gap は「workflow domain 未実装」ではなく「MCP exposure / wiring 未完了」の可能性が高い
今回までの audit により、少なくとも次の整理が可能になった。

- workflow service methods は存在する
- しかし、それに対応する visible MCP tool-handler definitions は確認できない
- さらに stdio runtime registration にも現れていない
- したがって、現時点の主要 gap は
  - workflow domain logic 不足
  ではなく
  - MCP public surface exposure / tool-handler / runtime wiring 不足
  の可能性が高い

---

#### 5. `workflow_resume` vs `resume_workflow` mismatch は継続
今回の audit でも、次の concrete mismatch は継続している。

- HTTP route: `workflow_resume`
- stdio tool: `resume_workflow`

これは単なる命名差ではなく、以下に影響する high-priority issue として引き続き扱うべき。

- client expectation
- docs correctness
- acceptance criteria traceability
- MCP public surface consistency

---

#### 6. resource wiring は引き続き未確認
required resources:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

については、今回時点でも current visible implementation からは:

- resource registration
- resource resolver
- `workspace://...` runtime wiring
- `memory://...` runtime wiring

の evidence が見えていない、という整理のまま。

---

### 今回変更したファイル
- `ctxledger/docs/imple_plan_review_0.1.0.md`
- `ctxledger/last_session.md`

---

### review ドキュメント上で今回さらに明確になった判断
#### service layer
- `register_workspace`
- `start_workflow`
- `create_checkpoint`
- `complete_workflow`

は visible implementation evidence がある

#### MCP public surface
- 上記 operation に対応する required MCP tool exposure は未確認または未整合
- さらに visible MCP tool-handler definitions も未確認
- したがって、残タスクの本質は
  - domain implementation
  より
  - MCP exposure / tool-handler / runtime wiring / docs reconciliation
  に寄っている

---

### 現在の整合状態
#### 強く揃っている領域
- workflow service core
- PostgreSQL persistence baseline
- Docker-based local deployment
- memory stub posture
- projection failure lifecycle docs/tests/ops guidance
- broad documentation coverage
- broad test presence

#### 具体監査で未解決が強くなった領域
- required MCP workflow tool exposure
- required MCP workflow tool-handler implementation or visibility
- required MCP resource exposure
- public naming consistency
- MCP public surface audit

---

### git 状態メモ
- review artifact:
  - `docs/imple_plan_review_0.1.0.md`
- この handoff 更新時点では、今回の missing tool-handler audit detail 反映について **まだ git commit 未実施**
- `.gitignore` は引き続き開発上必要な差分として存在しうるが、成果物には含めない前提

---

### 補足
- 今回は production code の変更なし
- 追加 test なし
- review doc / handoff の更新のみ
- ただし内容としては重要で、未解決タスクの性質が
  - 実装不足
  ではなく
  - MCP public surface への露出不足
  に加えて
  - visible tool-handler 不足
  の可能性が高いことを明確化した

---

### 次に自然な作業
次に自然なのは以下です。

1. `docs/imple_plan_review_0.1.0.md` の今回更新を descriptive message で git commit する
2. `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` の MCP tool-handler を実装する
3. そのうえで visible stdio runtime registration に不足している workflow tools を追加する
4. resource registration / resolver の実装有無を引き続き確定する