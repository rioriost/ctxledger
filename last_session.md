Phase 3 — Minimal HTTP MCP implementation に着手して、`/mcp` の HTTP MCP surface を実装・検証するところまで進めました。

更新した内容:

- `ctxledger/src/ctxledger/server.py`
  - HTTP runtime に `mcp_rpc` ハンドラが実際に載る構成を確認
  - `/mcp` で JSON-RPC request body を受ける HTTP MCP handler が動作する状態を整理
  - HTTP 経由で `initialize` / `tools/list` / `tools/call` を通す最小 MCP flow が使えることを確認
  - bearer token 認証ありの `/mcp` も同じ経路で動く前提が整っていることを確認

- `ctxledger/tests/test_server.py`
  - HTTP `/mcp` に対する MCP テストを追加
  - 追加した主な確認項目:
    - HTTP `initialize`
    - HTTP `tools/list`
    - HTTP `tools/call`
    - body なし request の 400
    - `/mcp` 以外の path に対する 404
    - auth 有効時の 401 / 成功時の 200
  - debug endpoints 無効時でも `mcp_rpc` が残ることに合わせて既存期待値を修正

## 現在の整理
ここまでで、少なくとも repository 上の「`/mcp` が placeholder ではなく最小 HTTP MCP endpoint として振る舞う」という証拠はかなり強くなりました。

- `/mcp` で `initialize` が返る
- `/mcp` で `tools/list` が返る
- `/mcp` で `tools/call` が返る
- auth 有効時の保護動作も HTTP MCP 側で確認できる
- `tests/test_server.py` は **163 passed**

## 重要な観察
今回の実装・検証で見えたこと:

- 以前 docs で blocker としていた「`/mcp` の usable remote MCP endpoint の証拠がない」という状態は、少なくとも code/test レベルではかなり解消された
- ただし現時点の実装は **JSON-RPC over single HTTP request/response の最小形** であり、
  docs 側で目標としている “MCP 2025-03-26 compatible” や “Streamable HTTP” と完全に一致しているかは、まだ別途整理が必要
- つまり blocker は
  - 「HTTP MCP endpoint がない」
  から
  - 「この最小 HTTP MCP 実装を release acceptance wording とどう整合させるか」
  に少し移った

## 次にやるべきこと
次フェーズ候補はこのあたりです。

1. docs/evidence を現実に合わせて更新
   - `docs/plans/http_mcp_acceptance_remediation_plan.md`
   - `docs/imple_plan_review_0.1.0.md`
   - `docs/v0.1.0_acceptance_evidence.md`

2. 必要なら HTTP `resources/list` / `resources/read` も acceptance に合わせて追加確認

3. `stdio` を本当に `v0.1.0` scope から落とすなら
   - config
   - CLI
   - runtime summary
   - tests
   の整理に進む

## 次の引き継ぎ先向けメモ
次に入るなら、まず docs 側の blocker 記述を再評価するのが自然です。

特に確認したい点:
- 現在の `/mcp` 実装を `v0.1.0` acceptance evidence としてどこまで主張してよいか
- “Streamable HTTP” を `v0.1.0` 必須から外すのか
- それとも `v0.1.0` の required transport wording を下げずに追加実装が必要か

少なくとも、**`/mcp` に HTTP MCP endpoint の証拠がない** という表現は、もうそのままでは維持しにくい状態です。