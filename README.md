# codmon-piyolog

ぴよログのデータフィードから育児記録を取得し、コドモン保護者Web版の「連絡帳」へ自動入力して下書き保存する。

## システム構成

```text
GitHub Actions (月〜金 07:30 JST)
    ↓
Python
    ↓
ぴよログ Feed / GAS API (前日の夕食)
    ↓
データ変換
    ↓
Playwright
    ↓
コドモンWeb
    ↓
下書き保存（朝の連絡帳 + 前日の夕食）
```

## 必要なもの

- **Google Apps Script (GAS)**: ぴよログから夕食データを取得するためのAPIエンドポイントとして使用
- **Google Spreadsheet**: 夕食データを一時保存するためのデータストアとして使用

### GAS / スプレッドシート セットアップ

1. **Google Spreadsheet を作成**
   - 新しいスプレッドシートを作成
   - 1行目にヘッダーを設定: 日付、朝夕食、メニューを最低限用意

2. **GAS プロジェクトを作成**
   - スプレッドシートから「拡張機能」→「Apps Script」でスクリプトエディタを開きコードを作成

3. **GAS を Web アプリとしてデプロイ**
   - 「デプロイ」→「新しいデプロイ」→ 種類「ウェブアプリ」
   - 実行ユーザー: 自分
   - アクセスできるユーザー: 全員（または自分のみ）
   - デプロイ後、URL と API キーを取得

4. **環境変数に設定**
   - `GAS_URL`: デプロイされたウェブアプリのURL
   - `GAS_KEY`: GAS側で設定したAPIキー

## 実行スケジュール

### 朝処理（月〜金 07:30 JST）

- 登園連絡の下書き作成
- 前日の夕食を取得して記録（夕食欄が空の場合）

## セットアップ

1. 依存パッケージのインストール

```bash
uv sync
```

2. ブラウザのインストール

```bash
uv run playwright install chromium
```

3. 環境変数の設定

`.env` ファイルを作成（`.env.sample` をコピー推奨）

```env
CODMON_EMAIL=xx@xxx.com
CODMON_PASSWORD=xxx
PIYOLOG_FEED_URL=https://feed.piyolog.com/v1/feed/24h/fdxx/xx
GAS_URL=https://script.google.com/macros/s/xx/exec
GAS_KEY=xxxx
HEADLESS=false  # ローカルは true/false、本番は true
```

## ローカル実行方法

### 朝処理（月〜金 07:30 JST）

```bash
HEADLESS=false uv run python -m src.main_morning
```

## ブラウザモード

- `HEADLESS=false`: ブラウザ表示（ローカル開発・デバッグ用）
- `HEADLESS=true`: headless mode（GitHub Actions等のCI用、デフォルト）

## GitHub Actions セットアップ

1. ワークフローファイルをプッシュ

```bash
git add .github/workflows/
git commit -m "Add GitHub Actions scheduled workflow"
git push
```

2. GitHub Secrets を設定

リポジトリ → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

以下の5つを追加:
| Name | Value |
|------|-------|
| `CODMON_EMAIL` | Codmonログインメール |
| `CODMON_PASSWORD` | Codmonパスワード |
| `PIYOLOG_FEED_URL` | ぴよログフィードURL |
| `GAS_URL` | GAS Web App URL |
| `GAS_KEY` | GAS APIキー |

3. 確認

**Actions** タブで "Morning Processing" が表示され、スケジュール実行または手動実行可能

## ユニットテスト

```bash
uv run pytest tests/
```

## E2Eテスト（認証情報が必要）

```bash
CODMON_EMAIL=xxx CODMON_PASSWORD=xxx PIYOLOG_FEED_URL=xxx uv run pytest tests/e2e/ -v
```
