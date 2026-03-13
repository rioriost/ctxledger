stdio removal patch 1D の続きとして、今回は **HTTP-only への residual stdio cleanup を source / docs / notes レベルでさらに進めた** セッションとして整理します。patch 1A の config/orchestration HTTP-only 化、patch 1B の server/module/CLI cleanup、patch 1C の legacy stdio module 削除を土台にして、今回は **remaining protocol/introspection wording と transport documentation の最終寄せ** を行いました。

このセッションで実際に進んだこと:

- `src/ctxledger/runtime/protocols.py` から stdio-only protocol type を削除
- `src/ctxledger/runtime/introspection.py` から stdio-specific fallback path を削除
- `src/ctxledger/server.py` の lifecycle docstring を HTTP-only wording に更新
- `README.md` の transport / debug / config / startup examples を HTTP-only に更新
- `docs/CHANGELOG.md` の startup summary wording を HTTP-only に更新
- `docs/architecture.md` の stdio transport assumptions を削除
- `docs/deployment.md` の runtime mode / config / exposure wording を HTTP-only に更新
- `docs/SECURITY.md` の debug exposure wording から stdio references を削除
- `pytest -q tests/test_config.py tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py tests/test_postgres_integration.py`
- **204 passed**

## 1. 進んだ変更: `src/ctxledger/runtime/protocols.py`
protocol layer に残っていた stdio-specific type surface を整理しました。

変更したこと:
- `TYPE_CHECKING` から `StdioTransportIntrospection` import を削除
- `StdioRuntimeAdapterProtocol` を削除
- `__all__` から `StdioRuntimeAdapterProtocol` を削除

新しい考え方:
- runtime protocol surface は HTTP-only の現在仕様に合わせる
- active protocol contract として維持すべきなのは
  - `ServerRuntime`
  - `McpRuntimeProtocol`
  - `HttpRuntimeAdapterProtocol`
  で十分
- stdio removal 後に protocol だけ残して “古い transport shape を暗黙に支持している” 状態を避ける

ポイント:
- source tree に残る stdio “型の残骸” を一段整理できた
- runtime boundary の説明責務がより明確になった

## 2. 進んだ変更: `src/ctxledger/runtime/introspection.py`
introspection helper から stdio-specific fallback を落としました。

変更したこと:
- `_is_stdio_runtime_like(...)` を削除
- `collect_runtime_introspection(...)` から stdio-like runtime 向け fallback path を削除

新しい考え方:
- runtime introspection は generic `introspect()` surface を持つ runtime のみを扱えばよい
- HTTP-only 現状では、明示的な introspection object を返す runtime を辿れば十分
- 削除済み legacy transport を “duck typing でまだ拾う” 必要はもうない

ポイント:
- introspection helper が transport migration 後も古い adapter shape に引きずられなくなった
- helper の責務がより小さくなった

## 3. 進んだ変更: `src/ctxledger/server.py`
server facade に残っていた wording も整理しました。

変更したこと:
- `CtxLedgerServer` docstring の
  - `provide a lifecycle boundary for HTTP/stdio adapters`
  を
  - `provide a lifecycle boundary for the HTTP runtime adapter`
  に更新

新しい考え方:
- docstring も active architecture を表現するべき
- 実装が HTTP-only なのに multi-transport wording を残さない

ポイント:
- 小さい変更ですが、今後の読み手が “stdio adapter がまだ正式にあるのでは？” と誤読しにくくなった

## 4. 進んだ変更: `README.md`
README の user-facing transport narrative をかなり整理しました。

変更したこと:
- architecture summary から “stdio support still exists” 記述を削除
- runtime debug payload examples から stdio blocks を削除
- `/debug/tools` example を HTTP-only expectation に更新
- configuration section から `CTXLEDGER_ENABLE_STDIO` を削除
- local / production env examples から `CTXLEDGER_ENABLE_STDIO=false` を削除
- Docker run example から `CTXLEDGER_ENABLE_STDIO=false` を削除
- startup summary section から `stdio_transport=enabled` 記述を削除

新しい考え方:
- README は現在の canonical operator/developer experience を反映する
- transport docs は HTTP-only を前提に統一
- debug endpoints の説明も HTTP runtime に対応した実 payload を示す

ポイント:
- source だけでなく user-facing primary doc も now-current behavior に揃った
- 初見の利用者が古い stdio option を前提に環境変数や runtime summary を読んで混乱する余地を減らせた

## 5. 進んだ変更: `docs/CHANGELOG.md`
changelog wording も HTTP-only に揃えました。

変更したこと:
- startup stderr summary の追加項目から
  - `stdio transport indicator when stdio is enabled`
  を削除
- 代わりに
  - `MCP endpoint for the HTTP runtime`
  という wording に整理

新しい考え方:
- changelog は historical note であっても current unreleased branch の reality を外しすぎない方がよい
- すでに stdio support が active feature ではないため、その表現を残さない

ポイント:
- “いま何が追加されたのか” を current branch と整合する表現に更新できた

## 6. 進んだ変更: `docs/architecture.md`
architecture doc の transport story を HTTP-only に寄せました。

変更したこと:
- system context から stdio supporting surface の記述を削除
- shared core / separate adapters セクションを HTTP adapter 前提に更新
- “Switching between HTTP and stdio must not alter business semantics” を削除し、
  HTTP transport concerns の wording に変更
- transport layer responsibilities から stdio handling を削除
- typed configuration boundary の `stdio enablement` を削除
- transport/adapter test section の `HTTP/stdio semantic parity` を削除

新しい考え方:
- architecture doc は historical split を語るより、今の architecture を説明すべき
- stdio extraction history は last_session や commit history で追えばよく、現行 architecture doc では active shape を優先する

ポイント:
- conceptual architecture と実装 reality のズレがかなり減った
- reader が “still dual transport” と誤解しにくくなった

## 7. 進んだ変更: `docs/deployment.md`
deployment guide も transport mode を一本化しました。

変更したこと:
- supported runtime modes を HTTP のみに更新
- supporting development runtime mode としての stdio説明を削除
- runtime mode section を HTTP-only へ簡素化
- config/env guidance に残っていた stdio-related行を整理
- debug exposure wording から enabled transports / stdio tools を削除

新しい考え方:
- deployment doc は “実際にどう動かすか” の文書なので、削除前提 transport を載せない
- operator-facing setup examples は current minimal env を示すべき

ポイント:
- deploy path の説明がより一貫した
- config examples から stale transport options を外せた

## 8. 進んだ変更: `docs/SECURITY.md`
security doc の debug surface explanation も HTTP-only に整理しました。

変更したこと:
- `/debug/*` が reveal しうる metadata から
  - `enabled transports`
  - `registered stdio tools`
  を削除

新しい考え方:
- operationally sensitive metadata の説明も current runtime surface に合わせる
- セキュリティ文書に stale transport mention を残すと、不要な attack surface を想像させてしまう

ポイント:
- security guidance が実態に即したものになった
- docs 間の transport narrative が揃ってきた

## 9. テスト結果
このセッションで確認できた green は次の通りです。

- `pytest -q tests/test_config.py tests/test_server.py tests/test_mcp_modules.py tests/test_cli.py tests/test_postgres_integration.py`
- **204 passed**

現時点の確認済み基準はそのまま:
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`
- **204 passed**

## 10. いまの状態の評価
今の状態は次のように整理できます。

### すでに整合しているもの
- `src/ctxledger/config.py`
- `src/ctxledger/runtime/orchestration.py`
- `src/ctxledger/runtime/status.py`
- `src/ctxledger/runtime/http_runtime.py`
- `src/ctxledger/runtime/introspection.py`
- `src/ctxledger/runtime/protocols.py`
- `src/ctxledger/server.py`
- `src/ctxledger/__init__.py`
- `README.md`
- `docs/CHANGELOG.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`

### この patch でさらに解消したもの
- residual stdio protocol type
- stdio-like runtime introspection fallback
- lifecycle/docstring wording の stale transport mention
- primary docs / deployment docs / security docs に残っていた stdio-centric explanation
- env / startup example の stale stdio flag

### まだ最終確認してもよさそうなもの
- 他 docs (`docs/mcp-api.md`, `docs/workflow-model.md`, `docs/memory-model.md`, `docs/design-principles.md`, `docs/roadmap.md` など) に historical stdio wording が残っていないか
- `.env.example` / `.env.production.example` 実ファイル内容の最終確認
- project-wide full test baseline
- 最終 commit 系列の整理

## 11. canonical ownership の再確認
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
- transport architecture は実質的に HTTP-only
- stdio は active subsystem / active protocol surface / active docs surface のどれでもない
- removal work はほぼ “residual mention cleanup と final verification” の段階に入った

## 12. このセッションでの結論
今回の結論は次の通りです。

- **HTTP-only residual stdio cleanup はさらに前進した**
- source-level stale types/helpers と docs-level stale wording の両方を整理した
- current verified baseline は引き続き **204 passed**
- stdio removal はほぼ最終確認フェーズに入っている

## 13. 次にやること
次の自然な一手は **stdio removal patch 1E / final verification sweep** です。

### patch 1E 候補
1. project-wide で residual `stdio` / `CTXLEDGER_ENABLE_STDIO` / `TransportMode.STDIO` / `TransportMode.BOTH` を最終探索
2. `docs/mcp-api.md` など未確認 docs の HTTP-only wording を必要なら更新
3. `.env.example` / `.env.production.example` の実ファイル内容が README examples と一致しているか確認
4. project-wide test run を回して final baseline を確定
5. stdio removal の完了判定メモを `last_session.md` に残す

## 14. 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. patch 1A として config/orchestration の HTTP-only 化は入っている
5. patch 1B として server/module/CLI cleanup は入っている
6. patch 1C として `src/ctxledger/mcp/stdio.py` の削除は入っている
7. **今回 patch 1D として residual stdio protocol/introspection/docs cleanup が入った**
8. `server.py` は stdio public surface を export しない
9. `runtime/status.py` は stdio readiness metadata を持たない
10. `runtime/http_runtime.py` は stdio builder に依存しない
11. `runtime/protocols.py` は stdio adapter protocol を持たない
12. `runtime/introspection.py` は stdio-like fallback を持たない
13. `README.md`, `docs/CHANGELOG.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/SECURITY.md` は HTTP-only wording にかなり寄っている
14. `tests/test_config.py` / `tests/test_server.py` / `tests/test_mcp_modules.py` / `tests/test_cli.py` / `tests/test_postgres_integration.py` は確認済みで **204 passed**
15. `docs/specification.md` は引き続き触っていない
16. まだ compliance claim はしない
17. 次は final residual sweep と project-wide verification が自然

## 15. コミット
このセッションのコミット候補メッセージ例:
- `Clean up residual stdio references`
- `Finish HTTP-only stdio documentation cleanup`
- `Remove remaining stdio protocol and docs mentions`
