# dsm-sa-8241

DSM・NEIGHBORHOOD・CIBONE・THE TOKYO・MOC-O・コナミスタイル・わこうねっと・ARKnets などの新着を5分おきに確認し、新商品が出たら ntfy でスマホに通知します。監視先は `watch.py` の `SITES` に追加できます。

- 監視プログラム: `watch.py`
- 自動実行の設定: `.github/workflows/watch.yml`
- 確認済み商品のリスト: `seen.json`（自動更新）
- 通知先: リポジトリの Secrets に `NTFY_TOPIC` として登録

## Filmarks 新着通知

Prime Video・Netflix・U-NEXT・ディズニープラスに新しく入った映画・ドラマ・アニメのうち、Filmarks のスコアが 3.8 以上の作品を、毎日チェックしてため、毎週金曜11時30分にスコア順のランキングで1通通知します。全件は `filmarks_weekly.md` で見られます（通知をタップで開きます）。
すでに他の契約中サブスクで見放題だった作品（別のサブスクに追加されただけのもの）は通知しません。

- 監視プログラム: `filmarks.py`（サブスクやスコアの基準は冒頭の `SERVICES` / `MIN_SCORE` で変更）
- 自動実行の設定: `.github/workflows/filmarks.yml`
- 確認済み作品のリスト: `filmarks_seen.json`（自動更新）
- 韓国のドラマ・映画は通知しません（`EXCLUDE_COUNTRIES` で変更）
- 初回は今ある作品を記録するだけで、「監視を開始しました」と1通だけ届きます
