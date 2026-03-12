Patch 2 の続きとして、`server.py` に残っていた bootstrap error の扱いをさらに整理しました。今回のセッションでは、前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler 実装 / server response builder / server factory wiring / resource response builder / database health helper の分離を土台にして、`ServerBootstrapError` の canonicalization を進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/errors.py` を新設
- `ctxledger/src/ctxledger/runtime/database_health.py` を更新して shared bootstrap error を使う形に変更
- `ctxledger/src/ctxledger/runtime/server_responses.py` を更新して shared bootstrap error を使う形に変更
- `ctxledger/src/ctxledger/runtime/orchestration.py` を更新して shared bootstrap error を使う形に変更
- `ctxledger/src/ctxledger/server.py` を更新して shared bootstrap error を canonical import として使う形に変更
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/errors.py`
今回の中心です。bootstrap 時の共有 error を `server.py` から分離するため、専用 helper module を追加しました。

追加したもの:
- `ServerBootstrapError`

ポイント:
- startup-time の設定不足
- bootstrap dependency 不足
- runtime 初期化不能
のような「サーバ起動を clean に止めるべき失敗」を表す shared error として切り出しました
- これにより、`server.py` だけが bootstrap error の定義元である必要がなくなりました
- helper module 同士が `server.py` 経由で error 型を参照する必要を減らしています

## 2. `ctxledger/src/ctxledger/runtime/database_health.py`
前回外出しした DB health helper を、shared bootstrap error を使う形へ変更しました。

変更したこと:
- local な `ServerBootstrapError` 定義を削除
- `runtime/errors.py` の `ServerBootstrapError` を使う形に変更

維持しているもの:
- `DatabaseHealthChecker`
- `DefaultDatabaseHealthChecker`
- `PostgresDatabaseHealthChecker`
- `build_database_health_checker(...)`

ポイント:
- `database_url is not configured`
- `psycopg` 未導入時の bootstrap failure
などの例外は shared error に統一されました
- DB health helper 自体の public shape は維持しています
- `server.py` から見ても、DB bootstrap failure が共通の error 型として扱いやすくなりました

## 3. `ctxledger/src/ctxledger/runtime/server_responses.py`
response helper でも shared bootstrap error を使う形へ変更しました。

変更したこと:
- `build_workflow_resume_response(...)` が shared bootstrap error を catch する形に変更
- `build_closed_projection_failures_response(...)` も同様に変更

ポイント:
- `server.get_workflow_resume(...)` が bootstrap failure を raise したときの扱いを
  `server.py` canonical class 依存から少し外せました
- workflow resume / closed projection failures history の `server_not_ready` response shape は維持しています
- helper module 側の error dependency がより明確になりました

## 4. `ctxledger/src/ctxledger/runtime/orchestration.py`
run entrypoint 側でも shared bootstrap error を使うように変更しました。

変更したこと:
- `run_server(...)` が `runtime/errors.py` 経由の `ServerBootstrapError` を catch する形に変更

ポイント:
- CLI entrypoint / bootstrap orchestration で扱う startup failure の canonical source が `runtime/errors.py` に寄りました
- `Startup failed: ...` の stderr 出力契約は維持しています
- orchestration helper が `server.py` の error 定義へ依存しない方向に一歩進みました

## 5. `ctxledger/src/ctxledger/server.py`
今回のもうひとつの中心変更です。`server.py` では shared bootstrap error を canonical import として使うように変更しました。

変更したこと:
- in-file `ServerBootstrapError` class 定義を削除
- `runtime/errors.py` から `ServerBootstrapError` を import する形に変更
- `CtxLedgerServer.get_workflow_resume(...)`
- `CtxLedgerServer.startup(...)`
などは shared error を raise する形になりました

ポイント:
- bootstrap error の定義責務を `server.py` から外せました
- `server.py` は error の canonical source ではなく、利用側に寄っています
- 既存 export surface は維持しており、`ctxledger.server.ServerBootstrapError` を import していた利用側は引き続き動く前提です

## 挙動面での現状
今回の変更も extraction / canonicalization 中心で、機能追加よりも責務整理を優先しています。

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
- bootstrap failure 時の stderr message shape

今回新しく進んだこと:
- bootstrap error の authority を `runtime/errors.py` に分離
- DB health helper / response helper / orchestration helper / server surface が shared error を使う形に寄せた
- helper module 同士が `server.py` の error 定義へ依存する必要を減らした
- `server.py` は application-facing surface と compatibility wrapper にさらに寄った

まだ残っているもの:
- helper module は `server.py` の canonical response classes / serializers にまだ依存している
- readiness / health / DB/bootstrap helper 境界の最終整理は未完
- canonical type definitions 全体の配置最適化はまだ途中
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
- 一度 `runtime/database_health.py` が `server.py` から error を import する形にしてしまい、module initialization 時の循環参照で test collection error が出ました
- そのため、shared error を `runtime/errors.py` に置く形へ修正しました
- 最終状態は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Canonicalize bootstrap error handling`
- `Extract shared runtime bootstrap error`

## 注意
- この session では `last_session.md` 更新まで実施していますが、git commit は未実施です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は bootstrap error canonicalization が中心で、full transport rewrite ではありません

## 実装の評価
今回の整理は小さいですが、依存関係をきれいにするうえでかなり意味があります。

進んだこと:
- bootstrap error の canonical source を `runtime/errors.py` に寄せられた
- DB health / response / orchestration / server の各 helper が共通 error を使うようになった
- `server.py` が error 定義の所有者である必要が薄れた
- helper module 間 dependency の見通しが少し良くなった
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- canonical response classes の配置最適化
- helper module から `server.py` canonical class への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. helper module が `server.py` canonical response class に依存している箇所をさらに整理する
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical response / protocol dataclass の配置を見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- helper module と `server.py` 間の canonical type dependency の整理
- readiness / health surface の整理
- bootstrap / response / transport helper の境界整理

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
15. resource response builder extraction が入っている
16. database health helper extraction が入っている
17. 今回、bootstrap error canonicalization step が入った
18. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
19. `docs/specification.md` は引き続き触らない
20. まだ compliance claim はしない
21. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / bootstrap error canonicalization の本体は外へ出始めた
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
- `runtime/errors.py` は shared bootstrap error の canonical module
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
- shared bootstrap error

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- canonical response / protocol dataclass 定義
- serializer 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **canonical type dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- response dataclass 群
- protocol/dataclass 定義の配置
- helper module から `server.py` canonical class への依存

を dedicated core/helper boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。