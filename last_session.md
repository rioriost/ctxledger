この session では、`ctxledger` の MCP サーバ機能そのものではなく、**MCP クライアント上の AI エージェントが `.rules` に従って workflow を記録する運用になっているか** を確認し、workflow-aware な handoff 情報を次セッションへ残しやすい形に整理しました。加えて、README に agent workflow usage guidance を追記し、`.coverage` を削除して作業ツリーのノイズも整理しました。さらに、README の手順どおりに Docker Compose で起動し、runtime debug endpoint と MCP workflow smoke を実地確認しました。

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

## この session で反映した方針

`.rules` は、housekeeping だけでなく **workflow-aware な運用ルール** に更新する前提で整理しました。  
含めるべきポイントは以下です。

- セッション開始時
  - `last_session.md` を読む
  - `workspace_register` で workspace を登録/確認する
  - 継続作業なら `workflow_resume`
  - 新規作業なら `workflow_start`
- 作業中
  - 計画確定、コード変更、テスト追加、検証完了などの節目ごとに `workflow_checkpoint`
- 作業完了時
  - `last_session.md` を更新
  - `workflow_complete`
  - descriptive な `git commit`
- resume projection を使うフローでは、その更新も checkpoint / close-out の一部として扱う

## Workflow handoff identifiers

次セッションの AI エージェントが workflow を再開しやすいよう、以下の識別子をこの note に残せる形を採用します。

- `workspace_id`
- `workflow_instance_id`
- `attempt_id`
- `ticket_id`

現時点では、この session で確定した実 ID は未記録です。次回以降、実際に MCP 経由で開始・再開した workflow の値をここへ残してください。

- `workspace_id`: `(record when available)`
- `workflow_instance_id`: `(record when available)`
- `attempt_id`: `(record when available)`
- `ticket_id`: `rules-workflow-tracking`

## この session で追加した README guidance

README には、MCP クライアント上の AI エージェントが `.rules` に従って workflow を記録する運用を明示するため、`Agent workflow usage guidance` を追記しました。主な内容は以下です。

- session start で `last_session.md` を読む
- current repository workspace を登録または確認する
- 継続作業では current workflow を resume する
- 新規作業では new workflow を start する
- planning / code changes / test updates / validation-debugging milestones ごとに progress checkpoint を残す
- session close / task completion 時に `last_session.md` を更新し、workflow を complete する
- handoff のため `workspace_id` / `workflow_instance_id` / `attempt_id` / `ticket_id` を `last_session.md` に残すとよい

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

## 今回の主な結論

- **README の手順でサーバを起動して Zed などを接続すれば、workflow 記録機能を使える状態ではある** に留まらず、実際に Docker Compose / debug endpoint / workflow smoke / resource read smoke まで成功した
- ただし、**AI エージェントにその記録を継続的に実行させるには `.rules` の明示的な運用指示が必要**
- 次セッションでは、`.rules` に加えて **handoff identifiers を `last_session.md` に残す運用** を併用すると、`workflow_resume` の成功率が上がります
- README にも agent workflow usage guidance を入れたため、エージェント運用ルールは `.rules` と README の両方から参照できる状態になりました
- 実地確認ベースでも、remote HTTP MCP server としての最小 workflow 運用フローは成立している

## 次セッションでやること

1. 実際の Zed などの MCP クライアント上の AI エージェントで、`.rules` に従った workflow-aware な運用が回るか確認する
2. 実運用 workflow を開始または再開したら、以下をこの note に記録する
   - `workspace_id`
   - `workflow_instance_id`
   - `attempt_id`
   - `ticket_id`
3. `tests/test_workflow_service.py` の未 commit 差分を確認し、意図した変更なら commit 対象に含める
4. 必要なら README の agent workflow usage guidance をさらに具体化し、workspace / workflow 識別子の残し方をテンプレート化する