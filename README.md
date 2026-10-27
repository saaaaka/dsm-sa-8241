# dsm-sa-8241

DSM・NEIGHBORHOOD・CIBONE・THE TOKYO の新着を5分おきに確認し、新商品が出たら ntfy でスマホに通知します。監視先は `watch.py` の `SITES` に追加できます。

- 監視プログラム: `watch.py`
- 自動実行の設定: `.github/workflows/watch.yml`
- 確認済み商品のリスト: `seen.json`（自動更新）
- 通知先: リポジトリの Secrets に `NTFY_TOPIC` として登録
