/**
 * 休暇シート 自動化スクリプト（3店舗合同管理・1ファイル1シート構成）
 *
 * Code.gs（1店舗用）とは別の、3店舗（井尻・西新・姪浜など）を1つのスプレッドシートで
 * 同時に管理するための版。3店舗用の別スプレッドシートにこちらを設置してください。
 * 他のエリア（3店舗の組み合わせ）用に複製する場合は、STORES の label（店名）だけ書き換えてください。
 * 人数構成が変わる場合は STORE_SLOT_ROW_COUNT（各店舗ブロックの行数）も調整してください。
 *
 * 機能:
 *   ① スタッフマスターの雛形を作成（名前/性別/資格/新患対応/院長/ピラティス/店舗を管理する別タブ）
 *   ② 原本テンプレートを作成（初回のみ。日付・曜日・店舗ごとの色分けブロックを1から自動生成します。
 *      日付の下には、院長会議・AM2.3年目研修など店舗をまたぐ全社/エリア共通の定例予定を書き込める
 *      「行事欄」も3店舗共通で1行分用意します。希望休/公休の自動入力・自動クリアの対象外です）
 *   ③ 月次シートを作成（「原本」テンプレートをコピーし、日付を自動配置。日本の祝日は日付の文字を赤にします）
 *   ④ 公休を自動入力（希望休(赤字)を除いた残り日数を、店舗ごとに独立して以下のルールで自動割り振り）
 *        ・各資格（柔道整復師/鍼灸師など）を持つスタッフ、およびピラティス対応スタッフが、
 *          その店舗の全出勤日で最低1人は勤務（ハード制約）
 *        ・院長は月初1〜7日間、希望休を含めて公休1日まで（ハード制約）
 *        ・同じスタッフに公休を2日以上連続させない（原則禁止。避けられない場合のみ警告の上で許容）
 *        ・同じスタッフを6日以上連続で勤務させない（MAX_CONSECUTIVE_WORK_DAYSを超える手前で公休を差し込む）
 *        ・女性スタッフ／新患対応可スタッフが、できるだけ全出勤日で0人にならないようにする（ソフト制約）
 *        ・候補日が複数ある場合はランダムに選ぶことで、毎回同じ割当パターンに固定化しないようにする
 *      ※性別・資格・新患対応・院長・ピラティス・所属店舗は「スタッフマスター」シート
 *        （名前/性別/資格/新患対応/院長/ピラティス/店舗）から取得します
 *      ※これらの制約はすべて「店舗ごとに独立」して判定・割当します。複数店舗を掛け持ちするスタッフが
 *        いる場合でも、店舗間で予定が重複しないようにする調整は行いません（1店舗当たりで条件を
 *        満たす、という運用要件のため）。掛け持ちスタッフの重複が心配な場合は、割当後に目視で
 *        確認してください。
 *
 * インストール方法:
 *   1. 3店舗合同用のスプレッドシートを別途用意する
 *   2. そのスプレッドシートのメニュー「拡張機能」→「Apps Script」を開く
 *   3. デフォルトの Code.gs の中身をこのファイルの内容で置き換えて保存
 *   4. スプレッドシートを再読み込みすると、メニューに「休暇シート自動化(3店舗)」が追加されます
 *   5. メニューの「①スタッフマスターの雛形を作成」→「②原本テンプレートを作成」の順に実行し、
 *      スタッフマスターに全スタッフを登録してから、「③ 月次シートを作成」→「④ 公休を自動入力」
 *      の順に進めてください
 *   6. 初回実行時は権限の承認が必要です（祝日取得は外部URL取得の承認が必要です）
 */

/** ===== 設定 ===== */

const TEMPLATE_SHEET_NAME = '原本';
const MASTER_SHEET_NAME = 'スタッフマスター';

// このスプレッドシートで同時管理する店舗一覧（上から順にカレンダー内の色分けブロックとして並ぶ）。
// 他のエリア（店舗の組み合わせ）用に複製した場合は、labelだけ書き換えてください。
// color はカレンダー内でその店舗のブロックに使う背景色（薄い色を推奨）。
const STORES = [
  { key: 'ijiri', label: '井尻', color: '#fdf2cc' },
  { key: 'nishijin', label: '西新', color: '#d9ead3' },
  { key: 'meinohama', label: '姪浜', color: '#cfe2f3' },
];

// 曜日と、それぞれが占める列(1始まり: A=1, B=2, ...)。1店舗用のCode.gsと同じ7曜日×2列構成
const WEEKDAY_COL_PAIRS = [
  [1, 2],   // 日 (A:B)
  [3, 4],   // 月 (C:D)
  [5, 6],   // 火 (E:F)
  [7, 8],   // 水 (G:H)
  [9, 10],  // 木 (I:J)
  [11, 12], // 金 (K:L)
  [13, 14], // 土 (M:N)
];

// 各店舗ブロックの行数（名前を記入できる行数）。1つの日付・曜日につき、この行数×2列（6マス）が
// その店舗のその日の公休記入欄になる
const STORE_SLOT_ROW_COUNT = 3;

// 日付の下に設ける「行事欄」（院長会議・AM2.3年目研修など、店舗をまたぐ全社/エリア共通の定例予定を
// 書き込める空欄）の行数。3店舗で共有する1行。希望休/公休の自動入力・自動クリアの対象外で、
// 原本テンプレートに直接記入した内容が月次シート作成のたびにそのまま引き継がれる。
const EVENT_ROW_COUNT = 1;

// 1週間分のブロックの高さ（日付行1 + 行事欄 + 店舗の数だけ繰り返す店舗ブロック）
const BLOCK_HEIGHT = 1 + EVENT_ROW_COUNT + STORES.length * STORE_SLOT_ROW_COUNT;

// ヘッダー領域（タイトル・店舗ごとの公休数入力欄・曜日見出し）の行
const TITLE_ROW = 1;
const STORE_QUOTA_LABEL_COL = 1; // A列: 「◯◯ 公休数」ラベル
const STORE_QUOTA_VALUE_COL = 2; // B列: 数値入力
const STORE_QUOTA_START_ROW = 3; // 店舗ごとに1行使う（3店舗なら3,4,5行目）
const WEEKDAY_HEADER_ROW = STORE_QUOTA_START_ROW + STORES.length + 1; // 店舗数ぶん+空白1行の次

// 日付が入っている行（週の先頭行）。ヘッダー領域のすぐ下から、BLOCK_HEIGHTごとに5週間ぶん並べる
const CALENDAR_TOP_ROW = WEEKDAY_HEADER_ROW + 1;
const DATE_ROWS = [0, 1, 2, 3, 4].map((i) => CALENDAR_TOP_ROW + i * BLOCK_HEIGHT);

// カレンダー全体の最終行
const CALENDAR_BOTTOM_ROW = DATE_ROWS[DATE_ROWS.length - 1] + BLOCK_HEIGHT - 1;

// 行事欄として使う実際の行番号一覧（希望休集計・公休自動入力の対象から除外するために使う）
const EVENT_ROWS = DATE_ROWS.map((dateRow) => dateRow + 1);

// 店舗ラベルを表示する列（曜日の14列の右隣。各店舗ブロックの行数ぶん縦に結合して店名を表示する）
const STORE_LABEL_COL = 15; // O列

// スタッフ一覧・ダブルチェック用サマリー（カレンダーの下）。店舗ごとに列を分けて横に並べる
// （店舗0=A/B列、店舗1=D/E列、店舗2=G/H列 ... 各店舗の名前列・公休数列の間に1列スペースを空ける）
const SUMMARY_HEADER_ROW = CALENDAR_BOTTOM_ROW + 2;
const SUMMARY_START_ROW = SUMMARY_HEADER_ROW + 1;
const SUMMARY_MAX_ROWS = 10;
const SUMMARY_COL_START = STORES.map((_, i) => 1 + i * 3); // A(1), D(4), G(7)

// カレンダー内で「その月に存在しない日」に使う背景色
const OUT_OF_MONTH_BG_COLOR = '#000000';

// 希望休(赤字)の文字色
const WISH_FONT_COLOR = '#ff0000';

// 祝日の日付の文字色（日曜と同じ赤にする場合はそのまま）
const HOLIDAY_FONT_COLOR = '#ff0000';

// 行事欄の背景色
const EVENT_ROW_BG_COLOR = '#fff9d6';

// 日本の祝日を取得する公開ICSフィードのURL
const HOLIDAY_ICS_URL =
  'https://calendar.google.com/calendar/ical/ja.japanese%23holiday%40group.v.calendar.google.com/public/basic.ics';

// 院長ルール：月初 DIRECTOR_EARLY_WEEK_DAYS 日間は、希望休を含めて公休を
// DIRECTOR_EARLY_WEEK_MAX 日までに制限する（ハード制約。店舗ごとに判定）
const DIRECTOR_EARLY_WEEK_DAYS = 7;
const DIRECTOR_EARLY_WEEK_MAX = 1;

// 「全出勤日、最低1人は勤務している」ことを保証したい資格（スタッフマスターの「資格」欄の値）の一覧
// （このリストにある資格を持つ人がその店舗のロスター内に1人もいない場合は、その資格の制約は
// 自動的にスキップされます）。ピラティスは「資格」欄とは別の専用列（○欄）で管理する。
const QUALIFICATIONS = ['柔道整復師', '鍼灸師'];

// 同じスタッフの公休を何日まで連続で許容するか（1 = 連続させない。原則禁止で運用）
const MAX_CONSECUTIVE_OFF_DAYS = 1;

// 同じスタッフを連続で勤務させてよい日数の上限（これを超える手前で公休を優先的に差し込む）
const MAX_CONSECUTIVE_WORK_DAYS = 5;

/** ===== メニュー ===== */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('休暇シート自動化(3店舗)')
    .addItem('① スタッフマスターの雛形を作成', 'createStaffMasterTemplate')
    .addItem('② 原本テンプレートを作成（初回のみ）', 'createThreeStoreTemplateSheet')
    .addSeparator()
    .addItem('③ 月次シートを作成', 'createMonthlySheets')
    .addItem('④ 公休を自動入力（このシート・3店舗まとめて）', 'autoFillRegularHolidays')
    .addToUi();
}

/** ===================================================================
 *  スタッフマスター
 *  =================================================================== */

// 「スタッフマスター」シートの雛形を作成
function createStaffMasterTemplate() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss.getSheetByName(MASTER_SHEET_NAME)) {
    ui.alert(`「${MASTER_SHEET_NAME}」は既に存在します。`);
    return;
  }
  const sheet = ss.insertSheet(MASTER_SHEET_NAME, 0);
  const header = ['名前', '性別', '資格', '新患対応', '院長', 'ピラティス', '店舗'];
  const colWidths = [120, 90, 160, 110, 90, 90, 200];
  sheet.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  colWidths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));
  const storeLabels = STORES.map((s) => s.label).join('、');
  ui.alert(
    'スタッフマスター作成',
    `「${MASTER_SHEET_NAME}」シートを作成しました。各スタッフの情報を1行ずつ入力してください。\n\n` +
      '・名前: 「姓　名」のようにフルネームで入力してください（区別のため）。' +
      'カレンダー・スタッフ一覧欄には自動的に姓（スペースより前の部分）だけが反映されます。' +
      '姓が同じスタッフがいると区別できないのでご注意ください\n' +
      '・性別: 「女」を含む場合（「女」「女性」どちらも可）のみ女性としてカウントします\n' +
      `・資格: ${QUALIFICATIONS.join('、')} など（複数ある場合は「、」区切り）\n` +
      '・新患対応: 対応可能なら「〇」（空欄は対応不可扱い）\n' +
      `・院長: 対象者なら「〇」（月初1〜${DIRECTOR_EARLY_WEEK_DAYS}日は、希望休を含めて公休${DIRECTOR_EARLY_WEEK_MAX}日までに制限されます）\n` +
      '・ピラティス: 対応可能なら「〇」（対応スタッフが限られているため、資格と同様に全出勤日で' +
      '最低1人配置されるよう自動入力が調整します）\n' +
      `・店舗: ${storeLabels} のうち所属する店舗名を「、」区切りで入力してください` +
      '（複数店舗を掛け持ちする場合は複数入力可）。ここに入力した店舗名でのみ、その店舗のロスターに反映されます',
    ui.ButtonSet.OK
  );
}

// マスターの「名前」欄（姓＋半角/全角スペース＋名）から、カレンダー表記に使う姓だけを取り出す
function surnameOf(name) {
  return String(name || '').trim().split(/[\s　]+/)[0];
}

// スタッフマスターを読み込み、
// { byName: { 姓: {fullName, gender, qualifications, newPatient, director, pilates, stores} }, collisions: [...] }
// の形で返す。カレンダー上の記入・集計はすべて「姓」で行うため、マスターの名前欄がフルネームでも姓だけをキーにする。
// マスターシートが無い場合は null を返す
function loadStaffMaster(ss) {
  const sheet = ss.getSheetByName(MASTER_SHEET_NAME);
  if (!sheet) return null;

  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return { byName: {}, collisions: [] };

  const header = data[0].map((h) => String(h).trim());
  const idxName = header.indexOf('名前');
  const idxGender = header.indexOf('性別');
  const idxQual = header.indexOf('資格');
  const idxNewPatient = header.findIndex((h) => h.indexOf('新患') !== -1);
  const idxDirector = header.indexOf('院長');
  const idxPilates = header.indexOf('ピラティス');
  const idxStores = header.indexOf('店舗');
  if (idxName === -1) return { byName: {}, collisions: [] };

  const byName = {};
  const collisions = [];
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const fullName = String(row[idxName] || '').trim();
    if (!fullName) continue;
    const displayName = surnameOf(fullName);

    const gender = idxGender !== -1 ? String(row[idxGender] || '').trim() : '';
    const qualRaw = idxQual !== -1 ? String(row[idxQual] || '').trim() : '';
    const qualifications = qualRaw ? qualRaw.split(/[,、・\/\s]+/).filter(Boolean) : [];
    const newPatientRaw = idxNewPatient !== -1 ? String(row[idxNewPatient] || '').trim() : '';
    const newPatient = /^(〇|○|o|yes|true|1)$/i.test(newPatientRaw);
    const directorRaw = idxDirector !== -1 ? String(row[idxDirector] || '').trim() : '';
    const director = /^(〇|○|o|yes|true|1)$/i.test(directorRaw);
    const pilatesRaw = idxPilates !== -1 ? String(row[idxPilates] || '').trim() : '';
    const pilates = /^(〇|○|o|yes|true|1)$/i.test(pilatesRaw);
    const storesRaw = idxStores !== -1 ? String(row[idxStores] || '').trim() : '';
    const stores = storesRaw ? storesRaw.split(/[,、・\/\s]+/).filter(Boolean) : [];

    if (byName[displayName]) {
      collisions.push(`${byName[displayName].fullName} / ${fullName}`);
    }
    byName[displayName] = { fullName, gender, qualifications, newPatient, director, pilates, stores };
  }
  return { byName, collisions };
}

// マスターから、指定した店舗に所属するスタッフの姓一覧を返す（登録順）
function rosterForStore(masterRaw, storeLabel) {
  if (!masterRaw) return [];
  return Object.keys(masterRaw.byName).filter((n) => masterRaw.byName[n].stores.includes(storeLabel));
}

/** ===================================================================
 *  ① 原本テンプレートを作成（初回のみ）
 *  =================================================================== */
function createThreeStoreTemplateSheet() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss.getSheetByName(TEMPLATE_SHEET_NAME)) {
    ui.alert(`「${TEMPLATE_SHEET_NAME}」は既に存在します。`);
    return;
  }
  const sheet = ss.insertSheet(TEMPLATE_SHEET_NAME, 0);

  // タイトル行
  sheet.getRange(TITLE_ROW, 1, 1, 14).merge();
  sheet.getRange(TITLE_ROW, 1).setValue('3店舗合同　月休暇').setFontWeight('bold').setFontSize(14);

  // 店舗ごとの公休数入力欄
  STORES.forEach((store, i) => {
    const row = STORE_QUOTA_START_ROW + i;
    sheet.getRange(row, STORE_QUOTA_LABEL_COL).setValue(`${store.label}　公休数（取得可能日数）`);
    sheet.getRange(row, STORE_QUOTA_VALUE_COL).setNumberFormat('0');
  });

  // 曜日見出し
  const weekdayNames = ['日', '月', '火', '水', '木', '金', '土'];
  WEEKDAY_COL_PAIRS.forEach((pair, i) => {
    const range = sheet.getRange(WEEKDAY_HEADER_ROW, pair[0], 1, 2);
    range.merge().setValue(weekdayNames[i]).setFontWeight('bold').setFontSize(14).setHorizontalAlignment('center');
    if (i === 0) range.setFontColor(HOLIDAY_FONT_COLOR);
    if (i === 6) range.setFontColor('#1155cc');
  });
  sheet.getRange(WEEKDAY_HEADER_ROW, STORE_LABEL_COL).setValue('店舗').setFontWeight('bold');

  // カレンダー本体（5週間ぶん）
  DATE_ROWS.forEach((dateRow) => {
    // 日付行：曜日ごとに1セル、太字・中央寄せにしておく（実際の日付は③で入る）
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      const range = sheet.getRange(dateRow, pair[0], 1, 2);
      range.merge().setFontWeight('bold').setFontSize(12).setHorizontalAlignment('center');
    });

    // 行事欄：曜日ごとに1セルへ結合し、共通の行事メモを書き込めるようにする
    const eventRow = dateRow + 1;
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      sheet
        .getRange(eventRow, pair[0], 1, 2)
        .merge()
        .setBackground(EVENT_ROW_BG_COLOR)
        .setFontSize(9)
        .setHorizontalAlignment('center')
        .setVerticalAlignment('middle');
    });
    sheet.getRange(eventRow, STORE_LABEL_COL).setValue('行事').setFontSize(9).setFontColor('#999999');

    // 店舗ごとのブロック：STORE_SLOT_ROW_COUNT行×14列を店舗色で塗り、O列に店舗名を縦結合で表示
    STORES.forEach((store, i) => {
      const blockTop = dateRow + 1 + EVENT_ROW_COUNT + i * STORE_SLOT_ROW_COUNT;
      sheet.getRange(blockTop, 1, STORE_SLOT_ROW_COUNT, 14).setBackground(store.color);
      sheet
        .getRange(blockTop, STORE_LABEL_COL, STORE_SLOT_ROW_COUNT, 1)
        .merge()
        .setValue(store.label)
        .setFontWeight('bold')
        .setHorizontalAlignment('center')
        .setVerticalAlignment('middle')
        .setBackground(store.color);
    });
  });

  sheet.getRange(CALENDAR_TOP_ROW, 1, CALENDAR_BOTTOM_ROW - CALENDAR_TOP_ROW + 1, 14).setBorder(
    true, true, true, true, true, true
  );

  // 列幅調整
  for (let c = 1; c <= 14; c++) sheet.setColumnWidth(c, 70);
  sheet.setColumnWidth(STORE_LABEL_COL, 70);

  // スタッフ一覧・ダブルチェック用サマリーの見出し
  STORES.forEach((store, i) => {
    const col = SUMMARY_COL_START[i];
    sheet.getRange(SUMMARY_HEADER_ROW, col).setValue(`${store.label}　名前`).setFontWeight('bold');
    sheet.getRange(SUMMARY_HEADER_ROW, col + 1).setValue('公休数').setFontWeight('bold');
  });

  ui.alert(
    '原本テンプレート作成 完了',
    `「${TEMPLATE_SHEET_NAME}」を作成しました。院長会議・研修など、店舗共通で決まっている定例予定が` +
      'あれば、各週の「行事」欄（薄い黄色のセル）に直接入力しておくと、月次シート作成のたびに' +
      '引き継がれます。準備ができたら「③ 月次シートを作成」に進んでください。',
    ui.ButtonSet.OK
  );
}

/** ===================================================================
 *  ③ 月次シートを作成
 *  =================================================================== */
function createMonthlySheets() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const ymRes = ui.prompt(
    '月次シート作成',
    '対象の年月を入力してください（例: 2026-10）',
    ui.ButtonSet.OK_CANCEL
  );
  if (ymRes.getSelectedButton() !== ui.Button.OK) return;
  const m = ymRes.getResponseText().trim().match(/^(\d{4})[\/\-](\d{1,2})$/);
  if (!m) {
    ui.alert('年月の形式が正しくありません。例: 2026-10 の形式で入力してください。');
    return;
  }
  const year = parseInt(m[1], 10);
  const month = parseInt(m[2], 10);

  const quotas = {};
  for (const store of STORES) {
    const quotaRes = ui.prompt(
      '月次シート作成',
      `${store.label}の${month}月の公休数（取得可能日数）を入力してください（例: 10）`,
      ui.ButtonSet.OK_CANCEL
    );
    if (quotaRes.getSelectedButton() !== ui.Button.OK) return;
    const quota = parseInt(quotaRes.getResponseText().trim(), 10);
    if (isNaN(quota)) {
      ui.alert('公休数は数値で入力してください。');
      return;
    }
    quotas[store.label] = quota;
  }

  const result = createMonthlySheetCore(ss, year, month, quotas);
  ui.alert(result.ok ? '月次シート作成 完了' : '月次シート作成 エラー', result.message, ui.ButtonSet.OK);
}

// 年・月・店舗ごとの公休数(quotas: {店舗名: 数値})から月次シートを作成する本体処理。
// 戻り値: { ok: boolean, message: string }
function createMonthlySheetCore(ss, year, month, quotas) {
  const notes = [];

  const srcSheet = ss.getSheetByName(TEMPLATE_SHEET_NAME);
  if (!srcSheet) {
    return {
      ok: false,
      message: `シート「${TEMPLATE_SHEET_NAME}」が見つかりませんでした。先に「② 原本テンプレートを作成」を実行してください。`,
    };
  }

  const newName = `${year}年${month}月`;
  if (ss.getSheetByName(newName)) {
    return { ok: false, message: `シート「${newName}」は既に存在します。` };
  }

  const newSheet = srcSheet.copyTo(ss);
  newSheet.setName(newName);
  newSheet.showSheet();
  ss.setActiveSheet(newSheet);
  ss.moveActiveSheet(srcSheet.getIndex() + 1);

  newSheet.getRange(TITLE_ROW, 1).setValue(`3店舗合同　${month}月休暇`);

  STORES.forEach((store, i) => {
    const row = STORE_QUOTA_START_ROW + i;
    newSheet.getRange(row, STORE_QUOTA_VALUE_COL).setValue(quotas[store.label]);
  });

  clearCalendarNames(newSheet);
  const holidayWarning = fillCalendarDates(newSheet, year, month);
  if (holidayWarning) notes.push(holidayWarning);

  // スタッフ一覧欄を、スタッフマスターの店舗ごとの所属スタッフで反映（姓のみ）
  const masterRaw = loadStaffMaster(ss);
  if (masterRaw === null) {
    notes.push(`「${MASTER_SHEET_NAME}」シートが見つからないため、スタッフ一覧欄への自動反映はスキップしました。`);
  } else {
    if (masterRaw.collisions.length) {
      notes.push(
        `「${MASTER_SHEET_NAME}」に姓が重複しているスタッフがいます（区別できません）: ${masterRaw.collisions.join('、')}`
      );
    }
    STORES.forEach((store, i) => {
      const names = rosterForStore(masterRaw, store.label);
      if (!names.length) {
        notes.push(`「${store.label}」に所属するスタッフがスタッフマスターに登録されていません。`);
        return;
      }
      writeStoreRosterNames(newSheet, i, names);
    });
  }

  let completionMsg =
    `シート「${newName}」を作成しました。\n\n` +
    'スタッフ一覧欄は、スタッフマスターの「店舗」欄を元に店舗ごとに自動反映しました。' +
    `行事欄などの内容は「${TEMPLATE_SHEET_NAME}」のままなので、必要に応じて手動で入力してください。`;
  if (notes.length) {
    completionMsg += `\n\n※${notes.join('\n※')}`;
  }
  return { ok: true, message: completionMsg };
}

// 「取得可能」欄（店舗ごとのB列の数値セル）から、今月の公休数を読み取る。{店舗名: 数値|null}
function getQuotasFromNote(sheet) {
  const quotas = {};
  STORES.forEach((store, i) => {
    const row = STORE_QUOTA_START_ROW + i;
    const v = sheet.getRange(row, STORE_QUOTA_VALUE_COL).getValue();
    const n = parseInt(v, 10);
    quotas[store.label] = isNaN(n) ? null : n;
  });
  return quotas;
}

// カレンダー内の記入済み名前をクリア（全店舗ぶん。行事欄は対象外）
function clearCalendarNames(sheet) {
  DATE_ROWS.forEach((dateRow) => {
    STORES.forEach((store, i) => {
      const blockTop = dateRow + 1 + EVENT_ROW_COUNT + i * STORE_SLOT_ROW_COUNT;
      sheet.getRange(blockTop, 1, STORE_SLOT_ROW_COUNT, 14).clearContent();
    });
  });
}

// 指定した年月の日本の祝日（日にちの数値の集合）を、公開ICSフィードから取得する
function getJapaneseHolidays(year, month) {
  const holidays = new Set();
  const monthPrefix = `${year}${('0' + month).slice(-2)}`;
  try {
    const res = UrlFetchApp.fetch(HOLIDAY_ICS_URL, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) {
      return {
        holidays,
        error: `祝日カレンダーの取得に失敗しました（HTTP ${res.getResponseCode()}）。祝日の色分けは行われていません。`,
      };
    }
    const text = res.getContentText();
    const re = /DTSTART;VALUE=DATE:(\d{8})/g;
    let match;
    while ((match = re.exec(text)) !== null) {
      const ymd = match[1];
      if (ymd.slice(0, 6) === monthPrefix) {
        holidays.add(parseInt(ymd.slice(6, 8), 10));
      }
    }
    return { holidays, error: null };
  } catch (e) {
    return {
      holidays,
      error: `祝日の取得に失敗しました: ${e}。祝日の色分けは行われていません。`,
    };
  }
}

// 指定した年月の日付をカレンダーに配置（曜日に応じた列に自動配置）。行事欄・店舗ブロックの
// 背景色は、その月に存在しない日の位置だけ黒塗りにし、存在する日の位置は原本テンプレートの
// 色（2週目=DATE_ROWS[1]を基準）に揃える。
function fillCalendarDates(sheet, year, month) {
  const topRow = DATE_ROWS[0];
  const bottomRow = CALENDAR_BOTTOM_ROW;
  const numRows = bottomRow - topRow + 1;

  const referenceRow = DATE_ROWS[1];
  const rowOffsets = [];
  for (let i = 0; i < BLOCK_HEIGHT; i++) rowOffsets.push(i);
  const validBgByOffset = rowOffsets.map(
    (offset) => sheet.getRange(referenceRow + offset, 1, 1, 14).getBackgrounds()[0]
  );

  const dateRowRange = sheet.getRange(referenceRow, 1, 1, 14);
  const refFontSizes = dateRowRange.getFontSizes()[0];
  const refFontWeights = dateRowRange.getFontWeights()[0];
  const refAligns = dateRowRange.getHorizontalAlignments()[0];
  const refFontColors = dateRowRange.getFontColors()[0];
  const refNumberFormats = dateRowRange.getNumberFormats()[0];

  DATE_ROWS.forEach((row) => {
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      sheet.getRange(row, pair[0]).clearContent();
    });
  });

  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const lastDate = new Date(year, month, 0).getDate();
  const holidayResult = getJapaneseHolidays(year, month);
  const holidays = holidayResult.holidays;

  const bgGrid = [];
  for (let i = 0; i < numRows; i++) bgGrid.push(new Array(14).fill(OUT_OF_MONTH_BG_COLOR));

  let day = 1;
  DATE_ROWS.forEach((dateRow, weekIndex) => {
    for (let colIndex = 0; colIndex < 7; colIndex++) {
      const pair = WEEKDAY_COL_PAIRS[colIndex];
      const gridIndex = weekIndex * 7 + colIndex;
      const isValid = gridIndex >= firstWeekday && day <= lastDate;

      if (isValid) {
        const col = pair[0];
        const fontColor = holidays.has(day) ? HOLIDAY_FONT_COLOR : refFontColors[col - 1];
        sheet
          .getRange(dateRow, col)
          .setValue(day)
          .setFontSize(refFontSizes[col - 1])
          .setFontWeight(refFontWeights[col - 1])
          .setHorizontalAlignment(refAligns[col - 1])
          .setFontColor(fontColor)
          .setNumberFormat(refNumberFormats[col - 1]);
        rowOffsets.forEach((offset) => {
          const r = dateRow + offset;
          const bgRow = validBgByOffset[offset];
          bgGrid[r - topRow][pair[0] - 1] = bgRow[pair[0] - 1];
          bgGrid[r - topRow][pair[1] - 1] = bgRow[pair[1] - 1];
        });
        day++;
      }
    }
  });

  sheet.getRange(topRow, 1, numRows, 14).setBackgrounds(bgGrid);

  let overflowWarning = null;
  if (day <= lastDate) {
    overflowWarning =
      `「${sheet.getName()}」: ${month}月は5週間のフォーマットに収まりません` +
      `（${day}日以降が配置できていません）。テンプレートの行数を手動で確認してください。`;
  }

  if (holidayResult.error && overflowWarning) return `${holidayResult.error}\n${overflowWarning}`;
  return holidayResult.error || overflowWarning;
}

// 指定した店舗(storeIndex)のスタッフ一覧欄を、名前リストで上書きする
function writeStoreRosterNames(sheet, storeIndex, names) {
  const col = SUMMARY_COL_START[storeIndex];
  const clearRows = Math.max(names.length, SUMMARY_MAX_ROWS);
  sheet.getRange(SUMMARY_START_ROW, col, clearRows, 2).clearContent();
  if (names.length) {
    sheet.getRange(SUMMARY_START_ROW, col, names.length, 1).setValues(names.map((n) => [n]));
  }
}

// 指定した店舗(storeIndex)のダブルチェック欄に、名前と公休数のペアを書き込む。
// 入りきらなかった分は文字列配列で返す（入りきった場合は空配列）
function writeStoreSummaryCounts(sheet, storeIndex, nameCountPairs) {
  const col = SUMMARY_COL_START[storeIndex];
  const toWrite = nameCountPairs.slice(0, SUMMARY_MAX_ROWS);
  if (toWrite.length) {
    sheet.getRange(SUMMARY_START_ROW, col, toWrite.length, 2).setValues(toWrite);
  }
  return nameCountPairs.slice(SUMMARY_MAX_ROWS).map(([n]) => n);
}

/** ===================================================================
 *  ④ 公休を自動入力（3店舗まとめて、店舗ごとに独立して割当）
 *  =================================================================== */
function autoFillRegularHolidays() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSheet();

  if (sheet.getName() === TEMPLATE_SHEET_NAME || sheet.getName() === MASTER_SHEET_NAME) {
    ui.alert('月次シート（例: 2026年10月）を開いた状態で実行してください。');
    return;
  }

  const detectedQuotas = getQuotasFromNote(sheet);
  const quotaLines = STORES.map((s) => `${s.label}: ${detectedQuotas[s.label] ?? '未検出'}日`).join('\n');
  const confirmQuota = ui.alert(
    '公休自動入力',
    `このシートから検出した店舗ごとの公休数は以下の通りです。\n${quotaLines}\n\nこの数値で進めてよろしいですか？`,
    ui.ButtonSet.YES_NO
  );
  if (confirmQuota !== ui.Button.YES) {
    ui.alert('公休数の入力欄（B列）を確認してから、もう一度実行してください。');
    return;
  }

  const quotas = {};
  for (const store of STORES) {
    const q = detectedQuotas[store.label];
    if (q === null) {
      ui.alert(`「${store.label}」の公休数が数値で入力されていません。B列を確認してください。`);
      return;
    }
    quotas[store.label] = q;
  }

  const result = autoFillRegularHolidaysCore(sheet, quotas);
  ui.alert('公休自動入力 完了', result.message, ui.ButtonSet.OK);
}

// シートと店舗ごとの公休数(quotas: {店舗名: 数値})を受け取り、店舗ごとに完全に独立して
// 公休の自動入力を行う。戻り値: { writeCount: number, message: string }
function autoFillRegularHolidaysCore(sheet, quotas) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const masterRaw = loadStaffMaster(ss);
  if (masterRaw === null) {
    return {
      writeCount: 0,
      message: `「${MASTER_SHEET_NAME}」シートが見つかりません。先に「① スタッフマスターの雛形を作成」から作成してください。`,
    };
  }

  const topRow = DATE_ROWS[0];
  const bottomRow = CALENDAR_BOTTOM_ROW;
  const numRows = bottomRow - topRow + 1;
  const range = sheet.getRange(topRow, 1, numRows, 14);
  const values = range.getValues();
  const fontColors = range.getFontColors();

  let totalWrites = 0;
  const storeSections = [];

  STORES.forEach((store, storeIndex) => {
    const roster = rosterForStore(masterRaw, store.label);
    if (!roster.length) {
      storeSections.push(`【${store.label}】所属スタッフがスタッフマスターに登録されていないため、スキップしました。`);
      return;
    }

    const quota = quotas[store.label];
    const section = autoFillStoreCore(sheet, values, fontColors, topRow, storeIndex, roster, quota, masterRaw);
    totalWrites += section.writeCount;
    storeSections.push(`【${store.label}】${section.message}`);
  });

  if (masterRaw.collisions.length) {
    storeSections.push(
      `※「${MASTER_SHEET_NAME}」に姓が重複しているスタッフがいます（区別できません）: ${masterRaw.collisions.join('、')}`
    );
  }

  return {
    writeCount: totalWrites,
    message: `合計${totalWrites}件の公休を自動入力しました。\n\n${storeSections.join('\n\n')}`,
  };
}

// 1店舗ぶんの公休自動入力（他店舗の状態には一切影響されない、完全に独立した処理）
function autoFillStoreCore(sheet, values, fontColors, topRow, storeIndex, roster, quota, masterRaw) {
  const storeOffset = 1 + EVENT_ROW_COUNT + storeIndex * STORE_SLOT_ROW_COUNT;

  // 日ごとの情報（この店舗の記入欄だけを対象に構築）
  const days = [];
  DATE_ROWS.forEach((dateRow) => {
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      const dateVal = values[dateRow - topRow][pair[0] - 1];
      if (dateVal === '' || dateVal === null) return;

      const slotCells = [];
      for (let i = 0; i < STORE_SLOT_ROW_COUNT; i++) {
        const r = dateRow + storeOffset + i;
        pair.forEach((c) => slotCells.push({ r, c }));
      }

      const filledNames = new Set();
      slotCells.forEach(({ r, c }) => {
        const v = values[r - topRow][c - 1];
        if (v) filledNames.add(String(v).trim());
      });

      days.push({ date: dateVal, slotCells, filledNames });
    });
  });

  if (!days.length) {
    return { writeCount: 0, message: 'カレンダーに日付が入力されていません。先に「③ 月次シートを作成」で日付を配置してください。' };
  }

  const master = {};
  roster.forEach((n) => {
    master[n] = masterRaw.byName[n];
  });

  const qualifiedByQual = {};
  QUALIFICATIONS.forEach((q) => {
    qualifiedByQual[q] = roster.filter((n) => master[n].qualifications.includes(q));
  });
  const femaleNames = roster.filter((n) => master[n].gender.indexOf('女') !== -1);
  const newPatientNames = roster.filter((n) => master[n].newPatient);
  const directorNames = roster.filter((n) => master[n].director);
  const pilatesNames = roster.filter((n) => master[n].pilates);

  const coverageGroups = QUALIFICATIONS.map((q) => ({ label: q, names: qualifiedByQual[q] })).concat([
    { label: 'ピラティス', names: pilatesNames },
  ]);

  const directorEarlyWeekCount = {};
  const directorWarnings = [];
  directorNames.forEach((n) => {
    const count = days.filter((d) => d.date <= DIRECTOR_EARLY_WEEK_DAYS && d.filledNames.has(n)).length;
    directorEarlyWeekCount[n] = count;
    if (count > DIRECTOR_EARLY_WEEK_MAX) {
      directorWarnings.push(
        `${n}: 希望休の時点で月初${DIRECTOR_EARLY_WEEK_DAYS}日間の公休が${count}日（上限${DIRECTOR_EARLY_WEEK_MAX}日）`
      );
    }
  });

  const existingViolations = [];
  days.forEach((day) => {
    const working = roster.filter((n) => !day.filledNames.has(n));
    const reasons = [];
    coverageGroups.forEach(({ label, names }) => {
      if (names.length > 0 && !working.some((n) => names.includes(n))) {
        reasons.push(`${label}0人`);
      }
    });
    if (femaleNames.length > 0 && !working.some((n) => femaleNames.includes(n))) {
      reasons.push('女性スタッフ0人');
    }
    if (newPatientNames.length > 0 && !working.some((n) => newPatientNames.includes(n))) {
      reasons.push('新患対応スタッフ0人');
    }
    if (reasons.length) existingViolations.push(`${day.date}日(${reasons.join('/')})`);
  });

  const redCountByName = {};
  roster.forEach((n) => (redCountByName[n] = 0));
  for (let i = 0; i < STORE_SLOT_ROW_COUNT; i++) {
    DATE_ROWS.forEach((dateRow) => {
      const r = dateRow + storeOffset + i;
      for (let c = 1; c <= 14; c++) {
        const v = values[r - topRow][c - 1];
        if (!v) continue;
        const name = String(v).trim();
        if (!roster.includes(name)) continue;
        const color = (fontColors[r - topRow][c - 1] || '').toLowerCase();
        if (color === WISH_FONT_COLOR) {
          redCountByName[name] = (redCountByName[name] || 0) + 1;
        }
      }
    });
  }

  const needs = roster.map((name) => ({ name, need: quota - (redCountByName[name] || 0) }));
  const overWish = needs.filter((n) => n.need < 0);

  const usedCells = new Set();
  const writes = [];
  const streakWarnings = [];
  const coverageNotes = [];
  const consecutiveNotes = [];
  breakLongWorkStreaks(
    needs,
    days,
    roster,
    coverageGroups,
    directorNames,
    directorEarlyWeekCount,
    values,
    topRow,
    usedCells,
    writes,
    streakWarnings,
    consecutiveNotes
  );

  let progress = true;
  while (progress) {
    progress = false;
    for (const staff of shuffle(needs)) {
      if (staff.need <= 0) continue;

      const picked = pickDayForStaff(
        staff.name,
        days,
        roster,
        coverageGroups,
        femaleNames,
        newPatientNames,
        directorNames,
        directorEarlyWeekCount
      );
      if (!picked) continue;
      const day = picked.day;

      const emptyCell = day.slotCells.find(
        ({ r, c }) => !values[r - topRow][c - 1] && !usedCells.has(`${r}_${c}`)
      );
      if (!emptyCell) continue;

      usedCells.add(`${emptyCell.r}_${emptyCell.c}`);
      writes.push({ row: emptyCell.r, col: emptyCell.c, name: staff.name });
      day.filledNames.add(staff.name);
      staff.need--;
      progress = true;

      if (directorNames.includes(staff.name) && day.date <= DIRECTOR_EARLY_WEEK_DAYS) {
        directorEarlyWeekCount[staff.name] = (directorEarlyWeekCount[staff.name] || 0) + 1;
      }

      if (picked.penalty > 0) {
        const consecutive = picked.reasons.includes('連休になります');
        const otherReasons = picked.reasons.filter((r) => r !== '連休になります');
        if (otherReasons.length) {
          coverageNotes.push(`${day.date}日に${staff.name}を割当（${otherReasons.join('/')}）`);
        }
        if (consecutive) {
          consecutiveNotes.push(`${day.date}日に${staff.name}を割当（既存の公休と連続してしまいます）`);
        }
      }
    }
  }

  writes.forEach((w) => {
    sheet.getRange(w.row, w.col).setValue(w.name).setFontColor('#000000');
  });

  const finalCountByName = {};
  roster.forEach((n) => (finalCountByName[n] = redCountByName[n] || 0));
  writes.forEach((w) => {
    finalCountByName[w.name] = (finalCountByName[w.name] || 0) + 1;
  });
  const summaryOverflow = writeStoreSummaryCounts(
    sheet,
    storeIndex,
    roster.map((n) => [n, finalCountByName[n]])
  );

  const shortages = needs.filter((n) => n.need > 0);
  let msg = `${writes.length}件の公休を自動入力しました。`;
  if (overWish.length) {
    msg += `\n※希望休(赤字)がすでに公休数を超えているスタッフ: ${overWish
      .map((n) => `${n.name}(${-n.need}日超過)`)
      .join('、')}`;
  }
  if (shortages.length) {
    msg += `\n※資格カバレッジの制約により割り当てきれなかったスタッフ: ${shortages
      .map((n) => `${n.name}(あと${n.need}日)`)
      .join('、')}（手動で調整してください）`;
  }
  if (existingViolations.length) {
    msg += `\n※希望休の時点で既に女性/新患対応/資格のカバレッジが0人になっている日: ${existingViolations.join('、')}`;
  }
  if (directorWarnings.length) {
    msg += `\n※院長ルール（月初${DIRECTOR_EARLY_WEEK_DAYS}日間は公休${DIRECTOR_EARLY_WEEK_MAX}日まで）が希望休の時点で既に超過: ${directorWarnings.join('、')}`;
  }
  if (streakWarnings.length) {
    msg += `\n※連勤(${MAX_CONSECUTIVE_WORK_DAYS}日超)の解消に関する警告:\n${streakWarnings.join('\n')}`;
  }
  if (coverageNotes.length) {
    msg += `\n※やむを得ず女性/新患対応のカバレッジが崩れた割り当て:\n${coverageNotes.join('\n')}`;
  }
  if (consecutiveNotes.length) {
    msg += `\n※やむを得ず連休になった割り当て:\n${consecutiveNotes.join('\n')}`;
  }
  if (summaryOverflow.length) {
    msg += `\n※スタッフ数が集計欄（最大${SUMMARY_MAX_ROWS}人）を超えているため記載できませんでした: ${summaryOverflow.join('、')}`;
  }

  return { writeCount: writes.length, message: msg };
}

// 配列をシャッフルしたコピーを返す（元の配列は変更しない）
function shuffle(array) {
  const arr = array.slice();
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// staffName をその日に休ませた場合に破られるハード制約を、
//   absolute: 院長ルール（連勤解消のためでも絶対に上書きしてはいけない）
//   overridable: 資格/ピラティスカバレッジ（他にどうしても方法が無い場合、連勤解消の最終手段としてのみ
//                上書きしてよい）
// の2種類に分けて返す
function hardConstraintReasons(day, staffName, roster, coverageGroups, directorNames, directorEarlyWeekCount) {
  const absolute = [];
  const overridable = [];

  if (
    directorNames.includes(staffName) &&
    day.date <= DIRECTOR_EARLY_WEEK_DAYS &&
    (directorEarlyWeekCount[staffName] || 0) >= DIRECTOR_EARLY_WEEK_MAX
  ) {
    absolute.push('院長ルール(月初の公休上限)');
  }

  const workingNames = roster.filter((n) => !day.filledNames.has(n) && n !== staffName);
  coverageGroups.forEach(({ label, names }) => {
    if (!names || names.length === 0) return;
    if (!workingNames.some((n) => names.includes(n))) overridable.push(`資格カバレッジ(${label}が0人)`);
  });

  return { absolute, overridable };
}

// staffName をその日に休ませることが、資格/ピラティスカバレッジ(ハード制約)・院長ルール(ハード制約)に
// 違反しないかを判定
function violatesHardConstraints(day, staffName, roster, coverageGroups, directorNames, directorEarlyWeekCount) {
  if (day.filledNames.has(staffName)) return true;
  const { absolute, overridable } = hardConstraintReasons(
    day,
    staffName,
    roster,
    coverageGroups,
    directorNames,
    directorEarlyWeekCount
  );
  return absolute.length > 0 || overridable.length > 0;
}

// staffName を dayIndex の日に休ませると、前日または翌日もその人の公休になり
// 「連休(MAX_CONSECUTIVE_OFF_DAYS超)」になってしまうかを判定
function wouldViolateConsecutiveOff(days, dayIndex, staffName) {
  if (MAX_CONSECUTIVE_OFF_DAYS >= 2) return false;
  const prev = days[dayIndex - 1];
  const next = days[dayIndex + 1];
  return (!!prev && prev.filledNames.has(staffName)) || (!!next && next.filledNames.has(staffName));
}

// staffName を休みにできる日の中から、資格/ピラティスカバレッジ・院長ルール(ハード制約)を守った上で、
// 連休にならない日を最優先候補とし、その中で「その時点で最も休みが少ない日」を優先して選ぶ
function pickDayForStaff(
  staffName,
  days,
  roster,
  coverageGroups,
  femaleNames,
  newPatientNames,
  directorNames,
  directorEarlyWeekCount
) {
  const candidates = [];
  days.forEach((day, index) => {
    if (violatesHardConstraints(day, staffName, roster, coverageGroups, directorNames, directorEarlyWeekCount)) {
      return;
    }

    const workingNames = roster.filter((n) => !day.filledNames.has(n) && n !== staffName);
    const reasons = [];
    if (femaleNames.length > 0 && !workingNames.some((n) => femaleNames.includes(n))) {
      reasons.push('女性スタッフ0人');
    }
    if (newPatientNames.length > 0 && !workingNames.some((n) => newPatientNames.includes(n))) {
      reasons.push('新患対応スタッフ0人');
    }
    const consecutive = wouldViolateConsecutiveOff(days, index, staffName);
    if (consecutive) reasons.push('連休になります');

    candidates.push({
      day,
      consecutive,
      penalty: reasons.length,
      reasons,
      crowding: day.filledNames.size,
    });
  });

  if (!candidates.length) return null;

  const nonConsecutive = candidates.filter((c) => !c.consecutive);
  const pool = nonConsecutive.length ? nonConsecutive : candidates;

  let bestScore = null;
  let bestGroup = [];
  pool.forEach((c) => {
    const score = c.crowding * 100 + c.penalty;
    if (bestScore === null || score < bestScore) {
      bestScore = score;
      bestGroup = [c];
    } else if (score === bestScore) {
      bestGroup.push(c);
    }
  });

  return bestGroup[Math.floor(Math.random() * bestGroup.length)];
}

// staffName の「休みではない日」の連続区間のうち、max日を超えて連続している最初の区間を検出する
function findFirstOverLongWorkStreak(days, staffName, max) {
  let runStart = null;
  for (let i = 0; i <= days.length; i++) {
    const isWorking = i < days.length && !days[i].filledNames.has(staffName);
    if (isWorking) {
      if (runStart === null) runStart = i;
      continue;
    }
    if (runStart !== null) {
      const runEnd = i - 1;
      if (runEnd - runStart + 1 > max) {
        return { start: runStart, end: runEnd };
      }
      runStart = null;
    }
  }
  return null;
}

// streak(連勤区間)内で、staffNameを休ませるのに最も適した日を選ぶ
function pickBreakDayInStreak(streak, staffName, days, roster, coverageGroups, directorNames, directorEarlyWeekCount) {
  const buildCandidates = (allowQualificationOverride) => {
    const list = [];
    for (let i = streak.start; i <= streak.end; i++) {
      const day = days[i];
      const { absolute, overridable } = hardConstraintReasons(
        day,
        staffName,
        roster,
        coverageGroups,
        directorNames,
        directorEarlyWeekCount
      );
      if (absolute.length) continue;
      if (overridable.length && !allowQualificationOverride) continue;
      list.push({
        index: i,
        consecutive: wouldViolateConsecutiveOff(days, i, staffName),
        crowding: day.filledNames.size,
        hardReasons: overridable,
      });
    }
    return list;
  };

  let candidates = buildCandidates(false);
  if (!candidates.length) {
    candidates = buildCandidates(true);
  }
  if (!candidates.length) return null;

  const nonConsecutive = candidates.filter((c) => !c.consecutive);
  const pool = nonConsecutive.length ? nonConsecutive : candidates;

  let bestCrowding = null;
  let bestGroup = [];
  pool.forEach((c) => {
    if (bestCrowding === null || c.crowding < bestCrowding) {
      bestCrowding = c.crowding;
      bestGroup = [c];
    } else if (c.crowding === bestCrowding) {
      bestGroup.push(c);
    }
  });

  return bestGroup[Math.floor(Math.random() * bestGroup.length)];
}

// 連勤上限(MAX_CONSECUTIVE_WORK_DAYS)を超える区間を検出し、各スタッフの公休予算(need)の範囲内で、
// 資格/ピラティスカバレッジ・院長ルールを守れる位置に公休を差し込んで解消する
function breakLongWorkStreaks(
  needs,
  days,
  roster,
  coverageGroups,
  directorNames,
  directorEarlyWeekCount,
  values,
  topRow,
  usedCells,
  writes,
  warnings,
  consecutiveNotes
) {
  shuffle(needs).forEach((staff) => {
    let guard = 0;
    while (guard++ < 50) {
      const streak = findFirstOverLongWorkStreak(days, staff.name, MAX_CONSECUTIVE_WORK_DAYS);
      if (!streak) break;

      const streakLabel = `${streak.start + 1}日〜${streak.end + 1}日（${streak.end - streak.start + 1}連勤）`;

      if (staff.need <= 0) {
        warnings.push(
          `${staff.name}: ${streakLabel}になりますが、公休の残り枠が無いため自動では解消できませんでした。手動で調整してください。`
        );
        break;
      }

      const picked = pickBreakDayInStreak(
        streak,
        staff.name,
        days,
        roster,
        coverageGroups,
        directorNames,
        directorEarlyWeekCount
      );

      if (!picked) {
        warnings.push(
          `${staff.name}: ${streakLabel}になりますが、院長ルール（月初の公休上限）と衝突するため解消できる日が見つかりませんでした。手動で調整してください。`
        );
        break;
      }

      let placed = false;
      {
        const day = days[picked.index];
        const emptyCell = day.slotCells.find(
          ({ r, c }) => !values[r - topRow][c - 1] && !usedCells.has(`${r}_${c}`)
        );
        if (emptyCell) {
          usedCells.add(`${emptyCell.r}_${emptyCell.c}`);
          writes.push({ row: emptyCell.r, col: emptyCell.c, name: staff.name });
          day.filledNames.add(staff.name);
          staff.need--;
          if (directorNames.includes(staff.name) && day.date <= DIRECTOR_EARLY_WEEK_DAYS) {
            directorEarlyWeekCount[staff.name] = (directorEarlyWeekCount[staff.name] || 0) + 1;
          }
          if (picked.consecutive) {
            consecutiveNotes.push(`${day.date}日に${staff.name}を割当（連勤解消のため、既存の公休と連続してしまいます）`);
          }
          if (picked.hardReasons.length) {
            warnings.push(
              `${staff.name}: ${day.date}日は本来${picked.hardReasons.join('・')}のため休ませられませんが、` +
                `${streakLabel}の解消を優先し、やむを得ずこの日に割り当てました。人員配置を確認してください。`
            );
          }
          placed = true;
        }
      }

      if (!placed) {
        warnings.push(
          `${staff.name}: ${streakLabel}になりますが、空きセルが無いため自動では解消できませんでした。手動で調整してください。`
        );
        break;
      }
    }
  });
}
