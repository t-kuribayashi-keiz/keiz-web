/**
 * 構造調査用スクリプト(読み取り専用)
 *
 * 「【2026年_月次報告】集客数」スプレッドシートの構造を読み取ってログに出す。
 * 月次転記を自動化するコードを書く前に、どのセルに何が入っているかを確定させるためのもの。
 * 本番の業務シートなので、セル位置を推測したまま書き込みコードを作らない。
 *
 * **このスクリプトは一切書き込みをしない。** setValue系は使っていない。
 *
 * 使い方:
 *   1. 対象スプレッドシートを開く → 拡張機能 → Apps Script
 *   2. このファイルの内容を貼り付けて保存
 *   3. 関数 probeAll を選択して実行(初回は承認を求められる)
 *   4. 「実行ログ」に出た内容をコピーして共有する
 */

// 調べたい月。転記先の行を特定するために使う。
var TARGET_MONTH_LABEL = '2026年8月';

function probeAll() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var out = [];

  out.push('=== スプレッドシート ===');
  out.push(ss.getName() + ' / ' + ss.getId());
  out.push('');

  out.push('=== シート一覧 ===');
  ss.getSheets().forEach(function (sheet, i) {
    out.push(
      i + ': ' + sheet.getName() +
      '  (最終行=' + sheet.getLastRow() + ', 最終列=' + sheet.getLastColumn() +
      ', 非表示=' + sheet.isSheetHidden() + ')'
    );
  });
  out.push('');

  // 転記先: 「年間計画」を名前に含むシートの33〜35行目。
  // 33行目はヘッダー、34行目が2026年8月の想定だが、実際の並びを確認する。
  ss.getSheets().forEach(function (sheet) {
    if (sheet.getName().indexOf('年間計画') === -1) return;
    out.push('=== 転記先候補: ' + sheet.getName() + ' の 32〜36行目 ===');
    out.push(dumpRows_(sheet, 32, 5));
    out.push('');
  });

  // 速報値タブ: 合計値がどこにあるかを見るため、先頭数行と末尾数行を出す。
  ss.getSheets().forEach(function (sheet) {
    var name = sheet.getName();
    if (name.indexOf('速報値') === -1) return;
    out.push('=== 速報値タブ: ' + name + ' ===');
    out.push('-- 先頭3行 --');
    out.push(dumpRows_(sheet, 1, 3));
    var last = sheet.getLastRow();
    if (last > 6) {
      out.push('-- 末尾4行(' + (last - 3) + '〜' + last + '行目) --');
      out.push(dumpRows_(sheet, last - 3, 4));
    }
    out.push('-- 「合計」を含むセル --');
    out.push(findCells_(sheet, '合計'));
    out.push('');
  });

  // ダッシュボード: AG〜AO(33〜41列目)が何の指標かを、ヘッダー行から特定する。
  ss.getSheets().forEach(function (sheet) {
    if (sheet.getName().indexOf('ダッシュボード') === -1) return;
    out.push('=== ダッシュボード: ' + sheet.getName() + ' のAG〜AO列 ===');
    var last = Math.min(sheet.getLastRow(), 40);
    for (var row = 1; row <= last; row++) {
      var values = sheet.getRange(row, 33, 1, 9).getDisplayValues()[0]; // AG=33列目
      if (values.join('').trim() === '') continue;
      var labels = [];
      for (var i = 0; i < values.length; i++) {
        if (String(values[i]).trim() !== '') {
          labels.push(colLetter_(33 + i) + row + '=' + values[i]);
        }
      }
      out.push('  ' + labels.join(' | '));
    }
    out.push('');
    out.push('-- 対象月「' + TARGET_MONTH_LABEL + '」を含むセル --');
    out.push(findCells_(sheet, TARGET_MONTH_LABEL));
    out.push('');
  });

  var text = out.join('\n');
  Logger.log(text);
  return text;
}

/** 指定行から count 行分を、空でないセルだけ「列文字+行=値」で出す。 */
function dumpRows_(sheet, startRow, count) {
  var lastCol = Math.min(sheet.getLastColumn(), 60);
  if (lastCol < 1 || startRow < 1) return '  (データなし)';
  var values = sheet.getRange(startRow, 1, count, lastCol).getDisplayValues();
  var lines = [];
  for (var r = 0; r < values.length; r++) {
    var cells = [];
    for (var c = 0; c < values[r].length; c++) {
      var v = String(values[r][c]).trim();
      if (v !== '') cells.push(colLetter_(c + 1) + (startRow + r) + '=' + v);
    }
    lines.push('  [' + (startRow + r) + '行] ' + (cells.length ? cells.join(' | ') : '(空)'));
  }
  return lines.join('\n');
}

/** シート内で needle を含むセルの位置と値を返す(最大20件)。 */
function findCells_(sheet, needle) {
  var lastRow = Math.min(sheet.getLastRow(), 300);
  var lastCol = Math.min(sheet.getLastColumn(), 60);
  if (lastRow < 1 || lastCol < 1) return '  (データなし)';
  var values = sheet.getRange(1, 1, lastRow, lastCol).getDisplayValues();
  var hits = [];
  for (var r = 0; r < values.length && hits.length < 20; r++) {
    for (var c = 0; c < values[r].length && hits.length < 20; c++) {
      if (String(values[r][c]).indexOf(needle) !== -1) {
        hits.push('  ' + colLetter_(c + 1) + (r + 1) + ' = ' + values[r][c]);
      }
    }
  }
  return hits.length ? hits.join('\n') : '  (該当なし)';
}

/** 1 -> A, 27 -> AA のような列文字に変換する。 */
function colLetter_(index) {
  var letters = '';
  while (index > 0) {
    var rem = (index - 1) % 26;
    letters = String.fromCharCode(65 + rem) + letters;
    index = Math.floor((index - 1) / 26);
  }
  return letters;
}
