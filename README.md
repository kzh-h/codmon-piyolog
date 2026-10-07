# codmon-piyolog

ぴよログのデータフィードから育児記録を取得し、コドモン保護者Web版の「連絡帳」へ自動入力して下書き保存するツール。

## 概要

毎朝（平日 07:30 JST）、以下の処理を自動で行います。

1. **ぴよログ Feed**: 当日の育児記録を取得
2. **GAS API**: スプレッドシートから前日の夕食データを取得
3. **データ変換**: 連絡帳の形式にデータを整形
4. **Playwright**: コドモン保護者Web版へログインし、連絡帳に入力して下書き保存

本番環境はGCP（Cloud Run Jobs / Cloud Scheduler）上でコンテナとして稼働し、GitHub ActionsはCI/CD基盤として利用しています。

---

## アーキテクチャ

### 1. 定期実行フロー（本番処理）

```text
Cloud Scheduler (平日 07:30 JST)
    │
    ▼
Cloud Run Jobs (codmon-piyolog)
    │  ├─ Secret Manager (認証情報の注入)
    │  ├─ ぴよログ Feed (育児記録取得)
    │  └─ GAS API (前日夕食データ取得)
    ▼
Playwright (Chromium)
    ▼
コドモンWeb（連絡帳の下書き保存）
```

### 2. CI/CD フロー

```text
Git Push / PR
    │
    ▼
GitHub Actions
    │  ├─ Ruff (format / lint)
    │  ├─ mypy
    │  └─ pytest (ユニットテストのみ)
    │
    ▼ main push かつ 対象ファイル変更時のみ
Workload Identity Federation (GCP認証)
    │
    ▼
Cloud Build (Docker build & push)
    │
    ▼
Artifact Registry ──> Cloud Run Jobs を更新
```

> **Note: GCPへ実行基盤を移行した背景**  
> 当初はGitHub Actionsの定期実行（cron）を利用していましたが、**実行開始に大きなタイムラグ（遅延）が発生し、決まった時間に提出が必要な連絡帳の自動化として実用性に欠けたため**、正確な時刻に起動できるCloud Schedulerへ移行しました。  
> 併せて、Playwright (Chromium) を含むコンテナ実行環境の確保や、機密情報（Codmon認証情報、GAS等のSecret）をCI/CD基盤から分離する目的で、「Cloud Scheduler + Cloud Run Jobs + Secret Manager」の構成を採用しています。

---

## GCP構成・インフラ

- **Project ID**: `codmon-piyologa-auto`
- **Region**: `asia-northeast1`


| サービス                             | 用途 / 設定                                                                                 |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| **Cloud Run Jobs**               | バッチ処理本体（`codmon-piyolog`）<br>1 CPU / 2 GiB / Timeout 300s / Retries 0 / `HEADLESS=true` |
| **Cloud Scheduler**              | 定期実行（`codmon-piyolog-morning`）<br>スケジュール: `30 7 * * 1-5` (JST)                          |
| **Cloud Build**                  | Dockerビルド &amp; Jobデプロイ（`cloudbuild.yaml`）                                              |
| **Artifact Registry**            | コンテナイメージ保存（`codmon-piyolog`）                                                            |
| **Secret Manager**               | 実行時環境変数の管理                                                                              |
| **Workload Identity Federation** | GitHub ActionsからGCPへのキーレス認証                                                             |


### サービスアカウント

- **Cloud Run 実行用**: `797724598266-compute@developer.gserviceaccount.com`（Secret参照権限）
- **Cloud Scheduler 用**: `codmon-piyolog-scheduler@codmon-piyologa-auto.iam.gserviceaccount.com`（Run起動権限）
- **GitHub Actions / Deploy用**: `codmon-piyolog-deployer@codmon-piyologa-auto.iam.gserviceaccount.com`（Cloud Build実行権限）

### Secret Managerで管理する環境変数

- `codmon-email` / `codmon-password`
- `piyolog-feed-url`
- `gas-url` / `gas-key`

---

## 外部連携セットアップ (GAS / スプレッドシート)

前日の夕食データを取得するためのエンドポイントとしてGASを利用します。

1. **Googleスプレッドシート作成**: 1行目に「日付」「朝夕食」「メニュー」を定義
2. **Apps Script作成**: スプレッドシートの「拡張機能」→「Apps Script」からAPIスクリプトを実装
3. **Webアプリとしてデプロイ**:
   - 種類: `ウェブアプリ`
   - 実行ユーザー: `自分`
   - アクセスできるユーザー: `全員`（APIキーで保護）
4. 発行された **URL** と **APIキー** を控えておく（ローカルは`.env`、本番はSecret Managerに登録）

---

## ローカル開発セットアップ

### 1. 環境構築

```bash
# 依存関係のインストール
uv sync

# Playwright用ブラウザのインストール
uv run playwright install chromium
```

### 2. 環境変数設定

`.env.sample` をコピーして `.env` を作成し、値を設定します。

```env
CODMON_EMAIL=your-email@example.com
CODMON_PASSWORD=your-password
PIYOLOG_FEED_URL=https://feed.piyolog.com/v1/feed/...
GAS_URL=https://script.google.com/macros/s/.../exec
GAS_KEY=your-gas-key
HEADLESS=false
```

### 3. 実行方法

実行環境およびブラウザ設定は以下の3パターンに対応しています。

```bash
# パターン1: ローカル開発 (ブラウザ画面を表示して実行)
HEADLESS=false uv run python -m src.main_morning

# パターン2: ローカル開発 (ヘッドレスで実行・GCPと同一設定で再現)
HEADLESS=true uv run python -m src.main_morning

# パターン3: GCP本番環境 (Cloud Run Jobs / Dockerコンテナ内で自動実行)
# ※ K_SERVICE, CLOUD_RUN_JOB, または ENVIRONMENT=gcp を検知して動作
```

- **共通**: ブラウザコンテキストは `locale=ja-JP` / `timezone_id=Asia/Tokyo`（JST）で起動します。実行は 07:30 JST = 22:30 UTC（前日）のため、コンテナのUTC時刻に引きずられて前日の連絡帳が開かれることを防ぎます。DockerfileでもコンテナのTZを `Asia/Tokyo` にしています。
- **ローカル (HEADLESS=false)**: Wayland環境向け引数でブラウザGUIを表示して実行
- **ローカル (HEADLESS=true) / GCP本番**: 完全に同じヘッドレス設定です（`--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, `--disable-blink-features=AutomationControlled`、viewport 1280x1080）。User-Agentは起動したChromiumの実バージョンから `HeadlessChrome` を含まない形で生成して設定します。`pattern_name`（`local_headless` / `gcp_headless`）はログ表示用の違いのみです。

### 4. テスト

```bash
# ユニットテスト (CIで実行されるものと同等)
uv run pytest tests/

# E2Eテスト (実際の認証情報が必要なためローカルのみで実行)
CODMON_EMAIL=xxx CODMON_PASSWORD=xxx PIYOLOG_FEED_URL=xxx uv run pytest tests/e2e/ -v
```

---

## デバッグ・原因調査

実行ごとに成果物ディレクトリ `<base>/runs/<run_id>/` が作られます。

- `run_id`: JSTの `YYYYmmdd-HHMMSS`。GCPでは末尾に `CLOUD_RUN_EXECUTION`（あれば `-task<CLOUD_RUN_TASK_INDEX>`）が付きます。
- `<base>`: ローカルは `<リポジトリ>/tmp`（`.gitignore` 済み）、GCPは `/tmp`。環境変数 `ARTIFACTS_DIR` で変更できます。
- 実行開始時と終了時に、成果物ディレクトリの絶対パスがログに出ます。

```text
tmp/runs/<run_id>/
├── run.log            # 全ログ (DEBUGレベル)
├── events.jsonl       # console / pageerror / requestfailed / 4xx-5xx / 非GETリクエスト / dialog / 画面遷移 (時刻付き)
├── environment.json   # 実行パターン, 起動引数, ブラウザ・Playwrightバージョン, UA, timezone, 現在時刻 等 (認証情報・Feed URLは含まない)
├── summary.json       # 成否, エラー(型/メッセージ/traceback), 各ステップ所要時間, ファイル一覧, GCS URI, 下書き保存の検証結果
├── trace-01.zip       # Playwright trace (パスワード入力より前)
├── trace-02.zip       # Playwright trace (ログイン完了後〜最後まで)
└── checkpoints/       # 主要ステップごとの NN-<name>.png (全画面) / .html / .json (URLとフォーム状態)
```

### トレースの開き方

```bash
uv run playwright show-trace tmp/runs/<run_id>/trace-02.zip
```

または https://trace.playwright.dev にzipをドラッグ＆ドロップします。

> **トレースが分割される理由**  
> Playwrightのtraceはfillした値やDOMスナップショット(入力欄のvalue)にパスワードが残ってしまい、GCSへアップロードされてしまいます。そのためパスワード入力からログイン完了までの間はトレースを一旦止め（`trace-01.zip` を出力）、完了後に再開します（以降が `trace-02.zip`）。既にログイン済みでパスワード入力が無い場合は `trace-01.zip` のみです。ログイン直前〜直後の様子は `checkpoints/` と `events.jsonl` で確認してください。

### GCSへのアップロード

- `GCS_TRACE_BUCKET` を設定すると、実行終了時（成功・失敗とも）に成果物ディレクトリ全体を `gs://<bucket>/runs/<run_id>/` 以下へアップロードします。未設定の場合はスキップします（ローカルでは通常未設定）。
- アップロード先のgs://プレフィックスとCloud ConsoleのURLがログに出ます。
- Cloud Run のサービスアカウントにバケットへの `roles/storage.objectCreator` が必要です。
- ライフサイクルルールの例（30日で削除）:

```bash
cat > lifecycle.json <<'EOF2'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 30}}]}
EOF2
gcloud storage buckets update gs://<bucket> --lifecycle-file=lifecycle.json
```

### GCSからダウンロードして調べる

```bash
gcloud storage cp -r gs://<bucket>/runs/<run_id> ./tmp/runs/
uv run playwright show-trace tmp/runs/<run_id>/trace-02.zip
```

### Cloud Logging での検索

GCPではログが1行JSON（`severity`, `message`, `run_id`, `logger`）で出力されます。`run_id` はGCSのパス名と同じです。

```text
resource.type="cloud_run_job"
jsonPayload.run_id="<run_id>"
```

### GCPの挙動をローカルで再現する

```bash
HEADLESS=true uv run python -m src.main_morning
```

起動引数・viewport・locale/timezone・UAの組み立てがGCPと同一です（実行環境のTZ差を確認したい場合は `TZ=UTC HEADLESS=true ...` で試せます）。成果物は `tmp/runs/<run_id>/` に出力されます。

### 関連する環境変数

| 変数 | 内容 |
| --- | --- |
| `ARTIFACTS_DIR` | 成果物のベースディレクトリ（デフォルト: ローカル `<リポジトリ>/tmp`, GCP `/tmp`） |
| `GCS_TRACE_BUCKET` | 設定時のみ成果物を `gs://<bucket>/runs/<run_id>/` へアップロード |

---

## CI/CD (GitHub Actions)

### トリガー仕様

- **Pull Request / main push**:
  - `ruff format --check`, `ruff check`, `mypy`, `pytest` を実行
  - ※ **CIコスト削減（GitHub Actionsの実行時間削減）** のため、ブラウザ起動や外部通信を伴う重いE2Eテストは除外し、高速なユニットテストのみを自動実行しています。
- **main push かつ デプロイ対象ファイルに変更がある場合**:
  - Cloud Buildを起動し、コンテナイメージのビルドおよびCloud Run Jobsのデプロイを実行

> **デプロイ対象**: `src/**`, `main.py`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`,  `.github/workflows/ci.yml`, `cloudbuild.yaml`  
> （※ `README.md` や `tests/**` などの変更では再デプロイはスキップされます）

---

## セキュリティガイドライン

- **認証情報のGitコミット厳禁**: パスワード、APIキー、Feed URL等の機密情報はリポジトリに含めないでください。
- **キーレス認証**: GitHub ActionsからGCPへのアクセスには、永続的なサービスアカウントキーJSONは使わず、Workload Identity Federationを利用しています。

