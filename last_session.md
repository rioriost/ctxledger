今回の変更
#### update session handoff with service-vs-MCP exposure audit result
`docs/imple_plan_0.1.0.md` と現在の repository state の比較作業をさらに進め、**workflow service 実装の存在**と**MCP public surface への露出不足の可能性**を切り分ける audit 結果を整理しました。

今回の方針:
- 「機能そのものが未実装なのか」「機能はあるが MCP surface に露出していないのか」を分けて把握する
- `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` について、domain/service layer と public MCP layer を別々に評価する
- 次の work loop が runtime wiring / tool exposure の実装に直行できるようにする

---

### 今回の監査で明確になったこと
#### 1. workflow service 側には主要操作が実装されている
`src/ctxledger/workflow/service.py` 上で、少なくとも以下の service methods が存在することを確認した。

- `register_workspace`
- `start_workflow`
- `create_checkpoint`
- `complete_workflow`

これにより、implementation plan 上の主要 workflow operations については、
少なくとも service/domain layer 側では実装が存在する、という見方が強くなった。

---

#### 2. しかし visible MCP stdio tool surface には対応する露出が見えていない
`src/ctxledger/server.py` の visible stdio runtime wiring では、少なくとも次の tool registrations が確認できている。

##### confirmed visible stdio tools
- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

一方で、implementation plan / README で required workflow tools とされる以下は、
inspected stdio runtime wiring 上では visible registration が確認できていない。

##### not visibly registered as stdio tools in inspected runtime wiring
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

---

#### 3. 現在の gap は「未実装」より「MCP exposure / wiring 不足」の可能性が高い
今回の audit により、少なくとも次の整理が可能になった。

- workflow service methods は存在する
- ただし、それらに対応する visible MCP tool-handler definitions / stdio registrations は確認できていない
- したがって、現時点の主要 gap は
  - workflow domain logic 不足
  ではなく
  - MCP public surface exposure / runtime wiring 不足
  の可能性が高い

---

#### 4. `workflow_resume` vs `resume_workflow` mismatch は引き続き unresolved
今回の audit でも、次の concrete mismatch は継続している。

- HTTP route: `workflow_resume`
- stdio tool: `resume_workflow`

これは単なる命名差ではなく、以下に影響する high-priority issue として引き続き扱うべき。

- client expectation
- docs correctness
- acceptance criteria traceability
- MCP public surface consistency

---

#### 5. resource wiring は引き続き未確認
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
- したがって、残タスクの本質は
  - domain implementation
  より
  - MCP exposure / tool wiring / docs reconciliation
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
- required MCP resource exposure
- public naming consistency
- MCP public surface audit

---

### git 状態メモ
- review artifact:
  - `docs/imple_plan_review_0.1.0.md`
- この handoff 更新時点では、今回の service-vs-MCP exposure audit result 反映について **まだ git commit 未実施**
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
  の可能性が高いことを明確化した

---

### 次に自然な作業
次に自然なのは以下です。

1. `docs/imple_plan_review_0.1.0.md` の今回更新を descriptive message で git commit する
2. `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` の MCP tool-handler 実装有無をさらに監査する
3. visible stdio runtime registration に不足している workflow tools を追加する
4. resource registration / resolver の実装有無を引き続き確定する