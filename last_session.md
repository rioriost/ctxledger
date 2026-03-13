このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- FastAPI ベースの `src/ctxledger/http_app.py` と Docker 起動導線は維持されています。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。

今回の作業:
- `docs/plans/http_fastapi_cleanup_plan.md` を新規作成し、HTTP MCP + FastAPI 導入後に残っている不要レイヤーの整理方針を文書化しました。
- cleanup の第一段として、`src/ctxledger/http_app.py` を変更し、FastAPI route から `runtime.dispatch(route_name, ...)` に再委譲せず、`runtime.http_handlers` の具体ハンドラを直接束縛する形に変更しました。
- これにより、FastAPI が HTTP route ownership を持ち、アプリ層の request flow が追いやすくなりました。
- `src/ctxledger/http_app.py` から `server.runtime._server = server` の後付け代入を削除しました。
- `src/ctxledger/runtime/http_runtime.py` を変更し、`HttpRuntimeAdapter` を `HttpRuntimeAdapter(server.settings, server=server)` で構築するようにして、runtime/server の依存関係を生成時に明示しました。
- `src/ctxledger/server.py` の `HttpRuntimeAdapter.__init__` に `server` 引数を追加し、private field の後付け patch を不要にしました。
- `src/ctxledger/server.py` の `build_http_runtime_adapter()` から `_server` の後付け代入を削除しました。
- 続けて test import cleanup を進め、`tests/test_server.py` の import を整理して、HTTP handler / server response / MCP tool/resource helper / response types の多くを `ctxledger.server` 経由ではなく canonical module から読む形へ変更しました。
- `tests/test_mcp_modules.py` でも `McpResourceResponse` / `McpToolResponse` の import を `ctxledger.server` から `ctxledger.runtime.types` へ移しました。
- さらに `src/ctxledger/server.py` から、未使用になっていた HTTP handler wrapper・response wrapper・path parser wrapper などの compatibility 関数をまとめて削除しました。
- pruning の途中で、`CtxLedgerServer.build_workspace_resume_resource_response()` と `CtxLedgerServer.build_workflow_detail_resource_response()` が削除した module-level wrapper を呼んでいたため resource read 系で `NameError` が発生しました。
- 上記 2 メソッドは `runtime.server_responses` をメソッド内で直接 import して呼ぶ形に修正し、resource path の挙動を回復させました。
- 追加で `tests/test_server.py` の serializer import を `ctxledger.server` から `ctxledger.runtime.serializers` に移し、`server.py` への依存をさらに減らしました。
- さらに `HttpRuntimeAdapter` に `handler(route_name)` / `require_handler(route_name)` を追加し、内部の `_handlers` dict へ直接触れずに registered handler を扱える accessor を用意しました。
- `dispatch_http_request()` は `_handlers.get(...)` ではなく `runtime.handler(route_name)` を使うように変更しました。
- `tests/test_server.py` の debug/runtime route まわりも `_handlers[...]` 直参照ではなく `handler(...)` / `require_handler(...)` 経由へ変更しました。
- さらに `src/ctxledger/server.py` に `build_runtime_dispatch_result()` を追加し、`HttpRuntimeAdapter.dispatch()` の実体を `dispatch_http_request()` ではなくこの helper に寄せました。
- `dispatch_http_request()` は互換維持の薄い wrapper として `build_runtime_dispatch_result()` を呼ぶだけの形になっていましたが、今回その最後の薄い wrapper 自体も削除しました。
- `tests/test_server.py` の dispatch result 系テストはすでに `build_runtime_dispatch_result()` を直接使う形に切り替わっていたため、今回の wrapper 削除で追加の振る舞い変更は発生していません。
- この段階で route registry はまだ残っていますが、dispatch の中心 helper は `build_runtime_dispatch_result()` に一本化され、`dispatch_http_request()` という移行用の名前は除去できました。
- `server.py` はまだ完全に小さくはないものの、以前より compatibility surface はかなり減り、HTTP handler / server response の一次公開窓口としての役割はかなり薄くなっています。
- 一方で、`HttpRuntimeAdapter.register_handler()`、`registered_routes()`、`RuntimeIntrospection` の公開位置などは依然として残っており、次段の整理対象です。

今回確認したテスト結果:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`
- 結果: `157 passed`

今回の直近コミット:
- `4e00ba0` — `Simplify FastAPI HTTP routing path`
- `33c8815` — `Move tests to canonical runtime modules`
- `9cd5f9e` — `Prune obsolete server compatibility wrappers`
- `6ef0808` — `Use runtime serializers directly in server tests`
- `5d278e0` — `Add explicit HTTP runtime handler accessors`
- `40eccdf` — `Extract runtime dispatch result helper`

現時点での設計メモ:
- `http_app.py` はかなり自然になり、FastAPI の route flow は直接的になっています。
- `server.py` の module-level wrapper はかなり減ったが、まだ bootstrap と runtime adapter と legacy-friendly export が混在しています。
- `CtxLedgerServer` の resource response メソッドは `runtime.server_responses` を遅延 import する形になっており、循環を避けつつ現状を保つための暫定バランスです。
- `build_runtime_dispatch_result()` が runtime dispatch の唯一の中心 helper になりました。
- `registered_routes()` は debug/introspection と既存テストで参照されているため、削除前に introspection の責務整理が必要です。
- 設定面では `TransportMode` と `http.enabled` の二重性がまだ残っており、HTTP 専用化に合わせた簡素化余地があります。
- FastAPI app は依然として import 時に `create_default_fastapi_app()` が走る shape なので、必要なら次段で lifespan 管理へ寄せる余地があります。
- `tests/test_server.py` はまだ `CtxLedgerServer` / `HttpRuntimeAdapter` / `build_http_runtime_adapter` / `build_runtime_dispatch_result` などを `ctxledger.server` から import しており、ここが今後の `server.py` 縮小の境界になります。
- serializer helper は `tests/test_server.py` 側では canonical module に寄せられたので、`server.py` からの再公開削減をさらに進めやすくなりました。
- route registry 自体は残るが、handler lookup と dispatch helper の窓口が整理されたので、将来 `_handlers` の実体や dispatch の置き場所を変えても追従しやすくなっています。

次セッションで優先してやること:
1. `server.py` にまだ残っている re-export / helper 群の棚卸しを続ける
2. `registered_routes()` を introspection 用の責務へさらに限定できるか考える
3. `RuntimeIntrospection` や他の公開位置を見直し、`server.py` から外せるものを外す
4. 可能なら FastAPI lifespan 管理への移行可否を確認する
5. 変更が一段落したら `pytest -q` で全体確認する
6. 問題なければ cleanup 用の次の descriptive commit を作成