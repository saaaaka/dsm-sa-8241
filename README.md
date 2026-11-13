# dsm-sa-8241

DSM・NEIGHBORHOOD・CIBONE・THE TOKYO・MOC-O・コナミスタイル・わこうねっと・ARKnets などの新着を5分おきに確認し、新商品が出たら ntfy でスマホに通知します。監視先は `watch.py` の `SITES` に追加できます。

- 監視プログラム: `watch.py`
- 自動実行の設定: `.github/workflows/watch.yml`
- 確認済み商品のリスト: `seen.json`（自動更新）
- 通知先: リポジトリの Secrets に `NTFY_TOPIC` として登録

## Filmarks 新着通知

Prime Video・Netflix・U-NEXT・ディズニープラスに新しく入った映画・ドラマ・アニメのうち、Filmarks のスコアが 4.0 以上の作品を 1日2回（12時台・19時台）通知します。

- 監視プログラム: `filmarks.py`（サブスクやスコアの基準は冒頭の `SERVICES` / `MIN_SCORE` で変更）
- 自動実行の設定: `.github/workflows/filmarks.yml`
- 確認済み作品のリスト: `filmarks_seen.json`（自動更新）
- 初回は今ある作品を記録するだけで、「監視を開始しました」と1通だけ届きます
