Patch 2 の続きとして、今回は **HTTP validation helper dependency cleanup** を進め、`runtime/http_handlers.py` に残っていた validation helper の `server.py` 経由依存をさらに整理しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup を土台にして、**HTTP validation path の direct canonical wiring** を進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/http_handlers.py` を更新して validation helper が `server.py` の `build_mcp_error_response(...)` wrapper ではなく canonical MCP tool handler module を直接使う形に変更
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/http_handlers.py`
今回の中心です。HTTP request argument validation helper が、まだ `server.py` の MCP error helper wrapper を経由していたため、canonical module へ直接向ける形に変更しました。

変更したこと:
- `parse_required_uuid_argument(...)` が `..server` ではなく `..mcp.tool_handlers` の `build_mcp_error_response(...)` を直接使う形に変更
- `parse_optional_projection_type_argument(...)` も同様に変更

維持しているもの:
- UUID validation error shape
- projection type validation error shape
- `invalid_request` code
- error payload の details shape
- HTTP projection failure endpoints の 400 mapping
- HTTP handler 全体の response shape

ポイント:
- `runtime/http_handlers.py` から `server.py` の validation-related wrapper dependency を一段減らせました
- validation error response の canonical source を、実際の所有者である MCP tool handler module 側に寄せられました
- small change ですが dependency graph をきれいにする意味があります

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

今回新しく進んだこと:
- HTTP validation helper が `server.py` wrapper を経由しない形に進んだ
- `runtime/http_handlers.py` の validation/error dependency が canonical MCP helper 側に少し寄った
- `server.py` は top-level facade / compatibility export としてさらに薄くなった

まだ残っているもの:
- `runtime/http_handlers.py` は型参照や protocol でまだ `server.py` に依存している
- `server.py` には application-facing server surface がまだ多く残っている
- helper module は一部 `server.py` の wrapper / protocol / adapter class に依存している
- readiness / health / DB/bootstrap helper 境界の最終整理は未完
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
- 今回の変更は小さく、focused regression のみ確認
- 最終状態は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Clean up HTTP validation helper dependencies`
- `Directly wire HTTP validation error helpers`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は HTTP validation helper dependency cleanup が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理はかなり小さいですが、依存関係の見通しを良くするうえで意味があります。

進んだこと:
- HTTP validation helper が `server.py` wrapper に依存しない形に寄せられた
- validation error helper の canonical source がより明確になった
- `server.py` の facade 化を少しだけ前に進められた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- helper module から `server.py` adapter/protocol への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `runtime/http_handlers.py` の type/protocol dependency をさらに整理する
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical protocol/dataclass/serializer/helper の配置をさらに見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- HTTP helper dependency の整理
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
18. shared runtime types extraction が入っている
19. shared runtime serializers extraction が入っている
20. HTTP runtime wrapper dependency cleanup が入っている
21. 今回、HTTP validation helper dependency cleanup が入った
22. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
23. `docs/specification.md` は引き続き触らない
24. まだ compliance claim はしない
25. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup の本体は外へ出始めた
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

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **HTTP type/protocol dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- `runtime/http_handlers.py` の type/protocol dependency
- `server.py` に残る adapter/protocol/wrapper dependency
- readiness / health helper の ownership
- transport helper と top-level facade の境界

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。