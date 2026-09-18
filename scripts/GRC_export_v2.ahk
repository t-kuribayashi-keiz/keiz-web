; ============================================================
; GRC_export_v2.ahk (AutoHotkey v2用)
;
; GRC(検索順位チェックツールGRC)の「項目一覧CSVファイル保存」を自動実行し、
; Google Drive for Desktopの同期フォルダにCSVを保存するスクリプト。
; Windowsタスクスケジューラから定期実行する想定。
;
; 前提:
;   - GRCが既に起動していること(このスクリプトはGRCを起動しない)
;   - AutoHotkey v2 がインストール済みであること
;
; 使う前に必ず書き換えること:
;   - SaveFolder … 実際のGoogle Drive同期フォルダのフルパスに変更する
;
; 動作確認について(重要):
;   このスクリプトは画面のスクリーンショットから設計したもので、実際に
;   このPC上で動かして確認したものではありません。初回は必ず「GRCが起動して
;   いる状態で、このスクリプトを手動でダブルクリックして実行」し、正しく
;   CSVが保存されるか目視で確認してください。エラーが出た場合、v2は
;   分かりやすいエラーメッセージ(行番号付き)が出るので、そのまま教えてください。
; ============================================================

#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2
SetWinDelay 100
SetKeyDelay 50, 50

; ▼▼▼ ここを実際の同期フォルダのパスに書き換えてください ▼▼▼
; 2026-09-18、実際にGRC計測PCで動作確認済みの値: "fs_10.WEB・社内システム\97.データ関連\SEO順位"
; (Google Drive for Desktop側の表示名がドライブ文字ではなくこの名前になっている環境のため、
; 実機ではエクスプローラーのアドレスバーからコピーした実際のパスに置き換えてある)
SaveFolder := "G:\共有ドライブ\GRC_順位データ"
; ▲▲▲ ここまで ▲▲▲

; ファイル名は実行日時を含めて一意にする(例: GRC_2026-09-18_1400.csv)
Stamp := FormatTime(, "yyyy-MM-dd_HHmm")
SavePath := SaveFolder . "\GRC_" . Stamp . ".csv"

; 保存先フォルダが無ければ作る
if !DirExist(SaveFolder)
    DirCreate(SaveFolder)

; --- GRCのウィンドウをアクティブにする ---
if WinExist("検索順位チェックツールGRC")
    WinActivate("検索順位チェックツールGRC")
else {
    MsgBox("GRCが起動していません。先にGRCを起動してから再実行してください。", "GRC自動化エラー", "Icon!")
    ExitApp
}

if !WinWaitActive("検索順位チェックツールGRC",, 10) {
    MsgBox("GRCのウィンドウをアクティブにできませんでした。", "GRC自動化エラー", "Icon!")
    ExitApp
}
Sleep 500

; --- ファイル(F) → 項目一覧CSVファイル保存(L) ---
Send "!f"
Sleep 300
Send "l"
Sleep 500

; --- 「項目一覧CSVファイル保存 出力設定」ダイアログを待つ ---
if !WinWaitActive("項目一覧CSVファイル保存",, 10) {
    MsgBox("「項目一覧CSVファイル保存 出力設定」ダイアログが開きませんでした。`nメニュー操作(Alt+F → L)がGRCの実際のショートカットと合っているか確認してください。", "GRC自動化エラー", "Icon!")
    ExitApp
}
Sleep 300

; 「最新のデータ」が既定で選ばれ、出力する列も前回設定が残っている前提。
; 何も変更せず「次へ」へ進む(次へボタンが既定ボタンであることを期待してEnterを送る)
Send "{Enter}"
Sleep 500

; --- 「名前を付けて保存」ダイアログを待つ ---
if !WinWaitActive("名前を付けて保存",, 10) {
    MsgBox("「名前を付けて保存」ダイアログが開きませんでした。", "GRC自動化エラー", "Icon!")
    ExitApp
}
Sleep 300

; ファイル名欄にフルパスを直接入力する(フォルダ移動が不要になる)
Send "^a"
Sleep 100
SendText SavePath
Sleep 300
Send "{Enter}"
Sleep 1000

; --- 上書き確認が出た場合(通常はファイル名が一意なので出ないはず) ---
if WinExist("確認") {
    WinActivate("確認")
    Sleep 200
    Send "{Enter}"
}

ExitApp
