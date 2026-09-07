# HPBリボン抽出CSVの置き場

`scripts/hpb_ribbon_extract.py` がローカルで出力する、月号ごとのKPI抽出CSV
(`2026-08.csv` など)を置く。`scripts/hpb_master_writer.py` と
`.github/workflows/hpb-ribbon-kpi.yml` がこれを読んでMasterへ転記する。

- **PDFの復号と抽出はローカルで行う**。リボンPDFは数百MBでメール受領のためGitHub Actionsに
  持ち込めない。ローカルで抽出だけ済ませ、この小さなCSV(数十KB)をコミットする。
- 列: `HPB店舗名, 院名, 年月号, 自社PV, エリア平均PV, 自社CVR, エリア平均CVR, 自社ACR,
  エリア平均ACR, 新規予約数実績, 女性率, 20代未満比率, 20代比率, 30代比率, 40代比率,
  50代以上比率, 集客数_ribbon_ALL, _months`
- 集客数はここには入れない。Master転記時に集客数シートの『◯月HPB(速報値)』当月列から結合する。
- **リポジトリが公開設定のあいだは実データCSVをコミットしない**(店舗別KPIは社内情報)。
