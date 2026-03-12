Patch 2 の続きとして、`server.py` に残っていた resource response building と database health/bootstrap 周りの責務をさらに外出ししました。今回のセッションでは、前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler 実装 / server response builder / server factory wiring の分離を土台にして、resource response builder と database health helper の抽出まで進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/database_health.py` を新設
- `ctxledger/src/ctxledger/runtime/server_responses.py` を拡張
- `ctxledger/src/ctxledger/server.py` を更新して、resource response building と database health helper を新 helper module 経由に変更
- 既存の `runtime/http_handlers.py` / `runtime/http_runtime.py` / `runtime/orchestration.py` / `runtime/composite.py` / `runtime/introspection.py` / `runtime/server_factory.py` と連携する形で責務分離を拡張
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/database_health.py`
今回の中心のひとつです。`server.py` に残っていた DB health checker 実装と builder を外出しするため、専用 helper module を追加しました。

追加したもの:
- `DatabaseHealthChecker`
- `ServerBootstrapError`
- `DefaultDatabaseHealthChecker`
- `PostgresDatabaseHealthChecker`
- `build_database_health_checker(...)`

ポイント:
- database URL 未設定時の lightweight placeholder health checker を `server.py` から分離しました
- PostgreSQL 用 connect timeout の query parsing を分離しました
- psycopg 利用可否に応じた checker 選択ロジックを helper 化しました
- `ping()` / `schema_ready()` の既存挙動は維持しています
- builder を外出ししたことで、`server.py` は DB health checker の利用側へさらに寄っています

注意:
- `ServerBootstrapError` は helper module 側にも同名で存在します
- 現状 `server.py` 側の `ServerBootstrapError` と完全統一したわけではなく、DB health helper 内部で閉じる形です
- ただし、今回の整理の目的は責務分離であり、公開 API shape には影響を出していません

## 2. `ctxledger/src/ctxledger/runtime/server_responses.py`
前回追加した response helper を今回さらに拡張し、resource response building もここへ寄せました。

今回追加・拡張したもの:
- `build_workspace_resume_resource_response(...)`
- `build_workflow_detail_resource_response(...)`

すでに入っていたもの:
- `build_workflow_resume_response(...)`
- `build_closed_projection_failures_response(...)`
- `build_projection_failures_ignore_response(...)`
- `build_projection_failures_resolve_response(...)`
- `build_runtime_introspection_response(...)`
- `build_runtime_routes_response(...)`
- `build_runtime_tools_response(...)`

ポイント:
- workspace resume resource response の本体を `server.py` から分離しました
- workflow detail resource response の本体も分離しました
- repository/UoW を持つ実サービス系と fake service 系の両方を考慮した分岐は維持しています
- resource not found / invalid_request / server_not_ready の response shape を維持しています
- `server.py` 側 canonical response class はそのまま使うため、必要な class は helper 側で function 内 import しています

注意:
- helper module は依然として `server.py` の canonical response classes と serializer に依存しています
- ただし、resource response building の実装本体が `server.py` から外れたことで、かなり見通しはよくなりました

## 3. `ctxledger/src/ctxledger/server.py`
今回の中心変更のもうひとつです。`server.py` はさらに薄くなりました。

変更したこと:
- `DefaultDatabaseHealthChecker` の実装本体を削除し、`runtime/database_health.py` から import する形に変更
- `PostgresDatabaseHealthChecker` の実装本体を削除し、`runtime/database_health.py` から import する形に変更
- `build_database_health_checker(...)` の実装本体を削除し、helper module から import する形に変更
- `CtxLedgerServer.build_workspace_resume_resource_response(...)` を wrapper 化
- `CtxLedgerServer.build_workflow_detail_resource_response(...)` を wrapper 化

結果として `server.py` に残る中心責務:
- application-facing server surface
- health / readiness
- runtime dispatch surface
- resource handler registration surface
- public compatibility wrapper 群
- canonical response / protocol dataclass 定義
- serializer 群
- server lifecycle surface

外れたもの:
- DB health checker 実装本体
- DB health checker builder 実装本体
- workspace/workflow resource response building の実装本体

互換性面の配慮:
- 既存 test / import surface を壊さないように、`server.py` 側に public wrapper を残しています
- `CtxLedgerServer` の public method 名は維持しています
- exported class/function 名も極力維持しています
- helper 実装の抽出であって、外部から見える API shape は変えていません

## 4. `ctxledger/src/ctxledger/runtime/server_factory.py`
この session では大きなロジック変更はありませんが、前回外出しした server construction helper として引き続き使われています。

維持しているもの:
- `build_workflow_service_factory(...)`
- `create_server(...)`

ポイント:
- workflow service factory の生成
- `CtxLedgerServer` の生成
- runtime injection
の wiring helper としての役割は維持しています

## 5. `ctxledger/src/ctxledger/runtime/http_handlers.py`
この session では大きな変更はありません。

維持しているもの:
- auth helper
- HTTP path/query parsing helper
- debug HTTP handlers
- workflow/projection failure HTTP handlers
- `build_mcp_http_handler(...)`

ポイント:
- request validation / auth / dispatch 寄りの責務へ整理された状態を維持しています

## 6. `ctxledger/src/ctxledger/runtime/http_runtime.py`
この session でも大きな変更はありません。

維持しているもの:
- `build_http_runtime_adapter(...)`

ポイント:
- route registration wiring はここ
- handler 実装本体は `runtime/http_handlers.py`
- response building は `runtime/server_responses.py`
- runtime selection / CLI entrypoint orchestration は `runtime/orchestration.py`
- server construction wiring は `runtime/server_factory.py`
という分割を維持しています

## 7. `ctxledger/src/ctxledger/runtime/orchestration.py`
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

## 8. `ctxledger/src/ctxledger/runtime/composite.py`
この session では変更はありません。

維持しているもの:
- `ServerRuntime`
- `CompositeRuntimeAdapter`

ポイント:
- 複数 transport runtime を束ねる canonical lifecycle 実装として引き続きここにあります

## 9. `ctxledger/src/ctxledger/runtime/introspection.py`
この session でも大きな変更はありません。

維持しているもの:
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- stdio / http / composite を横断して正規化する役割は引き続きここです

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
- resource response の既存 shape
- DB health checker 選択ロジックの既存 shape

今回新しく進んだこと:
- resource response building の authority を `runtime/server_responses.py` にさらに分離
- DB health checker 実装と builder の authority を `runtime/database_health.py` に分離
- `server.py` は application-facing surface と compatibility wrapper にさらに寄った
- transport/helper 群の責務分割が
  - introspection
  - orchestration
  - composite lifecycle
  - HTTP runtime builder
  - HTTP handler implementation
  - server response building
  - server construction wiring
  - database health/bootstrap
  の単位で見えやすくなった

まだ残っているもの:
- `server.py` は still application-facing server surface の中心
- helper module は `server.py` の canonical response classes / serializers に依存している
- `ServerBootstrapError` の canonicalization はまだ不十分
- readiness / health surface と DB/bootstrap helper 境界の最終整理は未完
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
- `runtime/database_health.py` と resource response 抽出後も **180 passed** を維持しています
- public compatibility を保つために wrapper 化を継続しています
- 最終状態は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract resource response builders`
- `Split database health helpers from server`

## 注意
- この session では `last_session.md` 更新まで実施していますが、git commit は未実施です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は resource response / database health extraction が中心で、full transport rewrite ではありません

## 実装の評価
今回の抽出は、前回の server response / factory extraction の自然な続きとして良い前進です。

進んだこと:
- `server.py` から workspace/workflow resource response building の実装本体を外出しできた
- `server.py` から DB health checker 実装本体も外出しできた
- runtime helper 群の責務分割がさらに見やすくなった
- 将来 `server.py` を
  - health/readiness public surface
  - workflow-facing public surface
  - compatibility export surface
  - canonical type definitions
  にさらに寄せやすくなった
- 既存 test expectation を保ったまま、小さく安全に前進できた

まだ未着手に近いこと:
- `ServerBootstrapError` の canonicalization
- helper module から `server.py` canonical class への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `ServerBootstrapError` の canonical 化を進める
2. helper module が `server.py` canonical class に依存している箇所をさらに整理する
3. readiness / health / DB/bootstrap boundary を整理する
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- `ServerBootstrapError` と DB/bootstrap helper の整理
- helper module と `server.py` 間の canonical type dependency の整理
- readiness / health surface の整理

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
13. server response builder extraction が入っている
14. server factory wiring extraction が入っている
15. 今回、resource response builder extraction が入った
16. 今回、database health helper extraction が入った
17. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
18. `docs/specification.md` は引き続き触らない
19. まだ compliance claim はしない
20. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server response building の canonical module
- `runtime/server_factory.py` は server construction wiring の canonical module
- `runtime/database_health.py` は DB health helper の canonical module
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
- database health helper
- resource response building

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- canonical response / protocol dataclass 定義
- serializer 群
- `ServerBootstrapError` の canonical 定義
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **error canonicalization と helper dependency boundary の整理** が一番きれいです。

たとえば:
- `ServerBootstrapError`
- database health helper 側の error 型
- helper module から `server.py` canonical class への依存

を dedicated core/helper boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical type definitions

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。