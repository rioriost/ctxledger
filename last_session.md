今回進めたこと

`0.3.0` memory foundation をさらに進めて、**`memory_search` を episode 直接検索から `memory_items` ベースへ移行**しました。  
前回までに入っていた

- repository / unit-of-work wiring
- episode → memory_item ingest

の上に、今回は **read path** と **integration coverage** をつなげています。

### 1. `src/ctxledger/memory/service.py`
主に `search()` を更新しました。

変更したこと:

- `memory_search` の実装を
  - episode lexical search
  - → **memory-item-based lexical search**
  に切り替えた
- `workspace_id` を UUID として解釈し、
  `memory_item_repository.list_by_workspace_id()` から検索対象を取るようにした
- 検索対象は現状:
  - `content`
  - metadata key/value
- scoring も episode 用から memory item 用へ寄せた
  - `content` match
  - `metadata_keys` match
  - `metadata_values` match

あわせて `SearchResultRecord` も memory-item ベースに広げました。

追加 / 変更されたフィールド:

- `memory_id`
- `workspace_id`
- `episode_id`
- `workflow_instance_id` は optional
- `summary` は memory item の `content` を返す形
- `attempt_id` は現状 `None`
- `metadata`
- `score`
- `matched_fields`

現状の result は、**memory item を返しつつ、summary 互換の surface を維持する過渡形**です。

### 2. `src/ctxledger/runtime/serializers.py`
search response serializer も新 shape に合わせて更新しました。

追加で serialize するようになったもの:

- `memory_id`
- `workspace_id`
- `episode_id`
- optional `workflow_instance_id`

つまり、runtime / MCP 応答でも **memory-item-based result shape** が通るようになりました。

### 3. `tests/test_coverage_targets.py`
既存テストを更新しました。

主に確認するようにしたこと:

- `remember_episode()` 後に作られた `memory_item` が
  `memory_search` の結果として返る
- `search_mode == "memory_item_lexical"`
- `memory_items_considered`
- hit result に
  - `memory_id`
  - `workspace_id`
  - `episode_id`
  が入る
- `matched_fields` が `summary` ではなく **`content`** になる

### 4. `tests/test_mcp_tool_handlers.py`
MCP tool handler 側の期待値も新 shape に更新しました。

変更したこと:

- success message を
  - `Episode-based memory search completed successfully.`
  - → `Memory-item-based lexical search completed successfully.`
- details を
  - `search_mode = "memory_item_lexical"`
  - `memory_items_considered = 1`
  に更新
- serialized result に
  - `memory_id`
  - `workspace_id`
  - `episode_id`
  - `workflow_instance_id = None`
  を期待するようにした
- `matched_fields` は `content`

### 5. `tests/test_postgres_integration.py`
PostgreSQL integration に、**memory search の end-to-end テスト**を追加しました。

追加したテストの流れ:

1. workspace register
2. workflow start
3. `remember_episode()` を 2 件実行
4. `memory_search(query="postgres", workspace_id=...)`
5. 結果が memory item ベースになっていることを確認
6. DB 上でも `memory_items` が作られていることを確認

このテストで確認していること:

- write path:
  - episode persistence
  - episode → memory_item ingest
- read path:
  - workspace-scoped memory item retrieval
  - lexical hit
- details:
  - `search_mode`
  - `memory_items_considered`
  - `results_returned`

## ここまでの意味

これで `0.3.0` の memory path は、少なくとも最初の1本として

- repository contract
- in-memory / PostgreSQL repository
- unit-of-work wiring
- episode persistence
- episode → memory_item ingest
- **memory_items ベース search**
- serializer / MCP surface
- PostgreSQL integration coverage

までつながりました。

つまり、memory subsystem はもう

- 「保存できる器」
- 「投入できる」
- 「検索できる」

ところまで一通り通り始めた状態です。

## 現時点でまだ未完了の部分

現状では、まだ次は未実装です。

- `memory_search` の ranking をより洗練すること
- `attempt_id` / `workflow_instance_id` を search result により豊かに戻すこと
- embedding の生成/保存
- `pgvector` 類似検索
- hybrid ranking
- type / provenance / filter の活用強化

今の `memory_search` は **semantic search ではなく lexical search のまま** です。  
ただし検索対象は episode ではなく `memory_items` に移ったので、embedding / vector 検索へ進むための足場はかなりよくなりました。

## 補足

今回の変更で少なくとも以下は diagnostics が clean でした。

- `src/ctxledger/memory/service.py`
- `src/ctxledger/runtime/serializers.py`
- `tests/test_coverage_targets.py`
- `tests/test_mcp_tool_handlers.py`
- `tests/test_postgres_integration.py`

また、`UnitOfWorkMemoryItemRepository.list_by_episode_id()` に残っていた不自然な error code も、
`NOT_IMPLEMENTED` 系へ揃え直しました。

## workflow / handoff メモ

この session では `last_session.md` の更新までは進めたが、  
**workflow checkpoint に必要な正しい `attempt_id` の再取得と canonical 記録はまだ未実施**です。

以前確認できていた running workflow の `workflow_instance_id` はあるが、  
checkpoint を打つ前に次回はまず resume 情報から **正しい `attempt_id` を確定**すること。

## 次の最短ルート

次はこの順が自然です。

1. workflow resume から `attempt_id` を取り直して checkpoint を打つ
2. search result に必要なら `workflow_instance_id` / `attempt_id` の復元方針を決める
3. embedding 生成・保存 path を入れる
4. `pgvector` 類似検索
5. hybrid ranking

このまま続けるなら、次にやるべきことは  
**canonical workflow checkpoint を打ったうえで、embedding / vector search の前段設計に入ること** です。

続けて、**embedding 保存パスのテスト**まで通しました。

## 今回やったこと

### `tests/test_coverage_targets.py`
追加・修正した内容:

#### 1. `make_settings()` を更新
- `EmbeddingSettings` の default を含めるようにしました
- これで config を使う他のテストにも影響が出にくい状態です

#### 2. local stub embedding 保存テストを追加
- `test_memory_service_persists_local_stub_embedding_after_memory_item_ingest`

確認していること:
- `remember_episode()` 実行
- `memory_item` が 1 件作られる
- `memory_embedding` も 1 件作られる
- `memory_id` が対応する
- `embedding_model`
- vector length
- `content_hash`
が期待どおり

#### 3. external provider 未実装時の継続テストを追加
- `test_memory_service_skips_embedding_persistence_when_external_provider_is_unimplemented`

確認していること:
- external provider descriptor を使っても
- `remember_episode()` 自体は成功
- `memory_item` は保存される
- `memory_embeddings` は保存されない

#### 4. hash テストの修正
- local stub は metadata-aware hash を使うようにしたので
- 期待値も metadata 込みに合わせました

### `src/ctxledger/memory/embeddings.py`
- `LocalStubEmbeddingGenerator` が
  `compute_content_hash(text, metadata)` を使うよう修正

## 実行結果

focused test 実行結果:

- `python -m pytest -q tests/test_coverage_targets.py -k 'embedding or persists_local_stub_embedding or skips_embedding_persistence'`
- **9 passed**

## diagnostics

clean です。

- `ctxledger/tests/test_coverage_targets.py`
- `ctxledger/src/ctxledger/memory/embeddings.py`

## いまの状態

これで embedding まわりは少なくとも

- provider-selectable config
- generator abstraction
- local stub generation
- ingest 時の embedding 保存
- external provider 未実装でも write path 継続
- unit-level verification

まで揃いました。

## 次の最短ルート

次にやる価値が高いのはこのどちらかです。

1. **PostgreSQL integration で local stub embedding 保存を確認**
   - `remember_episode`
   - `memory_embeddings` persistence
   - `list_by_memory_id`
2. **`custom_http` provider の実 HTTP 実装**
   - 外部API選択要件をさらに前に進めるならこちら

私のおすすめは、まず  
**PostgreSQL integration で embedding 保存まで通す**  
です。  
そのあと external HTTP provider 実装に進むと壊れにくいです。

## 今回の追記

上のおすすめどおり、**PostgreSQL integration で local stub embedding 保存まで確認済み**です。

### 確認できたこと
- `tests/test_postgres_integration.py` の
  `test_postgres_memory_remember_episode_persists_local_stub_embedding`
  で検証
- `remember_episode()` 実行後に
  - `memory_item` が workspace 配下に 1 件作成される
  - 対応する `memory_embedding` が 1 件保存される
- 保存された embedding について
  - `memory_id` が memory item と一致
  - `embedding_model == "local-stub-v1"`
  - vector length は `1536`
  - `content_hash` が入る

### 実行結果
- `python -m pytest -q tests/test_postgres_integration.py -k 'persists_local_stub_embedding'`
- **1 passed, 23 deselected**

### diagnostics
- `tests/test_postgres_integration.py`: clean
- `src/ctxledger/memory/embeddings.py`: clean

## 次回の続き方
次は以下のどちらかに進むのが自然です。

1. `custom_http` provider の実 HTTP 実装
2. vector 類似検索 / `pgvector` query path の導入

引き続き土台固めを優先するなら、次は  
**`custom_http` provider 実装前に embedding read/query path の要件整理**  
をしてから進めるとやりやすいです。

## 今回の追記

そのまま続けて、**`custom_http` provider の実 HTTP 実装** と  
**PostgreSQL integration での custom HTTP embedding 保存確認**、さらに  
**`pgvector` 類似検索の repository 土台** まで進めました。

### 1. `src/ctxledger/memory/embeddings.py`
`custom_http` provider の実 HTTP path を追加しました。

入れたこと:
- `urllib` ベースの `POST` 呼び出し
- request payload:
  - `text`
  - `model`
  - `metadata`
- request headers:
  - `Authorization: Bearer ...`
  - `Content-Type: application/json`
  - `Accept: application/json`

response の取り扱い:
- top-level
  - `embedding`
  - `vector`
- nested
  - `data[0].embedding`
  - `data[0].vector`
のどちらでも読めるようにした

model も
- top-level `model`
- nested `data[0].model`
から拾えるようにしました。

error mapping:
- HTTP error
- transport error
- invalid JSON
- embedding vector 不在
を `EmbeddingGenerationError` に正規化しています。

### 2. `tests/test_coverage_targets.py`
`custom_http` generator 向け focused test を追加・更新しました。

確認していること:
- top-level payload から embedding を返せる
- nested `data` payload から embedding を返せる
- HTTP 503 failure を details 付きで返す
- invalid JSON failure を返す
- missing embedding failure を返す

あわせて、既存の external provider の未実装確認は  
`CUSTOM_HTTP` ではなく `OPENAI` 側の未実装確認に寄せ直しました。

### 3. `tests/test_postgres_integration.py`
PostgreSQL integration に、**custom HTTP embedding 保存テスト**を追加しました。

追加したもの:
- `FakeCustomHTTPEmbeddingGenerator`
- `test_postgres_memory_remember_episode_persists_custom_http_embedding`

確認していること:
- `MemoryService` に fake custom HTTP generator を注入
- `remember_episode()` 実行
- generator に期待どおり
  - `text`
  - `metadata`
  が渡る
- PostgreSQL 側に
  - `memory_item`
  - 対応する `memory_embedding`
  が保存される
- 保存された embedding について
  - `embedding_model == "custom-http-test-model"`
  - `content_hash == "custom-http-content-hash"`
  - vector が期待どおり
  になっている

### 4. integration 実行時に分かったこと
最初の custom HTTP integration test は一度失敗しました。

原因:
- PostgreSQL の `memory_embeddings.embedding` は `VECTOR(1536)`
- fake custom HTTP generator は最初 `4` 次元 vector を返していた

つまり、問題は本体実装というより  
**integration test fixture の vector dimension 不整合**でした。

そのため fake generator を `1536` 次元に直して再実行し、通ることを確認しました。

### 5. `src/ctxledger/memory/service.py`
embedding repository contract に、**類似検索用の read path** を追加しました。

追加したもの:
- `MemoryEmbeddingRepository.find_similar(...)`
- `InMemoryMemoryEmbeddingRepository.find_similar(...)`
- `UnitOfWorkMemoryEmbeddingRepository.find_similar(...)`

in-memory 実装は今の段階では
- query embedding と stored embedding の単純な内積ベース
- created_at を tie-break
の最小実装です。

つまり、service/repository contract の上では  
**embedding write だけでなく similarity read の入口**ができました。

### 6. `src/ctxledger/db/postgres.py`
PostgreSQL repository に、**`pgvector` 類似検索 query path** を追加しました。

追加したもの:
- `PostgresMemoryEmbeddingRepository.find_similar(...)`

query の要点:
- `memory_embeddings` と `memory_items` を join
- `me.embedding IS NOT NULL`
- `ORDER BY me.embedding <-> %s::vector ASC`
- `workspace_id` がある場合は
  `mi.workspace_id = %s`
  で workspace scope をかける

つまり、repository 層には少なくとも
- embedding 保存
- `memory_id` 単位の取得
- `pgvector` 類似検索
が揃い始めた状態です。

## 実行結果

focused custom HTTP unit test:
- `python -m pytest -q tests/test_coverage_targets.py -k 'custom_http_embedding_generator or external_embedding_generator_reports_not_implemented_provider_details or external_embedding_generator_requires_api_key_at_runtime'`
- **7 passed**

focused PostgreSQL embedding integration:
- `python -m pytest -q tests/test_postgres_integration.py -k 'persists_custom_http_embedding or persists_local_stub_embedding'`
- **2 passed, 23 deselected**

## diagnostics

clean です。
- `src/ctxledger/memory/embeddings.py`
- `src/ctxledger/memory/service.py`
- `src/ctxledger/db/postgres.py`
- `tests/test_coverage_targets.py`
- `tests/test_postgres_integration.py`

## いまの状態

これで embedding まわりは少なくとも

- provider-selectable config
- generator abstraction
- local stub generation
- `custom_http` 実 HTTP generation
- ingest 時の embedding 保存
- local stub PostgreSQL persistence
- custom HTTP PostgreSQL persistence
- embedding repository similarity contract
- PostgreSQL `pgvector` similarity query の repository 土台

までつながりました。

ただし現時点ではまだ
**`memory_search` 自体は lexical-only のまま**です。

いま repository 層には
- vector search path がある
一方で
- service / MCP surface にはまだ semantic search を統合していない

という段階です。

## 次の最短ルート

次にやる価値が高いのはこの順です。

1. `find_similar()` の focused test を追加
   - in-memory
   - PostgreSQL integration
2. `MemoryService.search()` に semantic path を足す
   - query から embedding 生成
   - similarity candidates を result に反映
3. lexical + vector の hybrid ranking を入れる
4. serializer / MCP details に
   - `search_mode`
   - semantic candidate count
   - hybrid ranking 関連情報
   を広げる

このまま続けるなら、次の最短ルートは  
**`find_similar()` の test を足してから、`memory_search` へ semantic path を統合すること**  
です。

進めました。`memory_search` に **semantic / hybrid の入口**を入れています。

### 今回やったこと
- `src/ctxledger/memory/service.py`
  - `SearchResultRecord` に以下を追加
    - `lexical_score`
    - `semantic_score`
  - `MemoryService.search()` を更新
    - embedding generator と embedding repository がある場合:
      - query から embedding 生成
      - `find_similar()` 実行
      - lexical score と semantic score を合成
    - ない場合:
      - 従来どおり lexical-only fallback
  - details に追加
    - `semantic_candidates_considered`
    - `semantic_query_generated`
    - `semantic_generation_skipped_reason`
  - hybrid 有効時の message / mode を変更
    - `search_mode = "hybrid_memory_item_search"`
    - message: `Hybrid lexical and semantic memory search completed successfully.`

- `tests/test_coverage_targets.py`
  - in-memory search path の既存テスト期待値を更新
  - lexical-only fallback 時の
    - semantic candidate count
    - skipped reason
    - score breakdown
    を確認するように変更

- `tests/test_mcp_tool_handlers.py`
  - hybrid path の message / details 期待値に更新

### 検証したもの
- `python -m pytest -q tests/test_coverage_targets.py -k 'memory_service_records_episodes_and_returns_search_results'`
  - **1 passed**
- `python -m pytest -q tests/test_mcp_tool_handlers.py -k 'build_memory_search_tool_handler_uses_defaults_for_invalid_optional_values'`
  - **1 passed**

### diagnostics
clean です。
- `src/ctxledger/memory/service.py`
- `tests/test_coverage_targets.py`
- `tests/test_mcp_tool_handlers.py`

### 今の状態
いまはこうです。

- repository 層
  - embedding save
  - `find_similar()`
  - PostgreSQL `pgvector` similarity
- service 層
  - lexical fallback
  - semantic candidate retrieval
  - hybrid score 合成の初期版

ただし、まだ **surface 全体の整合** は終わっていません。  
特に次は以下が必要です。

1. `runtime/serializers.py` に `lexical_score` / `semantic_score` を出すか決めて反映
2. 残りの search 関連テストを hybrid-aware に更新
3. PostgreSQL integration で `memory_search` 自体の hybrid path を通す
4. 必要なら ranking を調整

必要ならこのまま次に、  
**serializer と残りの search tests を hybrid 仕様へ揃えるところ**まで続けます。

## 今回の補足
- 現在の作業ツリーには `last_session.md` 以外にも未コミット変更があります
- 変更対象には少なくとも以下が含まれています
  - `src/ctxledger/config.py`
  - `src/ctxledger/db/__init__.py`
  - `src/ctxledger/mcp/tool_handlers.py`
  - `src/ctxledger/memory/service.py`
  - `src/ctxledger/runtime/serializers.py`
  - `src/ctxledger/workflow/service.py`
  - `tests/test_config.py`
  - `tests/test_coverage_targets.py`
  - `tests/test_mcp_tool_handlers.py`
  - `tests/test_postgres_db.py`
  - `tests/test_postgres_integration.py`
  - `tests/test_server.py`

## 次回の最短確認
1. running workflow の resume を再試行して `attempt_id` を確定する
2. `memory_search` の PostgreSQL integration を hybrid 仕様で見直す
3. その結果を `last_session.md` と canonical workflow checkpoint に反映する

## commit 前メモ
- `memory_search` 周辺は lexical-only から hybrid へ進んでいる
- serializer 側には `lexical_score` / `semantic_score` の出力が入っている前提で確認する
- commit するなら、search / embedding / serializer / integration test をまとめた説明的なメッセージが自然

## 今回の追記
- hybrid search の focused validation を追加で実施
- `tests/test_postgres_integration.py -k 'memory_search or find_similar'`
  - **2 passed**
- `tests/test_coverage_targets.py -k 'serialize_search_memory_response or memory_service_records_episodes_and_returns_search_results'`
  - **2 passed**
- `tests/test_mcp_tool_handlers.py -k 'memory_search'`
  - 最初は **1 failed, 1 passed**
  - その後修正して **2 passed**

### 今回分かったこと
不一致は実装ではなく **MCP handler テスト期待値の取り残し** でした。

- `runtime/serializers.py` はすでに
  - `lexical_score`
  - `semantic_score`
  を search result payload に含める
- しかし `tests/test_mcp_tool_handlers.py` の
  `test_build_memory_search_tool_handler_uses_defaults_for_invalid_optional_values`
  では、その2項目をまだ期待していなかった

そのため、テスト期待値に

- `lexical_score: 3.0`
- `semantic_score: 0.0`

を追加して整合させたら通りました。

### diagnostics
- `tests/test_mcp_tool_handlers.py`: clean

### workflow
canonical checkpoint を記録済み:
- `hybrid_search_validation_synced`

### 次の最短ルート
1. `tests/test_mcp_tool_handlers.py` の修正を commit する
2. 必要なら server/search 周辺のもう少し広い suite を回す
3. その後に ranking 調整や PostgreSQL hybrid path の追加確認へ進む

## 今回の追記
- `tests/test_server.py` の `make_settings()` が `EmbeddingSettings` 未対応のままで、
  `AppSettings` 初期化時に `embedding` 必須化へ追従できていないことが、
  広めの suite 実行でまとめて表面化した
- 対応として `tests/test_server.py` に以下を追加
  - `EmbeddingProvider`
  - `EmbeddingSettings`
- `make_settings()` に disabled の embedding default を追加
  - `enabled=False`
  - `provider=EmbeddingProvider.DISABLED`
  - `model="local-stub-v1"`
  - `api_key=None`
  - `base_url=None`
  - `dimensions=None`

### 今回分かったこと
今回の大量失敗は `memory_search` 本体の回帰ではなく、  
**server テスト共通ヘルパーが embedding config 追加へ未追従だったこと** が原因でした。

### 実行結果
- `python -m pytest -q tests/test_server.py`
  - **134 passed**
- `python -m pytest -q tests/test_coverage_targets.py tests/test_mcp_tool_handlers.py tests/test_server.py tests/test_postgres_integration.py`
  - **419 passed in 10.58s**

### diagnostics
- `tests/test_server.py`: clean

### いまの状態
少なくとも今回の対象範囲では以下が揃っています。

- embedding config 追加
- serializer shape
- MCP handler response
- server wrapper expectations
- PostgreSQL integration
- server test scaffolding

つまり、**memory-search 関連の focused 〜 broader validation は一通り通った状態**です。

### 次回の最短ルート
1. compatibility / expectation sync ではなく、`memory_search` の ranking 改善へ戻る
2. semantic behavior の重み付けや hybrid score 調整を進める
3. 必要なら追加 integration / end-to-end coverage を広げる

## 今回の追記
- `src/ctxledger/memory/service.py` の hybrid score weighting を調整
- 変更前
  - `hybrid_score = lexical_score + (semantic_score * 2.0)`
- 変更後
  - lexical hit がある場合:
    - `hybrid_score = lexical_score + semantic_score`
  - lexical hit がない semantic-only result:
    - `hybrid_score = semantic_score * 0.75`

### 今回の意図
- semantic-only result が強く出すぎるのを少し抑える
- lexical evidence を持つ result をより上位にしやすくする
- ただし semantic-only fallback 自体は残す

### 追加した focused test
- `tests/test_coverage_targets.py`
  - `test_memory_service_hybrid_ranking_prefers_lexical_evidence`

この test で固定したこと:
- lexical + semantic の両方に当たる result が
- semantic-only result より上位になること
- semantic-only result の `semantic_score` 自体がやや高くても、
  最終順位は lexical evidence 側が勝つこと

### 実行結果
- `python -m pytest -q tests/test_coverage_targets.py -k 'hybrid_ranking_prefers_lexical_evidence or memory_service_records_episodes_and_returns_search_results'`
  - **2 passed**
- `python -m pytest -q tests/test_mcp_tool_handlers.py -k 'memory_search'`
  - **2 passed**
- `python -m pytest -q tests/test_server.py -k 'memory_search'`
  - **2 passed**
- `python -m pytest -q tests/test_postgres_integration.py -k 'memory_search or find_similar'`
  - **2 passed**

### diagnostics
- `src/ctxledger/memory/service.py`: clean
- `tests/test_coverage_targets.py`: clean

### いまの状態
これで `memory_search` の hybrid path は
- lexical-only fallback
- semantic candidate retrieval
- lexical evidence を優先する初期 weighting
- focused regression coverage

まで揃いました。

### 次回の最短ルート
1. 今回の weighting 調整を commit する
2. 必要なら broader suite に再投入する
3. その後に semantic score の式自体や ranking details の拡張へ進む
