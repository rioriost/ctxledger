このプロジェクトでは、Dockerコンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- FastAPI ベースの `src/ctxledger/http_app.py` と Docker 起動導線は維持されています。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 今回の作業では、ユーザー方針に合わせて **stdio MCP サーバの残骸を削除** しました。
- `src/ctxledger/config.py` から `StdioSettings`、`TransportMode.STDIO`、`TransportMode.BOTH`、`CTXLEDGER_ENABLE_STDIO` 依存を削除しました。
- `AppSettings` は HTTP 専用 shape に整理し、`transport` は `http` のみを受ける前提に変更しました。
- `src/ctxledger/runtime/orchestration.py` から `ctxledger.mcp.stdio` 参照、stdio runtime builder、stdio launch 分岐、stdio summary 出力を削除しました。
- `tests/test_config.py` から stdio 前提の設定テストを削除し、HTTP 専用の設定期待値に更新しました。
- `tests/test_cli.py` と `tests/test_server.py` の `StdioSettings` 依存を削除し、`AppSettings` 構築を HTTP 専用 shape に更新しました。
- 一時的に入れてしまった「stdio fallback で import error を逃がす修正」は取り消し済みです。stdio を復活させる方向のコードは入れていません。

今回確認したテスト結果:
- `pytest -q tests/test_config.py tests/test_cli.py tests/test_server.py`
- 結果: `171 passed`

現時点で残っていそうな確認対象:
1. `src` / `tests` 以外のドキュメントや補助スクリプトに `stdio` 記述が残っていないか
2. `README.md` や `docs/*` の transport 説明に `stdio` や `both` が残っていないか
3. 必要なら全体テストを回して HTTP 専用化で他に影響がないか確認する
4. 作業ループ完了時にコミットを切る

次セッションで優先してやること:
- `stdio` / `CTXLEDGER_ENABLE_STDIO` / `TransportMode.BOTH|STDIO` の全体 grep 相当の最終確認
- docs / README の stdio 記述削除
- 必要なら全テスト実行
- 最後に git commit