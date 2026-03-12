Patch 2 の続きとして、今回は **wrapper dependency cleanup in HTTP runtime wiring** を進め、`server.py` に残っていた HTTP runtime wiring 経由の wrapper 依存をさらに整理しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers の抽出を土台にして、**HTTP runtime registration path の direct canonical wiring** を進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/http_runtime.py` を更新して HTTP runtime registration helper を明示化
- `ctxledger/src/ctxledger/runtime/http_handlers.py` を更新して response helper wrapper ではなく canonical response builder module を直接使う形に変更
- 一度 circular import を踏んだため、`http_runtime.py` 内の stdio runtime builder import を function-local に戻して修正
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/http_runtime.py`
今回の中心です。HTTP runtime の registration wiring が `server.py` wrapper を経由しすぎていたため、canonical module 直結の形へ一段進めました。

変更したこと:
- `register_http_runtime_handlers(runtime, server)` を追加
- `build_http_runtime_adapter(server)` は `HttpRuntimeAdapter` を生成したあと、`register_http_runtime_handlers(...)` を使う形へ整理
- handler registration 時に使う各 HTTP handler builder は `runtime/http_handlers.py` から直接 import する形へ変更

ポイント:
- HTTP runtime wiring の責務が `runtime/http_runtime.py` により明確に寄りました
- `server.py` の HTTP handler wrapper を経由しなくても route registration できる形になりました
- registration path と adapter construction path の責務が読みやすくなりました

## 2. `ctxledger/src/ctxledger/runtime/http_handlers.py`
HTTP handler helper 側も、`server.py` の wrapper 関数ではなく canonical response builder module を直接使う形へ更新しました。

変更したこと:
- `build_workflow_resume_http_handler(...)` が `runtime/server_responses.py` の `build_workflow_resume_response(...)` を直接使う形に変更
- `build_closed_projection_failures_http_handler(...)` も同様に変更
- `build_projection_failures_ignore_http_handler(...)` も同様に変更
- `build_projection_failures_resolve_http_handler(...)` も同様に変更
- `build_runtime_introspection_http_handler(...)` も同様に変更
- `build_runtime_routes_http_handler(...)` も同様に変更
- `build_runtime_tools_http_handler(...)` も同様に変更

維持しているもの:
- HTTP auth error response shape
- invalid path 時の 404 response shape
- projection failures ignore/resolve の validation/error behavior
- runtime debug endpoint の response shape
- workflow resume / closed projection failures の response shape

ポイント:
- handler module から `server.py` wrapper への依存を一段減らせました
- HTTP handler 実装は transport/path/auth/validation により寄り、response building は canonical response builder に寄る形が少し進みました
- helper module 間 dependency の向きが少し自然になりました

## 3. 循環参照の修正
今回の作業中に一度 circular import が発生しました。

起きたこと:
- `runtime/http_runtime.py` が module import 時に `runtime/orchestration.py` の `build_stdio_runtime_adapter(...)` を import するようにしたところ、
  `runtime/orchestration.py` 側が `runtime/http_runtime.py` を import しているため、test collection 時に partially initialized module error が発生

対応:
- `build_stdio_runtime_adapter(...)` の import は `register_http_runtime_handlers(...)` の function-local import に戻して修正

ポイント:
- direct canonical wiring を進めつつ、module initialization order は壊さない形へ調整しました
- handler builder の direct import は残しつつ、循環参照の起点だけを局所的に遅延 import しています
- 最終状態は green です

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
- HTTP runtime wiring が `server.py` wrapper に依存する箇所を一部整理
- HTTP handler module が canonical response builder module を直接使う形に進んだ
- `runtime/http_runtime.py` が registration wiring の中心としてさらに明確になった
- `server.py` は top-level facade / compatibility export としてさらに薄くなった

まだ残っているもの:
- `runtime/http_handlers.py` の request argument validation はまだ `server.py` の MCP error helper に依存している
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
- 一度 circular import により test collection error が出ました
- `build_stdio_runtime_adapter(...)` の import を function-local に戻すことで解消しました
- 修正後の focused regression は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Clean up HTTP runtime wrapper dependencies`
- `Directly wire HTTP runtime handlers`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は wrapper dependency cleanup in HTTP runtime wiring が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理は小さめですが、依存関係の見通しを良くするうえで意味があります。

進んだこと:
- HTTP runtime registration path が `server.py` wrapper に依存しすぎない形に寄せられた
- HTTP handler 群が canonical response builder を直接使うようになった
- `runtime/http_runtime.py` が registration wiring の所有者としてさらに明確になった
- circular import を局所修正しつつ安全に前進できた
- 既存 test expectation を保ったまま前進できた

まだ未着手に近いこと:
- HTTP handler の request validation helper と MCP error helper の依存整理
- helper module から `server.py` adapter/protocol への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `runtime/http_handlers.py` の validation/error helper dependency をさらに整理する
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
20. 今回、HTTP runtime wrapper dependency cleanup が入った
21. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
22. `docs/specification.md` は引き続き触らない
23. まだ compliance claim はしない
24. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup の本体は外へ出始めた
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

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **HTTP helper dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- `runtime/http_handlers.py` の request argument validation helper
- MCP error response helper の ownership
- `server.py` に残る adapter/protocol/wrapper dependency
- readiness / health helper の ownership

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。