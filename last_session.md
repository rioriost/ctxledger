Docs realignment progress まで進めました。

更新した内容:

- `ctxledger/docs/plans/http_mcp_acceptance_remediation_plan.md`
  - 以前の「`/mcp` の HTTP MCP endpoint evidence is still missing」という前提を是正
  - 現在は `/mcp` での最小 HTTP MCP path が repository 上で証明されている前提に更新
  - `initialize` / `tools/list` / `tools/call` が HTTP で確認済みであることを反映
  - blocker classification を
    - **major implementation blocker**
    から
    - **substantially remediated for the minimal HTTP MCP path**
    に更新
  - 残課題を
    - endpoint 不在
    ではなく
    - acceptance wording / remaining scope alignment
    に再設定
  - Phase 5 の test remediation も、未証明扱いではなく
    “minimal HTTP MCP path は test-backed”
    という前提に更新

- `ctxledger/docs/imple_plan_review_0.1.0.md`
  - high-level assessment を更新
  - 現在の main issue を
    - 「HTTP MCP endpoint がない」
    ではなく
    - 「minimal HTTP MCP path はあるが、acceptance boundary の明確化が必要」
    へ変更
  - likely incomplete/unverified を
    - full HTTP MCP closeout coverage
    - HTTP MCP resources if required
    に寄せて整理
  - acceptance criteria section に
    - `/mcp` で `initialize` / `tools/list` / `tools/call`
      が見えていることを反映

- `ctxledger/docs/v0.1.0_acceptance_evidence.md`
  - acceptance matrix を HTTP-first の現実に合わせて更新
  - `MCP workflow tools are callable` を
    - HTTP `/mcp` 最小 path が証明済み
    という評価へ修正
  - `Docker-based local deployment works` も
    - minimal `/mcp` flow の証拠あり
    に更新
  - public surface snapshot に
    - `HTTP MCP route set`
    として `/mcp`
      - `initialize`
      - `tools/list`
      - `tools/call`
    を追加
  - closeout gaps を
    - “HTTP MCP endpoint proof is still missing”
    から
    - “minimal HTTP MCP path is evidenced, but closeout precision is still needed”
    に修正
  - closeout assessment も
    - **not yet proven**
    ではなく
    - **proven for the minimal path**
    に更新

## テスト状態

docs 更新後の確認として、少なくとも関連テストは通っている前提です。

- `tests/test_server.py`
- `tests/test_cli.py`
- `tests/test_config.py`

合計で **198 passed** の状態まで確認済みです。

## 現在の整理

ここまでで状況はかなりはっきりしました。

- `v0.1.0` の主軸は引き続き **HTTP MCP transport**
- ただし main blocker はもう
  **`/mcp` に HTTP MCP endpoint の証拠がない**
  ではない
- 現在の main question は:
  - いま証明済みの **minimal HTTP MCP path**
    (`initialize` / `tools/list` / `tools/call`)
    を `v0.1.0` acceptance としてどこまで主張するか
  - `resources/list` / `resources/read` を HTTP でも必須にするか
  - “MCP 2025-03-26 compatible” や “Streamable HTTP” の wording を
    `v0.1.0` でどう扱うか

## 次にやるべきこと

次フェーズとして自然なのはこのどちらかです。

### 1. release wording / scope decision を詰める
やること:
- `README.md`
- `docs/mcp-api.md`
- `docs/specification.md`
- `docs/deployment.md`
- `docs/architecture.md`
- `docs/CHANGELOG.md`

を、現在の実装 reality に合わせて揃える。

特に決めるべき論点:
- `v0.1.0` は
  - “minimum usable remote MCP server”
  として closeable か
- それとも
  - additional HTTP resource coverage
  - stricter protocol compatibility work
  が必要か

### 2. HTTP MCP coverage をさらに広げる
候補:
- HTTP で `workspace_register`
- HTTP で `workflow_start`
- HTTP で `workflow_checkpoint`
- HTTP で `workflow_resume`
- HTTP で `workflow_complete`
- 必要なら HTTP で `resources/list` / `resources/read`

の直接テストや実証を増やす

## 次の引き継ぎ先向けメモ

次に入る人は、まず「未実装 blocker の是正」は済んだ前提で考えてよいです。

つまり次の中心課題は:

- **endpoint existence**
ではなく
- **acceptance boundary and wording**

です。

特に確認すべきポイント:
1. `tools/call` はすでに generic に通るため、
   required workflow tools それぞれの HTTP-side acceptance evidence をどこまで追加で明示するか
2. `resources/list` / `resources/read` を `v0.1.0` required に残すか
3. `stdio` を本当に release scope から落とすなら、
   config / CLI / docs / tests をどこまで削るか
4. changelog と README のトーンを、
   “not yet evidenced”
   から
   “minimal path evidenced, broader closeout under evaluation”
   に変えるか

少なくとも、**`/mcp` に HTTP MCP endpoint の証拠がない** という記述は、もう維持しない前提で進めてよいです。