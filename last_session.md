Patch 2 の続きとして、`server.py` に残っていた server-facing response building と server construction wiring の責務をさらに外出ししました。今回のセッションでは、前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler 実装の分離を土台にして、workflow・projection・runtime response builder と server factory の抽出まで進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/server_responses.py` を新設
- `ctxledger/src/ctxledger/runtime/server_factory.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して、response building と server construction を新 helper module 経由に変更
- 既存の `runtime/http_handlers.py` / `runtime/http_runtime.py` / `runtime/orchestration.py` / `runtime/composite.py` / `runtime/introspection.py` と連携する形で責務分離を拡張
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/server_responses.py`
今回の中心です。`server.py` に残っていた response building のかなりの部分を外出しするため、専用 helper module を追加しました。

追加したもの:
- `build_workflow_resume_response(...)`
- `build_closed_projection_failures_response(...)`
- `build_projection_failures_ignore_response(...)`
- `build_projection_failures_resolve_response(...)`
- `build_runtime_introspection_response(...)`
- `build_runtime_routes_response(...)`
- `build_runtime_tools_response(...)`
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`

ポイント:
- workflow resume の HTTP/resource 向け canonical response building を `server.py` から分離しました
- closed projection failures history の response building を分離しました
- projection failure ignore / resolve の domain error mapping
  - `not_found`
  - `invalid_request`
  - `server_error`
  の整理を helper 化しました
- runtime introspection / routes / tools の debug response building も分離しました
- workspace resume resource / workflow detail resource の resource response building も helper 化しました
- `server.py` 側 canonical response class を壊さないため、必要な response class・serializer は helper 側で function 内 import しています
- introspection collection / serialization については `runtime/introspection.py` の canonical helper をそのまま利用しています

注意:
- helper module 側は `server.py` の canonical response classes や serializer に依存しています
- ただし、response building の実装本体が `server.py` 直下から外れたことで、責務境界はかなり見やすくなりました

## 2. `ctxledger/src/ctxledger/runtime/server_factory.py`
`build_workflow_service_factory(...)` と `create_server(...)` を `server.py` から外出しするため、server construction 用 helper module を追加しました。

追加したもの:
- `build_workflow_service_factory(...)`
- `create_server(...)`

ポイント:
- PostgreSQL UoW factory から `WorkflowService` factory を作る責務を `server.py` から分離しました
- `CtxLedgerServer` の生成と runtime injection の流れを helper module に寄せました
- `create_server(...)` は
  - `server_class`
  - `create_runtime`
  - `build_database_health_checker`
  を受け取る形で、既存 wiring を壊さずに helper 化しています
- これにより、server construction と transport/runtime construction の境界が前回より明確になりました

注意:
- 現状 `create_server(...)` helper は `server_class` と `create_runtime` を外から受け取る形なので、完全に独立した factory というより、wiring helper に近いです
- ただし、この形のほうが循環 import と公開 API 互換を壊しにくく、安全です

## 3. `ctxledger/src/ctxledger/server.py`
今回のもうひとつの中心変更です。`server.py` はさらに薄くなりました。

変更したこと:
- `CtxLedgerServer.build_workflow_resume_response(...)` を wrapper 化
- `CtxLedgerServer.build_closed_projection_failures_response(...)` を wrapper 化
- `CtxLedgerServer.build_projection_failures_ignore_response(...)` を wrapper 化
- `CtxLedgerServer.build_projection_failures_resolve_response(...)` を wrapper 化
- `CtxLedgerServer.build_runtime_introspection_response(...)` を wrapper 化
- `CtxLedgerServer.build_runtime_routes_response(...)` を wrapper 化
- `CtxLedgerServer.build_runtime_tools_response(...)` を wrapper 化
- top-level `build_workflow_service_factory(...)` を wrapper 化
- top-level `create_server(...)` を wrapper 化

今回の結果として `server.py` に残る中心責務:
- application-facing server surface
- health / readiness
- runtime dispatch surface
- resource handler registration surface
- public compatibility wrapper 群
- canonical response / protocol dataclass 定義
- serializer 群
- database health checker 実装

外れたもの:
- workflow/projection response building の実装本体
- runtime introspection debug response building の実装本体
- workflow service factory 実装本体
- server construction wiring の実装本体

互換性面の配慮:
- 既存 test / import surface を壊さないように、`server.py` 側に public wrapper を残しています
- `CtxLedgerServer` の public method 名は維持しています
- top-level helper 名も極力維持しています
- import 名衝突や wrapper 再帰を避けるため、`server.py` 側では extracted helper を alias import しています

## 4. `ctxledger/src/ctxledger/runtime/http_handlers.py`
この session では大きなロジック変更はありませんが、前回外出しした HTTP handler 実装本体の canonical module として引き続き使われています。

維持しているもの:
- auth helper
- HTTP path/query parsing helper
- debug HTTP handlers
- workflow/projection failure HTTP handlers
- `build_mcp_http_handler(...)`

ポイント:
- response building 本体の一部が `runtime/server_responses.py` へ移ったことで、HTTP handler は request validation / auth / dispatch 寄りの責務へ少し寄っています
- helper 群の分割がより明確になっています

## 5. `ctxledger/src/ctxledger/runtime/http_runtime.py`
この session では大きなロジック変更はありません。

維持しているもの:
- `build_http_runtime_adapter(...)`

ポイント:
- route registration wiring はここ
- handler 実装本体は `runtime/http_handlers.py`
- response building は `runtime/server_responses.py`
- runtime selection / CLI entrypoint orchestration は `runtime/orchestration.py`
  という分割がさらに明確になりました

## 6. `ctxledger/src/ctxledger/runtime/orchestration.py`
この session では大きなロジック変更はありません。

維持しているもの:
- `build_stdio_runtime_adapter(...)`
- `create_runtime(...)`
- `apply_overrides(...)`
- `install_signal_handlers(...)`
- `print_runtime_summary(...)`
- `run_server(...)`

ポイント:
- transport selection / run entrypoint orchestration の中心として引き続きここです
- HTTP runtime 作成は `runtime/http_runtime.py`
- server constructionは `runtime/server_factory.py`
- response building は `runtime/server_responses.py`
  という役割分担が前回より明確です

## 7. `ctxledger/src/ctxledger/runtime/composite.py`
この session では変更はありません。

維持しているもの:
- `ServerRuntime`
- `CompositeRuntimeAdapter`

ポイント:
- 複数 transport runtime を束ねる canonical lifecycle 実装として引き続きここにあります

## 8. `ctxledger/src/ctxledger/runtime/introspection.py`
この session でも大きな変更はありません。

維持しているもの:
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- stdio / http / composite を横断して正規化する役割は引き続きここです
- response builder 側も `server.py` ではなくこの canonical helper を使う構造になっています

## 挙動面での現状
今回の変更も extraction 中心で、機能追加よりも責務整理を優先しています。

維持しているもの:
- `initialize` over HTTP
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- `/mcp` path validation
- HTTP auth の挙動
- invalid JSON / invalid object / missing body 時のエラー挙動
- stdio / HTTP いずれも共通の RPC helper を利用する構造
- stdio public behavior と runtime summary の shape
- `create_runtime(settings)` の既存 test expectation
- composite runtime introspection の既存 shape
- HTTP route registration の既存 shape
- debug endpoint の既存 shape
- workflow / projection failure response の既存 shape

今回新しく進んだこと:
- workflow/projection/runtime response building の authority を `runtime/server_responses.py` に分離
- workflow service factory と server construction wiring の authority を `runtime/server_factory.py` に分離
- `server.py` は application-facing surface と compatibility wrapper にさらに寄った
- transport helper 群の責務分割が
  - introspection
  - orchestration
  - composite lifecycle
  - HTTP runtime builder
  - HTTP handler implementation
  - server response building
  - server construction wiring
  の単位で見えやすくなった

まだ残っているもの:
- `server.py` は still application-facing server surface の中心
- helper module は `server.py` の canonical response classes / serializers / health checker に依存している
- workspace/workflow resource response building は `CtxLedgerServer` method 本体ではまだ残る部分がある
- `build_database_health_checker(...)` はまだ `server.py`
- stdio 削除前提の final dependency cleanup は未完
- compliance claim はまだ不可

## テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

実行コマンド:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`

補足:
- `runtime/server_responses.py` と `runtime/server_factory.py` 抽出後も **180 passed** を維持しています
- alias import と wrapper 化で public compatibility を保ちつつ整理しています
- 最終状態は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract server response builders`
- `Split server factory wiring from server module`

## 注意
- この session では `last_session.md` 更新まで実施していますが、git commit は未実施です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は server response / factory extraction が中心で、full transport rewrite ではありません

## 実装の評価
今回の抽出は、前回の HTTP handler extraction の自然な続きとして良い前進です。

進んだこと:
- `server.py` から workflow/projection/runtime response building の実装本体をさらに外出しできた
- `server.py` から workflow service factory / server construction wiring の実装本体も外出しできた
- runtime helper 群の責務分割がかなり見やすくなった
- 将来 `server.py` を
  - health/readiness
  - workflow-facing public surface
  - compatibility export surface
  - canonical type definitions
  にさらに寄せやすくなった
- 既存 test expectation を保ったまま、小さく安全に前進できた

まだ未着手に近いこと:
- `server.py` に残る resource response building の整理
- `build_database_health_checker(...)` / DB health checker 配置の整理
- helper module から `server.py` canonical class への依存整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. workspace/workflow resource response building を `server.py` からさらに外出しする
2. `build_database_health_checker(...)` と DB health checker 群の配置を整理する
3. helper module が `server.py` canonical class に依存している箇所をさらに整理する
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- resource response builder の抽出
- DB health checker / bootstrap wiring の整理
- helper module と `server.py` 間の canonical type dependency の整理

## 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. `mcp/stdio.py` への stdio responsibility split は入っている
5. stdio builder extraction は入っている
6. stdio runtime bootstrap helper split は入っている
7. stdio runtime construction split は入っている
8. runtime introspection helper split も入っている
9. transport orchestration helper split も入っている
10. HTTP runtime builder extraction が入っている
11. composite runtime adapter extraction が入っている
12. HTTP handler implementation extraction が入っている
13. 今回、server response builder extraction が入った
14. 今回、server factory wiring extraction が入った
15. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
16. `docs/specification.md` は引き続き触らない
17. まだ compliance claim はしない
18. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server response building の canonical module
- `runtime/server_factory.py` は server construction wiring の canonical module
- `runtime/composite.py` は composite lifecycle の canonical 実装
- `runtime/orchestration.py` は runtime selection / run entrypoint orchestration の中心
- `runtime/introspection.py` は stdio/http/composite を横断して正規化する責務を持つ
- 既存 green 状態は **180 passed** を基準に見てよい

### すでに外出し済み
- MCP lifecycle helper
- Streamable HTTP scaffold
- MCP RPC helper
- stdio adapter
- stdio RPC server
- stdio dispatch helper
- stdio builder wiring
- stdio runtime bootstrap helper
- stdio runtime construction helper
- runtime introspection helper
- transport override / signal / summary / run entrypoint helper
- composite runtime lifecycle
- HTTP runtime route registration wiring
- HTTP auth helper
- HTTP path/query parsing helper
- HTTP handler implementation
- MCP HTTP bridge implementation
- server response building
- server construction wiring

### まだ `server.py` に残るもの
- resource response building の一部
- database health checker 群
- health/readiness/debug HTTP surface の公開面
- application-facing server surface 全般
- public compatibility wrapper 群
- canonical response / protocol dataclass 定義
- serializer 群

## 次に自然な一手
ここまで来たので、次は **resource response building と DB/bootstrap boundary の整理** が一番きれいです。

たとえば:
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`
- `build_database_health_checker(...)`
- `DefaultDatabaseHealthChecker`
- `PostgresDatabaseHealthChecker`

を dedicated helper / bootstrap module に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical type definitions

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。