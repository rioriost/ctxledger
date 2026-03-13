stdio removal patch 1C の続きとして、今回は **remaining stdio implementation cleanup を進め、dead source と lingering references をさらに削減** しました。patch 1A の HTTP-only config/orchestration、patch 1B の server/module/CLI cleanup を前提に、今回は **legacy stdio module 本体の削除と、それに追随する test/reference cleanup** を行っています。

このセッションで実際に進んだこと:

- `ctxledger/src/ctxledger/mcp/stdio.py` を削除
- `ctxledger/tests/test_postgres_integration.py` から `CTXLEDGER_ENABLE_STDIO` を削除
- `ctxledger/tests/test_server.py` に残っていた stdio introspection example を削除
- `pytest -q tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py tests/test_postgres_integration.py`
- **183 passed**

## 1. 進んだ変更: `ctxledger/src/ctxledger/mcp/stdio.py`
今回の中心です。legacy stdio implementation module を source tree から削除しました。

削除したもの:
- `StdioTransportIntrospection`
- `StdioRuntimeAdapter`
- `StdioRpcServer`
- `dispatch_mcp_tool(...)`
- `dispatch_mcp_resource(...)`
- `build_stdio_runtime_adapter(...)`
- `build_stdio_runtime(...)`
- `find_stdio_runtime(...)`
- `run_stdio_runtime_if_present(...)`

新しい考え方:
- stdio transport はもはや runtime surface / public surface / tested surface のいずれでも前提にしない
- HTTP-only migration は “facade から消した” 段階を超えて、**concrete implementation source の削除** に入った
- MCP RPC は HTTP runtime 側だけで成立させる

ポイント:
- patch 1B 時点では “legacy implementation として残っていた stdio module” を今回正式に removal 側へ進めた
- source tree 上の stdio runtime path が一段階さらに整理された
- これで stdio responsibility split の成果物は役目を終えたと見てよい

## 2. 進んだ変更: `ctxledger/tests/test_postgres_integration.py`
integration test 側に残っていた stdio env reference を整理しました。

変更したこと:
- `test_postgres_settings_can_build_uow_factory_from_loaded_settings(...)` の env から
  - `CTXLEDGER_ENABLE_STDIO`
  を削除

新しい考え方:
- loaded settings を構成する minimum env は HTTP-only semantics に合わせる
- integration test でも stdio enablement flag は不要

ポイント:
- patch 1A の config model 変更が integration test にも浸透
- “まだ stdio env を握っている箇所” を一つ潰せた

## 3. 進んだ変更: `ctxledger/tests/test_server.py`
server tests に残っていた stdio example payload も整理しました。

変更したこと:
- `test_serialize_runtime_introspection_collection_returns_json_ready_payloads()` から
  - `transport="stdio"` の introspection example
  - 対応する serialized expectation
  を削除

新しい考え方:
- serializer test も HTTP-only baseline に寄せる
- introspection collection の example は “HTTP + stdio の混在例” である必要がもうない

ポイント:
- stdio が “実装は消したが example だけ残る” 状態を避けた
- test fixtures / examples からも stdio を徐々に消していく流れが維持できている

## 4. テスト結果
このセッションで確認できた green は次の通りです。

- `pytest -q tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py tests/test_postgres_integration.py`
- **183 passed**

前セッションまでの確認済み green:
- `tests/test_config.py`
- **21 passed**

したがって現時点の確認済み基準は:

- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`

で、
- **204 passed**
として扱ってよいです。

## 5. いまの状態の評価
今の状態は次のように整理できます。

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
- `tests/test_postgres_integration.py`

### この patch で新たに進んだこと
- legacy stdio source module を削除
- integration test に残っていた stdio env reference を削除
- serializer/server test に残っていた stdio example を削除

### まだ確認したいもの
- 他の source/test/doc に `stdio` 文字列や historical comments が残っていないか
- dead imports / stale comments / stale names の最終 sweep
- 必要なら project-wide grep による residual stdio reference の最終確認
- project-wide test baseline の再確認

## 6. canonical ownership の再確認
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
- stdio は canonical ownership を持つ active subsystem ではなくなった
- MCP transport ownership は実質的に HTTP runtime 側へ一本化された

## 7. このセッションでの結論
今回の結論は次の通りです。

- **stdio removal patch 1C は前進した**
- legacy stdio module 本体を削除した
- server/config/integration test 側の lingering stdio references も追加で整理した
- 新しい確認済み green 基準は **204 passed**
- stdio removal は source/test 両面でかなり終盤に入っている

## 8. 次にやること
次の自然な一手は **stdio removal patch 1D** です。

### patch 1D 候補
1. source 全体で residual `stdio` references を最終探索
2. historical comments / docstrings / stale helper names の cleanup
3. 必要なら `README` や user-facing docs の transport wording を HTTP-only に更新
4. project-wide test run を回して最終 baseline を確定
5. removal 完了後の transport architecture を `last_session.md` に再整理

## 9. 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. patch 1A として config/orchestration の HTTP-only 化は入っている
5. patch 1B として server/module/CLI test cleanup と facade/runtime surface cleanup は入っている
6. **今回 patch 1C として `src/ctxledger/mcp/stdio.py` の削除が入った**
7. `server.py` は stdio public surface を export しない
8. `runtime/status.py` は stdio readiness metadata を持たない
9. `runtime/http_runtime.py` は stdio builder に依存しない
10. `tests/test_postgres_integration.py` から `CTXLEDGER_ENABLE_STDIO` は削除済み
11. `tests/test_server.py` の stdio introspection example は削除済み
12. `tests/test_config.py` は **21 passed**
13. `tests/test_server.py` / `tests/test_mcp_modules.py` / `tests/test_cli.py` / `tests/test_postgres_integration.py` は **183 passed**
14. 現時点の確認済み合計は **204 passed**
15. `docs/specification.md` は引き続き触っていない
16. まだ compliance claim はしない
17. 次は residual references / docs / project-wide verification を進めるのが自然

## 10. コミット
このセッションのコミット候補メッセージ例:
- `Remove legacy stdio module`
- `Advance stdio removal patch 1C`
- `Delete unused stdio runtime implementation`
