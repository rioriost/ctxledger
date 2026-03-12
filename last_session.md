Patch 2 の続きとして、今回は **health/readiness helper extraction** を進め、`server.py` に残っていた status surface の一部 ownership をさらに分離しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup を土台にして、**server facade boundary と readiness/health ownership の整理** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/status.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して `health()` / `readiness()` が shared status helper を使う形に変更
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/status.py`
今回の中心です。`server.py` に残っていた health/readiness の組み立てロジックを専用 helper module に抽出しました。

追加したもの:
- `build_health_status(server)`
- `build_readiness_status(server)`

ポイント:
- runtime introspection の収集
- status payload の組み立て
- DB reachability / schema readiness の判定
- `not_started`
- `database_unavailable`
- `schema_check_failed`
- `schema_not_ready`
- `ready`

といった readiness branching を `server.py` から切り出せました
- health/readiness の canonical helper が `runtime/status.py` に寄りました
- `server.py` は application-facing status surface を持ちつつ、実体ロジックの所有を少し減らせました

## 2. `ctxledger/src/ctxledger/server.py`
`server.py` 側では `health()` / `readiness()` の実装を thin wrapper に寄せました。

変更したこと:
- `health()` が `build_health_status(self)` を返す形に変更
- `readiness()` が `build_readiness_status(self)` を返す形に変更
- in-method にあった details 組み立てと DB/schema branching を削除

維持しているもの:
- `CtxLedgerServer.health()`
- `CtxLedgerServer.readiness()`
- `HealthStatus`
- `ReadinessStatus`
- 既存 details payload shape
- 既存 readiness status names
- 既存 health status shape

ポイント:
- public surface は変えずに ownership だけを外へ寄せられました
- `server.py` は facade / compatibility shell にさらに寄っています
- health/readiness public behavior は維持しています

## 挙動面での現状
今回の変更も extraction / canonicalization 中心で、機能追加ではなく責務整理を優先しています。

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
- CLI resume-workflow JSON output shape
- memory tool response shape
- bootstrap failure / startup failure の既存 shape
- health status payload shape
- readiness status payload shape

今回新しく進んだこと:
- health/readiness helper の canonical source を `runtime/status.py` に分離
- `server.py` の status surface が helper delegate に寄った
- `server.py` の facade 化をさらに少し進められた
- readiness / health ownership の整理を一歩進められた

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- helper module は一部 `server.py` の wrapper / adapter class に依存している
- canonical protocol/dataclass/serializer/helper 配置の最終最適化はまだ途中
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
- 今回の変更後、focused regression は green です
- health/readiness extraction 中心の変更で、behavioral regression は見えていません

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract health and readiness status helpers`
- `Move server status logic into runtime helpers`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は health/readiness helper extraction が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理は小さめですが、`server.py` の責務を減らすうえで意味があります。

進んだこと:
- health/readiness の組み立てロジックを `runtime/status.py` に寄せられた
- `server.py` が status helper の所有者である必要がさらに薄れた
- public import / method surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- helper module から `server.py` adapter/wrapper への依存整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `server.py` に残る adapter/wrapper ownership をさらに整理する
2. canonical protocol/dataclass/serializer/helper の配置をさらに見直す
3. stdio removal path を意識して transport-specific code をさらに隔離する
4. `server.py` を application-facing server surface と compatibility shell により近づける
5. runtime introspection / transport detection contract をさらに整える

特に安全そうなのは:
- server facade boundary の整理
- adapter/wrapper dependency の整理
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
17. shared bootstrap error canonicalization が入っている
18. shared runtime types extraction が入っている
19. shared runtime serializers extraction が入っている
20. HTTP runtime wrapper dependency cleanup が入っている
21. HTTP validation helper dependency cleanup が入っている
22. shared runtime protocols extraction が入っている
23. concrete HTTP adapter dependency cleanup が入っている
24. stdio introspection concrete dependency cleanup が入っている
25. 今回、health/readiness helper extraction が入った
26. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
27. `docs/specification.md` は引き続き触らない
28. まだ compliance claim はしない
29. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction の本体は外へ出始めた
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
- `runtime/types.py` は shared response/status dataclass の canonical module
- `runtime/serializers.py` は shared serializer の canonical module
- `runtime/protocols.py` は shared runtime helper protocol の canonical module
- `runtime/status.py` は health/readiness helper の canonical module
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
- shared runtime response/status dataclasses
- shared runtime serializers
- HTTP runtime registration wiring cleanup
- HTTP validation helper dependency cleanup
- shared runtime helper protocols
- concrete HTTP adapter dependency cleanup
- stdio introspection concrete dependency cleanup
- health/readiness status helpers

### まだ `server.py` に残るもの
- application-facing server surface 全般
- public compatibility wrapper 群
- adapter/wrapper ownership の最終整理

## 次に自然な一手
ここまで来たので、次は **server facade boundary と adapter ownership の整理** が一番きれいです。

たとえば:
- `server.py` に残る adapter/wrapper ownership
- top-level public facade と internal helper boundary
- transport helper と application-facing surface の分離
- final dependency cleanup の下準備

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。