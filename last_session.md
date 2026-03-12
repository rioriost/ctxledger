今回の変更
#### `ctxledger/src/ctxledger/server.py`
projection failure lifecycle の operator action surface を、まず MCP tool として実装しました。

追加した主な内容:
- `ProjectionArtifactType` の import
- `_parse_required_uuid_argument(...)`
- `_parse_optional_projection_type_argument(...)`
- `build_projection_failures_ignore_tool_handler(...)`
- `build_projection_failures_resolve_tool_handler(...)`

また、`build_resume_workflow_tool_handler(...)` でも UUID parse helper を使う形に整理しました。

---

#### 実装した MCP tools
追加した representative mutation-side tool:

- `projection_failures_ignore`
- `projection_failures_resolve`

#### `projection_failures_ignore`
役割:
- matching `open` projection failure records を `ignored` として close する

入力:
- `workspace_id` (required)
- `workflow_instance_id` (required)
- `projection_type` (optional)

成功時 response:
- `workspace_id`
- `workflow_instance_id`
- `projection_type`
- `updated_failure_count`
- `status = "ignored"`

#### `projection_failures_resolve`
役割:
- matching `open` projection failure records を `resolved` として close する

入力:
- `workspace_id` (required)
- `workflow_instance_id` (required)
- `projection_type` (optional)

成功時 response:
- `workspace_id`
- `workflow_instance_id`
- `projection_type`
- `updated_failure_count`
- `status = "resolved"`

---

#### validation / error handling
少なくとも次を追加しています。

- required UUID fields の validation
  - `workspace_id`
  - `workflow_instance_id`
- optional `projection_type` validation
- workflow service 未初期化時
  - `server_not_ready`
- service 呼び出し例外の MCP error mapping
  - `not_found`
  - `invalid_request`
  - `server_error`

`projection_type` の invalid input では、allowed values を details に返す形にしています。

---

#### stdio runtime registration
`build_stdio_runtime_adapter(...)` に次の tool registration を追加しました。

- `projection_failures_ignore`
- `projection_failures_resolve`

この結果、stdio tool surface は少なくとも次を含む状態です。

- `resume_workflow`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

---

#### `ctxledger/tests/test_server.py`
server 向けテストも追加しました。

追加した主なテスト:
- `build_projection_failures_ignore_tool_handler(...)`
  - success
  - missing `workspace_id`
  - bad `projection_type`
  - server not ready
- `build_projection_failures_resolve_tool_handler(...)`
  - success
  - bad `workflow_instance_id`
  - server not ready
- `build_stdio_runtime_adapter(...)`
  - projection failure lifecycle tools の registration
- `StdioRuntimeAdapter.dispatch_tool(...)`
  - `projection_failures_ignore`
  - `projection_failures_resolve`

また、`FakeWorkflowService` に以下の fake capability を追加しました。

- `ignore_resume_projection_failures(...)`
- `resolve_resume_projection_failures(...)`

---

### 現在の状態
projection failure lifecycle まわりは、少なくとも次の 2 系統が揃いつつあります。

1. read-side
- `workflow_resume`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

2. mutation-side
- `projection_failures_ignore`
- `projection_failures_resolve`

これで docs 上の representative design を、まず MCP tool surface として実装側へ降ろし始めた状態です。

---

### 確認状況
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし

一方で、
- `ctxledger/tests/test_server.py`

については、内容と噛み合わない古い unused import warning が残って見えており、diagnostics 表示側のずれか、あるいは別状態との差分確認が必要そうです。実ファイル内容上は unused import はかなり整理済みの想定です。

---

### 補足
- `.gitignore` は保守対象外として扱う前提
- この handoff でも `.gitignore` は作業対象に含めない

---

### 次に自然な作業
次に自然なのは以下です。

1. `tests/test_server.py` の diagnostics 表示ずれを確認して解消する
2. 新 MCP tools を docs に implemented surface として反映する
3. 必要なら HTTP action endpoint 版も追加する
4. 実 service / integration tests 側にも public surface 観点の coverage を広げる

この時点では、projection failure lifecycle の operator action surface は docs だけでなく MCP tool 実装としても入り始めた状態です。