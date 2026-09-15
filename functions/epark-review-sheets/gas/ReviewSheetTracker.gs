/**
 * EPARK口コミシート 提出状況トラッカー
 *
 * 2つの軸を同時に追う:
 *   軸1 現場の提出 … 各院が自院フォルダへ毎月3枚アップしたか
 *   軸2 本社の送付 … 本社スタッフがEPARK担当(溝口さん)へ送り、
 *                     「溝口さん送信済み」フォルダへ格納したか
 *
 * 設計の要点:
 *  - フォルダ名(2026.7 / 旧データ / 溝口さん送信済み …)は院ごとにバラバラなので
 *    月の判定には一切使わない。使うのは **ファイルのアップロード日時(createdTime)** だけ。
 *  - **フォルダの modifiedTime は信用しない。** Driveは子ファイルを足しても親フォルダの
 *    更新日時を必ず更新するとは限らない。実例: 064.小岩蔵前の「溝口さん送信済み」は
 *    フォルダ上は2024-12-19最終更新だが、中身には2026-07-23作成のファイルが入っている。
 *    フォルダ日付で見ると「2024年で止まっている」と誤読する。
 *  - シート枚数: 画像1ファイル = 1枚 / PDF = ページ数。
 *    口コミシートはA4片面仕様なので「ページ数 = シート枚数」で一致する。
 *  - PDFのページ数はバイト列から page tree の `/Type/Pages ... /Count N` を読む。
 *    実データ10本で検証済み(ObjStm・線形化なし、全件この形式)。
 *  - 送付済みかどうかは、そのファイルが入っているフォルダのパスで判定する
 *    (「溝口さん送信済み」配下 = 送付済み / 「溝口さん送信用」配下 = 送付待ち)。
 *  - Driveには一切書き込まない(読み取り専用)。ファイルの移動・削除はしない。
 *
 * 使い方:
 *  1. このコードをスプレッドシートのApps Scriptに貼り付けて保存
 *  2. リロードすると現れる [口コミシート管理] メニュー → [初期セットアップ]
 *  3. [全件スキャン(最初の1回)] を実行
 *  4. [毎月の自動実行をONにする] で月次トリガーを登録
 */

// ============================================================
// 設定
// ============================================================

var DEFAULTS = {
  ROOT_FOLDER_ID: '19KJ9VShEjOJ_pebMhw-3saQvw6P9-d8A', // 「口コミシート・写真」フォルダ
  REQUIRED_PER_MONTH: 3,      // 毎月の必要シート枚数
  MONTHS_TO_SHOW: 13,         // 提出状況シートに出す月数
  EXCLUDE_KEYWORDS: ''        // 院名にこの語(カンマ区切り)を含むフォルダは集計対象外
};

var SHEETS = {
  STATUS: '提出状況',
  SEND: '送付状況',
  DETAIL: '明細',
  CONFIG: '設定',
  DIAG: '_診断',
  STATE: '_状態',
  CACHE: '_キャッシュ',
  LOG: '実行ログ'
};

var LIMITS = {
  MAX_RUNTIME_MS: 4.5 * 60 * 1000,  // これを超えたら中断して続きをトリガー実行
  MAX_PDF_BYTES: 25 * 1024 * 1024,  // これより大きいPDFはページ数解析せず「要確認」
  MAX_DEPTH: 6                      // フォルダ再帰の深さ上限(無限ループ保険)
};

var DETAIL_COLS = 11;
var TZ = 'Asia/Tokyo';

// ============================================================
// メニュー
// ============================================================

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('口コミシート管理')
    .addItem('初期セットアップ', 'setup')
    .addSeparator()
    .addItem('全件スキャン(最初の1回)', 'runFullScan')
    .addItem('中断した処理を再開', 'continueScan')
    .addItem('集計シートだけ作り直す', 'rebuildSummaries')
    .addItem('スキャンを中止', 'stopScan')
    .addSeparator()
    .addItem('PDFページ数取得のテスト', 'testPdfPageCount')
    .addItem('サンプル院で診断スキャン', 'diagnoseSample')
    .addSeparator()
    .addItem('毎月の自動実行をONにする', 'enableMonthlyTrigger')
    .addItem('毎月の自動実行をOFFにする', 'disableMonthlyTrigger')
    .addSeparator()
    .addItem('Chatwork取り込み(バックログ一括)', 'chatworkImportBacklog')
    .addItem('Chatwork取り込み(新着のみ)', 'chatworkImportNew')
    .addItem('Chatwork自動監視をONにする', 'enableChatworkTrigger')
    .addItem('Chatwork自動監視をOFFにする', 'disableChatworkTrigger')
    .addToUi();
}

// ============================================================
// セットアップ
// ============================================================

function setup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var cfg = getOrCreateSheet_(ss, SHEETS.CONFIG);
  if (cfg.getLastRow() === 0) {
    cfg.getRange(1, 1, 5, 3).setValues([
      ['設定項目', '値', '説明'],
      ['ルートフォルダID', DEFAULTS.ROOT_FOLDER_ID, '各院フォルダが並んでいる親フォルダのID'],
      ['必要シート枚数/月', DEFAULTS.REQUIRED_PER_MONTH, 'この枚数以上で「達成」扱い'],
      ['表示月数', DEFAULTS.MONTHS_TO_SHOW, '提出状況シートに何ヶ月分出すか'],
      ['除外キーワード', DEFAULTS.EXCLUDE_KEYWORDS, '院名にこの語を含むフォルダを集計対象外にする(カンマ区切り)']
    ]);
    cfg.getRange(1, 1, 1, 3).setFontWeight('bold').setBackground('#e8eaed');
    cfg.setColumnWidth(1, 160).setColumnWidth(2, 320).setColumnWidth(3, 420);
    cfg.setFrozenRows(1);
  }

  getOrCreateSheet_(ss, SHEETS.STATUS);
  getOrCreateSheet_(ss, SHEETS.SEND);
  initDetailSheet_(getOrCreateSheet_(ss, SHEETS.DETAIL));

  var cache = getOrCreateSheet_(ss, SHEETS.CACHE);
  if (cache.getLastRow() === 0) cache.appendRow(['fileId', 'ページ数', '解析日時', '取得方法']);
  var state = getOrCreateSheet_(ss, SHEETS.STATE);
  if (state.getLastRow() === 0) state.appendRow(['フォルダID', '院名', '処理済み']);
  var log = getOrCreateSheet_(ss, SHEETS.LOG);
  if (log.getLastRow() === 0) log.appendRow(['日時', '種別', '内容']);

  cache.hideSheet();
  state.hideSheet();

  SpreadsheetApp.getUi().alert(
    'セットアップ完了',
    'シートを作成しました。\n\n次に [口コミシート管理] → [全件スキャン(最初の1回)] を実行してください。\n' +
    '院数が多いため、初回は数分〜十数分かかり、途中で自動的に中断・再開を繰り返します。',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

// ============================================================
// スキャン本体
// ============================================================

function runFullScan() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();

  // 前回の中断が残っていると二重に走るので、先に止める
  deleteContinuationTriggers_();

  // ページ数を取得できなかった記録は残さない。解析手段を改善したときに
  // 古い「取得不可」がキャッシュに居座ると、いつまでも再挑戦されないため。
  purgeFailedCache_(ss);

  var root;
  try {
    root = DriveApp.getFolderById(cfg.rootFolderId);
  } catch (e) {
    throw new Error('ルートフォルダを開けません。設定シートのフォルダIDを確認してください: ' + cfg.rootFolderId);
  }

  var stores = [];
  var it = root.getFolders();
  while (it.hasNext()) {
    var f = it.next();
    stores.push([f.getId(), f.getName(), '']);
  }
  stores.sort(function (a, b) { return a[1] < b[1] ? -1 : (a[1] > b[1] ? 1 : 0); });

  var state = getOrCreateSheet_(ss, SHEETS.STATE);
  state.clear();
  state.appendRow(['フォルダID', '院名', '処理済み']);
  if (stores.length > 0) state.getRange(2, 1, stores.length, 3).setValues(stores);

  initDetailSheet_(getOrCreateSheet_(ss, SHEETS.DETAIL));

  PropertiesService.getDocumentProperties().setProperty('scanIndex', '0');
  log_('開始', '全件スキャン開始 / 対象院フォルダ ' + stores.length + '件');

  continueScan();
}

function continueScan() {
  var started = Date.now();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();
  var props = PropertiesService.getDocumentProperties();

  deleteContinuationTriggers_();

  var state = ss.getSheetByName(SHEETS.STATE);
  var lastRow = state ? state.getLastRow() : 0;
  if (lastRow < 2) {
    throw new Error('院フォルダ一覧が空です。先に [全件スキャン(最初の1回)] を実行してください。');
  }
  var stores = state.getRange(2, 1, lastRow - 1, 3).getValues();

  var detail = ss.getSheetByName(SHEETS.DETAIL);
  var pdfCache = loadPdfCache_(ss);
  var newCacheRows = [];

  var idx = parseInt(props.getProperty('scanIndex') || '0', 10);
  var processed = 0;

  while (idx < stores.length) {
    if (Date.now() - started > LIMITS.MAX_RUNTIME_MS) {
      props.setProperty('scanIndex', String(idx));
      flushCache_(ss, newCacheRows);
      scheduleContinuation_();
      log_('中断', idx + '/' + stores.length + '院まで処理。1分後に自動で再開します。');
      return;
    }

    var storeId = stores[idx][0];
    var storeName = String(stores[idx][1]);

    if (isExcluded_(storeName, cfg.excludeKeywords)) { idx++; continue; }

    var rows = [];
    var dupIndex = {};
    try {
      walkFolder_(DriveApp.getFolderById(storeId), storeName, '', 0,
                  rows, pdfCache, newCacheRows, null, dupIndex);
      markDuplicates_(rows, dupIndex);
    } catch (e) {
      log_('エラー', storeName + ' の走査に失敗: ' + e.message);
    }

    if (rows.length > 0) {
      detail.getRange(detail.getLastRow() + 1, 1, rows.length, DETAIL_COLS).setValues(rows);
    }

    state.getRange(idx + 2, 3).setValue('済');
    idx++;
    processed++;
  }

  props.setProperty('scanIndex', String(idx));
  flushCache_(ss, newCacheRows);

  rebuildSummaries();
  log_('完了', '全院のスキャンが完了しました(今回 ' + processed + '院を処理)');
}

/**
 * 院フォルダ配下を再帰的に走査し、ファイル1件=1行のデータを rows に積む。
 */
function walkFolder_(folder, storeName, relPath, depth, rows, pdfCache, newCacheRows, stats, dupIndex) {
  if (depth > LIMITS.MAX_DEPTH) return;
  if (stats) stats.folders++;

  var files = folder.getFiles();
  while (files.hasNext()) {
    var file = files.next();
    var mime = file.getMimeType();

    // ショートカットは実体が別にあるので二重計上しない
    if (mime === 'application/vnd.google-apps.shortcut') {
      if (stats) stats.shortcuts++;
      continue;
    }

    // ゴミ箱に入っているファイルは「提出」ではない。DriveAppのイテレータは
    // ゴミ箱内のファイルも返すことがあるため、明示的に除外する。
    if (file.isTrashed()) {
      if (stats) stats.trashed++;
      continue;
    }

    var created = file.getDateCreated();
    var counted = countSheets_(file, mime, pdfCache, newCacheRows, stats);

    if (stats) {
      stats.files++;
      if (mime.indexOf('image/') === 0) stats.images++;
      else if (mime === 'application/pdf') stats.pdfs++;
      else if (mime.indexOf('application/vnd.google-apps') === 0) stats.native++;
      else stats.others++;

      if (relPath === '') stats.rootLoose++;

      // 同名かつ同サイズのファイルが複数の場所にあれば、移動ではなくコピー運用の疑い
      var key = file.getName() + '|' + file.getSize();
      stats.dupKeys[key] = (stats.dupKeys[key] || 0) + 1;

      if (!stats.oldest || created < stats.oldest) stats.oldest = created;
      if (!stats.newest || created > stats.newest) stats.newest = created;
    }

    rows.push([
      storeName,
      Utilities.formatDate(created, TZ, 'yyyy-MM'),
      file.getName(),
      counted.kind,
      counted.sheets,
      created,
      relPath === '' ? '(直下)' : relPath,
      sendStatusOf_(relPath),
      '',                      // 重複判定はこの院を歩き終えてから markDuplicates_ で入れる
      counted.note,
      file.getUrl()
    ]);

    // 同名かつ同サイズ = 同一シートのコピーとみなす。院内で行番号を控えておく。
    if (dupIndex) {
      var dupKey = file.getName() + '|' + file.getSize();
      if (!dupIndex[dupKey]) dupIndex[dupKey] = [];
      dupIndex[dupKey].push(rows.length - 1);
    }
  }

  var subs = folder.getFolders();
  while (subs.hasNext()) {
    var sub = subs.next();
    walkFolder_(sub, storeName, relPath === '' ? sub.getName() : relPath + ' / ' + sub.getName(),
                depth + 1, rows, pdfCache, newCacheRows, stats, dupIndex);
  }
}

/**
 * 院内で「同名かつ同サイズ」のファイルを重複とみなし、
 * **アップロードが最も古い1件を原本**として残し、それ以外に「重複」の印を付ける。
 *
 * 本社が「溝口さん送信済み」へ格納する運用が、移動ではなくコピーの院・時期があるため
 * (実測: 949件中28件 3%)、これを放置すると同じ口コミシートを二重に数えてしまう。
 *
 * 印を付けるだけで行は消さない。**提出状況は重複を除いて数え、送付状況は重複も含めて数える**
 * (コピー運用の院で送付済み判定が消えないようにするため)。
 */
function markDuplicates_(rows, dupIndex) {
  var marked = 0;
  for (var key in dupIndex) {
    var idxs = dupIndex[key];
    if (idxs.length < 2) continue;

    idxs.sort(function (a, b) {
      var da = rows[a][5], db = rows[b][5];
      return (da instanceof Date ? da.getTime() : 0) - (db instanceof Date ? db.getTime() : 0);
    });

    for (var i = 1; i < idxs.length; i++) {
      rows[idxs[i]][8] = '重複';
      marked++;
    }
  }
  return marked;
}

/**
 * ファイルの置き場所(相対パス)から、本社→溝口さんへの送付状態を判定する。
 * フォルダ名は院ごとに揺れる(「溝口さん送信済み」「溝口さん送信用」など)ので
 * 部分一致で拾い、判別しきれないものは正直に「溝口(要確認)」として出す。
 */
function sendStatusOf_(relPath) {
  if (!relPath) return '';
  var sent = relPath.indexOf('送信済') !== -1 || relPath.indexOf('送付済') !== -1;
  if (sent) return '送付済み';
  var waiting = relPath.indexOf('送信用') !== -1 || relPath.indexOf('送付用') !== -1;
  if (waiting) return '送付待ち';
  if (relPath.indexOf('溝口') !== -1) return '溝口(要確認)';
  return '';
}

/**
 * ファイル1件が口コミシート何枚に相当するかを返す。
 *  - 画像 → 1枚
 *  - PDF  → ページ数(A4片面なのでページ数=枚数)
 *  - それ以外 → 0枚 + 要確認
 */
function countSheets_(file, mime, pdfCache, newCacheRows, stats) {
  if (mime.indexOf('image/') === 0) return { kind: '画像', sheets: 1, note: '' };

  if (mime === 'application/pdf') {
    var id = file.getId();
    if (pdfCache.hasOwnProperty(id)) {
      if (stats) stats.pdfCached++;
      return pdfResult_(pdfCache[id], pdfMethodCache[id] || '');
    }

    var r = pdfPageCountFast_(file, stats);

    pdfCache[id] = r.pages;
    pdfMethodCache[id] = r.method;
    newCacheRows.push([id, r.pages, new Date(), r.method]);

    return pdfResult_(r.pages, r.method);
  }

  if (mime.indexOf('video/') === 0) return { kind: '動画', sheets: 0, note: '要確認(動画)' };
  return { kind: 'その他', sheets: 0, note: '要確認(' + mime + ')' };
}

/**
 * PDFのページ数を取得する。速度がすべてなので2段構え。
 *
 * 1) **末尾8KBだけ** HTTP Range で取得して読む(通常はこれで決まる)
 *    実データ10本で page tree の位置を測ったところ、`/Type/Pages ... /Count N` は
 *    **全件がファイル末尾から621〜939バイト以内**にあった。9.5MBのPDFでも同じ。
 *    実体を丸ごと落とすと1院あたり数十MBのダウンロードになり、
 *    158院のスキャンが数時間コースになる(実測: 4.5分で2〜7院しか進まなかった)。
 * 2) 末尾で読めなければ、従来どおりファイル全体を取得して読む(遅いので最後の手段)。
 *    こちらに落ちても精度は変わらない。
 */
/**
 * PDFのページ数の扱いを1か所にまとめる。
 * 画像XObject数から推定した値は **「推定」と明記して明細に出す**。
 * 断定できない数字を、確定値と同じ顔で並べないための措置。
 */
function pdfResult_(pages, method) {
  if (!(pages > 0)) return { kind: 'PDF', sheets: 0, note: '要確認(ページ数を判定できず)' };
  if (method === 'image') {
    return { kind: 'PDF', sheets: pages, note: '推定(画像数から算出。ページツリーが圧縮されており直接読めず)' };
  }
  return { kind: 'PDF', sheets: pages, note: '' };
}

function pdfPageCountFast_(file, stats) {
  var id = file.getId();

  try {
    var res = UrlFetchApp.fetch(
      'https://www.googleapis.com/drive/v3/files/' + id + '?alt=media&supportsAllDrives=true',
      {
        headers: {
          Authorization: 'Bearer ' + ScriptApp.getOAuthToken(),
          Range: 'bytes=-8192'
        },
        muteHttpExceptions: true
      });
    var code = res.getResponseCode();
    if (code === 206 || code === 200) {
      var n = pdfPageCount_(res.getContentText('ISO-8859-1'));
      // 末尾の切れ端を読んでいるので、常識外れの値は信用しない
      if (n > 0 && n <= 500) {
        if (stats) stats.pdfTail++;
        return { pages: n, method: 'tail' };
      }
    }
  } catch (e) {
    // 握りつぶして全体取得にフォールバック
  }

  try {
    if (file.getSize() <= LIMITS.MAX_PDF_BYTES) {
      var raw = file.getBlob().getDataAsString('ISO-8859-1');

      var full = pdfPageCount_(raw);
      if (full > 0) {
        if (stats) stats.pdfFull++;
        return { pages: full, method: 'full' };
      }

      // ページツリーがObjStm(圧縮オブジェクトストリーム)の中にあり平文では読めない個体。
      // 画像XObjectはストリームを持つのでObjStmに入らず平文で残るため、その個数を代理値にする。
      // 実測で裏付け済み: 正解が分かるPDF40本で一致率100%、
      // さらにPDF1.6の個体4本をローカルで展開して真のページ数と一致することを確認済み。
      var imgs = imageXObjectCount_(raw);
      if (imgs > 0 && imgs <= 500) {
        if (stats) stats.pdfImage++;
        return { pages: imgs, method: 'image' };
      }
    }
  } catch (e2) {
    // 取得できず
  }

  if (stats) stats.pdfFail++;
  return { pages: -1, method: 'fail' };
}

/** 診断用のカウンタ一式 */
function newStats_() {
  return {
    folders: 0, files: 0, images: 0, pdfs: 0, native: 0, others: 0,
    shortcuts: 0, trashed: 0, rootLoose: 0,
    pdfTail: 0, pdfFull: 0, pdfImage: 0, pdfFail: 0, pdfCached: 0,
    dupKeys: {}, oldest: null, newest: null
  };
}

function dupCount_(stats) {
  var n = 0;
  for (var k in stats.dupKeys) if (stats.dupKeys[k] > 1) n += stats.dupKeys[k] - 1;
  return n;
}

/**
 * 全件を流す前の計測用。院リスト全体から等間隔にサンプルを取り、
 * 1院あたりの所要時間と、精度に効く指標(ゴミ箱混入・重複疑い・PDF取得方式の内訳・
 * 画像/PDF/その他の比率)を `_診断` シートに出す。
 *
 * ここで前提が崩れていないことを確認してから全件スキャンに進むこと。
 */
function diagnoseSample() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();
  var sampleSize = 8;

  // 解析手段を変えたあとの再計測で、古い「取得不可」がキャッシュに残っていると
  // 新しい経路が試されず、改善したかどうかが分からなくなる
  purgeFailedCache_(ss);

  var root = DriveApp.getFolderById(cfg.rootFolderId);
  var stores = [];
  var it = root.getFolders();
  while (it.hasNext()) {
    var f = it.next();
    stores.push({ id: f.getId(), name: f.getName() });
  }
  stores.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });

  // 先頭に偏らないよう等間隔に抜く
  var picks = [];
  var step = Math.max(1, Math.floor(stores.length / sampleSize));
  for (var i = 0; i < stores.length && picks.length < sampleSize; i += step) picks.push(stores[i]);

  var sh = getOrCreateSheet_(ss, SHEETS.DIAG);
  sh.clear();
  var header = ['院名', '所要秒', 'フォルダ数', 'ファイル数', '画像', 'PDF', 'Googleネイティブ',
                'その他', 'ゴミ箱除外', 'ショートカット除外', '直下ファイル',
                'PDF末尾取得', 'PDF全体取得', 'PDF画像推定', 'PDF失敗', 'PDFキャッシュ命中',
                '重複除外', '最古アップ', '最新アップ'];
  sh.getRange(1, 1, 1, header.length).setValues([header])
    .setFontWeight('bold').setBackground('#e8eaed').setWrap(true);
  sh.setFrozenRows(1);
  sh.setColumnWidth(1, 220);

  var pdfCache = loadPdfCache_(ss);
  var newCacheRows = [];
  var total = newStats_();
  var totalSec = 0;
  var started = Date.now();
  var done = 0;
  var totalDups = 0;

  for (var p = 0; p < picks.length; p++) {
    // 途中で打ち切られても計測済みの分は残るよう、1院ずつ追記する
    if (Date.now() - started > LIMITS.MAX_RUNTIME_MS) {
      log_('診断', '時間切れのため ' + done + '院で打ち切り');
      break;
    }

    var t0 = Date.now();
    var stats = newStats_();
    var rows = [];
    var dupIndex = {};
    var dups = 0;
    try {
      walkFolder_(DriveApp.getFolderById(picks[p].id), picks[p].name, '', 0,
                  rows, pdfCache, newCacheRows, stats, dupIndex);
      dups = markDuplicates_(rows, dupIndex);
    } catch (e) {
      log_('診断エラー', picks[p].name + ': ' + e.message);
    }
    var sec = (Date.now() - t0) / 1000;
    totalSec += sec;
    done++;
    totalDups += dups;

    sh.appendRow([picks[p].name, sec, stats.folders, stats.files, stats.images, stats.pdfs,
                  stats.native, stats.others, stats.trashed, stats.shortcuts, stats.rootLoose,
                  stats.pdfTail, stats.pdfFull, stats.pdfImage, stats.pdfFail, stats.pdfCached,
                  dups, stats.oldest || '', stats.newest || '']);
    flushCache_(ss, newCacheRows);

    var keys = ['folders','files','images','pdfs','native','others','shortcuts','trashed',
                'rootLoose','pdfTail','pdfFull','pdfImage','pdfFail','pdfCached'];
    for (var k = 0; k < keys.length; k++) total[keys[k]] += stats[keys[k]];
  }

  sh.appendRow(['合計', totalSec, total.folders, total.files, total.images, total.pdfs,
                total.native, total.others, total.trashed, total.shortcuts, total.rootLoose,
                total.pdfTail, total.pdfFull, total.pdfImage, total.pdfFail, total.pdfCached,
                totalDups, '', '']);
  sh.getRange(2, 18, Math.max(1, done), 2).setNumberFormat('yyyy/MM/dd');

  var perStore = done > 0 ? totalSec / done : 0;
  log_('診断',
       done + '院を計測 / 1院あたり平均 ' + perStore.toFixed(1) + '秒 → ' +
       '全' + stores.length + '院なら約 ' + Math.round(perStore * stores.length / 60) + '分。' +
       'PDF 末尾取得' + total.pdfTail + ' / 全体取得' + total.pdfFull +
       ' / 画像推定' + total.pdfImage + ' / 失敗' + total.pdfFail +
       ' / キャッシュ命中' + total.pdfCached +
       ' / ゴミ箱除外' + total.trashed + ' / 重複除外' + totalDups);
}

/**
 * ページ数を取得できなかったPDFの正体を突き止める。
 * 末尾取得・全体取得それぞれで何が見えているかを `_診断PDF` シートに出す。
 * 失敗率が高かった院を対象にする。
 */
function diagnosePdfFailures() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();
  var prefixes = ['043', '064', '113'];
  var maxExamine = 60;
  var maxRecord = 15;

  var root = DriveApp.getFolderById(cfg.rootFolderId);
  var targets = [];
  var it = root.getFolders();
  while (it.hasNext()) {
    var f = it.next();
    for (var i = 0; i < prefixes.length; i++) {
      if (f.getName().indexOf(prefixes[i]) === 0) targets.push(f);
    }
  }

  var pdfs = [];
  for (var t = 0; t < targets.length; t++) collectPdfs_(targets[t], pdfs, 0);

  var sh = getOrCreateSheet_(ss, '_診断PDF');
  sh.clear();
  var header = ['ファイル名', 'サイズ', 'HTTP', '末尾長', '末尾に/Count', '末尾に/Type/Pages',
                '全体に/Count', '全体に/Type/Pages', 'ObjStm', 'XRefStm', 'ヘッダ',
                '画像XObject数', 'URL', '判定'];
  sh.getRange(1, 1, 1, header.length).setValues([header])
    .setFontWeight('bold').setBackground('#e8eaed').setWrap(true);
  sh.setFrozenRows(1);
  sh.setColumnWidth(1, 300);

  var examined = 0, recorded = 0, okCount = 0;
  var started = Date.now();

  for (var p = 0; p < pdfs.length && examined < maxExamine && recorded < maxRecord; p++) {
    if (Date.now() - started > LIMITS.MAX_RUNTIME_MS) break;
    examined++;
    var file = pdfs[p];

    var tail = '', code = 0;
    try {
      var res = UrlFetchApp.fetch(
        'https://www.googleapis.com/drive/v3/files/' + file.getId() + '?alt=media&supportsAllDrives=true',
        { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken(), Range: 'bytes=-8192' },
          muteHttpExceptions: true });
      code = res.getResponseCode();
      tail = res.getContentText('ISO-8859-1');
    } catch (e) {
      code = -1;
    }

    var tailPages = pdfPageCount_(tail);
    if (tailPages > 0 && tailPages <= 500) { okCount++; continue; }  // 成功したものは記録しない

    // ここから先は失敗した個体のみ。全体を取って中身を比べる。
    var full = '';
    try {
      if (file.getSize() <= LIMITS.MAX_PDF_BYTES) {
        full = file.getBlob().getDataAsString('ISO-8859-1');
      }
    } catch (e2) {
      full = '';
    }

    recorded++;
    sh.appendRow([
      file.getName(),
      file.getSize(),
      code,
      tail.length,
      /\/Count\s+\d+/.test(tail),
      /\/Type\s*\/Pages/.test(tail),
      /\/Count\s+\d+/.test(full),
      /\/Type\s*\/Pages/.test(full),
      full.indexOf('ObjStm') !== -1,
      full.indexOf('XRefStm') !== -1 || /\/Type\s*\/XRef/.test(full),
      full.substring(0, 8),
      imageXObjectCount_(full),
      file.getUrl(),
      'ページ数取得不可'
    ]);
  }

  log_('診断PDF',
       'PDF ' + examined + '本を検査 / 成功 ' + okCount + ' / 失敗を ' + recorded + '件記録。' +
       '対象院: ' + prefixes.join(',') + ' → _診断PDF シート参照');
}

/**
 * 画像XObject(`/Subtype /Image`)の個数を数える。
 * 画像XObjectは「ストリームを持つオブジェクト」なのでObjStm(圧縮オブジェクトストリーム)には
 * 入らず、PDF 1.6でも平文のまま残る。スキャン系PDFは1ページ=1画像なので、
 * ページツリーが読めない個体のページ数の代理値になりうる。
 * ただし**仮説なので、正解が分かるPDFで一致率を検証してから使うこと**(validateImageHeuristic)。
 */
function imageXObjectCount_(raw) {
  if (!raw) return 0;
  var m = raw.match(/\/Subtype\s*\/Image/g);
  return m ? m.length : 0;
}

/**
 * 「画像XObject数 = ページ数」という仮説を、**正解が分かっているPDF**で検証する。
 * ページツリーが平文で読める個体(PDF 1.3/1.4)だけを対象にし、
 * `/Count` から得た真のページ数と画像XObject数を突き合わせる。
 * 一致率が十分高くなければ、この代理値は採用しない。
 */
function validateImageHeuristic() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();
  var prefixes = ['023', '043', '064', '113', '134', '158'];
  var maxFiles = 40;

  var root = DriveApp.getFolderById(cfg.rootFolderId);
  var targets = [];
  var it = root.getFolders();
  while (it.hasNext()) {
    var f = it.next();
    for (var i = 0; i < prefixes.length; i++) {
      if (f.getName().indexOf(prefixes[i]) === 0) targets.push(f);
    }
  }

  var pdfs = [];
  for (var t = 0; t < targets.length; t++) collectPdfs_(targets[t], pdfs, 0);

  var sh = getOrCreateSheet_(ss, '_診断画像仮説');
  sh.clear();
  var header = ['区分', 'ファイル名', 'サイズ', 'ヘッダ', '真のページ数(/Count)',
                '画像XObject数', '一致', 'URL'];
  sh.getRange(1, 1, 1, header.length).setValues([header])
    .setFontWeight('bold').setBackground('#e8eaed').setWrap(true);
  sh.setFrozenRows(1);
  sh.setColumnWidth(2, 300);

  var checked = 0, match = 0, unreadable = 0;
  var maxUnreadable = 10;
  var started = Date.now();

  for (var p = 0; p < pdfs.length && (checked < maxFiles || unreadable < maxUnreadable); p++) {
    if (Date.now() - started > LIMITS.MAX_RUNTIME_MS) break;
    var file = pdfs[p];
    if (file.getSize() > LIMITS.MAX_PDF_BYTES) continue;

    var full = '';
    try {
      full = file.getBlob().getDataAsString('ISO-8859-1');
    } catch (e) {
      continue;
    }

    var truth = pdfPageCount_(full);
    var imgs = imageXObjectCount_(full);

    if (truth > 0) {
      // 正解が分かる個体 → 仮説の検証に使う
      if (checked >= maxFiles) continue;
      var ok = (truth === imgs);
      if (ok) match++;
      checked++;
      sh.appendRow(['検証(読める)', file.getName(), file.getSize(), full.substring(0, 8),
                    truth, imgs, ok, file.getUrl()]);
    } else {
      // ページツリーが読めない個体(PDF 1.6系) → 正解を人手で確認するためURLを出す
      if (unreadable >= maxUnreadable) continue;
      unreadable++;
      sh.appendRow(['要正解確認(読めない)', file.getName(), file.getSize(), full.substring(0, 8),
                    '', imgs, '', file.getUrl()]);
    }
  }

  log_('診断画像仮説',
       '正解が分かるPDF ' + checked + '本で検証 / 一致 ' + match + '本 (' +
       (checked ? Math.round(match / checked * 100) : 0) + '%) / ' +
       '読めない個体を ' + unreadable + '本、URL付きで出力(正解を実物で確認すること)');
}

function collectPdfs_(folder, out, depth) {
  if (depth > LIMITS.MAX_DEPTH) return;
  var files = folder.getFiles();
  while (files.hasNext()) {
    var f = files.next();
    if (f.getMimeType() === 'application/pdf' && !f.isTrashed()) out.push(f);
  }
  var subs = folder.getFolders();
  while (subs.hasNext()) collectPdfs_(subs.next(), out, depth + 1);
}

function padRows_(rows, width) {
  for (var i = 0; i < rows.length; i++) {
    while (rows[i].length < width) rows[i].push('');
  }
  return rows;
}

/** 走行中の自動再開チェーンを止める */
function stopScan() {
  deleteContinuationTriggers_();
  log_('停止', '継続トリガーを削除しました(スキャンは再開されません)');
  try {
    SpreadsheetApp.getUi().alert('スキャンの自動再開を停止しました。');
  } catch (e) {
    // エディタから実行した場合はUIが無いので無視する
  }
}

/**
 * 末尾取得方式が正しく動くかを、ページ数が判明している実ファイルで確認する。
 * 結果は実行ログシートに出る。本番スキャンの前に一度走らせること。
 */
function testPdfPageCount() {
  var samples = [
    ['1ISftrq7ArvNAOfYbjXQ8Q-kWfoBddGw2', 3, '小岩蔵前 イーパーク口コミ.pdf (274KB)'],
    ['1RvAsmnWRnIE-6AgOB1q0xf89R1YSsmmT', 1, '口コミシート (46).pdf (139KB)'],
    ['1C5FYyFSRJ0mV78-eXOGg9xFx08istZq6', 1, '岡山駅前 イーパーク 口コミシート.pdf (776KB)'],
    ['1RRIv_Z2-1IV-Y_qRTPqFlF7Pw_7Q_Uw4', 3, '2026.9月 EPARK口コミ (拡張子なし675KB)'],
    ['1VRhjXUr2pITYiDOHM2vB1nU-o9E7PiVC', 3, 'R8.8口コミ.pdf (9.5MB 大きいファイル)']
  ];

  var ok = 0;
  for (var i = 0; i < samples.length; i++) {
    var started = Date.now();
    var got;
    try {
      got = pdfPageCountFast_(DriveApp.getFileById(samples[i][0]));
    } catch (e) {
      got = 'エラー: ' + e.message;
    }
    var pass = (got === samples[i][1]);
    if (pass) ok++;
    log_(pass ? 'テストOK' : 'テストNG',
         samples[i][2] + ' → 期待 ' + samples[i][1] + ' / 実際 ' + got +
         ' (' + (Date.now() - started) + 'ms)');
  }
  log_('テスト結果', ok + '/' + samples.length + ' 一致');
}

/**
 * PDFのバイト列(latin1文字列)からページ数を取り出す。実データ10本で検証済み。
 * 取りこぼしを防ぐため3段構え。どれも駄目なら -1(=要確認)を返し、
 * 0枚として黙って握りつぶさない。
 */
function pdfPageCount_(raw) {
  // 1) page tree のルート: /Type/Pages ... /Count N (間に /MediaBox が挟まる版あり)
  var m = raw.match(/\/Type\s*\/Pages[\s\S]{0,300}?\/Count\s+(\d+)/);
  if (m) return parseInt(m[1], 10);

  // 2) /Count の最大値(入れ子の page tree を想定)
  var all = raw.match(/\/Count\s+(\d+)/g);
  if (all && all.length > 0) {
    var max = 0;
    for (var i = 0; i < all.length; i++) {
      var n = parseInt(all[i].replace(/\/Count\s+/, ''), 10);
      if (n > max) max = n;
    }
    if (max > 0) return max;
  }

  // 3) /Type/Page オブジェクトの個数
  var pages = raw.match(/\/Type\s*\/Page[^s]/g);
  if (pages && pages.length > 0) return pages.length;

  return -1;
}

// ============================================================
// 集計シートの組み立て
// ============================================================

function rebuildSummaries() {
  var agg = aggregateDetail_();
  buildStatusSheet_(agg);
  buildSendSheet_(agg);
}

/**
 * 明細シートを1回だけ読んで、提出(全ファイル)と送付済み(溝口さん送信済み配下)を
 * 院×月で集計する。
 */
function aggregateDetail_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cfg = readConfig_();
  var detail = ss.getSheetByName(SHEETS.DETAIL);

  var months = recentMonths_(cfg.monthsToShow);
  var mIdx = {};
  for (var i = 0; i < months.length; i++) mIdx[months[i]] = i;

  var submitted = {};   // 院 -> 月ごとの提出枚数
  var sent = {};        // 院 -> 月ごとの送付済み枚数
  var lastUpload = {};  // 院 -> 最終アップ日
  var sentLastMonth = {};  // 院 -> 送付済みファイルの最新月(表示範囲外も含む)
  var sentLastDate = {};   // 院 -> 送付済みファイルの最新アップ日
  var waiting = {};     // 院 -> 送付待ち枚数
  var ambiguous = {};   // 院 -> 溝口(要確認)枚数
  var needsCheck = {};  // 院 -> 要確認件数
  var rootLoose = {};   // 院 -> 直下に置かれたファイル数
  var dupCounts = {};   // 院 -> 重複として除外した件数
  var estimated = {};   // 院 -> ページ数を推定で埋めた件数

  function ensure(store) {
    if (submitted[store]) return;
    submitted[store] = zeros_(months.length);
    sent[store] = zeros_(months.length);
    waiting[store] = 0;
    ambiguous[store] = 0;
    needsCheck[store] = 0;
    rootLoose[store] = 0;
    dupCounts[store] = 0;
    estimated[store] = 0;
  }

  var lastRow = detail ? detail.getLastRow() : 0;
  if (lastRow >= 2) {
    var data = detail.getRange(2, 1, lastRow - 1, DETAIL_COLS).getValues();
    for (var r = 0; r < data.length; r++) {
      var store = String(data[r][0]);
      var mk = monthKeyOf_(data[r][1]);
      var sheets = Number(data[r][4]) || 0;
      var created = data[r][5];
      var loc = String(data[r][6]);
      var sendState = String(data[r][7]);
      var isDup = String(data[r][8]) === '重複';
      var note = String(data[r][9]);

      ensure(store);

      if (isDup) dupCounts[store]++;
      if (note.indexOf('推定') === 0) estimated[store]++;

      // 提出枚数は重複(コピー)を除いて数える。二重計上を避けるため。
      if (!isDup && mIdx.hasOwnProperty(mk)) submitted[store][mIdx[mk]] += sheets;

      // 送付済みは重複も含めて数える。コピー運用の院で送付済み判定が消えないようにするため。
      if (sendState === '送付済み') {
        if (mIdx.hasOwnProperty(mk)) sent[store][mIdx[mk]] += sheets;
        if (!sentLastMonth[store] || mk > sentLastMonth[store]) sentLastMonth[store] = mk;
        if (created instanceof Date && (!sentLastDate[store] || created > sentLastDate[store])) {
          sentLastDate[store] = created;
        }
      } else if (sendState === '送付待ち') {
        waiting[store] += sheets;
      } else if (sendState === '溝口(要確認)') {
        ambiguous[store] += sheets;
      }

      if (created instanceof Date && (!lastUpload[store] || created > lastUpload[store])) {
        lastUpload[store] = created;
      }
      if (note !== '') needsCheck[store]++;
      if (loc === '(直下)') rootLoose[store]++;
    }
  }

  return {
    cfg: cfg, months: months,
    storeNames: storeOrder_(ss, cfg),
    submitted: submitted, sent: sent,
    lastUpload: lastUpload, sentLastMonth: sentLastMonth, sentLastDate: sentLastDate,
    waiting: waiting, ambiguous: ambiguous,
    needsCheck: needsCheck, rootLoose: rootLoose,
    dupCounts: dupCounts, estimated: estimated
  };
}

/** 軸1: 現場の提出状況 */
function buildStatusSheet_(a) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreateSheet_(ss, SHEETS.STATUS);
  var months = a.months;
  var req = a.cfg.requiredPerMonth;

  var header = ['院名'].concat(months)
                       .concat(['今月判定', '最終アップ日', '直下放置', '重複除外',
                                'ページ数推定', '要確認', 'フォルダ']);
  var out = [header];

  for (var k = 0; k < a.storeNames.length; k++) {
    var name = a.storeNames[k];
    var counts = a.submitted[name] || zeros_(months.length);
    var cur = counts[months.length - 1];
    out.push([name].concat(counts).concat([
      cur >= req ? '達成' : (cur > 0 ? '不足' : '未提出'),
      a.lastUpload[name] || '',
      a.rootLoose[name] || 0,
      a.dupCounts[name] || 0,
      a.estimated[name] || 0,
      a.needsCheck[name] || 0,
      ''
    ]));
  }

  writeMatrix_(sh, out, months.length, req, months.length + 3);
  linkFolders_(sh, out, header.length);
  log_('集計', '提出状況を更新(' + (out.length - 1) + '院)');
}

/** 軸2: 本社→溝口さんへの送付状況 */
function buildSendSheet_(a) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreateSheet_(ss, SHEETS.SEND);
  var months = a.months;
  var req = a.cfg.requiredPerMonth;
  var thisMonth = months[months.length - 1];

  var header = ['院名'].concat(months)
                       .concat(['送付済み最新月', '送付済み最終アップ日', '未送付疑いの月',
                                '送付待ち枚数', '溝口フォルダ要確認', 'フォルダ']);
  var out = [header];

  for (var k = 0; k < a.storeNames.length; k++) {
    var name = a.storeNames[k];
    var sentCounts = a.sent[name] || zeros_(months.length);
    var subCounts = a.submitted[name] || zeros_(months.length);

    // 提出はあるのに送付済み配下に同月のファイルが無い月(当月は処理途中なので除く)
    var suspects = [];
    for (var i = 0; i < months.length; i++) {
      if (months[i] === thisMonth) continue;
      if (subCounts[i] > 0 && sentCounts[i] === 0) suspects.push(months[i]);
    }

    out.push([name].concat(sentCounts).concat([
      a.sentLastMonth[name] || '(送付済み記録なし)',
      a.sentLastDate[name] || '',
      suspects.join(', '),
      a.waiting[name] || 0,
      a.ambiguous[name] || 0,
      ''
    ]));
  }

  writeMatrix_(sh, out, months.length, req, months.length + 3);
  linkFolders_(sh, out, header.length);
  log_('集計', '送付状況を更新(' + (out.length - 1) + '院)');
}

/**
 * 院×月のマトリクスを書き出し、枚数セルに色をつける。
 * 0=赤 / 1〜(必要枚数-1)=黄 / 必要枚数以上=緑
 */
function writeMatrix_(sh, out, monthCount, req, dateCol) {
  var cols = out[0].length;
  sh.clear();
  sh.clearConditionalFormatRules();
  sh.getRange(1, 1, out.length, cols).setValues(out);

  sh.getRange(1, 1, 1, cols).setFontWeight('bold').setBackground('#e8eaed')
    .setVerticalAlignment('middle').setWrap(true);
  sh.setFrozenRows(1);
  sh.setFrozenColumns(1);
  sh.setColumnWidth(1, 220);

  if (out.length <= 1) return;

  sh.getRange(2, dateCol, out.length - 1, 1).setNumberFormat('yyyy/MM/dd HH:mm');

  // 「送付済み最新月」("2026-08"のような文字列)も同じ罠で自動的に日付化されるので、
  // 表示を安定させるため書式をプレーンテキストに固定する(計算結果自体は影響を受けない)。
  if (dateCol > 2) sh.getRange(2, dateCol - 1, out.length - 1, 1).setNumberFormat('@');

  var range = sh.getRange(2, 2, out.length - 1, monthCount);
  sh.setConditionalFormatRules([
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberGreaterThanOrEqualTo(req).setBackground('#d9ead3').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberBetween(1, req - 1).setBackground('#fff2cc').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenNumberEqualTo(0).setBackground('#f4cccc').setRanges([range]).build()
  ]);
}

function linkFolders_(sh, out, col) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var state = ss.getSheetByName(SHEETS.STATE);
  if (!state || state.getLastRow() < 2 || out.length <= 1) return;

  var sv = state.getRange(2, 1, state.getLastRow() - 1, 2).getValues();
  var idByName = {};
  for (var t = 0; t < sv.length; t++) idByName[String(sv[t][1])] = String(sv[t][0]);

  var links = [];
  for (var u = 1; u < out.length; u++) {
    var fid = idByName[out[u][0]];
    links.push([fid ? '=HYPERLINK("https://drive.google.com/drive/folders/' + fid + '","開く")' : '']);
  }
  sh.getRange(2, col, links.length, 1).setFormulas(links);
}

function storeOrder_(ss, cfg) {
  var state = ss.getSheetByName(SHEETS.STATE);
  var names = [];
  if (state && state.getLastRow() >= 2) {
    var sv = state.getRange(2, 2, state.getLastRow() - 1, 1).getValues();
    for (var s = 0; s < sv.length; s++) {
      var nm = String(sv[s][0]);
      if (nm !== '' && !isExcluded_(nm, cfg.excludeKeywords)) names.push(nm);
    }
  }
  return names;
}

// ============================================================
// トリガー
// ============================================================

function enableMonthlyTrigger() {
  disableMonthlyTrigger();
  ScriptApp.newTrigger('monthlyRun').timeBased().onMonthDay(1).atHour(6).create();
  SpreadsheetApp.getUi().alert('毎月1日の6時台に自動スキャンします。');
}

function disableMonthlyTrigger() {
  var ts = ScriptApp.getProjectTriggers();
  for (var i = 0; i < ts.length; i++) {
    if (ts[i].getHandlerFunction() === 'monthlyRun') ScriptApp.deleteTrigger(ts[i]);
  }
}

function monthlyRun() { runFullScan(); }

function scheduleContinuation_() {
  ScriptApp.newTrigger('continueScan').timeBased().after(60 * 1000).create();
}

function deleteContinuationTriggers_() {
  var ts = ScriptApp.getProjectTriggers();
  for (var i = 0; i < ts.length; i++) {
    if (ts[i].getHandlerFunction() === 'continueScan') ScriptApp.deleteTrigger(ts[i]);
  }
}

// ============================================================
// ユーティリティ
// ============================================================

function readConfig_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEETS.CONFIG);
  var cfg = {
    rootFolderId: DEFAULTS.ROOT_FOLDER_ID,
    requiredPerMonth: DEFAULTS.REQUIRED_PER_MONTH,
    monthsToShow: DEFAULTS.MONTHS_TO_SHOW,
    excludeKeywords: []
  };
  if (!sh || sh.getLastRow() < 2) return cfg;

  var vals = sh.getRange(2, 1, sh.getLastRow() - 1, 2).getValues();
  for (var i = 0; i < vals.length; i++) {
    var key = String(vals[i][0]).trim();
    var val = vals[i][1];
    if (key === 'ルートフォルダID' && String(val).trim() !== '') cfg.rootFolderId = String(val).trim();
    if (key === '必要シート枚数/月' && Number(val) > 0) cfg.requiredPerMonth = Number(val);
    if (key === '表示月数' && Number(val) > 0) cfg.monthsToShow = Number(val);
    if (key === '除外キーワード' && String(val).trim() !== '') {
      cfg.excludeKeywords = String(val).split(',')
        .map(function (s) { return s.trim(); })
        .filter(function (s) { return s !== ''; });
    }
  }
  return cfg;
}

function isExcluded_(storeName, keywords) {
  if (!keywords || keywords.length === 0) return false;
  for (var i = 0; i < keywords.length; i++) {
    if (storeName.indexOf(keywords[i]) !== -1) return true;
  }
  return false;
}

function recentMonths_(n) {
  var out = [];
  var now = new Date();
  for (var i = n - 1; i >= 0; i--) {
    var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    out.push(Utilities.formatDate(d, TZ, 'yyyy-MM'));
  }
  return out;
}

/**
 * 明細シートの「対象月」列を安全に読む。
 *
 * バグの経緯: `walkFolder_` は "2026-09" のような文字列を書き込んでいるつもりだったが、
 * セル書式が「自動」だとGoogleスプレッドシート側が日付として自動解釈し、
 * 実際に保存される値は Date(2026-09-01) になっていた(表示上は「2026-9-1」)。
 * 結果、集計側の文字列一致(`mIdx.hasOwnProperty(mk)`)が常に外れ、
 * **全158院・全13ヶ月が「未提出」と誤判定される**という実害が出た(2026-09-12 本番で発覚)。
 *
 * 幸い保存されているDateは年月として正しい値なので、再スキャンせずここで復元できる。
 * `initDetailSheet_` 側でも対象月列を書式「@」(プレーンテキスト)に固定し、
 * 今後の書き込みで同じ変換が起きないようにしてある。
 */
/** 一時デバッグ用: 明細のB列が実際どう保存されているかを確かめる */
function debugMonthKeyRun() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var detail = ss.getSheetByName(SHEETS.DETAIL);
  var lastRow = detail.getLastRow();
  var vals = detail.getRange(2, 1, lastRow - 1, 11).getValues();
  var cfg = readConfig_();
  var months = recentMonths_(cfg.monthsToShow);
  var mIdx = {};
  for (var i = 0; i < months.length; i++) mIdx[months[i]] = i;

  var lines = [];
  var found = 0;
  for (var r = 0; r < vals.length && found < 5; r++) {
    if (String(vals[r][0]).indexOf('馬橋') === -1) continue;
    var raw = vals[r][1];
    var mk = monthKeyOf_(raw);
    var isDup = String(vals[r][8]) === '重複';
    lines.push(vals[r][2] + ' | raw=' + JSON.stringify(raw) + ' | isDate=' + (raw instanceof Date) +
               ' | mk=' + mk + ' | inMIdx=' + mIdx.hasOwnProperty(mk) + ' | isDup=' + isDup +
               ' | sheets=' + vals[r][4]);
    found++;
  }
  lines.push('mIdx keys = ' + Object.keys(mIdx).join(','));
  log_('デバッグ2', lines.join(' || '));
}

function monthKeyOf_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, TZ, 'yyyy-MM');
  return String(v);
}

function zeros_(n) {
  var a = [];
  for (var i = 0; i < n; i++) a.push(0);
  return a;
}

function initDetailSheet_(sh) {
  sh.clear();
  sh.getRange(1, 1, 1, DETAIL_COLS).setValues([[
    '院名', '対象月', 'ファイル名', '種別', 'シート枚数', 'アップ日時',
    '置き場所', '送付区分', '重複', '要確認', 'URL'
  ]]);
  sh.getRange(1, 1, 1, DETAIL_COLS).setFontWeight('bold').setBackground('#e8eaed');
  sh.setFrozenRows(1);
  sh.setColumnWidth(1, 200).setColumnWidth(3, 300).setColumnWidth(7, 240).setColumnWidth(9, 220);

  // 「対象月」列("2026-09"のような文字列)を書式「自動」のままにすると、
  // Googleスプレッドシートが日付として解釈して勝手に変換してしまう
  // (実例: "2026-09" → 実体はDate(2026-09-01)、表示は「2026-9-1」)。
  // 集計側の文字列一致がこれで全滅した実害があったため、列全体をプレーンテキスト固定にする。
  sh.getRange('B:B').setNumberFormat('@');
}

/**
 * ページ数が取れなかった(0以下)キャッシュ行を捨てる。
 * 解析手段を足したときに、古い「取得不可」が残っていると再挑戦されない。
 */
function purgeFailedCache_(ss) {
  var sh = ss.getSheetByName(SHEETS.CACHE);
  if (!sh || sh.getLastRow() < 2) return;

  var vals = sh.getRange(2, 1, sh.getLastRow() - 1, 4).getValues();
  var keep = [];
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][0]) !== '' && Number(vals[i][1]) > 0) keep.push(vals[i]);
  }
  var removed = vals.length - keep.length;
  if (removed === 0) return;

  sh.getRange(2, 1, vals.length, 4).clearContent();
  if (keep.length > 0) sh.getRange(2, 1, keep.length, 4).setValues(keep);
  log_('キャッシュ', 'ページ数を取得できなかった ' + removed + '件を破棄(次回再挑戦する)');
}

/** fileId -> ページ数の取得方法('tail' / 'full' / 'image' / 'fail')。loadPdfCache_ で埋まる */
var pdfMethodCache = {};

function loadPdfCache_(ss) {
  var sh = ss.getSheetByName(SHEETS.CACHE);
  var cache = {};
  pdfMethodCache = {};
  if (!sh || sh.getLastRow() < 2) return cache;
  var vals = sh.getRange(2, 1, sh.getLastRow() - 1, 4).getValues();
  for (var i = 0; i < vals.length; i++) {
    var id = String(vals[i][0]);
    if (id === '') continue;
    cache[id] = Number(vals[i][1]);
    pdfMethodCache[id] = String(vals[i][3] || '');
  }
  return cache;
}

function flushCache_(ss, rows) {
  if (!rows || rows.length === 0) return;
  var sh = ss.getSheetByName(SHEETS.CACHE);
  sh.getRange(sh.getLastRow() + 1, 1, rows.length, 4).setValues(rows);
  rows.length = 0;
}

function getOrCreateSheet_(ss, name) {
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  return sh;
}

function log_(kind, message) {
  try {
    var sh = getOrCreateSheet_(SpreadsheetApp.getActiveSpreadsheet(), SHEETS.LOG);
    sh.appendRow([new Date(), kind, message]);
  } catch (e) {
    // ログ失敗で本処理を止めない
  }
}

// ============================================================================
// Chatwork連携: Googleドライブにアップロードできなかった提出を拾う
//
// 現場は基本Googleドライブへ直接アップロードするが、不具合等でできない場合、
// 本部宛のChatworkルーム(EPARK運用グループ)へ添付ファイルで送ってくる運用がある。
// 従来は本部スタッフがそれを見て手動でDriveへアップロードしていた。ここではそれを
// 自動化する: Chatwork APIでルームの添付ファイルを取得し、メッセージ本文から院名を
// 特定して、該当する院フォルダへ直接アップロードする。
//
// 設計の要点:
//  - トークンは Script Properties の CHATWORK_API_TOKEN から読む。
//    **このリポジトリにもチャットにも一切書かない。** 値が漏れたら失効・再発行が必要。
//  - 院名の特定は「メッセージ本文に、既知の院フォルダ名(数字接頭辞を除いた部分)が
//    部分一致するか」で行う。一致しない・複数の院に一致する場合は自動処理せず
//    「Chatwork取り込み要確認」シートに出して人手判断に回す(絶対に推測で確定しない)。
//  - 取り込み済みのfile_idは _Chatwork取込済 シートに記録し、同じファイルを二重に
//    アップロードしない。
//  - ダウンロードはChatwork APIの create_download_url=1 で得られる署名付きURLを使う。
//    ブラウザ操作は一切不要(この方式に至った経緯: ブラウザの添付プレビューは
//    別ドメインのiframeで、ダウンロードボタンのクリックが自動操作から安定しなかった)。
// ============================================================================

var CHATWORK = {
  ROOM_ID: '97417946',           // EPARK 運用グループ
  API_BASE: 'https://api.chatwork.com/v2',
  TOKEN_PROP: 'CHATWORK_API_TOKEN',
  STATE_PROP: 'chatworkLastUploadTimeUnix', // 新着監視の基準点(Unix秒)
  IMPORTED_SHEET: '_Chatwork取込済',
  REVIEW_SHEET: 'Chatwork取り込み要確認',
  MAX_RUNTIME_MS: 4.5 * 60 * 1000 // OCRフォールバックが重いため、6分の実行時間上限より早めに打ち切る
};

function chatworkToken_() {
  var t = PropertiesService.getScriptProperties().getProperty(CHATWORK.TOKEN_PROP);
  if (!t) {
    throw new Error(
      'CHATWORK_API_TOKENが未設定です。Apps Scriptエディタの[プロジェクトの設定]→' +
      '[スクリプト プロパティ]で設定してください(値はここにも他のどこにも書かない)。');
  }
  return t;
}

function chatworkFetch_(path, params) {
  var qs = '';
  if (params) {
    var parts = [];
    for (var k in params) parts.push(k + '=' + encodeURIComponent(params[k]));
    qs = '?' + parts.join('&');
  }
  var res = UrlFetchApp.fetch(CHATWORK.API_BASE + path + qs, {
    headers: { 'X-ChatWorkToken': chatworkToken_() },
    muteHttpExceptions: true
  });
  var code = res.getResponseCode();
  if (code === 429) throw new Error('Chatwork APIレート制限(429)。時間を置いて再実行してください。');
  if (code >= 400) throw new Error('Chatwork APIエラー ' + code + ': ' + res.getContentText().slice(0, 300));
  if (code === 204) return null;
  return JSON.parse(res.getContentText());
}

/** ルーム内の全ファイル一覧を取得する。since指定でそれ以降のみに絞る。 */
function chatworkListFiles_(sinceUnix) {
  var params = {};
  if (sinceUnix) params.upload_time_since = String(sinceUnix);
  var files = chatworkFetch_('/rooms/' + CHATWORK.ROOM_ID + '/files', params) || [];
  files.sort(function (a, b) { return a.upload_time - b.upload_time; });
  return files;
}

/** 直近100件のメッセージを取得し、message_id -> 本文 のマップを作る(院名特定に使う)。 */
function chatworkMessageBodies_() {
  var msgs = chatworkFetch_('/rooms/' + CHATWORK.ROOM_ID + '/messages', { force: '1' }) || [];
  var map = {};
  for (var i = 0; i < msgs.length; i++) map[msgs[i].message_id] = msgs[i].body || '';
  return map;
}

/**
 * 直近100件の一括取得に無いメッセージを、message_id指定で1件だけ取りに行く。
 * バックログ(3週間以上前)はほぼ確実にここを通る。取れなければnullを返す。
 */
function chatworkFetchMessage_(messageId) {
  try {
    var msg = chatworkFetch_('/rooms/' + CHATWORK.ROOM_ID + '/messages/' + messageId, null);
    return msg ? (msg.body || '') : null;
  } catch (e) {
    return null;
  }
}

/** Chatwork独自のタグ([To:...]や[rp aid=...]等)を取り除き、読める本文だけにする。 */
function chatworkStripMarkup_(body) {
  return String(body || '')
    .replace(/\[To:\d+\][^\n]*\n?/g, '')
    .replace(/\[rp aid=\d+[^\]]*\]/g, '')
    .replace(/\[qt\][\s\S]*?\[\/qt\]/g, '')
    .replace(/\[picon:\d+\]/g, '')
    .replace(/\[[^\]]+\]/g, '');
}

/**
 * 明細シートと同じ「院フォルダ一覧」(_状態シート)を使って、本文中に含まれる院名を特定する。
 * まず完全一致(核の部分文字列一致)を試し、0件ならOCR等の表記ゆれ(全角スペース混入・
 * 「接骨院」等の一般名詞の挿入・1〜2文字のOCR誤読)を許容するあいまい一致にフォールバックする
 * (2026-09-14、栗林さん指摘の実例: 「下赤塚口接骨院」→下赤塚北口、「都色駅前整骨院」→都賀駅前 等)。
 * 一致0件・複数件はここでは決めない(呼び出し側で要確認に回す)。
 */
function chatworkMatchStore_(bodyText, storeList) {
  var matches = chatworkMatchStoreExact_(bodyText, storeList);
  if (matches.length === 0) matches = chatworkMatchStoreFuzzy_(bodyText, storeList);
  return matches; // 0件 or 1件が理想。2件以上残るのは真に紛らわしいケース
}

function chatworkMatchStoreExact_(bodyText, storeList) {
  var matches = [];
  for (var i = 0; i < storeList.length; i++) {
    var core = chatworkStoreCore_(storeList[i].name);
    if (core.length >= 2 && bodyText.indexOf(core) !== -1) {
      matches.push(storeList[i]);
    }
  }
  return chatworkPreferLongestMatch_(matches);
}

// 一致判定の際に無視してよい、院名によく混入する一般名詞(長い順に並べること)。
var CHATWORK_GENERIC_FACILITY_WORDS_ = [
  'はりきゅう整骨院', '鍼灸整骨院', '接骨鍼灸院', '整骨院', '接骨院', '鍼灸院', '整体院'
];

/** 空白(全角含む)と一般名詞を取り除き、あいまい一致の比較に使える形にする。 */
function chatworkFuzzyNormalize_(s) {
  var t = String(s || '').replace(/[\s　]/g, '');
  for (var i = 0; i < CHATWORK_GENERIC_FACILITY_WORDS_.length; i++) {
    t = t.split(CHATWORK_GENERIC_FACILITY_WORDS_[i]).join('');
  }
  return t;
}

/** 2文字列間の編集距離(レーベンシュタイン距離)。 */
function chatworkEditDistance_(a, b) {
  var m = a.length, n = b.length;
  var prev = [];
  for (var j = 0; j <= n; j++) prev.push(j);
  for (var i = 1; i <= m; i++) {
    var cur = [i];
    for (var j = 1; j <= n; j++) {
      cur.push(Math.min(
        prev[j] + 1,
        cur[j - 1] + 1,
        prev[j - 1] + (a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1)
      ));
    }
    prev = cur;
  }
  return prev[n];
}

/**
 * needle(院名の核)がhaystack(本文/OCRテキスト)の中に、多少の誤読・脱字があっても
 * 含まれているかを判定する。needleが短すぎる場合は誤爆を避けるため完全一致のみ。
 */
function chatworkFuzzyContains_(haystack, needle) {
  if (needle.length < 3) return haystack.indexOf(needle) !== -1;
  if (haystack.indexOf(needle) !== -1) return true;

  var maxDist = needle.length <= 6 ? 1 : 2;

  // 事前フィルタ: needleの文字がhaystackにほとんど無いなら、編集距離では届かないので早期に諦める
  // (155院ぶん総当たりで編集距離計算をすると重いため)。
  var hitChars = 0;
  for (var k = 0; k < needle.length; k++) {
    if (haystack.indexOf(needle.charAt(k)) !== -1) hitChars++;
  }
  if (hitChars < needle.length - maxDist) return false;

  for (var len = needle.length - 1; len <= needle.length + 1; len++) {
    if (len < 1) continue;
    for (var i = 0; i + len <= haystack.length; i++) {
      if (chatworkEditDistance_(haystack.substr(i, len), needle) <= maxDist) return true;
    }
  }
  return false;
}

function chatworkMatchStoreFuzzy_(bodyText, storeList) {
  var haystack = chatworkFuzzyNormalize_(bodyText);
  var matches = [];
  for (var i = 0; i < storeList.length; i++) {
    var needle = chatworkFuzzyNormalize_(chatworkStoreCore_(storeList[i].name));
    if (needle.length >= 3 && chatworkFuzzyContains_(haystack, needle)) {
      matches.push(storeList[i]);
    }
  }
  return chatworkPreferLongestMatch_(matches);
}

/** 複数一致した場合、最も長い(=最も具体的な)院名を優先する。 */
function chatworkPreferLongestMatch_(matches) {
  if (matches.length > 1) {
    matches.sort(function (a, b) {
      return chatworkStoreCore_(b.name).length - chatworkStoreCore_(a.name).length;
    });
    var top = chatworkStoreCore_(matches[0].name).length;
    matches = matches.filter(function (m) {
      return chatworkStoreCore_(m.name).length === top;
    });
  }
  return matches;
}

/**
 * 送信者名 → 担当院(名前の断片)の対応表。
 * 2026-09-14、栗林さんから共有された8月/9月の組織図(2608月組織図.pdf/2609月組織図.pdf)をもとに作成。
 * 断片は実際の院名(_状態シート)の部分文字列になるように選んである。
 * 複数院を掛け持ちしている人、8月→9月で担当院が変わった人は候補を複数入れてある。
 * その場合は院を1つに決め打ちせず、要確認シートに候補として書き残すだけにする
 * (chatworkMatchStoreBySender_の呼び出し側を参照)。
 */
var CHATWORK_SENDER_STORE_FRAGMENTS_ = {
  '二上舞夢': ['新狭山'],
  '井上雅裕': ['北仙台'],
  '伊熊孝弥': ['新浜松'],
  '内田芙雅': ['池下エキナカ'],
  '前川優弥': ['市川南口'],
  '前田智紀': ['都賀駅前', '八街駅前'],
  '宮前拓也': ['二和向台駅前'],
  '山形笙': ['琴似本通り'],
  '進藤陸': ['千歳', '恵庭', '南平岸'],
  '春日脩河': ['南平岸', '札幌北円山'],
  '櫻井海': ['新松戸クラシオン'],
  '立川上総': ['鎌ヶ谷西口', '柏の葉キャンパス'],
  '緒方光': ['四街道もねの里'],
  '野田将吾': ['二条駅前'],
  '鈴木秋磨': ['上板橋'],
  '葉計勇太': ['新潟松崎', '新潟こうど'],
  '土屋翔': ['石田'],
  '山本剛大': ['南流山駅前'],
  '廣野裕哉': ['郡山若葉'],
  '根口巧': ['八千代大和田', '成田公津の杜'],
  '江戸悠真': ['梅郷'],
  '海老原祐太': ['町田'],
  '辰拓弥': ['東深井'],
  // 8月は2院兼務(池袋・下赤塚)、9月は池袋のみ。本文だけでは月が分からないため両方を候補として残す
  '佐藤生都': ['池袋', '下赤塚']
};

/**
 * 本社スタッフ(特定の院を持たない)の一覧。ルール・テンプレート・全院共通の連絡等を
 * このルームに投稿するが、それ自体が特定院の提出物になることは無いため、
 * 院名マッチングの対象から外す(2026-09-14、栗林さん指示)。
 */
var CHATWORK_STAFF_EXCLUDED_ = ['志田猛', '矢動丸小桃', '栗林司'];

function chatworkIsExcludedStaff_(senderName) {
  return CHATWORK_STAFF_EXCLUDED_.indexOf(chatworkNormalizeSenderName_(senderName)) !== -1;
}

/** Chatworkの表示名から、休暇注記([休:...]等)や全角/半角スペースを取り除いた素の氏名にする。 */
function chatworkNormalizeSenderName_(name) {
  return String(name || '')
    .replace(/【[^】]*】/g, '')
    .replace(/[\s　]/g, '')
    .trim();
}

function chatworkStoreCore_(name) {
  return String(name).replace(/^\d+\.?\s*/, '').trim();
}

/**
 * 本文に院名が無かった場合のフォールバック。送信者名から想定院を絞り込む。
 * 候補が1院に決まったときだけ「マッチ」として返す(呼び出し側でそのまま自動アップロードに使われる)。
 * 2院以上残る場合はここでは決めず、空配列を返す代わりに候補一覧をそのまま返す
 * (呼び出し側で「1件なら確定、2件以上なら要確認+候補メモ」を判断する)。
 */
function chatworkMatchStoreBySender_(senderName, storeList) {
  var key = chatworkNormalizeSenderName_(senderName);
  var fragments = CHATWORK_SENDER_STORE_FRAGMENTS_[key];
  if (!fragments) return [];

  var found = [];
  for (var i = 0; i < fragments.length; i++) {
    for (var j = 0; j < storeList.length; j++) {
      var core = chatworkStoreCore_(storeList[j].name);
      if (core.indexOf(fragments[i]) !== -1 && found.indexOf(storeList[j]) === -1) {
        found.push(storeList[j]);
      }
    }
  }
  return found;
}

function chatworkStoreList_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var state = ss.getSheetByName(SHEETS.STATE);
  if (!state || state.getLastRow() < 2) {
    throw new Error('_状態シートが空です。先にEPARKトラッカーの全件スキャンを1度実行してください。');
  }
  var vals = state.getRange(2, 1, state.getLastRow() - 1, 2).getValues();
  var out = [];
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][1]) !== '') out.push({ id: String(vals[i][0]), name: String(vals[i][1]) });
  }
  return out;
}

function chatworkImportedIds_(ss) {
  var sh = getOrCreateSheet_(ss, CHATWORK.IMPORTED_SHEET);
  if (sh.getLastRow() === 0) {
    sh.appendRow(['file_id', '院名', 'ファイル名', 'DriveファイルID', '取込日時']);
    sh.hideSheet();
  }
  var ids = {};
  if (sh.getLastRow() >= 2) {
    var vals = sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues();
    for (var i = 0; i < vals.length; i++) ids[String(vals[i][0])] = true;
  }
  return { sheet: sh, ids: ids };
}

function chatworkReviewSheet_(ss) {
  var sh = getOrCreateSheet_(ss, CHATWORK.REVIEW_SHEET);
  if (sh.getLastRow() === 0) {
    sh.appendRow(['検知日時', 'file_id', '送信者', 'メッセージ本文(抜粋)', 'ファイル名', '状態', 'メモ']);
    sh.getRange(1, 1, 1, 7).setFontWeight('bold').setBackground('#e8eaed');
    sh.setFrozenRows(1);
    sh.setColumnWidth(4, 320).setColumnWidth(5, 220);
  }
  return sh;
}

/**
 * 要確認シートに既に載っているfile_idの集合。再実行のたびに同じ行を重複追加しないため
 * (chatworkImportNewは30分おきに走るので、これが無いと未解決の1件が無限に増殖する)。
 */
function chatworkReviewedIds_(sh) {
  var ids = {};
  if (sh.getLastRow() >= 2) {
    var vals = sh.getRange(2, 2, sh.getLastRow() - 1, 1).getValues();
    for (var i = 0; i < vals.length; i++) ids[String(vals[i][0])] = true;
  }
  return ids;
}

/**
 * Chatworkルームの添付ファイルを取り込む中核処理。
 * sinceUnix を渡すとそれ以降の分だけ、渡さなければ(0扱い)取れる範囲を全部見る
 * (バックログ一括取り込み用。Chatwork APIのfiles一覧は件数上限があるため、
 *  巨大なバックログの場合は複数回に分けて実行が必要になることがある)。
 */
function chatworkImport_(sinceUnix) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var storeList = chatworkStoreList_();
  var bodies = chatworkMessageBodies_();
  var files = chatworkListFiles_(sinceUnix);
  var imported = chatworkImportedIds_(ss);
  var reviewSheet = chatworkReviewSheet_(ss);
  var reviewedIds = chatworkReviewedIds_(reviewSheet);

  var done = 0, skipped = 0, excluded = 0, needsReview = 0, maxUploadTime = sinceUnix || 0;
  var startTime = Date.now();
  var timedOut = false;

  for (var i = 0; i < files.length; i++) {
    // OCRフォールバックは1件あたり数十秒かかることがあるため、6分の実行時間上限に
    // 引っかかる前に安全に打ち切り、続きは1分後のトリガーで自動的に再開する。
    if (Date.now() - startTime > CHATWORK.MAX_RUNTIME_MS) {
      timedOut = true;
      break;
    }
    var f = files[i];
    if (f.upload_time > maxUploadTime) maxUploadTime = f.upload_time;

    if (imported.ids[String(f.file_id)]) { skipped++; continue; }
    if (reviewedIds[String(f.file_id)]) { skipped++; continue; }
    if (chatworkIsExcludedStaff_(f.account ? f.account.name : '')) { excluded++; continue; }

    var rawBody = bodies[f.message_id];
    if (rawBody === undefined) {
      // 直近100件の一括取得には無い(バックログで頻発)。message_id指定で個別に取りに行く。
      rawBody = chatworkFetchMessage_(f.message_id);
    }
    if (rawBody === null || rawBody === undefined) {
      reviewSheet.appendRow([new Date(), f.file_id, f.account ? f.account.name : '',
                             '(本文取得不可: メッセージが見つかりません)', f.filename, '要確認', '']);
      needsReview++;
      continue;
    }
    var bodyText = chatworkStripMarkup_(rawBody);
    var matches = chatworkMatchStore_(bodyText, storeList);
    var senderNote = '';

    if (matches.length === 0) {
      // 本文に院名が無い場合、組織図由来の送信者→院マップで絞り込む(前田さん等の実提出で頻発)。
      var senderMatches = chatworkMatchStoreBySender_(f.account ? f.account.name : '', storeList);
      if (senderMatches.length === 1) {
        matches = senderMatches;
      } else if (senderMatches.length > 1) {
        senderNote = '送信者候補: ' + senderMatches.map(function (s) { return s.name; }).join(' / ');
      }
    }

    // 本文・送信者のどちらでも1院に決まらない場合、最後の手段としてファイル自体をOCRし、
    // 手書きされた院名が読み取れないか試す(栗林さん指示、2026-09-14)。
    // 巨大ファイル(既知の例: 47MB超のPDF)はOCR変換が長時間かかり6分の実行時間を食い潰すため、
    // 既存のPDFページ数解析と同じ25MBの上限でスキップし、要確認へ回す。
    var blob = null;
    var ocrText = '';
    var ocrTooLarge = Number(f.filesize) > 25 * 1024 * 1024;
    if (matches.length !== 1 && !ocrTooLarge && chatworkLooksLikeDocument_(f.filename)) {
      try {
        blob = chatworkFetchFileBlob_(f);
        var ocrResult = chatworkOcrGuessStore_(blob, storeList);
        ocrText = ocrResult.text;
        if (ocrResult.matches.length === 1) matches = ocrResult.matches;
      } catch (e) {
        log_('ChatworkOCR取得失敗', 'file_id=' + f.file_id + ' : ' + String(e.message).slice(0, 200));
      }
    }

    if (matches.length !== 1) {
      var note = senderNote;
      if (ocrText) note += (note ? ' / ' : '') + 'OCR抜粋: ' + ocrText.replace(/\s+/g, ' ').slice(0, 150);
      if (ocrTooLarge) note += (note ? ' / ' : '') + 'ファイルが25MB超のためOCR未実施';
      reviewSheet.appendRow([new Date(), f.file_id, f.account ? f.account.name : '',
                             bodyText.slice(0, 200), f.filename,
                             matches.length === 0 ? '要確認(院名不明)' : '要確認(複数院に一致)', note]);
      needsReview++;
      continue;
    }

    try {
      if (blob) {
        chatworkUploadBlobToStore_(blob, f, matches[0], imported.sheet);
      } else {
        chatworkDownloadAndUpload_(f, matches[0], imported.sheet);
      }
      done++;
    } catch (e) {
      reviewSheet.appendRow([new Date(), f.file_id, f.account ? f.account.name : '',
                             bodyText.slice(0, 200), f.filename, '要確認(エラー)', String(e.message).slice(0, 200)]);
      needsReview++;
    }
  }

  PropertiesService.getScriptProperties().setProperty(CHATWORK.STATE_PROP, String(maxUploadTime));
  log_('Chatwork取込', done + '件アップロード / ' + skipped + '件は取込済みでスキップ / ' +
       excluded + '件は本社スタッフ投稿のため対象外 / ' +
       needsReview + '件は要確認シートへ' + (timedOut ? ' (時間切れのため中断。1分後に自動継続します)' : ''));
  return { done: done, skipped: skipped, excluded: excluded, needsReview: needsReview, timedOut: timedOut };
}

/** 実行時間切れで中断した続きを、1分後のワンタイムトリガーで自動的に再実行する。 */
function chatworkScheduleContinuation_(functionName) {
  ScriptApp.newTrigger(functionName).timeBased().after(60 * 1000).create();
}

/** Chatworkの添付ファイルを実際にダウンロードし、Blobとして返す。 */
function chatworkFetchFileBlob_(fileMeta) {
  var detail = chatworkFetch_('/rooms/' + CHATWORK.ROOM_ID + '/files/' + fileMeta.file_id,
                               { create_download_url: '1' });
  if (!detail || !detail.download_url) throw new Error('ダウンロードURLを取得できませんでした');

  var res = UrlFetchApp.fetch(detail.download_url, { muteHttpExceptions: true });
  if (res.getResponseCode() >= 400) {
    throw new Error('ファイル取得失敗 HTTP ' + res.getResponseCode());
  }
  return res.getBlob().setName(fileMeta.filename);
}

/** 取得済みのBlobを該当院フォルダへアップロードし、取込済みシートに記録する。 */
function chatworkUploadBlobToStore_(blob, fileMeta, store, importedSheet) {
  var folder = DriveApp.getFolderById(store.id);
  var created = folder.createFile(blob);

  importedSheet.appendRow([String(fileMeta.file_id), store.name, fileMeta.filename,
                           created.getId(), new Date()]);
}

/** 1ファイルを実際にダウンロードし、該当院フォルダへアップロードする。 */
function chatworkDownloadAndUpload_(fileMeta, store, importedSheet) {
  var blob = chatworkFetchFileBlob_(fileMeta);
  chatworkUploadBlobToStore_(blob, fileMeta, store, importedSheet);
}

/** 院名の手がかりを探す価値がある(=写真かPDFの)ファイルかどうかを、拡張子だけで大まかに判定する。 */
function chatworkLooksLikeDocument_(filename) {
  return /\.(jpe?g|png|pdf|heic|tiff?|bmp|gif)$/i.test(String(filename || ''));
}

/**
 * DriveのBlobをGoogle Docへ変換(OCR)し、テキスト化する。
 * 本文にも送信者名にも院名の手がかりが無い場合の最後の手段で、
 * 用紙に手書きされた院名が読み取れないかを試す(栗林さん指示、2026-09-14)。
 * 変換用の一時ファイルは処理後に必ずゴミ箱へ移動する。失敗しても例外は投げず、空の結果を返す。
 */
function chatworkOcrGuessStore_(blob, storeList) {
  var tempFile = null, ocrDocId = null;
  try {
    tempFile = DriveApp.createFile(blob);
    var ocrDoc = Drive.Files.copy(
      { title: 'Chatwork-OCR一時変換' },
      tempFile.getId(),
      { ocr: true, ocrLanguage: 'ja' }
    );
    ocrDocId = ocrDoc.id;
    var text = DocumentApp.openById(ocrDocId).getBody().getText();
    return { text: text || '', matches: chatworkMatchStore_(text || '', storeList) };
  } catch (e) {
    log_('ChatworkOCR失敗', String(e.message).slice(0, 200));
    return { text: '', matches: [] };
  } finally {
    try { if (tempFile) tempFile.setTrashed(true); } catch (e1) { /* 無視 */ }
    try { if (ocrDocId) DriveApp.getFileById(ocrDocId).setTrashed(true); } catch (e2) { /* 無視 */ }
  }
}

/** メニュー: 初回のバックログを一括取り込む(sinceUnix=0で取れる範囲を全部見る) */
function chatworkImportBacklog() {
  var result = chatworkImport_(0);
  if (result.timedOut) {
    chatworkScheduleContinuation_('chatworkImportBacklog');
    return;
  }
  try {
    SpreadsheetApp.getUi().alert(
      'Chatwork取り込み完了',
      result.done + '件アップロードしました。\n' +
      result.needsReview + '件は院名を自動特定できず「' + CHATWORK.REVIEW_SHEET + '」シートに残しています。\n' +
      '内容を確認のうえ、手動でアップロードしてください。',
      SpreadsheetApp.getUi().ButtonSet.OK);
  } catch (e) { /* エディタから実行時はUIが無いので無視 */ }
}

/** メニュー/トリガー: 前回チェック以降の新着だけを取り込む */
function chatworkImportNew() {
  var since = Number(PropertiesService.getScriptProperties().getProperty(CHATWORK.STATE_PROP) || '0');
  var result = chatworkImport_(since);
  if (result.timedOut) {
    chatworkScheduleContinuation_('chatworkImportNew');
  }
}

function enableChatworkTrigger() {
  disableChatworkTrigger();
  ScriptApp.newTrigger('chatworkImportNew').timeBased().everyMinutes(30).create();
  try {
    SpreadsheetApp.getUi().alert('Chatworkルームの自動監視を30分ごとにONにしました。');
  } catch (e) { /* エディタ実行時は無視 */ }
}

function disableChatworkTrigger() {
  var ts = ScriptApp.getProjectTriggers();
  for (var i = 0; i < ts.length; i++) {
    if (ts[i].getHandlerFunction() === 'chatworkImportNew') ScriptApp.deleteTrigger(ts[i]);
  }
}

/**
 * Chatwork API疎通・トークン設定の確認用。まずこれを実行して、
 * ルーム名が正しく取れることを確認してから本取り込みに進むこと。
 */
function chatworkTestConnection() {
  var room = chatworkFetch_('/rooms/' + CHATWORK.ROOM_ID, null);
  log_('Chatwork疎通テスト', 'ルーム名=' + room.name + ' / room_id=' + room.room_id +
       ' / トークンは正しく設定されています');
}

/**
 * OCRフォールバックの小規模検証用。_Chatwork取込済シートの3行目(既にアップロード済みの実ファイル)を
 * そのままOCRにかけ、Drive APIのOCR変換が動くこと・院名が読み取れることを確認する。
 * 本番のimport処理には一切影響しない(読み取り専用のテスト)。
 */
function chatworkTestOcr() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(CHATWORK.IMPORTED_SHEET);
  var row = sh.getRange(3, 1, 1, 5).getValues()[0];
  var driveId = row[3];
  var blob = DriveApp.getFileById(driveId).getBlob();
  var storeList = chatworkStoreList_();
  var result = chatworkOcrGuessStore_(blob, storeList);
  log_('ChatworkOCRテスト',
       '対象=' + row[1] + '(' + row[2] + ') / 抽出文字数=' + result.text.length +
       ' / マッチ院=' + result.matches.map(function (s) { return s.name; }).join(',') +
       ' / 冒頭100字=' + result.text.slice(0, 100).replace(/\n/g, ' '));
}
