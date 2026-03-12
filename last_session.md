Patch 1 implementation progress まで進めました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/mcp/` パッケージを新設
- 以下の新規ファイルを追加:
  - `ctxledger/src/ctxledger/mcp/__init__.py`
  - `ctxledger/src/ctxledger/mcp/tool_schemas.py`
  - `ctxledger/src/ctxledger/mcp/tool_handlers.py`
  - `ctxledger/src/ctxledger/mcp/resource_handlers.py`

## 1. `ctxledger/src/ctxledger/mcp/tool_schemas.py`
`server.py` から、低リスクで再利用価値の高い MCP schema 群を抽出しました。

移したもの:
- `McpToolSchema`
- `DEFAULT_EMPTY_MCP_TOOL_SCHEMA`
- `serialize_mcp_tool_schema(...)`
- `WORKSPACE_REGISTER_TOOL_SCHEMA`
- `WORKFLOW_RESUME_TOOL_SCHEMA`
- `WORKFLOW_START_TOOL_SCHEMA`
- `WORKFLOW_CHECKPOINT_TOOL_SCHEMA`
- `WORKFLOW_COMPLETE_TOOL_SCHEMA`
- `PROJECTION_FAILURES_IGNORE_TOOL_SCHEMA`
- `PROJECTION_FAILURES_RESOLVE_TOOL_SCHEMA`
- `MEMORY_REMEMBER_EPISODE_TOOL_SCHEMA`
- `MEMORY_SEARCH_TOOL_SCHEMA`
- `MEMORY_GET_CONTEXT_TOOL_SCHEMA`

これは Patch 1 plan で想定していた
「stable MCP assets の切り出し」
に対応しています。

## 2. `ctxledger/src/ctxledger/mcp/tool_handlers.py`
`server.py` から、transport-neutral に近い tool handler builder 群を抽出しました。

移したもの:
- `build_mcp_success_response(...)`
- `build_mcp_error_response(...)`
- `_parse_required_uuid_argument(...)`
- `_parse_optional_projection_type_argument(...)`
- `_parse_required_string_argument(...)`
- `_parse_optional_string_argument(...)`
- `_parse_optional_dict_argument(...)`
- `_parse_optional_verify_status_argument(...)`
- `_parse_required_workflow_status_argument(...)`
- `_map_workflow_error_to_mcp_response(...)`

および以下の handler builder:
- `build_resume_workflow_tool_handler(...)`
- `build_workspace_register_tool_handler(...)`
- `build_workflow_start_tool_handler(...)`
- `build_workflow_checkpoint_tool_handler(...)`
- `build_workflow_complete_tool_handler(...)`
- `build_projection_failures_ignore_tool_handler(...)`
- `build_projection_failures_resolve_tool_handler(...)`
- `build_memory_remember_episode_tool_handler(...)`
- `build_memory_search_tool_handler(...)`
- `build_memory_get_context_tool_handler(...)`

注意点:
- `server.py` 側の auxiliary HTTP routes がまだ `_parse_required_uuid_argument(...)` /
  `_parse_optional_projection_type_argument(...)` を使っていたため、
  その2つは `server.py` 側にも残してあります。
- つまり完全移行ではなく、Patch 1 の安全な抽出に留めています。

## 3. `ctxledger/src/ctxledger/mcp/resource_handlers.py`
resource まわりの parser / handler / thin wrapper を抽出しました。

移したもの:
- `parse_workspace_resume_resource_uri(...)`
- `parse_workflow_detail_resource_uri(...)`
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`
- `build_workspace_resume_resource_handler(...)`
- `build_workflow_detail_resource_handler(...)`

実装中に 1 点注意:
- invalid resource URI 用の not_found response 構築で不自然な式が入ってしまったため、
  修正済みです。
- 現在は helper 経由で正しく `McpResourceResponse` を返す形になっています。

## 4. `ctxledger/src/ctxledger/server.py`
`server.py` 側は以下の方針で修正しました。

- 新設した `mcp/` モジュールから import する形に変更
- schema 定義の重複を削除
- tool handler builder 群の重複を削除
- resource parser / handler の重複を削除
- ただし以下はまだ `server.py` に残置:
  - custom `/mcp` transport path (`build_mcp_http_handler(...)`)
  - `handle_mcp_rpc_request(...)`
  - `HttpRuntimeAdapter`
  - `StdioRpcServer`
  - `StdioRuntimeAdapter`
  - auxiliary HTTP routes
  - startup / readiness / bootstrap
  - `_parse_required_uuid_argument(...)`
  - `_parse_optional_projection_type_argument(...)`
    （aux HTTP routes のために当面残置）
- `MemoryService` import を一度落として test failure が出たため、復帰済み

## テスト状態
Patch 1 の目的は「挙動を変えずに抽出する」ことだったので、
まず `tests/test_server.py` を確認しました。

結果:
- **163 passed**

途中で出た問題:
- auxiliary HTTP routes から `_parse_required_uuid_argument` が見えなくなって NameError
- `build_stdio_runtime_adapter(...)` で `MemoryService` import が欠けて NameError

どちらも修正済みで、現時点では `tests/test_server.py` は green です。

## 現在の整理
ここまでで Patch 1 のゴールは概ね達成です。

達成できたこと:
- `server.py` から stable MCP assets の一部抽出
- 新しい `ctxledger.mcp` package の土台作成
- 既存挙動を維持したまま責務分離を少し前進
- 次の patch で lifecycle / transport scaffold を入れる下地づくり

まだ残っているもの:
- custom `/mcp` transport はそのまま
- lifecycle authority はまだ `server.py` 側に強く残っている
- stdio / HTTP の transport coupling もまだ強い
- result mapping も local envelope 依存のまま

## 次にやること
次は plan 通りなら **Patch 2** です。

対象:
- `ctxledger/src/ctxledger/mcp/lifecycle.py`
- `ctxledger/src/ctxledger/mcp/streamable_http.py`

そこでやること:
- `initialize`
- `protocolVersion`
- `notifications/initialized`
- `/mcp` を generic route ではなく MCP endpoint として扱う scaffold

を入れて、
`server.py` から protocol authority を動かし始めることです。

## 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. `tests/test_server.py` は 163 passed
3. `docs/specification.md` は絶対に触らない
4. まだ custom `/mcp` transport は生きているので、
   compliance claim は一切してはいけない
5. 次の主作業は Patch 2:
   - lifecycle scaffold
   - Streamable HTTP scaffold

特に注意:
- `server.py` から helper を全部一気に消すと auxiliary HTTP routes が壊れやすい
- Patch 2 では「authority を移す」ことが主目的で、
  full transport rewrite を一気にやろうとしない方が安全