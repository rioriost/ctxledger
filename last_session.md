Patch 2 の続きとして、今回は **canonical type dependency と public surface boundary の整理** を進め、`server.py` に残っていた response/status dataclass 群の ownership をさらに分離しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error の抽出を土台にして、**shared runtime types extraction** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/types.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して shared runtime types を re-export する形に変更
- `ctxledger/src/ctxledger/runtime/server_responses.py` を更新して shared runtime types を canonical import として使う形に変更
- `ctxledger/src/ctxledger/runtime/http_handlers.py` を更新して shared runtime types を canonical import として使う形に変更
- `ctxledger/src/ctxledger/runtime/introspection.py` を更新して `ServerRuntime` protocol の型依存を `server.py` から切り離す形に変更
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/types.py`
今回の中心です。`server.py` に残っていた shared response/status dataclass 群を専用 module に抽出しました。

追加したもの:
- `HealthStatus`
- `ReadinessStatus`
- `WorkflowResumeResponse`
- `ProjectionFailureHistoryResponse`
- `ProjectionFailureActionResponse`
- `RuntimeIntrospectionResponse`
- `McpResourceResponse`
- `McpToolResponse`
- `RuntimeDispatchResult`
- `McpHttpResponse`

ポイント:
- helper module が `server.py` に dataclass 定義そのものを依存しなくてよい形に寄せました
- response/status object の canonical source を `runtime/types.py` に移せました
- response builder / HTTP handler / transport helper が shared type module を参照できるようになりました

## 2. `ctxledger/src/ctxledger/server.py`
`server.py` 側では dataclass 定義の所有をやめ、shared runtime types を import / re-export する形に変更しました。

変更したこと:
- in-file の response/status dataclass 定義を削除
- `runtime/types.py` から各 dataclass を import
- 既存の `ctxledger.server.*` import surface は維持

維持しているもの:
- `ctxledger.server.WorkflowResumeResponse`
- `ctxledger.server.ProjectionFailureHistoryResponse`
- `ctxledger.server.ProjectionFailureActionResponse`
- `ctxledger.server.RuntimeIntrospectionResponse`
- `ctxledger.server.McpResourceResponse`
- `ctxledger.server.McpToolResponse`
- `ctxledger.server.RuntimeDispatchResult`
- `ctxledger.server.McpHttpResponse`
- `ctxledger.server.HealthStatus`
- `ctxledger.server.ReadinessStatus`

ポイント:
- external import surface は壊さずに canonical ownership だけ移せました
- `server.py` は application-facing facade / compatibility shell にさらに寄りました
- tests や利用側が `ctxledger.server` から import している前提を維持しています

## 3. `ctxledger/src/ctxledger/runtime/server_responses.py`
response helper は shared runtime types を使う形へ更新しました。

変更したこと:
- `WorkflowResumeResponse`
- `ProjectionFailureHistoryResponse`
- `ProjectionFailureActionResponse`
- `RuntimeIntrospectionResponse`

などを `runtime/types.py` から参照する形に変更

維持しているもの:
- response payload shape
- `server_not_ready` response shape
- projection failure action response shape
- runtime introspection / routes / tools response shape

ポイント:
- helper module から `server.py` への canonical type dependency を一段減らせました
- serializer だけはまだ `server.py` に残しており、そこは次段の整理候補です

## 4. `ctxledger/src/ctxledger/runtime/http_handlers.py`
HTTP handler helper も shared runtime types を使う形へ変更しました。

変更したこと:
- `WorkflowResumeResponse`
- `ProjectionFailureHistoryResponse`
- `ProjectionFailureActionResponse`
- `RuntimeIntrospectionResponse`
- `McpHttpResponse`

などを `runtime/types.py` から参照する形に変更

維持しているもの:
- HTTP auth error response shape
- invalid path 時の 404 response shape
- projection failures ignore/resolve の validation/error behavior
- runtime debug endpoint の response shape
- MCP over HTTP の response shape

ポイント:
- `server.py` から response dataclass 定義を借りる必要が減りました
- handler 側は behavior helper と transport-specific wiring により寄っています

## 5. `ctxledger/src/ctxledger/runtime/introspection.py`
小さめですが意味のある整理です。`ServerRuntime` protocol の型依存を `server.py` 経由にしない形に寄せました。

変更したこと:
- local な `ServerRuntime` protocol を `runtime/introspection.py` 側に定義
- `TYPE_CHECKING` での `server.py` 依存を少し減らした

ポイント:
- introspection helper の型 dependency が少し self-contained になりました
- 実行時の behavior は変えていません
- 本質的には dependency boundary の整理です

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
- bootstrap failure / startup failure の既存 shape

今回新しく進んだこと:
- response/status dataclass の canonical source を `runtime/types.py` に分離
- helper module が `server.py` canonical class 定義に依存する箇所を一部整理
- `server.py` は top-level facade / compatibility export としてさらに薄くなった
- `runtime/introspection.py` の protocol 型依存も少し独立させられた

まだ残っているもの:
- serializer 群はまだ `server.py` に残っている
- helper module は一部 `server.py` の serializer / wrapper に依存している
- readiness / health / DB/bootstrap helper 境界の最終整理は未完
- canonical protocol/dataclass 配置の最終最適化はまだ途中
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
- 今回の変更後、対象ファイルの diagnostics も確認し、追加エラーなしを確認しました
- focused regression は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract shared runtime response types`
- `Canonicalize shared runtime response dataclasses`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ただしこのメモ時点で commit 実施有無は未確認扱いにしておくのが安全です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は shared runtime types extraction が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理は小さめですが、依存関係の見通しを良くするうえで意味があります。

進んだこと:
- response/status dataclass の canonical source を `runtime/types.py` に寄せられた
- response helper / HTTP handler helper が shared type module を使う形に進んだ
- `server.py` が type 定義の所有者である必要がさらに薄れた
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- serializer 群の配置最適化
- helper module から `server.py` serializer への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. serializer 群を `server.py` から dedicated module へ寄せる
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical protocol/dataclass の配置をさらに見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- serializer と canonical type dependency の整理
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
17. shared bootstrap error canonicalization が入っている
18. 今回、shared runtime types extraction が入った
19. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
20. `docs/specification.md` は引き続き触らない
21. まだ compliance claim はしない
22. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- serializer 群もまだ `server.py` に残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server response building の canonical module
- `runtime/server_factory.py` は server construction wiring の canonical module
- `runtime/database_health.py` は DB health helper の canonical module
- `runtime/errors.py` は shared bootstrap error の canonical module
- `runtime/types.py` は shared response/status dataclass の canonical module
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

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- serializer 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **serializer dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- `serialize_workflow_resume(...)`
- `serialize_closed_projection_failures_history(...)`
- `serialize_stub_response(...)`
- runtime introspection serializer の ownership
- helper module から `server.py` serializer への依存

を dedicated helper/core module に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。