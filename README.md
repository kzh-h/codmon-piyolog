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

| サービス | 用途 / 設定 |
|---|---|
| **Cloud Run Jobs** | バッチ処理本体（`codmon-piyolog`）<br>1 CPU / 1 GiB / Timeout 300s / Retries 0 / `HEADLESS=true` |
| **Cloud Scheduler** | 定期実行（`codmon-piyolog-morning`）<br>スケジュール: `30 7 * * 1-5` (JST) |
| **Cloud Build** | Dockerビルド & Jobデプロイ（`cloudbuild.yaml`） |
| **Artifact Registry** | コンテナイメージ保存（`codmon-piyolog`） |
| **Secret Manager** | 実行時環境変数の管理 |
| **Workload Identity Federation** | GitHub ActionsからGCPへのキーレス認証 |

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

```bash
# 朝の連絡帳入力処理を実行 (ブラウザ画面を表示して実行)
HEADLESS=false uv run python -m src.main_morning
```

- `HEADLESS=false`: ブラウザを表示（ローカルデバッグ向け）
- `HEADLESS=true`: ヘッドレス実行（CI / 本番環境向け）

### 4. テスト

```bash
# ユニットテスト (CIで実行されるものと同等)
uv run pytest tests/

# E2Eテスト (実際の認証情報が必要なためローカルのみで実行)
CODMON_EMAIL=xxx CODMON_PASSWORD=xxx PIYOLOG_FEED_URL=xxx uv run pytest tests/e2e/ -v
```

---

## CI/CD (GitHub Actions)

### トリガー仕様

- **Pull Request / main push**:
  - `ruff format --check`, `ruff check`, `mypy`, `pytest` を実行
  - ※ **CIコスト削減（GitHub Actionsの実行時間削減）** のため、ブラウザ起動や外部通信を伴う重いE2Eテストは除外し、高速なユニットテストのみを自動実行しています。
- **main push かつ デプロイ対象ファイルに変更がある場合**:
  - Cloud Buildを起動し、コンテナイメージのビルドおよびCloud Run Jobsのデプロイを実行

> **デプロイ対象**: `src/**`, `main.py`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `cloudbuild.yaml`  
> （※ `README.md` や `tests/**` などの変更では再デプロイはスキップされます）

---

## セキュリティガイドライン

- **認証情報のGitコミット厳禁**: パスワード、APIキー、Feed URL等の機密情報はリポジトリに含めないでください。
- **キーレス認証**: GitHub ActionsからGCPへのアクセスには、永続的なサービスアカウントキーJSONは使わず、Workload Identity Federationを利用しています。