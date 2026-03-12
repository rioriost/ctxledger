今回の変更
#### add core workflow MCP tools to stdio runtime surface
`v0.1.0` implementation plan review で identified していた **required workflow MCP tool exposure gap** に対応し、stdio runtime に core workflow tools を追加しました。

今回の方針:
- すでに service/domain layer に存在していた workflow operations を、public MCP tool surface に正しく露出する
- `workspace_register` / `workflow_start` / `workflow_checkpoint` / `workflow_complete` を `server.py` の MCP tool-handler と stdio registration に接続する
- 既存の projection failure lifecycle / memory stub / debug/runtime introspection surface と整合する形で response / validation / server-not-ready behavior を揃える
- 直前まで review で整理していた「未実装というより MCP exposure / tool wiring 不足」という gap を実装で埋める

---

### `ctxledger/src/ctxledger/server.py` で追加・更新した内容
#### 1. workflow service inputs / statuses / errors の import を追加
追加した主な import:
- `RegisterWorkspaceInput`
- `StartWorkflowInput`
- `CreateCheckpointInput`
- `CompleteWorkflowInput`
- `WorkflowInstanceStatus`
- `VerifyStatus`
- `WorkflowError`

これにより、server layer の MCP tool-handlers から service-layer use case inputs を直接構築できるようにした。

---

#### 2. MCP tool argument parsing helpers を追加
追加した helper:
- `_parse_required_string_argument(...)`
- `_parse_optional_string_argument(...)`
- `_parse_optional_dict_argument(...)`
- `_parse_optional_verify_status_argument(...)`
- `_parse_required_workflow_status_argument(...)`
- `_map_workflow_error_to_mcp_response(...)`

役割:
- required / optional argument の validation を transport boundary で統一
- `verify_status` / `workflow_status` の enum conversion を明示
- `WorkflowError` を representative MCP error shape に正規化
- generic exception fallback も existing MCP error response style に合わせて処理

主な正規化方針:
- validation / conflict / mismatch 系 -> `invalid_request`
- not-found 系 -> `not_found`
- その他 -> `server_error`

---

#### 3. core workflow MCP tool-handlers を追加
追加した handler:
- `build_workspace_register_tool_handler(server)`
- `build_workflow_start_tool_handler(server)`
- `build_workflow_checkpoint_tool_handler(server)`
- `build_workflow_complete_tool_handler(server)`

それぞれの behavior:
- arguments を parse / validate
- `workflow_service` 未初期化なら `server_not_ready`
- service call 実行
- result を MCP success payload に serialize
- service exception を normalized MCP error に変換

##### `workspace_register`
受け取る主な fields:
- `repo_url`
- `canonical_path`
- `default_branch`
- `workspace_id` (optional)
- `metadata` (optional)

success payload:
- `workspace_id`
- `repo_url`
- `canonical_path`
- `default_branch`
- `metadata`
- `created_at`
- `updated_at`

##### `workflow_start`
受け取る主な fields:
- `workspace_id`
- `ticket_id`
- `metadata` (optional)

success payload:
- `workflow_instance_id`
- `attempt_id`
- `workspace_id`
- `ticket_id`
- `workflow_status`
- `attempt_status`
- `created_at`

##### `workflow_checkpoint`
受け取る主な fields:
- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `summary` (optional)
- `checkpoint_json` (optional object)
- `verify_status` (optional)
- `verify_report` (optional object)

success payload:
- `checkpoint_id`
- `workflow_instance_id`
- `attempt_id`
- `step_name`
- `created_at`
- `latest_verify_status`

##### `workflow_complete`
受け取る主な fields:
- `workflow_instance_id`
- `attempt_id`
- `workflow_status`
- `summary` (optional)
- `verify_status` (optional)
- `verify_report` (optional object)
- `failure_reason` (optional)

success payload:
- `workflow_instance_id`
- `attempt_id`
- `workflow_status`
- `attempt_status`
- `finished_at`
- `latest_verify_status`

---

#### 4. stdio runtime registration に core workflow tools を追加
`build_stdio_runtime_adapter(server)` で追加した registrations:
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`

これで stdio tool surface は少なくとも:
- `resume_workflow`
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_complete`
- `projection_failures_ignore`
- `projection_failures_resolve`
- memory stub tools
を含む状態になった。

---

#### 5. `__all__` export を更新
追加 export:
- `build_workspace_register_tool_handler`
- `build_workflow_start_tool_handler`
- `build_workflow_checkpoint_tool_handler`
- `build_workflow_complete_tool_handler`

---

### `ctxledger/tests/test_server.py` で追加・更新した内容
#### 1. `FakeWorkflowService` を拡張
追加した fake support:
- `register_workspace_result`
- `register_workspace_calls`
- `start_workflow_result`
- `start_workflow_calls`
- `create_checkpoint_result`
- `create_checkpoint_calls`
- `complete_workflow_result`
- `complete_workflow_calls`

追加した fake methods:
- `register_workspace(...)`
- `start_workflow(...)`
- `create_checkpoint(...)`
- `complete_workflow(...)`

これにより、新規 MCP tool-handlers の argument forwarding / payload shaping を server tests で直接固定できるようにした。

---

#### 2. core workflow MCP tool-handler tests を追加
追加した代表 test:
- `test_build_workspace_register_tool_handler_returns_success_payload()`
- `test_build_workspace_register_tool_handler_returns_invalid_request_for_missing_repo_url()`
- `test_build_workspace_register_tool_handler_returns_server_not_ready_error()`

- `test_build_workflow_start_tool_handler_returns_success_payload()`
- `test_build_workflow_start_tool_handler_returns_invalid_request_for_bad_workspace_id()`
- `test_build_workflow_start_tool_handler_returns_server_not_ready_error()`

- `test_build_workflow_checkpoint_tool_handler_returns_success_payload()`
- `test_build_workflow_checkpoint_tool_handler_returns_invalid_request_for_missing_step_name()`
- `test_build_workflow_checkpoint_tool_handler_returns_server_not_ready_error()`

- `test_build_workflow_complete_tool_handler_returns_success_payload()`
- `test_build_workflow_complete_tool_handler_returns_invalid_request_for_bad_status()`
- `test_build_workflow_complete_tool_handler_returns_server_not_ready_error()`

固定した内容:
- required argument validation
- enum validation
- `workflow_service` call shape
- success payload contract
- `server_not_ready` contract

---

#### 3. stdio runtime registration/introspection expectation を更新
更新した領域:
- `build_stdio_runtime_adapter(...)` の registered tool assertions
- composite runtime introspection / health / readiness / startup summary / debug tools payload expectations

反映した tool set:
- `memory_get_context`
- `memory_remember_episode`
- `memory_search`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `resume_workflow`
- `workflow_checkpoint`
- `workflow_complete`
- `workflow_start`
- `workspace_register`

これにより、new MCP tools が
- runtime introspection
- debug `/debug/tools`
- health/readiness runtime summary
- startup stderr summary
にも反映されることを tests で固定した。

---

### 今回変更したファイル
- `ctxledger/src/ctxledger/server.py`
- `ctxledger/tests/test_server.py`
- `ctxledger/docs/imple_plan_review_0.1.0.md`
- `ctxledger/last_session.md`

---

### 実装計画 review への反映
`docs/imple_plan_review_0.1.0.md` も今回内容に合わせて更新した。

主な更新点:
- 以前の「required workflow MCP tools が visible registration に見えない」という gap を更新
- 現在は:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_complete`
  が visible stdio runtime wiring に存在することを反映
- workflow MCP gap は「missing exposure」から
  - `workflow_resume` vs `resume_workflow` naming consistency
  - required resource surface
  に重心が移ったことを整理

---

### 現在の整合状態
#### service / MCP exposure
- workflow service methods:
  - `register_workspace`
  - `start_workflow`
  - `create_checkpoint`
  - `resume_workflow`
  - `complete_workflow`
  が存在
- stdio MCP tools:
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `resume_workflow`
  - `workflow_complete`
  が存在
- projection failure lifecycle tools:
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  が存在
- memory stub tools:
  - `memory_remember_episode`
  - `memory_search`
  - `memory_get_context`
  が存在

#### docs / implementation plan review
- core workflow MCP tool exposure gap はかなり解消
- ただし unresolved として残る主題は:
  - `workflow_resume` vs `resume_workflow` naming alignment
  - required MCP resources
  - public surface matrix / acceptance evidence table

#### tests
- `tests/test_server.py` で core workflow MCP tool-handlers の contract を固定済み
- runtime introspection / debug tools payload も expanded tool set に合わせて固定済み

---

### 確認結果
今回確認できた範囲:
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `139 passed`

---

### git 状態メモ
- 直前までの review / docs 関連コミット:
  - `224065d Add v0.1.0 implementation plan review`
  - `5f8751c Refine v0.1.0 MCP surface review`
  - `e4c2e89 Clarify MCP exposure gaps in review`
  - `9cee123 Record missing workflow tool handlers`
- この handoff 更新時点では、今回の core workflow MCP tool exposure 実装について **まだ git commit 未実施**
- `.gitignore` は引き続き開発上必要な差分として存在しうるが、成果物には含めない前提

---

### 補足
- 今回は HTTP route surface の追加はしていない
- 追加したのは stdio MCP tool surface
- `workflow_resume` の public naming は依然として
  - HTTP route: `workflow_resume`
  - stdio tool: `resume_workflow`
  で不一致
- そのため、implementation plan review 上の最重要未解決テーマは今や
  - resource surface
  - resume naming consistency
  に寄っている

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の core workflow MCP tool exposure 実装を descriptive message で git commit する
2. `resume_workflow` を `workflow_resume` に寄せるかどうか決めて、runtime / docs / tests を整合させる
3. required MCP resources
   - `workspace://{workspace_id}/resume`
   - `workspace://{workspace_id}/workflow/{workflow_instance_id}`
   の実装有無を確定し、未実装なら実装する
4. public surface matrix または acceptance evidence table を追加して、`v0.1.0` closeout の判断材料を揃える