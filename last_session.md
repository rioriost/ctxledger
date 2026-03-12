今回の変更
#### close out v0.1.0 public surface review with resource docs and acceptance evidence
直前まで進めていた `v0.1.0` closeout 作業として、**required workflow MCP resources の実装反映** と **acceptance evidence の整理** まで進めました。

今回の方針:
- すでに実装済みになった workflow tools / workflow resources / runtime introspection surface を docs に反映する
- `README.md` / `docs/mcp-api.md` / `docs/imple_plan_review_0.1.0.md` を、現在の public surface に合わせて更新する
- `v0.1.0` の完了判断をしやすくするため、acceptance criteria と実装・テスト・docs の対応を 1 枚で見られる evidence matrix を追加する
- 直近の主要 gap だった
  - workflow tool exposure
  - resume naming mismatch
  - required workflow resource missing
  が埋まった前提で、残課題を **documentation/evidence closeout** に絞る

---

### 今回追加・更新した docs
#### 1. `ctxledger/docs/mcp-api.md`
更新した主な内容:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

について、**implemented on stdio runtime** であることを明記した。

追加・更新した観点:
- current implementation status
- current response shape
- `resource` payload が `workflow_resume` と同系統の composite resume payload であること
- `memory://episode/{episode_id}`
- `memory://summary/{scope}`
  は引き続き future-facing / stubbed resource であること

これにより、MCP API reference 上で:
- required workflow resources は実装済み
- memory resources はまだ未実装寄り
という整理が明確になった。

---

#### 2. `ctxledger/README.md`
更新した主な内容:
- runtime debug example payload を resource-aware に更新
- stdio runtime 側に visible な:
  - `tools`
  - `resources`
  の両方が見える example を追加・更新

主な反映内容:
- HTTP runtime example では:
  - `resources: []`
- stdio runtime example では:
  - `workflow_resume`
  - `workspace://{workspace_id}/resume`
  - `workspace://{workspace_id}/workflow/{workflow_instance_id}`

が visible であることを反映

これにより README は、現在の runtime introspection payload とかなり近い形になった。

---

#### 3. `ctxledger/docs/imple_plan_review_0.1.0.md`
更新した主な内容:
- 以前 unresolved 扱いだった **required MCP resources** を、現在は stdio runtime で implemented と整理し直した
- naming mismatch についても、現在は `workflow_resume` で aligned 済みであることを反映
- main remaining work を:
  - acceptance evidence
  - public surface matrix
  - final documentation alignment
  に再整理した

主な update:
- `6.2 Required MCP resources are now implemented on the stdio runtime`
- `6.3 Public workflow tool naming is now aligned across plan, README, and runtime`
- `Task C` を implementation gap から docs/evidence follow-up に寄せた
- short conclusion / recommended next action を closeout-oriented に更新した

これにより review 文書は、古い gap 分析というより
**ほぼ closeout checklist に近い状態**になった。

---

#### 4. 新規追加: `ctxledger/docs/v0.1.0_acceptance_evidence.md`
新規作成した内容:
- `v0.1.0` acceptance evidence matrix

含めた主な項目:
- Server starts successfully in local development
- PostgreSQL-backed tables exist and are initialized
- MCP workflow tools are callable
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
- resumable workflow reconstruction after restart
- required workflow MCP resources
- Docker-based local deployment
- core API behavior is documented
- basic tests validate critical workflow paths
- runtime debug visibility
- projection failure lifecycle visibility
- memory APIs remain safely stubbed/deferred

各行で整理した列:
- Implementation Evidence
- Public Surface Evidence
- Test Evidence
- Documentation Evidence
- Status
- Notes

加えて:
- confirmed stdio workflow tools
- confirmed stdio resources
- confirmed HTTP workflow/ops routes
- confirmed debug route set
- remaining closeout gaps
- practical closeout assessment

も追記した。

このファイルによって、`v0.1.0` の closeout 判断に必要な evidence がかなり一望しやすくなった。

---

### 直前に完了していた実装土台
今回の docs/evidence 整理は、以下の直前作業が完了している前提で行った。

#### workflow naming alignment
- stdio tool: `workflow_resume`
- HTTP route: `workflow_resume`

#### required stdio workflow resources
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

#### runtime introspection expansion
- stdio introspection に `resources` を含む
- health / readiness / startup summary でも `resources` が見える

#### test status
- `tests/test_server.py`
  - `152 passed`

---

### 今回変更・追加したファイル
- `ctxledger/README.md`
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/imple_plan_review_0.1.0.md`
- `ctxledger/docs/v0.1.0_acceptance_evidence.md`
- `ctxledger/last_session.md`

---

### 現在の public surface まとめ
#### confirmed stdio workflow tools
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`

#### confirmed stdio auxiliary tools
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

#### confirmed stdio workflow resources
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

#### confirmed HTTP workflow/ops routes
- `workflow_resume`
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`

#### confirmed HTTP debug routes
- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`

---

### 現在の意味合い
この時点で、`v0.1.0` review 上の大きな gap だったものは概ね整理された。

すでに埋まっている主要項目:
- core workflow MCP tool exposure
- `workflow_resume` naming consistency
- required stdio workflow MCP resources
- runtime/debug surface visibility
- acceptance evidence matrix

そのため、`v0.1.0` の残作業はもう
**機能実装の穴埋め** というより、
**closeout quality / final judgment / lightweight doc polishing**
の領域になっている。

---

### 確認済み状態
確認済みとして持ってよいもの:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `ctxledger/README.md`: diagnostics 問題なし
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし
- `ctxledger/docs/imple_plan_review_0.1.0.md`: diagnostics 問題なし
- `ctxledger/docs/v0.1.0_acceptance_evidence.md`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `152 passed`

---

### 直近コミット
直近の relevant commits:
- `ae7d27e Align workflow resume MCP naming`
- `703dd96 Implement workflow MCP resources`
- `366202e Document MCP resource surface`
- `6507862 Add v0.1.0 acceptance evidence matrix`

この handoff 更新時点では、
**last_session.md 自体の最新 closeout 反映については commit 未記録**
と扱うのが安全。

---

### 次に自然な作業
次に自然なのは以下。

1. `last_session.md` のこの最新内容を含めて必要なら commit する
2. `v0.1.0` を「closeable」扱いにするか最終判断する
3. もし closeout をさらに強めるなら:
   - `docs/imple_plan_review_0.1.0.md` を短く要約して final verdict を追記
   - `docs/v0.1.0_acceptance_evidence.md` への cross-links を README か review doc に足す
4. それが済んだら次フェーズとして:
   - memory subsystem expansion
   - richer resource surfaces
   - stronger end-to-end deployment evidence
   のどれに進むか決める

### 要約
- required workflow MCP resources 実装後の docs 反映まで完了
- `README.md` / `docs/mcp-api.md` / `docs/imple_plan_review_0.1.0.md` を current public surface に合わせて更新
- `docs/v0.1.0_acceptance_evidence.md` を新規追加
- `v0.1.0` の残課題は、もう実装穴ではなく **closeout evidence と最終整理** が中心