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

## ユニットテスト

```bash
uv run pytest tests/
```

## E2Eテスト（認証情報が必要）

```bash
CODMON_EMAIL=xxx CODMON_PASSWORD=xxx PIYOLOG_FEED_URL=xxx uv run pytest tests/e2e/ -v
```