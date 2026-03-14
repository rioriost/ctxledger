この session では、`ctxledger` の MCP サーバ機能そのものではなく、**MCP クライアント上の AI エージェントが `.rules` に従って workflow を記録する運用になっているか** を確認し、その運用前提が README・`.rules`・`last_session.md` に一貫して反映されるよう整理しました。加えて、README の Quick Start を **認証なし** と **認証付き（推奨）** に分け、認証付きでは **bearer token が必須であり、起動・smoke・MCP クライアント設定で同じ token を揃える必要がある** こと、**token の具体的な生成例**、および **`envrcctl secret set` / `envrcctl exec -- ...` を使う optional な運用** まで反映しました。さらに、検証により **Zed は MCP 設定ファイル中の環境変数を展開しない** ことが分かったため、その注意書きも README に追記済みです。最後に、`.rules` を整理し、**`last_session.md` は `ctxledger` 開発時だけの housekeeping** として分離しつつ、**一般の `ctxledger` 利用プロジェクト向け workflow ルール** を独立させました。

この追記ではさらに、**memory 系 tool のロードマップ解釈**を整理しました。現在の文書群から読む限り、`v0.1.0` では `memory_remember_episode` / `memory_search` / `memory_get_context` は意図的に stub または deferred であり、自然な段階整理は次のとおりです。

- `0.2`: episodic memory
  - `memory_remember_episode` が最も直接対応する tool
  - `memory_get_context` は episode ベースの初期形が入る可能性がある
- `0.3`: semantic search
  - `memory_search` が最も直接対応する tool
  - `memory_get_context` は relevance-based retrieval を強める方向で拡張される可能性がある
- `0.4`: hierarchical memory retrieval
  - `memory_get_context` は multi-layer context assembly 的な役割へ拡張されうる

この整理に合わせて、README と `docs/roadmap.md` に **tool-to-version mapping の説明を追加済み**です。また、`.rules` にも terminal workflow guidance を追加し、`workflow_complete` は terminal transition であり、close 後の追加作業は新しい workflow を開始すべきことを明記しました。さらに、README の `Agent workflow usage guidance` と `docs/workflow-model.md` にも、terminal workflow は inspect 対象であって continuation 対象ではなく、close 後の追加作業は新しい workflow または適切な continuation path で扱うべきことを追記済みです。加えて、`docs/architecture.md` にも同趣旨の説明を追加し、completion semantics・checkpoint semantics・terminal resumable status の各節で、terminal workflow の扱いが `.rules` / README / workflow model と整合するようそろえました。あわせて、tests を見直し、terminal workflow guidance に関する既存のテストカバレッジとして **terminal workflow への checkpoint 拒否** と **terminal resume status の確認** は既に存在していることを確認したうえで、さらに **「terminal workflow は inspection 対象で continuation 対象ではない」** ことと、**close 後の追加作業は新しい workflow で進める** ことを、より意図レベルで読める test として `tests/test_workflow_service.py` に追加しました。加えて、`tests/test_postgres_integration.py` にも **terminal resume は inspection 用で continuation ではない** ことを確認する integration test を追加し、PostgreSQL-backed path でも同じ意味づけが保たれることを確認しました。

## この session で完了したこと

- `ctxledger/.rules` を housekeeping 中心の内容から、**2層構造のルール**に整理した
  - `ctxledger` 開発専用 housekeeping
  - `ctxledger` 利用プロジェクト向け一般 workflow rules
- `last_session.md` については、
  - **`ctxledger` 自体を開発する時だけ必要**
  - 一般の利用プロジェクトでは前提にしない
  という位置づけを `.rules` 上で明確にした
- ただし、`ctxledger` 開発時でも下の一般 workflow rules は適用されることを `.rules` に明記した
- 一般 workflow rules から
  - `last_session.md` の存在に依存するよう読める文言
  を外し、repo 内の continuation note や resume artifact は **derived / auxiliary context** 扱いに整理した
- `README.md` に `Agent workflow usage guidance` を追加し、AI エージェントが
  - `workspace_register`
  - `workflow_start`
  - `workflow_resume`
  - `workflow_checkpoint`
  - `workflow_complete`
  を使うべきことを明示した
- README の Quick Start を以下の 2 系統に整理した
  - **認証なし**: `http://127.0.0.1:8080/mcp`
  - **認証付き（推奨）**: `http://127.0.0.1:8091/mcp`
- 認証付き Quick Start に以下を追加・整理した
  - `CTXLEDGER_SMALL_AUTH_TOKEN` を使うこと
  - startup / smoke / MCP client config で **同じ token** を使うこと
  - 不一致時は `401` になること
  - `openssl rand -hex 32`
  - `python -c "import secrets; print(secrets.token_urlsafe(32))"`
    を使った token 生成例
  - `envrcctl` を使う場合の optional な運用
- `envrcctl` については、README 上で次を反映した
  - token は `envrcctl secret set CTXLEDGER_SMALL_AUTH_TOKEN --stdin` で保存する
  - 実行時は `envrcctl exec -- ...` で環境に注入する
  - Zed は MCP 設定ファイル中の環境変数を展開しないため、`envrcctl secret get CTXLEDGER_SMALL_AUTH_TOKEN` などで取得した実 token を `YOUR_TOKEN_HERE` に貼り付ける必要がある
- `.coverage` を削除して作業ツリーのノイズを整理した
- README の手順どおりに Docker Compose で起動し、runtime debug endpoint と MCP workflow smoke を実地確認した
- README の認証付き説明は、`envrcctl` 周りを **optional** として一段下げ、冗長さを減らす方向で整理した

## 確認したこと

- README 上では `ctxledger` は remote HTTP MCP server として動作し、workflow tools として少なくとも以下を公開しています。
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `workflow_complete`
- そのため、Zed などの MCP クライアントから **workflow を記録するためのサーバ側機能は存在する** 状態です。
- 一方で、作業ディレクトリ直下の `.rules` は当初 housekeeping のみで、AI エージェントに対して
  - セッション開始時に workflow を開始/再開すること
  - 作業中に checkpoint を残すこと
  - 作業完了時に workflow を complete すること
  を求めていませんでした。
- このため、**現状の `.rules` に従うだけでは、AI エージェントが workflow 記録フローを実行する保証がない**、という問題を確認しました。
- 検証の結果、**Zed は MCP 設定ファイル中の環境変数を展開しない** ことも確認しました。
- また、`last_session.md` は **`ctxledger` 開発時のブートストラップ補助ファイル**であり、一般の利用プロジェクト向け rules の前提にしてはいけないことも整理しました。

## Workflow handoff identifiers

次セッションの AI エージェントが workflow を再開しやすいよう、以下の識別子をこの note に残せる形を採用します。

- `workspace_id`
- `workflow_instance_id`
- `attempt_id`
- `ticket_id`

現時点では、この session で workflow-aware 運用確認と memory roadmap clarification のために複数の実 ID が得られています。次回以降も、実際に MCP 経由で開始・再開した workflow の値をここへ追記してください。

- workspace / initial MCP tool check
  - `workspace_id`: `98b6d72c-1805-4a55-a872-c1b2ee8bda45`
  - `workflow_instance_id`: `07e227cf-f5dc-4664-ab99-93544d666c93`
  - `attempt_id`: `c8fc7c2f-142d-4229-8104-a9a0175517ff`
  - `ticket_id`: `mcp-tool-check`
- memory roadmap clarification
  - `workspace_id`: `98b6d72c-1805-4a55-a872-c1b2ee8bda45`
  - `workflow_instance_id`: `3c4ee912-8f55-47e3-8e0e-908aa9281de2`
  - `attempt_id`: `19347f06-01ae-4505-96ad-031b17907e69`
  - `ticket_id`: `memory-roadmap-clarification`
- prior session carry-forward
  - `ticket_id`: `rules-workflow-tracking`

## 実地確認結果

README の手順に沿って、以下を実施しました。

- `docker compose -f docker/docker-compose.yml up -d --build`
- `curl http://127.0.0.1:8080/debug/runtime`
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow`
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read`

確認できたこと:

- `ctxledger-postgres` と `ctxledger-server` はともに healthy で起動した
- `/debug/runtime` は HTTP runtime と workflow routes / tools / resources を返した
- workflow smoke では以下が成功した
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `workflow_complete`
- resource read 付き smoke でも以下が成功した
  - `resources/list`
  - `resources/read` for `workspace://{workspace_id}/resume`
  - `resources/read` for `workspace://{workspace_id}/workflow/{workflow_instance_id}`

この確認により、**README の手順どおりに起動し、Zed などの MCP クライアントが同じ MCP surface を使う前提では、workflow 記録と resume/resource 読み出しの最小フローは実際に動作する** ことを確認できました。

実地確認で得られた代表的な識別子:

- workflow smoke 1
  - `workspace_id`: `e163b9d0-8c84-4971-af4e-72a9eedad840`
  - `workflow_instance_id`: `57a41b5e-1b11-4188-8e60-89ef88bc0937`
  - `attempt_id`: `9ad36c3b-bfe1-44fe-b6b7-d9daa15bee06`
  - `ticket_id`: `SMOKE-CTXLEDGER-001`
- workflow smoke 2 with resource read
  - `workspace_id`: `48b4b42a-98a2-4520-a83a-95353234a02e`
  - `workflow_instance_id`: `9a340c21-876f-4365-bbd7-2e5b0af107a6`
  - `attempt_id`: `2bcaa2e7-cbea-4f85-ae48-8147383649d5`
  - `ticket_id`: `SMOKE-CTXLEDGER-001`

## 現在のコード状態に関する補足

- `tests/test_workflow_service.py` の `test_record_resume_projection_fresh_status_fills_missing_timestamps()` は未完成ではなく、既に存在しており、`FRESH` 状態記録時に不足 timestamp を補完することを検証するテストです。
- 同ファイルには未 commit の追加テスト差分があり、少なくとも以下の観点が含まれています。
  - `test_complete_workflow_writes_verify_report_when_requested()`
  - `test_record_resume_projection_fresh_status_fills_missing_timestamps()`
- `.coverage` は削除して、生成物由来のノイズは整理しました。
- 作業ツリー上では `.envrc` が未追跡の可能性があるため、次セッションで扱いを確認すると安全です。
- `.gitignore` や `README.md` に未 commit 差分が残っている可能性があるため、次にまとめて確認するとよいです。

## 今回の主な結論

- **README の手順でサーバを起動して Zed などを接続すれば、workflow 記録機能を使える状態ではある** に留まらず、実際に Docker Compose / debug endpoint / workflow smoke / resource read smoke まで成功した
- ただし、**AI エージェントにその記録を継続的に実行させるには `.rules` の明示的な運用指示が必要**
- `.rules` と README の両方に workflow-aware な guidance を入れたため、エージェント運用ルールはかなり明確になった
- `last_session.md` は **`ctxledger` 開発専用 housekeeping** として扱い、一般の利用プロジェクト向け rules からは分離した方が自然
- 認証付き Quick Start は、**token の決め方・生成・再利用・`401` 条件** を含めて説明できる状態になった
- `envrcctl` は有用だが **optional** 扱いにした方が Quick Start の主線が見えやすい
- **Zed は MCP 設定ファイル中の環境変数を展開しない** ため、`envrcctl` は AI エージェントや shell 実行時の参照には有効でも、Zed の MCP 設定 JSON 中の `YOUR_TOKEN_HERE` を自動置換する用途には使えない
- そのため、Zed では `envrcctl secret get CTXLEDGER_SMALL_AUTH_TOKEN` などで取得した実 token を貼り付ける必要がある
- README 本文は、現時点では大きな破綻はなく、主に `envrcctl` 周りを optional に落としたことでかなり読みやすくなった
- `.rules` も、`ctxledger` 開発専用 housekeeping と一般 workflow rules を分けたことで、目的がかなり明確になった
- memory roadmap については、現時点の資料から
  - `0.2` は `memory_remember_episode`
  - `0.3` は `memory_search`
  - `memory_get_context` は `0.2`〜`0.4` にまたがる段階実装候補
  と読むのが最も自然、という整理に到達した
- したがって、`memory_get_context` が `0.2` で完全実装されると断定するのは避け、**episode-oriented initial form → stronger relevance retrieval → multi-layer context assembly** という進化的な説明に寄せるのが安全
- workflow lifecycle については、`workflow_complete` は **terminal transition** として扱うべきであり、`completed` / `failed` / `cancelled` になった workflow には追加 checkpoint を打てない、という運用ルールを明示化する必要があると確認した
- 今回の失敗は product bug ではなく、**いったん `workflow_complete` した同じ workflow に対して後から checkpoint を追加しようとした運用ミス** によるものだった
- そのため、作業継続の可能性があるうちは `workflow_complete` を早まらせず、close 後に新しい作業が発生したら **新しい workflow を開始する** という guidance を `.rules` に追加するのが妥当、という結論に至った
- tests の観点では、少なくとも以下のカバレッジを確認・補強できた
  - `tests/test_workflow_service.py` に **terminal workflow への checkpoint 拒否**
  - `tests/test_workflow_service.py` に **terminal attempt への checkpoint 拒否**
  - `tests/test_workflow_service.py` と `tests/test_postgres_integration.py` に **`workflow_complete` 後の `resume.resumable_status == TERMINAL`**
  - `tests/test_workflow_service.py` に **terminal resume result は inspection 対象で continuation ではない** ことをより直接に示す test
  - `tests/test_workflow_service.py` に **completed workflow 後の追加作業は新しい workflow で進める** ことをより直接に示す test
  - `tests/test_postgres_integration.py` に **PostgreSQL-backed integration path でも terminal resume は inspection 用で continuation ではない** ことを示す test
- これにより、README / docs で明文化した terminal workflow guidance は、実装挙動レベルだけでなく intent-level の test 名と assertion でも以前より読み取りやすくなり、unit 相当と PostgreSQL integration の両方で意味づけを確認できる状態になった

## 次セッションでやること

1. 実際の Zed などの MCP クライアント上の AI エージェントで、更新後の `.rules` と関連ドキュメントに従った workflow-aware な運用が回るか確認する
2. 実運用 workflow を開始または再開したら、以下をこの note に記録する
   - `workspace_id`
   - `workflow_instance_id`
   - `attempt_id`
   - `ticket_id`
3. `.envrc` の扱いを確認し、必要なら整理する
4. `tests/test_workflow_service.py` と `tests/test_postgres_integration.py` の未 commit 差分を確認し、意図した変更なら commit 対象に含める
5. `README.md` と `.gitignore` の未 commit 差分が残っていれば、必要に応じて整理して commit する