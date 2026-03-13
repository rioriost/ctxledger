このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。

今回の作業:
- `server.py` 依存の縮小を継続し、tests と runtime modules の import を canonical location へ寄せる整理を進めました。
- `tests/test_server.py` で `create_runtime` と `print_runtime_summary` の import を `ctxledger.runtime.orchestration` から読む形へ変更しました。
- `tests/test_server.py` から `build_runtime_dispatch_result` への依存を外し、dispatch helper の代わりに `HttpRuntimeAdapter.dispatch()` の public surface を直接検証する形へ変更しました。
- `runtime.orchestration.create_runtime()` は `server` と `http_runtime_builder` を要求するシグネチャなので、対応する test は `HttpRuntimeAdapter(settings)` を返す builder を渡す形に修正しました。
- `HttpRuntimeAdapter.dispatch()` は module-level `build_runtime_dispatch_result()` helper を経由せず、自身で handler lookup と route-not-found 応答を返すように変更しました。
- これにより `build_runtime_dispatch_result()` は不要になり、`src/ctxledger/server.py` から関数定義を削除しました。
- あわせて `src/ctxledger/server.py` の `__all__` から `build_runtime_dispatch_result` と `RuntimeDispatchResult` の再公開を削除しました。
- `HttpRuntimeAdapter` 本体を `src/ctxledger/server.py` から `src/ctxledger/runtime/http_runtime.py` へ移動しました。
- `src/ctxledger/runtime/http_runtime.py` は、HTTP handler registration だけでなく、HTTP runtime adapter の concrete implementation も持つ canonical module になりました。
- `src/ctxledger/runtime/http_runtime.py` の `build_http_runtime_adapter()` から `..server` への runtime import 依存を削除しました。
- `src/ctxledger/server.py` は `HttpRuntimeAdapter` を `ctxledger.runtime.http_runtime` から import する側へ回り、server module から concrete adapter 実装を取り除きました。
- `tests/test_server.py` の `HttpRuntimeAdapter` import も `ctxledger.server` ではなく `ctxledger.runtime.http_runtime` から読む形へ変更しました。
- この変更により、`tests/test_server.py` における `ctxledger.server` 依存は `CtxLedgerServer` と `create_server` のみに縮小しました。
- `src/ctxledger/server.py` の export surface を棚卸しし、`__all__` を意図的な public API のみに絞りました。
- `src/ctxledger/server.py` の `__all__` は `CtxLedgerServer` / `create_server` / `run_server` のみを公開する shape に変更しました。
- あわせて `server.py` から、もはや public surface として残す必要がない大量の import と再公開前提コードを削減しました。
- この export slimming により、`ctxledger.server` は bootstrap / top-level entrypoint module としての性格がかなり明確になりました。
- `src/ctxledger/mcp/tool_handlers.py` に残っていた `from ..server import McpToolResponse` を修正し、`McpToolResponse` の canonical import 先を `ctxledger.runtime.types` に変更しました。
- これにより、MCP tool response の生成は `server.py` を経由しない形に整理され、slimmed server exports と整合するようになりました。
- `src/ctxledger/server.py` に残っていた internal bridge helper も整理しました。
- `server.py` から `build_http_runtime_adapter()` / `build_workflow_service_factory()` / `create_runtime()` / `_print_runtime_summary()` を削除しました。
- `create_server()` は `runtime.server_factory.create_server()` への委譲をやめ、`CtxLedgerServer(...)` の構築、workflow service factory の選択、`build_http_runtime_adapter(server)` による runtime 装着を `server.py` 内で直接行う形に変更しました。
- `src/ctxledger/runtime/server_factory.py` を整理し、現在の `server.py` から使われなくなっていた `create_server()` helper を削除しました。
- `src/ctxledger/runtime/server_factory.py` は `build_workflow_service_factory()` のみを持つ小さな factory module に縮小されました。
- `runtime.server_factory` から不要になった type-only import と protocol import を削除し、module の責務に合わせて import surface を簡素化しました。
- `src/ctxledger/runtime/server_responses.py` に残っていた `server.py` への response type backref を整理しました。
- `build_workspace_resume_resource_response()` と `build_workflow_detail_resource_response()` が `from ..server import McpResourceResponse` を使っていたため、これを canonical な `ctxledger.runtime.types.McpResourceResponse` 参照へ変更しました。
- これにより、server response builder 群は response DTO 型について `server.py` を経由しない構成になり、response type の dependency direction もより自然になりました。
- debug/introspection response の組み立てを serializer 側の表現へ寄せました。
- `src/ctxledger/runtime/server_responses.py` の `build_runtime_routes_response()` と `build_runtime_tools_response()` は、生の introspection object から直接 dict を組み立てるのではなく、`serialize_runtime_introspection()` の出力を使って `transport` / `routes` / `tools` を切り出す形に変更しました。
- `build_runtime_introspection_response()` はもともと `serialize_runtime_introspection_collection()` を通していたため、debug introspection family 全体の表現がより一貫しました。
- route registry の naming を introspection responsibility に寄せました。
- `src/ctxledger/runtime/http_runtime.py` の `registered_routes()` を `introspection_endpoints()` に改名しました。
- `HttpRuntimeAdapter.introspect()` は `routes=self.introspection_endpoints()` を返す形へ更新され、route registry が「HTTP dispatch 全般の公開 API」ではなく「runtime introspection に載せる endpoint 集合」であることがメソッド名から明確になりました。
- `HttpRuntimeAdapter.start()` / `stop()` の logging extras も `registered_routes` ではなく `introspection_endpoints` キーで出す形に変更しました。
- `src/ctxledger/runtime/protocols.py` の `HttpRuntimeAdapterProtocol` も `registered_routes()` ではなく `introspection_endpoints()` を要求する shape に更新しました。
- `tests/test_server.py` で route registry を直接確認していた箇所も `registered_routes()` から `introspection_endpoints()` へ追従しました。
- `test_http_runtime_adapter_introspect_returns_registered_routes()` では、固定 tuple 直書きではなく `runtime.introspection_endpoints()` と `introspection.routes` が一致することを確認する形に変更しました。
- live Docker validation も実施しました。
- `docker compose -f docker/docker-compose.yml up -d --build` で PostgreSQL と `ctxledger` サービスを起動しました。
- `docker compose -f docker/docker-compose.yml ps` で `ctxledger-postgres` / `ctxledger-server` の両方が healthy になっていることを確認しました。
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read` を実行し、live Docker 上で以下が通ることを確認しました。
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `resources/list`
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `resources/read` for workspace resume
  - `resources/read` for workflow detail
  - `workflow_complete`
- これにより、HTTP-only cleanup 後の remote MCP server 実装が Docker Compose 経由でも end-to-end に動作することを確認しました。
- 最後に `pytest -q` を全体実行し、cleanup 一連の変更後も全体回帰がないことを確認しました。

今回確認したテスト結果:
- `pytest -q tests/test_server.py`
- 結果: `140 passed`
- `pytest -q tests/test_server.py tests/test_cli.py`
- 結果: `152 passed`
- `pytest -q tests/test_server.py tests/test_cli.py tests/test_postgres_integration.py`
- 結果: `168 passed`
- `pytest -q`
- 結果: `254 passed`

今回確認した live Docker validation:
- `docker compose -f docker/docker-compose.yml up -d --build`
- `docker compose -f docker/docker-compose.yml ps`
- 結果:
  - `ctxledger-postgres` healthy
  - `ctxledger-server` healthy
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read`
- 結果: live Docker 上の remote MCP workflow/resource smoke が完走

今回の直近コミット:
- `d316d74` — `Reduce server test imports to runtime modules`
- `968499e` — `Trim remaining server test helper imports`
- `b3a5b95` — `Inline HTTP adapter dispatch helper`
- `0224852` — `Move HTTP runtime adapter into runtime module`
- `93b472b` — `Import HTTP runtime adapter from canonical module in tests`
- `3181d7a` — `Slim server exports to public entrypoints`
- `d7d2284` — `Inline server bootstrap helper flow`
- `28de53a` — `Prune unused runtime server factory helper`
- `0ad5419` — `Use runtime response types directly in server responses`
- `1bfc34d` — `Align debug runtime responses with serializers`
- `089bc2e` — `Clarify runtime route registry introspection role`
- `c9e4a77` — `Record full cleanup verification status`
- `5d8500b` — `Record cleanup plan completion status`

現時点での設計メモ:
- `server.py` から concrete HTTP adapter 実装が抜けたことで、bootstrap surface と runtime implementation の境界がかなり自然になりました。
- `ctxledger.runtime.http_runtime` は naming 的にも責務的にも、`HttpRuntimeAdapter` の canonical home としてかなり妥当です。
- `tests/test_server.py` から見た `ctxledger.server` の責務はかなり細ってきており、bootstrap と application server object の窓口に近づいています。
- `create_runtime` と `print_runtime_summary` は `runtime.orchestration` 側が本来の公開位置として自然です。
- `build_runtime_dispatch_result()` は削除済みで、HTTP dispatch の public surface は `HttpRuntimeAdapter.dispatch()` に一本化されました。
- `server.py` の `__all__` は `CtxLedgerServer` / `create_server` / `run_server` のみに絞られ、意図しない compatibility barrel 的役割はかなり薄くなりました。
- `create_server` はまだ `server.py` が自然な public 窓口です。CLI や app factory の import point としても扱いやすい状態です。
- `tests/test_cli.py` では `ctxledger.server.run_server` を monkeypatch しているため、`run_server` は現時点では `server.py` の public surface に残しておく方が安全です。
- `introspection_endpoints()` への rename により、旧 `registered_routes()` が曖昧に抱えていた責務はかなり整理されました。
- route registry 自体は依然として `_handlers` の key 集合を返しており、runtime introspection がこれを `routes` として公開する設計は維持されています。
- `mcp/tool_handlers.py` 側の `McpToolResponse` 参照が canonical `runtime.types` に寄ったので、MCP response types の dependency direction はより自然になりました。
- `server.py` に残っていた internal bridge helper がなくなったことで、server bootstrap の責務と call graph はさらに単純化されました。
- `runtime.server_factory.py` は `build_workflow_service_factory()` のみを提供する最小 module になり、server bootstrap helper の旧 layering artifact はさらに減りました。
- `runtime.server_responses.py` からも remaining `server.py` 経由の response type import が外れ、debug routes/tools response も serializer ベースの表現へ揃ったため、runtime introspection 系の payload 変換責務は以前より一貫しています。
- 現時点では HTTP-only cleanup の大きな pruning は一段落しており、Docker Compose 上の live remote MCP validation まで通っているため、この cleanup スレッドは実質完了扱いでよい状態です。

次セッションで優先してやること:
1. もし cleanup を正式にクローズするなら、`docs/plans/http_fastapi_cleanup_plan.md` に完了扱いの最終メモを加えるか検討する
2. live Docker auth path (`docker/docker-compose.auth.yml`) でも必要なら追加 smoke を行う
3. 新しい cleanup 候補がなければ、この HTTP-only cleanup スレッドは一区切りとして次の機能・改善タスクへ進む
4. 追加変更を入れる場合は、変更後に `pytest -q` と必要な Docker smoke を再実行して回帰確認を維持する
5. 問題なければ次の descriptive commit を作成する
6. もし別トピックへ移るなら、この handoff を起点に新しい作業目標を定義する