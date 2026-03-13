stdio removal patch 1B の続きとして、今回は **server/module test cleanup を HTTP-only semantics に合わせて完了** させ、patch 1A で止まっていた import/runtime surface の不整合を解消しました。前回の `config.py` / `runtime/orchestration.py` の HTTP-only 化を前提に、今回は **server facade / runtime status / HTTP runtime registration / CLI parser / MCP module tests / server tests** をまとめて追従させています。

このセッションで実際に進んだこと:

- `ctxledger/src/ctxledger/server.py` から stdio-related import/export surface を削除
- `ctxledger/src/ctxledger/runtime/status.py` を HTTP-only readiness metadata に更新
- `ctxledger/src/ctxledger/runtime/http_runtime.py` の MCP wiring を stdio builder 非依存に変更
- `ctxledger/src/ctxledger/__init__.py` の CLI transport choices を HTTP-only に変更
- `ctxledger/tests/test_mcp_modules.py` を HTTP-only semantics に更新
- `ctxledger/tests/test_server.py` の stdio/both 前提を削除し HTTP-only expectation に更新
- `pytest -q tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py`
- **167 passed**

## 1. 進んだ変更: `ctxledger/src/ctxledger/server.py`
patch 1A のブロッカーだった facade surface の不整合を解消しました。

変更したこと:
- `server.py` から以下の stdio-related import を削除
  - `StdioRpcServer`
  - `StdioRuntimeAdapter`
  - `dispatch_mcp_resource`
  - `dispatch_mcp_tool`
- `runtime.orchestration` からの
  - `build_stdio_runtime_adapter`
  import/export を削除
- `__all__` から stdio public surface を削除
- startup logging から `stdio_enabled` を削除
- `HttpRuntimeAdapter` に HTTP-only MCP RPC surface を追加
  - `registered_tools()`
  - `tool_schema()`
  - `dispatch_tool()`
- `build_http_runtime_adapter(server)` で runtime に `server` 参照を持たせるようにして、HTTP 経由の MCP tool dispatch を成立させた

新しい考え方:
- facade は stdio symbol を public API として持たない
- MCP over HTTP で必要な tool listing / tool dispatch は `HttpRuntimeAdapter` が直接担う
- つまり `mcp_rpc` は stdio adapter に依存せず、HTTP runtime 自身で成立する

ポイント:
- patch 1A で生じた import error を根本から解消
- `server.py` は HTTP-only semantics にかなり寄った
- ただし file 名や一部 docstring に “stdio adapters” 的な文言は残っている可能性があるので、最終 cleanup 余地は少しある

## 2. 進んだ変更: `ctxledger/src/ctxledger/runtime/status.py`
status helper 側にも stdio removal を反映しました。

変更したこと:
- readiness details から `stdio_enabled` を削除

新しい考え方:
- readiness/health payload は HTTP-only runtime metadata を返す
- transport readiness の補助情報は `http_enabled` と runtime introspection で十分

ポイント:
- `AppSettings.stdio` 削除後に残っていた参照を除去
- patch 1A 後の `AttributeError` をここで解消

## 3. 進んだ変更: `ctxledger/src/ctxledger/runtime/http_runtime.py`
HTTP runtime registration wiring の stdio 依存も除去しました。

変更したこと:
- `register_http_runtime_handlers(...)` から
  - `build_stdio_runtime_adapter`
  への依存を削除
- `mcp_runtime = runtime` に変更して、HTTP handler registration が HTTP runtime 自身を MCP runtime として扱うように整理

新しい考え方:
- MCP HTTP endpoint は stdio runtime を shadow adapter として使わない
- HTTP runtime 自身が `registered_tools()` / `tool_schema()` / `dispatch_tool()` を持つことで完結する

ポイント:
- これで HTTP registration wiring は stdio removal 後も self-contained
- `http_runtime.py` の canonical role がより明確になった

## 4. 進んだ変更: `ctxledger/src/ctxledger/__init__.py`
CLI surface も HTTP-only に追従させました。

変更したこと:
- `serve --transport` の choices を
  - `("http", "stdio")`
  から
  - `("http",)`
  に変更

新しい考え方:
- CLI 上も stdio transport は指定不可
- config/runtime semantics と CLI parser を一致させる

ポイント:
- patch 1A で config が HTTP-only なのに CLI が stdio を許していたズレを解消
- `tests/test_cli.py` との整合も保ちやすくなった

## 5. 進んだ変更: `ctxledger/tests/test_mcp_modules.py`
module-level MCP tests も stdio concrete dependency を外しました。

変更したこと:
- `StdioSettings` import を削除
- `StdioRuntimeAdapter` import を削除
- `make_settings()` を HTTP-only shape に更新
  - `transport=TransportMode.HTTP`
  - `http_enabled=True`
  - `stdio` field なし
- lifecycle tests 用に軽量 runtime stub を使う形へ変更
- `FakeRpcRuntime.tool_schema()` は `DEFAULT_EMPTY_MCP_TOOL_SCHEMA` を返すように更新

新しい考え方:
- lifecycle / RPC module tests は stdio concrete adapter を直接必要としない
- 必要なのは “registered_tools / registered_resources / tool_schema / dispatch_* を持つ runtime protocol” だけ

ポイント:
- concrete stdio adapter dependency cleanup が test 側にも浸透した
- `test_mcp_modules.py` は HTTP-only migration に追随済み

## 6. 進んだ変更: `ctxledger/tests/test_server.py`
今回の主作業です。stdio/both 前提を server test から実質的に外しました。

変更したこと:
- import から
  - `dispatch_mcp_resource`
  - `dispatch_mcp_tool`
  を削除
- startup log expectation から `stdio_enabled` を削除
- debug tools tests を HTTP-only expectation に更新
  - `runtime_tools` payload は `{ "tools": [] }`
- composite runtime / `TransportMode.BOTH` / `stdio_enabled=True` 前提のケースを HTTP-only に置換
- runtime summary expectation から stdio runtime 部分を削除
- `"stdio_transport=enabled"` の expectation を削除

新しい考え方:
- server tests の green 基準は HTTP runtime introspection のみ
- debug tools endpoint は stdio tool inventory を返さず、HTTP runtime tool surface だけを見る
- summary は HTTP runtime introspection と MCP endpoint を出せばよい

ポイント:
- patch 1B の中心だった “server/module test cleanup” を完了
- stdio/both transport 前提が test green 条件から外れた
- 旧来の composite runtime introspection expectation はここで卒業

## 7. テスト結果
このセッションで確認できた green は次の通りです。

- `pytest -q tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py`
- **167 passed**

前セッションの green:
- `tests/test_config.py`
- **21 passed**

したがって現時点の確認済み基準は:
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`

で、
- **188 passed**
として扱ってよいです。

## 8. いまの状態の評価
今の状態はこう整理できます。

### すでに整合しているもの
- `src/ctxledger/config.py`
- `src/ctxledger/runtime/orchestration.py`
- `src/ctxledger/server.py`
- `src/ctxledger/runtime/status.py`
- `src/ctxledger/runtime/http_runtime.py`
- `src/ctxledger/__init__.py`
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`

### この patch で解消したブロッカー
- `server.py` が `build_stdio_runtime_adapter` を import/export していた問題
- readiness/status が `settings.stdio` を参照していた問題
- HTTP runtime registration が stdio builder に依存していた問題
- test collection 時点の import error
- server/module tests の stdio/both transport 依存

### まだ removal 対象として残っていそうなもの
- `src/ctxledger/mcp/stdio.py` 自体
- そこに残る `StdioRuntimeAdapter` / `StdioRpcServer` / stdio dispatch helpers
- stdio extraction patch 群で残している source files / dead code
- PostgreSQL integration test など、まだ `CTXLEDGER_ENABLE_STDIO` を握っている箇所
- 他に `TransportMode.STDIO` / `TransportMode.BOTH` / `stdio` env を前提にする未探索テスト群

## 9. canonical ownership の再確認
このセッション後も canonical ownership は次の理解でよいです。

- bootstrap error: `runtime/errors.py`
- response/status dataclasses: `runtime/types.py`
- serializers: `runtime/serializers.py`
- shared helper protocols: `runtime/protocols.py`
- health/readiness helper: `runtime/status.py`
- HTTP handler implementation: `runtime/http_handlers.py`
- HTTP runtime registration wiring: `runtime/http_runtime.py`
- response/resource response implementation: `runtime/server_responses.py`
- server construction wiring: `runtime/server_factory.py`
- DB health helper: `runtime/database_health.py`
- runtime introspection normalization: `runtime/introspection.py`
- transport/runtime selection orchestration: `runtime/orchestration.py`

追加の含意:
- `server.py` は facade と HTTP runtime concrete surface を持つが、stdio public facade ではもうない
- stdio concrete implementation が残っていても、canonical public surface からはかなり外れた

## 10. このセッションでの結論
今回の結論は次の通りです。

- **stdio removal patch 1B は実質完了**
- patch 1A で止まっていた import/runtime surface mismatch は解消
- server/module/CLI tests は HTTP-only semantics に追随
- 新しい green 基準が作れた
- stdio は今後、**public/tested surface cleanup 済みの legacy implementation** として removal を進められる状態に入った

## 11. 次にやること
次の自然な一手は **stdio removal patch 1C** です。

### patch 1C 候補
1. `src/ctxledger/mcp/stdio.py` の usage を全探索
2. もはや public/runtime path から使われていない stdio implementation を削除
   - `StdioRuntimeAdapter`
   - `StdioRpcServer`
   - stdio dispatch helpers
   - stdio runtime build/find helpers
3. まだ残る `CTXLEDGER_ENABLE_STDIO` / stdio env / stdio transport references を integration tests 含めて除去
4. 必要なら dead imports / stale comments / docstrings cleanup
5. project-wide test baseline を再確定

## 12. 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. `mcp/stdio.py` への stdio responsibility split は残っているが removal 対象
5. stdio builder/runtime bootstrap/runtime construction split も残っているが removal 対象
6. runtime introspection / orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / serializers / protocols / validation cleanup 群は入っている
7. patch 1A として config/orchestration の HTTP-only 化は入っている
8. **今回 patch 1B として server/module/CLI test cleanup と facade/runtime surface cleanup が入った**
9. `server.py` は stdio public surface をもう export しない
10. `runtime/status.py` は stdio readiness metadata をもう持たない
11. `runtime/http_runtime.py` は stdio builder に依存しない
12. `tests/test_config.py` は **21 passed**
13. `tests/test_server.py` / `tests/test_mcp_modules.py` / `tests/test_cli.py` は **167 passed**
14. 現時点の確認済み合計は **188 passed**
15. `docs/specification.md` は引き続き触っていない
16. まだ compliance claim はしない
17. 最終的には stdio source 自体も削除前提で進める

## 13. コミット
このセッションのコミット候補メッセージ例:
- `Finish HTTP-only server and MCP test cleanup`
- `Complete stdio removal patch 1B`
- `Remove stdio server facade surface`
