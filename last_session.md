Patch 2 の続きとして、`server.py` に残っていた transport orchestration / HTTP transport まわりの責務をさらに外出ししました。今回のセッションでは、前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime の分離を土台にして、HTTP handler 実装本体の抽出まで進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/http_handlers.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して、HTTP handler 実装本体を新 helper module 経由に変更
- `ctxledger/src/ctxledger/runtime/http_runtime.py` は新しい HTTP handler helper を利用する形を維持
- `ctxledger/src/ctxledger/runtime/orchestration.py` / `ctxledger/src/ctxledger/runtime/composite.py` / `ctxledger/src/ctxledger/runtime/introspection.py` と組み合う形で責務分離を拡張
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/http_handlers.py`
今回の中心です。`server.py` に残っていた HTTP handler 実装本体を外出しするため、専用 helper module を追加しました。

追加したもの:
- `extract_bearer_token(...)`
- `build_http_auth_error_response(...)`
- `require_http_bearer_auth(...)`
- `parse_required_uuid_argument(...)`
- `parse_optional_projection_type_argument(...)`
- `parse_workflow_resume_request_path(...)`
- `parse_closed_projection_failures_request_path(...)`
- `build_workflow_resume_http_handler(...)`
- `build_closed_projection_failures_http_handler(...)`
- `build_projection_failures_ignore_http_handler(...)`
- `build_projection_failures_resolve_http_handler(...)`
- `build_runtime_introspection_http_handler(...)`
- `build_runtime_routes_http_handler(...)`
- `build_runtime_tools_http_handler(...)`
- `build_mcp_http_handler(...)`

ポイント:
- 認証 helper
  - bearer token 抽出
  - auth error response 生成
  - auth validation
  を `server.py` から分離しました
- HTTP route path parsing
  - workflow resume
  - closed projection failures
  を `server.py` から分離しました
- projection failure 系 endpoint の query argument parsing / validation をここへ移しました
- debug endpoint
  - `/debug/runtime`
  - `/debug/routes`
  - `/debug/tools`
  の handler 実装本体もここへ移しました
- MCP over HTTP bridge の `build_mcp_http_handler(...)` もここへ移しました
- Streamable HTTP scaffold と RPC helper を使う構造自体は維持しています
- `server.py` 側 canonical response type を壊さないため、必要な response class / helper は function 内 import で参照しています
- 循環 import を抑えるため、型参照は `TYPE_CHECKING` と function 内 import を併用しています

注意:
- helper module 側から `server.py` の response class や builder function を参照する箇所があるため、依存はゼロではありません
- ただし、HTTP handler の実装本体を `server.py` 直下に置き続けるよりは責務境界がかなり見えやすくなりました

## 2. `ctxledger/src/ctxledger/server.py`
今回のもうひとつの中心変更です。`server.py` はさらに薄くなりました。

変更したこと:
- `build_workflow_resume_http_handler(...)` を wrapper 化
- `build_closed_projection_failures_http_handler(...)` を wrapper 化
- `build_projection_failures_ignore_http_handler(...)` を wrapper 化
- `build_projection_failures_resolve_http_handler(...)` を wrapper 化
- `build_runtime_introspection_http_handler(...)` を wrapper 化
- `build_runtime_routes_http_handler(...)` を wrapper 化
- `build_runtime_tools_http_handler(...)` を wrapper 化
- `build_mcp_http_handler(...)` を wrapper 化
- `_extract_bearer_token(...)` / `_http_auth_error_response(...)` / `_require_http_bearer_auth(...)` も extracted helper 経由に変更
- `_parse_required_uuid_argument(...)` / `_parse_optional_projection_type_argument(...)` も extracted helper 経由に変更
- `parse_workflow_resume_request_path(...)` / `parse_closed_projection_failures_request_path(...)` も extracted helper 経由に変更

結果として `server.py` に残る中心責務:
- application-facing server surface
- health / readiness
- workflow / projection failure response building
- resource response building
- runtime/server construction entrypoint
- public compatibility wrapper 群

外れたもの:
- HTTP auth helper 実装本体
- HTTP path / query parsing helper 実装本体
- debug HTTP handler 実装本体
- workflow resume HTTP handler 実装本体
- projection failure 系 HTTP handler 実装本体
- MCP HTTP bridge 実装本体

互換性面の配慮:
- 既存 test / import surface を壊さないように、`server.py` 側に public wrapper を残しています
- 直接 import されうる関数名は極力維持しています
- `build_http_runtime_adapter(...)` / `create_runtime(...)` / `_print_runtime_summary(...)` の wrapper 方針も継続しています

## 3. `ctxledger/src/ctxledger/runtime/http_runtime.py`
大きな構造変更はありませんが、HTTP runtime builder が新しい handler helper module と組み合う形になっています。

現在の責務:
- `HttpRuntimeAdapter` を構築する
- `mcp_rpc`
- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`
  の route registration wiring を担う

ポイント:
- route registration wiring はここ
- handler 実装本体は `runtime/http_handlers.py`
- runtime selection / CLI entrypoint orchestration は `runtime/orchestration.py`
  という役割分担が前回より明確になりました

## 4. `ctxledger/src/ctxledger/runtime/orchestration.py`
今回の session では大きなロジック変更はありませんが、前回までに外出しした runtime orchestration の中心として引き続き使われています。

維持しているもの:
- `build_stdio_runtime_adapter(...)`
- `create_runtime(...)`
- `apply_overrides(...)`
- `install_signal_handlers(...)`
- `print_runtime_summary(...)`
- `run_server(...)`

ポイント:
- transport selection の中心はここ
- HTTP runtime 作成は `runtime/http_runtime.py`
- composite lifecycle は `runtime/composite.py`
- introspection 正規化は `runtime/introspection.py`
  という分割がより明確になっています

## 5. `ctxledger/src/ctxledger/runtime/composite.py`
今回の session では大きな変更はありません。

維持しているもの:
- `ServerRuntime`
- `CompositeRuntimeAdapter`

ポイント:
- 複数 transport runtime を束ねる canonical lifecycle 実装として引き続きここにあります
- `server.py` が composite lifecycle 実装本体を持たない構造は維持されています

## 6. `ctxledger/src/ctxledger/runtime/introspection.py`
今回の session では大きな変更はありません。

維持しているもの:
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- stdio / http / composite を横断して正規化する役割は引き続きここです
- `server.py` は introspection 実装本体の利用者である状態を維持しています

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

今回新しく進んだこと:
- HTTP auth helper の authority を `runtime/http_handlers.py` に分離
- workflow / projection failure / debug / MCP HTTP handler 実装本体を `runtime/http_handlers.py` に分離
- `server.py` は HTTP transport 実装の「公開面と wrapper」にさらに近づいた
- transport helper 群の責務分割が
  - introspection
  - orchestration
  - composite lifecycle
  - HTTP runtime builder
  - HTTP handler implementation
  の単位で見えやすくなった

まだ残っているもの:
- `server.py` はまだ workflow/projection response building の中心
- `server.py` は still application-facing server surface の中心
- helper module は `server.py` の canonical response classes / builders に依存している
- `create_server(...)` と runtime wiring boundary の最終整理は未完
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
- `runtime/http_handlers.py` 抽出後も **180 passed** を維持しています
- 今回は import path の誤りや wrapper 再帰のような事故を避けるため、`server.py` 側 import 名に alias を付けて wrapper との衝突を避けています
- 最終状態は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract HTTP handler implementations`
- `Move HTTP auth and route handlers out of server`

## 注意
- この session では `last_session.md` 更新まで実施していますが、git commit は未実施です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は HTTP handler extraction が中心で、full transport rewrite ではありません

## 実装の評価
今回の抽出は、前回の HTTP runtime builder extraction の自然な続きとして良い前進です。

進んだこと:
- `server.py` から HTTP handler 実装本体を大きく外出しできた
- `server.py` から auth helper / path parser / debug handler / MCP HTTP bridge 実装本体も外出しできた
- runtime helper 群の責務分割がかなり見やすくなった
- 将来 `server.py` を
  - health/readiness
  - workflow-facing server surface
  - resource/response building
  - public compatibility shell
  にさらに寄せやすくなった
- 既存 test expectation を保ったまま、小さく安全に前進できた

まだ未着手に近いこと:
- `server.py` に残る workflow/projection response building の整理
- `create_server(...)` と runtime builder boundary の整理
- HTTP helper module から `server.py` canonical class への依存の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `create_server(...)` と runtime wiring の責務をさらに整理する
2. workflow/projection response builder を `server.py` から外出しする
3. HTTP helper module が `server.py` canonical class に依存している箇所を整理する
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と bootstrap shell により近づける

特に安全そうなのは:
- workflow/projection response builder の抽出
- `create_server(...)` / `create_runtime(...)` boundary の整理
- HTTP helper module と `server.py` 間の canonical type dependency の整理

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
12. 今回、HTTP handler implementation extraction が入った
13. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
14. `docs/specification.md` は引き続き触らない
15. まだ compliance claim はしない
16. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
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

### まだ `server.py` に残るもの
- workflow/projection/resource response building
- `create_server(...)` の中心 wiring
- health/readiness/debug HTTP surface の公開面
- application-facing server surface 全般
- public compatibility wrapper 群

## 次に自然な一手
ここまで来たので、次は **workflow/projection response building と server construction wiring の整理** が一番きれいです。

たとえば:
- `build_workflow_resume_response(...)`
- `build_closed_projection_failures_response(...)`
- `build_projection_failures_ignore_response(...)`
- `build_projection_failures_resolve_response(...)`
- `create_server(...)`

を dedicated helper / builder module に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness
- workflow-facing public surface
- bootstrap shell
- compatibility export surface

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。