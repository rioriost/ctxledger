今回の変更
#### refresh session handoff with concrete MCP runtime audit findings
`docs/imple_plan_0.1.0.md` と現在の repository state の比較にもとづき、**MCP runtime surface の具体的な監査結果**を整理し、review document に反映しました。

今回の方針:
- 抽象的な「未確認」ではなく、現時点で見えている runtime wiring を具体的に棚卸しする
- `v0.1.0` implementation plan に対して、何が実際に露出していて、何が未確認/未整合なのかを後続作業向けに明確化する
- 次の work loop がそのまま実装監査や surface 整合タスクに入れるようにする

---

### 今回更新した review の主眼
#### 1. `server.py` ベースの concrete runtime audit を明記
review ドキュメント上で、少なくとも以下を concrete finding として整理した。

##### confirmed visible HTTP handlers
- `workflow_resume`
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`
- optional debug handlers:
  - `runtime_introspection`
  - `runtime_routes`
  - `runtime_tools`

##### confirmed visible stdio tools
- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

---

#### 2. plan-required workflow tools の未整合候補を具体化
`docs/imple_plan_0.1.0.md` / `README.md` では required workflow tools として:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

が期待されている一方、visible stdio runtime wiring では少なくとも次が見えていない、という整理にした。

##### not visibly registered as stdio tools in inspected runtime wiring
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

これにより、「未解決タスク」がより具体的な runtime audit finding に変わった。

---

#### 3. `workflow_resume` vs `resume_workflow` mismatch を concrete finding 化
review 内で naming mismatch を抽象論ではなく、以下の concrete difference として整理した。

- HTTP route: `workflow_resume`
- stdio tool: `resume_workflow`

これにより、後続作業では:
- canonical public name を決める
- runtime / docs / tests / plan を整合させる
という判断に直行できるようにした。

---

#### 4. resource wiring 未確認を grep-based finding として明記
required resources:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

について、review 上で少なくとも以下の concrete audit result を残した。

##### no visible implementation evidence found
- resource handler registration
- resource resolver layer
- `workspace://...` runtime wiring
- `memory://...` runtime wiring

これにより、「resource は未確認」という曖昧な表現ではなく、
「現在見えている Python implementation からは wiring evidence が確認できていない」
という形に整理した。

---

### 今回変更したファイル
- `ctxledger/docs/imple_plan_review_0.1.0.md`
- `ctxledger/last_session.md`

---

### review ドキュメント上で今回さらに明確になった open questions
#### 1. required workflow tools は本当に MCP tool として露出しているか
現時点の concrete audit では、stdio tools として明示的に見えるのは:

- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- memory stub tools

であり、plan-required workflow tools のうち以下は visible registration 未確認:

- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

#### 2. required resources は実装済みか
docs には存在するが、current visible implementation からは:
- registration
- resolver
- runtime wiring
の evidence が見えていない。

#### 3. canonical public name はどちらか
- `workflow_resume`
- `resume_workflow`

これは docs / client expectation / acceptance criteria / runtime surface をまたぐ high-priority issue として整理した。

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
- この handoff 更新時点では、今回の concrete audit findings 反映について **まだ git commit 未実施**
- `.gitignore` は引き続き開発上必要な差分として存在しうるが、成果物には含めない前提

---

### 補足
- 今回は production code の変更なし
- 追加 test なし
- review doc / handoff の更新のみ
- ただし内容は抽象的な inventory から一歩進み、`server.py` ベースの runtime audit result を review に織り込んだ形
- 次の作業は docs 追加よりも、MCP public surface の実装監査または不足分の実装に進むのが自然

---

### 次に自然な作業
次に自然なのは以下です。

1. `docs/imple_plan_review_0.1.0.md` の concrete audit findings 反映を descriptive message で git commit する
2. `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` の MCP tool exposure 有無をさらに掘る
3. resource registration / resolver の実装有無を確定する
4. 監査結果を public surface matrix に落とす