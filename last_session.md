Wording and deployment doc progress まで進めました。

更新した内容:

- `ctxledger/README.md`
  - `v0.1.0` の public messaging を HTTP-first に修正
  - 「MCP 2025-03-26 compatibility」を広く断定する表現を避けて、
    現時点で repository 上で証明されている
    **minimal HTTP MCP surface at `/mcp`**
    という表現に変更
  - `/mcp` での確認済み最小 path:
    - `initialize`
    - `tools/list`
    - `tools/call`
    を明記
  - debug endpoints は MCP protocol surface そのものではないことを明記
  - runtime payload examples に `mcp_rpc` を反映

- `ctxledger/docs/mcp-api.md`
  - docs 冒頭を、現在の evidence に合わせて修正
  - `v0.1.0` で現在証明済みなのは
    **HTTP `/mcp` の minimal MCP path**
    だと明記
  - `tools/list` / `inputSchema` discoverability を、
    stdio 限定ではなく public MCP evidence として書き換え
  - HTTP `/mcp` と
    - workflow-specific HTTP routes
    - operator/action routes
    - debug routes
    を明確に分離
  - 新しく
    **Primary HTTP MCP Path**
    セクションを追加
  - stdio は supporting/development surface として位置づけ直し

- `ctxledger/docs/architecture.md`
  - primary interface を
    - `HTTP-first MCP at /mcp`
    - `stdio as supporting/development surface`
    に変更
  - transport adapter の説明も同様に整理
  - `v0.1.0` acceptance surface として、
    `/mcp` の minimal HTTP MCP path
    (`initialize` / `tools/list` / `tools/call`)
    を明記
  - broader protocol-scope claims は別判断だと整理

- `ctxledger/docs/deployment.md`
  - runtime modes を現実に合わせて修正
  - primary runtime mode を
    **HTTP MCP at `/mcp`**
    と明示
  - `v0.1.0` deployment posture として
    `CTXLEDGER_TRANSPORT=http`
    を中心に再整理
  - `CTXLEDGER_ENABLE_STDIO` は primary release posture ではないことを明記
  - deployment recommendation を
    `/mcp` を canonical MCP endpoint とする方向に修正

- `ctxledger/docs/CHANGELOG.md`
  - Notes に
    **minimal HTTP MCP path at `/mcp` is now evidenced**
    を追記
  - closeout framing が
    “endpoint missing”
    ではなく
    “minimal path proven, broader scope still under evaluation”
    であることを反映

## テスト状態

関連する回帰確認として、少なくとも以下は通過済み前提です。

- `tests/test_server.py`
- `tests/test_cli.py`
- `tests/test_config.py`

結果:
- **198 passed**

## 現在の整理

ここまでで、docs のトーンはかなり揃ってきました。

- `v0.1.0` は **HTTP-first**
- `/mcp` の **minimal HTTP MCP path** は証明済み
- ただし、
  - `resources/list` / `resources/read`
  - broader protocol compatibility wording
  - strict `2025-03-26` claim
  はまだ追加判断が必要
- stdio は repository 内にはまだ残っているが、
  release acceptance の主証拠ではない

## 次にやるべきこと

次の自然な候補は 2 つです。

### 1. `docs/specification.md` の wording を同じトーンに揃える
特に確認したい点:
- `MCP 2025-03-26` をどの強さで主張しているか
- Streamable HTTP を必須扱いしていないか
- current evidence とズレた表現が残っていないか

### 2. HTTP MCP acceptance evidence をさらに厚くする
候補:
- HTTP で `workspace_register`
- HTTP で `workflow_start`
- HTTP で `workflow_checkpoint`
- HTTP で `workflow_resume`
- HTTP で `workflow_complete`
- 必要なら HTTP で `resources/list` / `resources/read`

の直接テスト追加

## 次の引き継ぎ先向けメモ

次に入る人は、まず `docs/specification.md` を見るのがよいです。

今の中心課題はもう
- endpoint existence
ではなく
- **spec wording と acceptance boundary の整合**
です。

特に判断ポイント:
1. `minimal usable remote MCP server` という closeoutで十分か
2. `MCP 2025-03-26 compatible` をそのまま維持するか
3. HTTP resource coverage を `v0.1.0` 必須にするか
4. stdio を release scope から本当に削るなら、
   config / CLI / tests / docs をどこまで落とすか

少なくとも、README / mcp-api / architecture / deployment / changelog は
「`/mcp` の minimal HTTP MCP path は証明済み」
という前提に更新済みです。