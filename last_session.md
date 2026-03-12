今回の変更
#### implement required workflow MCP resources on stdio runtime
`v0.1.0` review 上で最大の残課題だった **required MCP resource surface** に対応し、stdio runtime に workflow resources を追加しました。

今回の方針:
- public MCP surface に必要とされていた resource layer を、stdio runtime adapter に明示的に追加する
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
  を resource handler / dispatch / introspection に接続する
- 既存の `workflow_resume` tool / resume serialization / runtime debug surfaces と整合する payload shape を使う
- fake workflow service を使う tests でも安定するように、resource response builder は
  - real service (`_uow_factory` を持つ)
  - test fake service (`resume_result` を持つ)
  の両方に対応させる

---

### `ctxledger/src/ctxledger/server.py` で追加・更新した内容
#### 1. MCP resource response type を追加
追加:
- `McpResourceResponse`

shape:
- `status_code`
- `payload`
- `headers`

これにより、tool response とは分離して resource response を扱えるようにした。

---

#### 2. stdio runtime adapter に resource registry / dispatch を追加
`StdioRuntimeAdapter` に追加:
- `_resource_handlers`
- `register_resource_handler(...)`
- `registered_resources()`
- `dispatch_resource(...)`

また、start/stop log metadata にも:
- `registered_resources`
を追加した。

---

#### 3. runtime introspection shape を拡張
`RuntimeIntrospection` に追加:
- `resources: tuple[str, ...] = ()`

`serialize_runtime_introspection(...)` も更新し、runtime payload に:
- `resources`
を含めるようにした。

これにより、health / readiness / startup summary / runtime introspection payload で resource surface も見えるようになった。

---

#### 4. MCP resource dispatch function を追加
追加:
- `dispatch_mcp_resource(...)`

behavior:
- stdio runtime に登録された resource patterns を走査
- URI parser を使って適切な resource handler を選択
- 成功時:
  - `RuntimeDispatchResult(status="ok")`
- handler が 4xx/5xx を返す場合:
  - `RuntimeDispatchResult(status="error")`
- 未登録/未一致の場合:
  - `resource_not_found`
  - 404
  の `McpResourceResponse` を返す

---

#### 5. workflow resource URI parsers を追加
追加:
- `parse_workspace_resume_resource_uri(...)`
- `parse_workflow_detail_resource_uri(...)`

supported URIs:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

validation:
- UUID parse
- expected path segment count / kind
- invalid format は `None`

---

#### 6. workflow resource response builders を追加
追加:
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`

##### `workspace://{workspace_id}/resume`
semantics:
1. workspace に running workflow があればそれを選ぶ
2. なければ latest workflow を選ぶ
3. なければ not_found

success payload:
- `uri`
- `resource`
  - `serialize_workflow_resume(...)` の payload

error cases:
- `server_not_ready`
- workspace not found
- no workflow available

##### `workspace://{workspace_id}/workflow/{workflow_instance_id}`
semantics:
- exact workflow identity lookup
- workspace mismatch は invalid_request

success payload:
- `uri`
- `resource`
  - `serialize_workflow_resume(...)` の payload

error cases:
- `server_not_ready`
- workflow not found
- workflow/workspace mismatch

---

#### 7. fake service compatibility fallback を追加
resource builder は:
- real `WorkflowService` の場合:
  - `_uow_factory` を使って workspace / workflow selection を行う
- tests 用 fake service の場合:
  - `resume_result` から workspace_id / workflow_instance_id / workspace mismatch を判定する

これにより、server tests に real DB-style fake UoW を新設せずに resource tests を追加できる形にした。

---

#### 8. stdio runtime registration に required resources を追加
`build_stdio_runtime_adapter(server)` に追加した registrations:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

これで stdio runtime は tool だけでなく required workflow resources も visible になった。

---

#### 9. exports を追加
`__all__` に追加:
- `McpResourceResponse`
- `dispatch_mcp_resource`
- `build_workspace_resume_resource_handler`
- `build_workspace_resume_resource_response`
- `build_workflow_detail_resource_handler`
- `build_workflow_detail_resource_response`
- `parse_workspace_resume_resource_uri`
- `parse_workflow_detail_resource_uri`

---

### `ctxledger/tests/test_server.py` で追加・更新した内容
#### 1. resource imports / response assertions を追加
追加 import:
- `McpResourceResponse`
- `dispatch_mcp_resource`
- `build_workspace_resume_resource_handler`
- `build_workflow_detail_resource_handler`
- `parse_workspace_resume_resource_uri`
- `parse_workflow_detail_resource_uri`

---

#### 2. resource parser tests を追加
追加した代表 test:
- `test_parse_workspace_resume_resource_uri_returns_workspace_id_for_valid_uri()`
- `test_parse_workspace_resume_resource_uri_returns_none_for_invalid_uri()`
- `test_parse_workflow_detail_resource_uri_returns_ids_for_valid_uri()`
- `test_parse_workflow_detail_resource_uri_returns_none_for_invalid_uri()`

---

#### 3. resource handler tests を追加
追加した代表 test:
- `test_build_workspace_resume_resource_handler_returns_success_payload()`
- `test_build_workspace_resume_resource_handler_returns_not_found_for_invalid_uri()`
- `test_build_workspace_resume_resource_handler_returns_server_not_ready_error()`

- `test_build_workflow_detail_resource_handler_returns_success_payload()`
- `test_build_workflow_detail_resource_handler_returns_not_found_for_invalid_uri()`
- `test_build_workflow_detail_resource_handler_returns_server_not_ready_error()`

固定した内容:
- resource URI validation
- success payload contract
- `server_not_ready`
- exact workflow resource identity behavior

---

#### 4. resource dispatch test を追加
追加:
- `test_dispatch_mcp_resource_returns_dispatch_result_for_success()`
- `test_dispatch_mcp_resource_returns_resource_not_found_result()`

固定した内容:
- stdio resource dispatch status
- dispatch target
- `resource_not_found` behavior

---

#### 5. stdio introspection / composite runtime expectations を更新
更新した領域:
- `StdioRuntimeAdapter.introspect()`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`
- health/readiness/startup/runtime summary expectations
- composite runtime introspection expectations

resource expectations として追加されたもの:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

---

#### 6. HTTP-only runtime introspection expectations も更新
HTTP runtime に resource surface は現時点では追加していないため、
HTTP-side expectations では:
- `resources: []`
を明示するように更新した。

これにより payload contract が transport ごとに明確になった。

---

### 今回変更したファイル
- `ctxledger/src/ctxledger/server.py`
- `ctxledger/tests/test_server.py`
- `ctxledger/last_session.md`

---

### 現在の整合状態
#### stdio MCP workflow tools
現在の stdio MCP tools には少なくとも:
- `workspace_register`
- `workflow_start`
- `workflow_checkpoint`
- `workflow_resume`
- `workflow_complete`
- `projection_failures_ignore`
- `projection_failures_resolve`
- `memory_remember_episode`
- `memory_search`
- `memory_get_context`

#### stdio MCP workflow resources
現在の stdio MCP resources には:
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

が含まれる。

#### runtime introspection
stdio introspection では:
- `tools`
- `resources`
の両方が visible

HTTP introspection では現時点で:
- `routes`
- `tools: []`
- `resources: []`

という扱い

---

### `v0.1.0` review 上の意味合い
今回の変更により、これまで未確認 / likely missing と扱っていた:

- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`

が stdio runtime 上で visible registration / dispatch / tests まで揃った。

そのため、`v0.1.0` review 上の主要未解決テーマは
**resource missing** からさらに狭まり、

- acceptance evidence / public surface matrix
- docs への resource implementation reflected status の最終整理

に寄った。

---

### 確認結果
今回確認できた範囲:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `152 passed`

---

### git 状態メモ
- 直前の関連コミット:
  - `32bcb2f Expose core workflow MCP tools`
  - `ae7d27e Align workflow resume MCP naming`
- 今回の MCP resource 実装については
  **この handoff 更新時点では commit 未記録**
- `.gitignore` は引き続き ignore 対象の状態差分として扱う前提

---

### 補足
- 今回追加したのは **stdio MCP resource surface**
- HTTP route surface に resource endpoint を追加したわけではない
- resource payload は現状 `serialize_workflow_resume(...)` ベースなので、
  workflow detail resource も exact-identity selection の上で same resume payload shape を返す
- fake workflow service 互換のために test-friendly fallback を server layer に入れている

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の required MCP resource 実装を descriptive message で git commit する
2. `README.md`
3. `docs/mcp-api.md`
4. `docs/imple_plan_review_0.1.0.md`
   に resource 実装済み状態を明示反映する
5. 必要なら public surface matrix / acceptance evidence table を追加する

### 要約
- stdio runtime に required workflow MCP resources を追加した
- `workspace://{workspace_id}/resume`
- `workspace://{workspace_id}/workflow/{workflow_instance_id}`
  を parser / handler / dispatch / introspection / tests まで実装した
- runtime introspection payload は `resources` を含むように拡張した
- `tests/test_server.py` は `152 passed`
- `v0.1.0` の主な残課題は、もう resource missing ではなく
  **acceptance evidence と public surface documentation の最終整理**