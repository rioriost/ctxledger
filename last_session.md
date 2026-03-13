このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。

今回の作業:
- `server.py` 依存の縮小を続け、`tests/test_server.py` の import をさらに canonical module 側へ寄せました。
- `tests/test_server.py` で `create_runtime` と `print_runtime_summary` の import を `ctxledger.runtime.orchestration` から読む形へ変更しました。
- `tests/test_server.py` から `build_runtime_dispatch_result` への依存を外し、dispatch helper の代わりに `HttpRuntimeAdapter.dispatch()` の public surface を直接検証する形へ変更しました。
- `runtime.orchestration.create_runtime()` は `server` と `http_runtime_builder` を要求するシグネチャなので、対応する test は `HttpRuntimeAdapter(settings)` を返す builder を渡す形に修正しました。
- 続けて `src/ctxledger/server.py` を整理し、`HttpRuntimeAdapter.dispatch()` が module-level `build_runtime_dispatch_result()` helper を経由せず、自身で handler lookup と route-not-found 応答を返すように変更しました。
- これにより `build_runtime_dispatch_result()` は不要になったため、`src/ctxledger/server.py` から関数定義を削除しました。
- あわせて `src/ctxledger/server.py` の `__all__` から `build_runtime_dispatch_result` と `RuntimeDispatchResult` の再公開を削除しました。
- さらに `HttpRuntimeAdapter` 本体を `src/ctxledger/server.py` から `src/ctxledger/runtime/http_runtime.py` へ移動しました。
- `src/ctxledger/runtime/http_runtime.py` は、HTTP handler registration だけでなく、HTTP runtime adapter の concrete implementation も持つ canonical module になりました。
- `src/ctxledger/runtime/http_runtime.py` の `build_http_runtime_adapter()` から `..server` への runtime import 依存を削除しました。
- `src/ctxledger/server.py` は `HttpRuntimeAdapter` を `ctxledger.runtime.http_runtime` から import する側へ回り、server module から concrete adapter 実装を取り除きました。
- これにより、`server.py` の責務は一段と bootstrap / lifecycle / public entrypoint 側へ寄りました。
- さらに `tests/test_server.py` の `HttpRuntimeAdapter` import も `ctxledger.server` ではなく `ctxledger.runtime.http_runtime` から読む形へ変更しました。
- この変更により、`tests/test_server.py` における `ctxledger.server` 依存は `CtxLedgerServer` と `create_server` のみに縮小しました。
- 続けて `src/ctxledger/server.py` の export surface を棚卸しし、`__all__` を意図的な public API のみに絞りました。
- `src/ctxledger/server.py` の `__all__` は `CtxLedgerServer` / `create_server` / `run_server` のみを公開する shape に変更しました。
- あわせて `server.py` から、もはや public surface として残す必要がない大量の import と再公開前提コードを削減しました。
- この export slimming により、`ctxledger.server` は bootstrap / top-level entrypoint module としての性格がかなり明確になりました。
- 上記 export slimming の影響で、`src/ctxledger/mcp/tool_handlers.py` に残っていた `from ..server import McpToolResponse` が壊れ、MCP error/success response 生成で `ImportError` が発生しました。
- `src/ctxledger/mcp/tool_handlers.py` を修正し、`McpToolResponse` の canonical import 先を `ctxledger.runtime.types` に変更しました。
- これにより、MCP tool response の生成は `server.py` を経由しない形に整理され、slimmed server exports と整合するようになりました。
- 今回さらに `src/ctxledger/server.py` に残っていた internal bridge helper を整理しました。
- `server.py` から `build_http_runtime_adapter()` / `build_workflow_service_factory()` / `create_runtime()` / `_print_runtime_summary()` を削除しました。
- `create_server()` は `runtime.server_factory.create_server()` への委譲をやめ、`CtxLedgerServer(...)` の構築、workflow service factory の選択、`build_http_runtime_adapter(server)` による runtime 装着を `server.py` 内で直接行う形に変更しました。
- これにより、`server.py` の server bootstrap flow は一段短くなり、top-level entrypoint module として読んだときの初期化経路が追いやすくなりました。
- さらに `src/ctxledger/runtime/server_factory.py` を整理し、現在の `server.py` から使われなくなっていた `create_server()` helper を削除しました。
- `src/ctxledger/runtime/server_factory.py` は `build_workflow_service_factory()` のみを持つ小さな factory module に縮小されました。
- あわせて `runtime.server_factory` から不要になった type-only import と protocol import を削除し、module の責務に合わせて import surface を簡素化しました。
- さらに `src/ctxledger/runtime/server_responses.py` に残っていた `server.py` への response type backref を整理しました。
- `build_workspace_resume_resource_response()` と `build_workflow_detail_resource_response()` が `from ..server import McpResourceResponse` を使っていたため、これを canonical な `ctxledger.runtime.types.McpResourceResponse` 参照へ変更しました。
- これにより、server response builder 群は response DTO 型について `server.py` を経由しない構成になり、response type の dependency direction もより自然になりました。
- さらに debug/introspection response の組み立てを serializer 側の表現へ寄せました。
- `src/ctxledger/runtime/server_responses.py` の `build_runtime_routes_response()` と `build_runtime_tools_response()` は、生の introspection object から直接 dict を組み立てるのではなく、`serialize_runtime_introspection()` の出力を使って `transport` / `routes` / `tools` を切り出す形に変更しました。
- これにより debug response も introspection serializer の表現と揃い、routes/tools/debug payload の shape 変更が将来入った場合でも追従点が減る形になりました。
- `build_runtime_introspection_response()` はもともと `serialize_runtime_introspection_collection()` を通していたため、今回の変更で debug introspection family 全体の表現がより一貫しました。
- 今回さらに route registry の naming を introspection responsibility に寄せました。
- `src/ctxledger/runtime/http_runtime.py` の `registered_routes()` を `introspection_endpoints()` に改名しました。
- `HttpRuntimeAdapter.introspect()` は `routes=self.introspection_endpoints()` を返す形へ更新され、route registry が「HTTP dispatch 全般の公開 API」ではなく「runtime introspection に載せる endpoint 集合」であることがメソッド名から明確になりました。
- `HttpRuntimeAdapter.start()` / `stop()` の logging extras も `registered_routes` ではなく `introspection_endpoints` キーで出す形に変更しました。
- `src/ctxledger/runtime/protocols.py` の `HttpRuntimeAdapterProtocol` も `registered_routes()` ではなく `introspection_endpoints()` を要求する shape に更新しました。
- `tests/test_server.py` で route registry を直接確認していた箇所も `registered_routes()` から `introspection_endpoints()` へ追従しました。
- `test_http_runtime_adapter_introspect_returns_registered_routes()` では、固定 tuple 直書きではなく `runtime.introspection_endpoints()` と `introspection.routes` が一致することを確認する形に変更し、registry naming cleanup 後の意図に寄せました。
- これにより route registry は、実装上は `_handlers` の key 集合を返しつつも、外向きには introspection/debug 用 surface であることがより明確になりました。
- `tests/test_server.py` を再実行し、この naming/責務整理後も既存の debug/runtime/introspection 挙動が維持されていることを確認しました。

今回確認したテスト結果:
- `pytest -q tests/test_server.py`
- 結果: `140 passed`
- `pytest -q tests/test_server.py tests/test_cli.py`
- 結果: `152 passed`
- `pytest -q tests/test_server.py tests/test_cli.py tests/test_postgres_integration.py`
- 結果: `168 passed`

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
- route registry の introspection-oriented rename 変更は、まだ commit していません。

現時点での設計メモ:
- `server.py` から concrete HTTP adapter 実装が抜けたことで、bootstrap surface と runtime implementation の境界がかなり自然になりました。
- `ctxledger.runtime.http_runtime` は naming 的にも責務的にも、`HttpRuntimeAdapter` の canonical home としてかなり妥当です。
- `tests/test_server.py` から見た `ctxledger.server` の責務はかなり細ってきており、bootstrap と application server object の窓口に近づいています。
- `create_runtime` と `print_runtime_summary` は `runtime.orchestration` 側が本来の公開位置として自然です。
- `build_runtime_dispatch_result()` は削除済みで、HTTP dispatch の public surface は `HttpRuntimeAdapter.dispatch()` に一本化されました。
- `server.py` の `__all__` は `CtxLedgerServer` / `create_server` / `run_server` のみに絞られ、意図しない compatibility barrel 的役割はかなり薄くなりました。
- `create_server` はまだ `server.py` が自然な public 窓口です。CLI や app factory の import point としても扱いやすい状態です。
- `tests/test_cli.py` では `ctxledger.server.run_server` を monkeypatch しているため、`run_server` は現時点では `server.py` の public surface に残しておく方が安全です。
- 旧 `registered_routes()` は introspection/debug 用責務を示しきれていなかったため、`introspection_endpoints()` への rename により意図はかなり明確になりました。
- route registry 自体は依然として `_handlers` の key 集合を返しており、runtime introspection がこれを `routes` として公開する設計は維持されています。
- `mcp/tool_handlers.py` 側の `McpToolResponse` 参照が canonical `runtime.types` に寄ったので、MCP response types の dependency direction はより自然になりました。
- `server.py` に残っていた internal bridge helper がなくなったことで、server bootstrap の責務と call graph はさらに単純化されました。
- `runtime.server_factory.py` は `build_workflow_service_factory()` のみを提供する最小 module になり、server bootstrap helper の旧 layering artifact はさらに減りました。
- `runtime.server_responses.py` からも remaining `server.py` 経由の response type import が外れ、debug routes/tools response も serializer ベースの表現へ揃ったため、runtime introspection 系の payload 変換責務は以前より一貫しています。

次セッションで優先してやること:
1. 今回の route registry の introspection-oriented rename 変更を descriptive commit にまとめる
2. 必要なら `tests/test_cli.py` や他の周辺 test も含めて naming 変更の波及を確認する
3. 変更がまとまった段階で `pytest -q` を全体実行して回帰確認する
4. `tests/test_cli.py` の patch 対象も含め、`server.py` の public API をどこまで意図的に残すかを最終的に決める
5. 問題なければ cleanup の次の descriptive commit を作成する
6. その後、HTTP-only cleanup の残タスクがあれば `docs/plans/http_fastapi_cleanup_plan.md` と照らして次の pruning 候補を決める