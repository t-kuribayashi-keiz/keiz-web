/**
 * 休暇シート 自動化スクリプト（1ファイル1店舗構成）
 *
 * 他店舗用に複製する場合は、STORE_LABEL の値だけ書き換えてください。
 *
 * 機能:
 *   ① 月次シートを作成（「原本」テンプレートをコピーし、日付を自動配置。日本の祝日は日付の文字を赤にします）
 *   ② 公休を自動入力（希望休(赤字)を除いた残り日数を、以下のルールで自動割り振り）
 *        ・各資格（柔道整復師/鍼灸師/ピラティスなど）を持つスタッフが全出勤日で最低1人は勤務（ハード制約）
 *        ・院長は月初1〜7日間、希望休を含めて公休1日まで（ハード制約）
 *        ・同じスタッフに公休を2日以上連続させない（原則禁止。避けられない場合のみ警告の上で許容）
 *        ・同じスタッフを6日以上連続で勤務させない（MAX_CONSECUTIVE_WORK_DAYSを超える手前で公休を差し込む）
 *        ・女性スタッフ／新患対応可スタッフが、できるだけ全出勤日で0人にならないようにする（ソフト制約）
 *        ・候補日が複数ある場合はランダムに選ぶことで、毎回同じ割当パターンに固定化しないようにする
 *      ※性別・資格・新患対応・院長は「スタッフマスター」シート（名前/性別/資格/新患対応/院長）から取得します
 *   ③ 行事欄（院長会議・AM2.3年目研修など、会社/エリア共通の定例予定）
 *        ・日付行のすぐ下に、EVENT_ROW_COUNT行ぶんの空欄を用意（希望休/公休の自動入力・自動クリアの対象外）
 *        ・原本テンプレートに直接記入しておけば、月次シートを作成するたびにそのまま引き継がれる
 *        ・原本テンプレートが未対応(行が無い)の場合は、メニューの「行事欄をテンプレートに追加」を
 *          最初に1回だけ実行してください
 *
 * インストール方法:
 *   1. スプレッドシートのメニュー「拡張機能」→「Apps Script」を開く
 *   2. デフォルトの Code.gs の中身をこのファイルの内容で置き換えて保存
 *   3. スプレッドシートを再読み込みすると、メニューに「休暇シート自動化」が追加されます
 *   4. 初回実行時は権限の承認が必要です（祝日取得は外部URL取得の承認が必要です）
 *   5. 行事欄を初めて使う場合は、メニューの「行事欄をテンプレートに追加（初回のみ）」を実行してから
 *      「① 月次シートを作成」を行ってください
 *
 * 注意（スマホ/iPadでメニューが出ない件）:
 *   Apps Scriptで作ったカスタムメニュー（「休暇シート自動化」）は、Googleスプレッドシートの仕様上、
 *   Android/iOSアプリ版やモバイルブラウザ版には表示されません（PC版のブラウザでのみ操作できます）。
 *   これはGoogle側の仕様上の制限であり、このスクリプト側では解決できません。モバイルからもボタン操作
 *   したい場合は、別途「ウェブアプリ」として公開しモバイルのブラウザからURLを開いて操作する仕組みを
 *   新たに作る必要があります（相応の追加実装が必要になるため、必要であれば別途ご相談ください）。
 */

/** ===== 設定（シート構造。原本テンプレートを元に決定） ===== */

// コピー元として使うテンプレートシート名
const TEMPLATE_SHEET_NAME = '原本';

// このスプレッドシートがどの店舗用か。1ファイル1店舗構成なので、
// 他店舗用に複製した際はこの値だけ書き換えてください（例: '下総中山北口'）。
// タイトル欄には「${STORE_LABEL}　${月}月休暇」の形で入ります。
const STORE_LABEL = '下総中山駅前';

// 曜日と、それぞれが占める列(1始まり: A=1, B=2, ...)。テンプレートの結合セル(A:B=日, C:D=月, ...)に対応
const WEEKDAY_COL_PAIRS = [
  [1, 2],   // 日 (A:B)
  [3, 4],   // 月 (C:D)
  [5, 6],   // 火 (E:F)
  [7, 8],   // 水 (G:H)
  [9, 10],  // 木 (I:J)
  [11, 12], // 金 (K:L)
  [13, 14], // 土 (M:N)
];

// 各日付行の直下、名前を記入できる行数（原本テンプレートで固定：3行）
const SLOT_ROW_COUNT = 3;

// 日付の下に設ける「行事欄」（院長会議・AM2.3年目研修など、会社/エリア共通の定例予定を書き込める
// 空欄）の行数。行事欄は希望休/公休の自動入力・自動クリアの対象外で、原本テンプレートに直接記入した
// 内容が月次シート作成のたびにそのまま引き継がれる（曜日固定の定例予定は原本に書いておけば毎月反映される）。
const EVENT_ROW_COUNT = 1;

// 1週間分のブロックの高さ（日付行1 + 行事欄 + 名前記入欄）。DATE_ROWSの算出に使う
const WEEK_BLOCK_HEIGHT = 1 + EVENT_ROW_COUNT + SLOT_ROW_COUNT;

// 日付が入っている行（週の先頭行）。原本テンプレートに行事欄を追加した後の位置から算出する
// （行事欄追加前は 4,8,12,16,20 だったが、行事欄ぶん後ろにずれる。EVENT_ROW_COUNT=1なら 4,9,14,19,24）
const DATE_ROWS = [0, 1, 2, 3, 4].map((i) => 4 + i * WEEK_BLOCK_HEIGHT);

// カレンダー全体の最終行（日付行＋行事欄＋名前記入欄の一番下）。スタッフ一覧欄の検索範囲を
// カレンダー内と誤認しないための下端判定にも使う
const CALENDAR_BOTTOM_ROW = DATE_ROWS[DATE_ROWS.length - 1] + EVENT_ROW_COUNT + SLOT_ROW_COUNT;

// 行事欄として使う実際の行番号一覧（希望休集計・公休自動入力の対象から除外するために使う）
const EVENT_ROWS = DATE_ROWS.flatMap((dateRow) => {
  const rows = [];
  for (let i = 1; i <= EVENT_ROW_COUNT; i++) rows.push(dateRow + i);
  return rows;
});

// タイトルセル（例:「下総駅前　9月休暇」が入るセル）
const TITLE_CELL = 'C1';

// 「◯日：　日　◯日：　日　取得可能◯」のメモが入るセル
const QUOTA_NOTE_CELL = 'P1';

// P列・Q列にある「名前／休暇数」のダブルチェック欄（原本テンプレート固定：P5〜、Qは既存のCOUNTIF式）
const ROSTER_SUMMARY_NAME_COL = 16; // P列
const ROSTER_SUMMARY_START_ROW = 5;
const ROSTER_SUMMARY_MAX_ROWS = 8;

// カレンダー内で「その月に存在しない日」に使う背景色（テンプレートの黒塗りに合わせる）
const OUT_OF_MONTH_BG_COLOR = '#000000';

// 希望休(赤字)の文字色
const WISH_FONT_COLOR = '#ff0000';

// 祝日の日付の文字色（日曜と同じ赤にする場合はそのまま）
const HOLIDAY_FONT_COLOR = '#ff0000';

// 日本の祝日を取得する公開ICSフィードのURL。
// CalendarApp.getCalendarById()は実行者本人がこのカレンダーを自分のGoogleカレンダーに
// 事前に追加(購読)していないと取得に失敗するため、購読不要で誰でも読める公開ICSを直接取得する方式にしている。
const HOLIDAY_ICS_URL =
  'https://calendar.google.com/calendar/ical/ja.japanese%23holiday%40group.v.calendar.google.com/public/basic.ics';

// スタッフマスターのシート名（名前・性別・資格・新患対応・院長を管理する別タブ）
const MASTER_SHEET_NAME = 'スタッフマスター';

// 院長ルール：月初 DIRECTOR_EARLY_WEEK_DAYS 日間は、希望休を含めて公休を
// DIRECTOR_EARLY_WEEK_MAX 日までに制限する（ハード制約）
const DIRECTOR_EARLY_WEEK_DAYS = 7;
const DIRECTOR_EARLY_WEEK_MAX = 1;

// 「全出勤日、最低1人は勤務している」ことを保証したい資格の一覧
// （このリストにある資格を持つ人がロスター内に1人もいない場合は、その資格の制約は自動的にスキップされます）
// ピラティスは対応できるスタッフが限られており、院によっては2名いる場合もあるため、他の資格と同様に
// 「全出勤日で最低1人」のハード制約対象としてここに含めている。
const QUALIFICATIONS = ['柔道整復師', '鍼灸師', 'ピラティス'];

// 同じスタッフの公休を何日まで連続で許容するか（1 = 連続させない。原則禁止で運用）
const MAX_CONSECUTIVE_OFF_DAYS = 1;

// 同じスタッフを連続で勤務させてよい日数の上限（これを超える手前で公休を優先的に差し込む）
const MAX_CONSECUTIVE_WORK_DAYS = 5;

/** ===== メニュー ===== */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('休暇シート自動化')
    .addItem('① 月次シートを作成', 'createMonthlySheets')
    .addItem('② 公休を自動入力（このシート）', 'autoFillRegularHolidays')
    .addSeparator()
    .addItem('スタッフマスターの雛形を作成', 'createStaffMasterTemplate')
    .addItem('行事欄をテンプレートに追加（初回のみ）', 'insertEventRowIntoTemplate')
    .addToUi();
}

/** ===================================================================
 *  ① 月次シートを作成
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

  const quotaRes = ui.prompt(
    '月次シート作成',
    `${month}月の公休数（取得可能日数）を入力してください（例: 10）`,
    ui.ButtonSet.OK_CANCEL
  );
  if (quotaRes.getSelectedButton() !== ui.Button.OK) return;
  const quota = parseInt(quotaRes.getResponseText().trim(), 10);
  if (isNaN(quota)) {
    ui.alert('公休数は数値で入力してください。');
    return;
  }

  const rosterNotes = [];

  // コピー元は常に「原本」テンプレートを使用
  const srcSheet = ss.getSheetByName(TEMPLATE_SHEET_NAME);
  if (!srcSheet) {
    ui.alert(`シート「${TEMPLATE_SHEET_NAME}」が見つかりませんでした。`);
    return;
  }

  const newName = `${year}年${month}月`;
  if (ss.getSheetByName(newName)) {
    ui.alert(`シート「${newName}」は既に存在します。`);
    return;
  }

  const newSheet = srcSheet.copyTo(ss);
  newSheet.setName(newName);
  newSheet.showSheet();
  ss.setActiveSheet(newSheet);
  // 「原本」のすぐ右に挿入
  ss.moveActiveSheet(srcSheet.getIndex() + 1);

  // タイトル欄
  newSheet.getRange(TITLE_CELL).setValue(`${STORE_LABEL}　${month}月休暇`);

  // 「取得可能」メモの末尾の数値を今回の公休数に更新
  const noteCell = newSheet.getRange(QUOTA_NOTE_CELL);
  const noteBase = String(noteCell.getValue() || '').replace(/\d+$/, '');
  noteCell.setValue(`${noteBase}${quota}`);

  // カレンダー内の名前欄をクリアしてから、対象月の日付を配置（行事欄は原本の内容をそのまま引き継ぐ）
  clearCalendarNames(newSheet);
  const holidayWarning = fillCalendarDates(newSheet, year, month);
  if (holidayWarning) rosterNotes.push(holidayWarning);

  // スタッフ一覧欄（「名前」見出しの下）を、スタッフマスターの全スタッフで反映（姓のみ）
  const masterRaw = loadStaffMaster(ss);
  if (masterRaw === null) {
    rosterNotes.push(
      `「${MASTER_SHEET_NAME}」シートが見つからないため、スタッフ一覧欄への自動反映はスキップしました。`
    );
  } else {
    if (masterRaw.collisions.length) {
      rosterNotes.push(
        `「${MASTER_SHEET_NAME}」に姓が重複しているスタッフがいます（区別できません）: ${masterRaw.collisions.join('、')}`
      );
    }
    const allStaff = Object.keys(masterRaw.byName);
    if (allStaff.length) {
      const wrote = writeRosterNames(newSheet, allStaff);
      if (!wrote) {
        rosterNotes.push(
          `「${newName}」: スタッフ一覧欄（「名前」見出し）が見つからず、マスターからの反映をスキップしました。`
        );
      }
    } else {
      rosterNotes.push(`「${MASTER_SHEET_NAME}」にスタッフが登録されていません。`);
    }
  }

  let completionMsg =
    `シート「${newName}」を作成しました。\n\n` +
    'スタッフ一覧欄は、スタッフマスターを元に自動反映しました。' +
    `研修日程・特別休などの注記は「${TEMPLATE_SHEET_NAME}」の内容のままなので、必要に応じて手動で入力してください。`;
  if (rosterNotes.length) {
    completionMsg += `\n\n※${rosterNotes.join('\n※')}`;
  }
  ui.alert('月次シート作成 完了', completionMsg, ui.ButtonSet.OK);
}

// P列(名前)にスタッフ名を記載する（Q列は既存のCOUNTIF式が自動で日数を数える）。
// P/Q欄に入りきらなかったスタッフ名の配列を返す（入りきった場合は空配列）
function writeRosterSummary(sheet, names) {
  const range = sheet.getRange(
    ROSTER_SUMMARY_START_ROW,
    ROSTER_SUMMARY_NAME_COL,
    ROSTER_SUMMARY_MAX_ROWS,
    1
  );
  range.clearContent();

  const toWrite = names.slice(0, ROSTER_SUMMARY_MAX_ROWS);
  if (toWrite.length) {
    sheet
      .getRange(ROSTER_SUMMARY_START_ROW, ROSTER_SUMMARY_NAME_COL, toWrite.length, 1)
      .setValues(toWrite.map((n) => [n]));
  }

  return names.slice(ROSTER_SUMMARY_MAX_ROWS);
}

// 「取得可能」メモ欄（QUOTA_NOTE_CELL）の末尾の数値から、今月の公休数を読み取る
// （①月次シート作成時に書き込まれた数値）。数値が見つからない場合は null を返す
function getQuotaFromNote(sheet) {
  const text = String(sheet.getRange(QUOTA_NOTE_CELL).getValue() || '');
  const m = text.match(/(\d+)\s*$/);
  return m ? parseInt(m[1], 10) : null;
}

// カレンダー内（日付行の下、名前記入欄SLOT_ROW_COUNT行×14列）の記入済み名前をクリア。
// 行事欄(EVENT_ROW_COUNT行ぶん)はクリア対象外。原本テンプレートに記入された内容(院長会議など)を
// 毎月そのまま引き継ぐため。
function clearCalendarNames(sheet) {
  DATE_ROWS.forEach((dateRow) => {
    sheet.getRange(dateRow + 1 + EVENT_ROW_COUNT, 1, SLOT_ROW_COUNT, 14).clearContent();
  });
}

// 指定した年月の日本の祝日（日にちの数値の集合）を、公開ICSフィードから取得する。
// 戻り値: { holidays: Set<number>, error: string|null }（取得・解析に失敗した場合は holidays は空、error にメッセージ）
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

// 指定した年月の日付をカレンダーに配置（曜日に応じた列に自動配置）。
// 祝日取得に失敗した場合は、そのエラーメッセージ（呼び出し元でユーザーに表示するため）を返す。成功時は null。
function fillCalendarDates(sheet, year, month) {
  const topRow = DATE_ROWS[0];
  const bottomRow = CALENDAR_BOTTOM_ROW;
  const numRows = bottomRow - topRow + 1;

  // 「その月に存在する日」の背景色は、必ず8〜14日が入る2週目(DATE_ROWS[1])の色を基準にする
  // （コピー元の月では存在しない日として黒塗りされていたセルが、そのまま残ってしまうのを防ぐため）
  // 日付行・行事欄・記入欄とでは色が違うため、行オフセットごとに基準色を取得する
  const referenceRow = DATE_ROWS[1];
  // 0=日付行、1〜EVENT_ROW_COUNT=行事欄、それ以降=記入欄
  const rowOffsets = [];
  for (let i = 0; i <= EVENT_ROW_COUNT + SLOT_ROW_COUNT; i++) rowOffsets.push(i);
  const validBgByOffset = rowOffsets.map(
    (offset) => sheet.getRange(referenceRow + offset, 1, 1, 14).getBackgrounds()[0]
  );

  // 日付の文字書式（サイズ・太さ・配置・色・表示形式）も、実際に使われたことがない列で
  // 崩れた書式が残らないよう、2週目の日付行を基準に揃える
  const dateRowRange = sheet.getRange(referenceRow, 1, 1, 14);
  const refFontSizes = dateRowRange.getFontSizes()[0];
  const refFontWeights = dateRowRange.getFontWeights()[0];
  const refAligns = dateRowRange.getHorizontalAlignments()[0];
  const refFontColors = dateRowRange.getFontColors()[0];
  const refNumberFormats = dateRowRange.getNumberFormats()[0];

  // 既存の日付をクリア
  DATE_ROWS.forEach((row) => {
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      sheet.getRange(row, pair[0]).clearContent();
    });
  });

  const firstWeekday = new Date(year, month - 1, 1).getDay(); // 0=日 ... 6=土
  const lastDate = new Date(year, month, 0).getDate();
  const holidayResult = getJapaneseHolidays(year, month);
  const holidays = holidayResult.holidays;

  // 背景色をまとめて書き換えるためのグリッド（初期値は「存在しない日」の黒塗り）
  const bgGrid = [];
  for (let i = 0; i < numRows; i++) bgGrid.push(new Array(14).fill(OUT_OF_MONTH_BG_COLOR));

  let day = 1;
  DATE_ROWS.forEach((dateRow, weekIndex) => {
    for (let colIndex = 0; colIndex < 7; colIndex++) {
      const pair = WEEKDAY_COL_PAIRS[colIndex];
      const gridIndex = weekIndex * 7 + colIndex; // 0始まりの通し週インデックス
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
      // 無効な場合は bgGrid の初期値（黒塗り）のまま
    }
  });

  sheet.getRange(topRow, 1, numRows, 14).setBackgrounds(bgGrid);

  if (day <= lastDate) {
    SpreadsheetApp.getUi().alert(
      `「${sheet.getName()}」: ${month}月は5週間のフォーマットに収まりません` +
        `（${day}日以降が配置できていません）。テンプレートの行数を手動で確認してください。`
    );
  }

  return holidayResult.error;
}

/** ===================================================================
 *  行事欄（院長会議・研修など）の追加 — 初回のみ実行
 *  =================================================================== */

// 行事欄を追加する前、原本テンプレートで実際に使われていた日付行の位置（固定値）。
// この関数はテンプレートを1回だけ移行するための処理なので、現在のDATE_ROWS定義とは別に持つ。
const LEGACY_DATE_ROWS_BEFORE_EVENT_ROW = [4, 8, 12, 16, 20];

// 「原本」テンプレートの各週の日付行のすぐ下に、行事欄(EVENT_ROW_COUNT行)を挿入する。
// 院長会議・AM2.3年目研修など、会社/エリアで決まっている定例予定を書き込めるようにするための、
// 一度だけの移行処理。既に行事欄を追加済みのテンプレートに対して再実行すると、行がずれて
// 二重に挿入されてしまうため、必ず1回だけ実行すること。
function insertEventRowIntoTemplate() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(TEMPLATE_SHEET_NAME);
  if (!sheet) {
    ui.alert(`シート「${TEMPLATE_SHEET_NAME}」が見つかりませんでした。`);
    return;
  }

  const confirmRes = ui.alert(
    '行事欄の追加（初回のみ）',
    `「${TEMPLATE_SHEET_NAME}」の各週の日付行のすぐ下に、行事欄を${EVENT_ROW_COUNT}行追加します。\n\n` +
      '院長会議・AM2.3年目研修など、会社/エリアで決まっている定例予定は、追加後にこの行事欄へ直接' +
      '入力しておくと、毎月シートを複製した際にそのまま引き継がれます。\n\n' +
      '※既に一度実行済みの場合、再実行すると行がずれて二重に追加されてしまいます。初回の1回だけ' +
      '実行してください。よろしいですか？',
    ui.ButtonSet.YES_NO
  );
  if (confirmRes !== ui.Button.YES) return;

  // 下の週から順に処理する（上の週から挿入すると、それより下の日付行の位置がずれてしまうため）
  [...LEGACY_DATE_ROWS_BEFORE_EVENT_ROW]
    .sort((a, b) => b - a)
    .forEach((dateRow) => {
      sheet.insertRowsAfter(dateRow, EVENT_ROW_COUNT);
      for (let i = 1; i <= EVENT_ROW_COUNT; i++) {
        const r = dateRow + i;
        WEEKDAY_COL_PAIRS.forEach((pair) => {
          sheet.getRange(r, pair[0], 1, pair[1] - pair[0] + 1).merge();
        });
        sheet
          .getRange(r, 1, 1, 14)
          .setBackground('#fff9d6')
          .setFontSize(9)
          .setHorizontalAlignment('center')
          .setVerticalAlignment('middle');
        sheet.setRowHeight(r, 21);
      }
    });

  ui.alert(
    '行事欄の追加 完了',
    `「${TEMPLATE_SHEET_NAME}」に行事欄を追加しました。\n` +
      '院長会議・AM2.3年目研修など定例の予定があれば、該当する曜日・週の行事欄に入力しておいてください。',
    ui.ButtonSet.OK
  );
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
  const header = ['名前', '性別', '資格', '新患対応', '院長'];
  const colWidths = [120, 90, 160, 110, 90]; // 入力しやすいよう、見出しの文字数に関わらず十分な幅を確保
  sheet.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
  sheet.setFrozenRows(1);
  colWidths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));
  ui.alert(
    'スタッフマスター作成',
    `「${MASTER_SHEET_NAME}」シートを作成しました。各スタッフの情報を1行ずつ入力してください。\n\n` +
      '・名前: 「姓　名」のようにフルネームで入力してください（区別のため）。' +
      'カレンダー・スタッフ一覧欄には自動的に姓（スペースより前の部分）だけが反映されます。' +
      '姓が同じスタッフがいると区別できないのでご注意ください\n' +
      '・性別: 「女」を含む場合（「女」「女性」どちらも可）のみ女性としてカウントします\n' +
      `・資格: ${QUALIFICATIONS.join('、')} など（複数ある場合は「、」区切り）\n` +
      '・新患対応: 対応可能なら「〇」（空欄は対応不可扱い）\n' +
      `・院長: 対象者なら「〇」（月初1〜${DIRECTOR_EARLY_WEEK_DAYS}日は、希望休を含めて公休${DIRECTOR_EARLY_WEEK_MAX}日までに制限されます）`,
    ui.ButtonSet.OK
  );
}

// マスターの「名前」欄（姓＋半角/全角スペース＋名）から、カレンダー表記に使う姓だけを取り出す
function surnameOf(name) {
  return String(name || '').trim().split(/[\s　]+/)[0];
}

// スタッフマスターを読み込み、
// { byName: { 姓: {fullName, gender, qualifications, newPatient, director} }, collisions: [...] }
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

    if (byName[displayName]) {
      collisions.push(`${byName[displayName].fullName} / ${fullName}`);
    }
    byName[displayName] = { fullName, gender, qualifications, newPatient, director };
  }
  return { byName, collisions };
}

/** ===================================================================
 *  ② 公休を自動入力
 *  =================================================================== */
function autoFillRegularHolidays() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSheet();

  const roster = findRoster(sheet);
  if (!roster.length) {
    ui.alert(
      'スタッフ一覧が見つかりませんでした。\n' +
        '「名前」という見出しの下にスタッフ名が並んでいるか確認してください（カレンダー下部の集計表）。'
    );
    return;
  }

  const confirmRes = ui.alert(
    'スタッフ確認',
    `このシートから検出したスタッフ: ${roster.join('、')}\n\nこの内容で処理を続けますか？`,
    ui.ButtonSet.YES_NO
  );
  if (confirmRes !== ui.Button.YES) return;

  // 公休数は、①で「取得可能」欄に書き込まれた数値をまず検出し、確認だけ取る（毎回の再入力を避けるため）
  let quota = getQuotaFromNote(sheet);
  if (quota !== null) {
    const confirmQuota = ui.alert(
      '公休自動入力',
      `このシートの「取得可能」欄から、今月の公休数は${quota}日と検出しました。この数値で進めてよろしいですか？`,
      ui.ButtonSet.YES_NO
    );
    if (confirmQuota !== ui.Button.YES) quota = null;
  }
  if (quota === null) {
    const quotaRes = ui.prompt(
      '公休自動入力',
      'この月の公休数（1人あたりの日数）を入力してください（例: 10）',
      ui.ButtonSet.OK_CANCEL
    );
    if (quotaRes.getSelectedButton() !== ui.Button.OK) return;
    quota = parseInt(quotaRes.getResponseText().trim(), 10);
    if (isNaN(quota)) {
      ui.alert('公休数は数値で入力してください。');
      return;
    }
  }

  // カレンダー範囲を一括取得（4行目〜最終slot行、A〜N列）
  const topRow = DATE_ROWS[0];
  const bottomRow = CALENDAR_BOTTOM_ROW;
  const numRows = bottomRow - topRow + 1;
  const range = sheet.getRange(topRow, 1, numRows, 14);
  const values = range.getValues();
  const fontColors = range.getFontColors();

  // 日ごとの情報（存在する日付・すでに埋まっている人・空きセル）を構築
  // ※ DATE_ROWS→WEEKDAY_COL_PAIRSの順で日付が昇順に埋まっているため、この days 配列は
  //   「日付が1日から連続で並ぶ、日付の昇順の配列」になる（= days[i].date は常に i+1）。
  //   連休・連勤の判定で「前後の日」を配列インデックスで参照するために、この前提を利用している。
  const days = [];
  DATE_ROWS.forEach((dateRow) => {
    WEEKDAY_COL_PAIRS.forEach((pair) => {
      const dateVal = values[dateRow - topRow][pair[0] - 1];
      if (dateVal === '' || dateVal === null) return; // その月に存在しない日は対象外

      const slotCells = [];
      for (let i = 1; i <= SLOT_ROW_COUNT; i++) {
        const r = dateRow + EVENT_ROW_COUNT + i; // 行事欄ぶんスキップして、名前記入欄だけを対象にする
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
    ui.alert('カレンダーに日付が入力されていません。先に「① 月次シートを作成」で日付を配置してください。');
    return;
  }

  // スタッフマスターを読み込み（性別・資格・新患対応・院長）
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const masterRaw = loadStaffMaster(ss);
  const masterWarnings = [];
  const master = {};
  roster.forEach((n) => {
    master[n] = (masterRaw && masterRaw.byName[n]) || {
      gender: '',
      qualifications: [],
      newPatient: false,
      director: false,
    };
  });
  if (masterRaw === null) {
    masterWarnings.push(
      `「${MASTER_SHEET_NAME}」シートが見つからないため、性別・資格・新患対応の条件は考慮せずに処理しました。` +
        '（メニューの「スタッフマスターの雛形を作成」から作成できます）'
    );
  } else {
    if (masterRaw.collisions.length) {
      masterWarnings.push(
        `「${MASTER_SHEET_NAME}」に姓が重複しているスタッフがいます（区別できません）: ${masterRaw.collisions.join(
          '、'
        )}`
      );
    }

    const unregistered = roster.filter((n) => !masterRaw.byName[n]);
    if (unregistered.length) {
      masterWarnings.push(
        `「${MASTER_SHEET_NAME}」に未登録のスタッフ: ${unregistered.join(
          '、'
        )}（性別・資格・新患対応なしとして処理しました）`
      );
    }
  }

  const qualifiedByQual = {};
  QUALIFICATIONS.forEach((q) => {
    qualifiedByQual[q] = roster.filter((n) => master[n].qualifications.includes(q));
  });
  const femaleNames = roster.filter((n) => master[n].gender.indexOf('女') !== -1);
  const newPatientNames = roster.filter((n) => master[n].newPatient);
  const directorNames = roster.filter((n) => master[n].director);

  // 院長ルール：月初DIRECTOR_EARLY_WEEK_DAYS日間の休み日数を、希望休の分も含めてカウント
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

  // 既存の入力（希望休など）だけで、すでにカバレッジ条件が崩れている日をチェック（情報提供のみ）
  const existingViolations = [];
  days.forEach((day) => {
    const working = roster.filter((n) => !day.filledNames.has(n));
    const reasons = [];
    QUALIFICATIONS.forEach((q) => {
      if (qualifiedByQual[q].length > 0 && !working.some((n) => qualifiedByQual[q].includes(n))) {
        reasons.push(`${q}0人`);
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

  // 希望休(赤字)の件数をスタッフごとに集計
  const redCountByName = {};
  roster.forEach((n) => (redCountByName[n] = 0));

  for (let r = topRow; r <= bottomRow; r++) {
    if (DATE_ROWS.includes(r) || EVENT_ROWS.includes(r)) continue; // 日付行・行事欄はスキップ
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
  }

  const needs = roster.map((name) => ({
    name,
    need: quota - (redCountByName[name] || 0),
  }));
  const overWish = needs.filter((n) => n.need < 0);

  // ---- 事前処理：連勤上限(MAX_CONSECUTIVE_WORK_DAYS)を超える区間に、公休予算の範囲内で先に休みを差し込む ----
  const usedCells = new Set(); // "r_c" で使用済みセルを管理
  const writes = [];
  const streakWarnings = [];
  const coverageNotes = []; // やむを得ずカバレッジが崩れた割り当て
  const consecutiveNotes = []; // やむを得ず連休になった割り当て
  breakLongWorkStreaks(
    needs,
    days,
    roster,
    qualifiedByQual,
    directorNames,
    directorEarlyWeekCount,
    values,
    topRow,
    usedCells,
    writes,
    streakWarnings,
    consecutiveNotes
  );

  // ---- 残りの公休予算を、資格/院長ルール(ハード制約)・連休回避・カバレッジ(ソフト制約)を踏まえて割り振る ----
  // ラウンドロビンで割り振る（1人ずつ順番に、最も休みが少ない日を優先して割り当て）。
  // 処理順・同点候補からの選択にランダム性を持たせ、毎回同じ割当パターンに固定化しないようにする。
  let progress = true;
  while (progress) {
    progress = false;
    for (const staff of shuffle(needs)) {
      if (staff.need <= 0) continue;

      const picked = pickDayForStaff(
        staff.name,
        days,
        roster,
        qualifiedByQual,
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

  // ダブルチェック用に、P列へスタッフ名を記載（Q列は既存のCOUNTIF式が希望休+自動入力分をまとめて数える）
  const summaryOverflow = writeRosterSummary(sheet, roster);

  const shortages = needs.filter((n) => n.need > 0);
  let msg = `${writes.length}件の公休を自動入力しました。`;
  if (masterWarnings.length) {
    msg += `\n\n※${masterWarnings.join('\n※')}`;
  }
  if (overWish.length) {
    msg += `\n\n※希望休(赤字)がすでに公休数を超えているスタッフ: ${overWish
      .map((n) => `${n.name}(${-n.need}日超過)`)
      .join('、')}`;
  }
  if (shortages.length) {
    msg += `\n\n※資格カバレッジの制約により割り当てきれなかったスタッフ: ${shortages
      .map((n) => `${n.name}(あと${n.need}日)`)
      .join('、')}\n手動で調整してください。`;
  }
  if (existingViolations.length) {
    msg += `\n\n※希望休の時点で既に女性/新患対応/資格のカバレッジが0人になっている日: ${existingViolations.join('、')}`;
  }
  if (directorWarnings.length) {
    msg += `\n\n※院長ルール（月初${DIRECTOR_EARLY_WEEK_DAYS}日間は公休${DIRECTOR_EARLY_WEEK_MAX}日まで）が希望休の時点で既に超過: ${directorWarnings.join(
      '、'
    )}`;
  }
  if (streakWarnings.length) {
    msg += `\n\n※連勤(${MAX_CONSECUTIVE_WORK_DAYS}日超)の解消に関する警告:\n${streakWarnings.join('\n')}`;
  }
  if (coverageNotes.length) {
    msg += `\n\n※やむを得ず女性/新患対応のカバレッジが崩れた割り当て:\n${coverageNotes.join('\n')}`;
  }
  if (consecutiveNotes.length) {
    msg += `\n\n※やむを得ず連休になった割り当て:\n${consecutiveNotes.join('\n')}`;
  }
  if (summaryOverflow.length) {
    msg += `\n\n※スタッフ数がP列の集計欄（最大${ROSTER_SUMMARY_MAX_ROWS}人）を超えているため記載できませんでした: ${summaryOverflow.join(
      '、'
    )}`;
  }
  ui.alert('公休自動入力 完了', msg, ui.ButtonSet.OK);
}

// 配列をシャッフルしたコピーを返す（元の配列は変更しない）。
// 割当処理の順序・同点候補の選択にランダム性を持たせ、毎回同じパターンに固定化しないために使う。
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
//   overridable: 資格カバレッジ（他にどうしても方法が無い場合、連勤解消の最終手段としてのみ上書きしてよい）
// の2種類に分けて返す（どちらも無ければ両方とも空配列）。
function hardConstraintReasons(day, staffName, roster, qualifiedByQual, directorNames, directorEarlyWeekCount) {
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
  QUALIFICATIONS.forEach((q) => {
    const holders = qualifiedByQual[q];
    if (!holders || holders.length === 0) return; // ロスターに該当資格者がいなければ制約なし
    if (!workingNames.some((n) => holders.includes(n))) overridable.push(`資格カバレッジ(${q}が0人)`);
  });

  return { absolute, overridable };
}

// staffName をその日に休ませることが、資格カバレッジ(ハード制約)・院長ルール(ハード制約)に違反しないかを判定
// （通常の割当では、資格カバレッジ・院長ルールのどちらも一切上書きしない。上書きが許されるのは
// breakLongWorkStreaksの最終手段の探索(pickBreakDayInStreak)だけ）
function violatesHardConstraints(day, staffName, roster, qualifiedByQual, directorNames, directorEarlyWeekCount) {
  if (day.filledNames.has(staffName)) return true; // 既にその日は休み扱い
  const { absolute, overridable } = hardConstraintReasons(
    day,
    staffName,
    roster,
    qualifiedByQual,
    directorNames,
    directorEarlyWeekCount
  );
  return absolute.length > 0 || overridable.length > 0;
}

// staffName を dayIndex(= days配列のインデックス。days[i].date は常に i+1) の日に休ませると、
// 前日または翌日もその人の公休になり「連休(MAX_CONSECUTIVE_OFF_DAYS超)」になってしまうかを判定
function wouldViolateConsecutiveOff(days, dayIndex, staffName) {
  if (MAX_CONSECUTIVE_OFF_DAYS >= 2) return false; // 連休を許容する設定なら常にfalse
  const prev = days[dayIndex - 1];
  const next = days[dayIndex + 1];
  return (!!prev && prev.filledNames.has(staffName)) || (!!next && next.filledNames.has(staffName));
}

// staffName を休みにできる日の中から、資格カバレッジ・院長ルール(ハード制約)を守った上で、
// 連休(公休の連続)にならない日を最優先候補とし、その中で「その時点で最も休みが少ない日」を優先して選ぶ。
// 同条件の候補が複数ある場合はランダムに選ぶ（月内でまんべんなく、かつ毎回同じパターンにならないようにするため）。
// 連休を避けられる候補が1つも無い場合のみ、連休ありも候補に含めて選ぶ（その場合 reasons に「連休になります」が入る）
function pickDayForStaff(
  staffName,
  days,
  roster,
  qualifiedByQual,
  femaleNames,
  newPatientNames,
  directorNames,
  directorEarlyWeekCount
) {
  const candidates = [];
  days.forEach((day, index) => {
    if (violatesHardConstraints(day, staffName, roster, qualifiedByQual, directorNames, directorEarlyWeekCount)) {
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
      crowding: day.filledNames.size, // その日に既に休んでいる人数（少ないほど優先）
    });
  });

  if (!candidates.length) return null;

  const nonConsecutive = candidates.filter((c) => !c.consecutive);
  const pool = nonConsecutive.length ? nonConsecutive : candidates;

  let bestScore = null;
  let bestGroup = [];
  pool.forEach((c) => {
    // crowdingを最優先、同点なら女性/新患対応のペナルティが小さい方を優先
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

// staffName の「休みではない日」の連続区間のうち、max日を超えて連続している最初の区間を検出する。
// 戻り値は { start, end }（days配列のインデックス、両端含む）。無ければ null。
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

// streak(連勤区間)内で、staffNameを休ませるのに最も適した日を選ぶ。
// 通常はまず、資格カバレッジ・院長ルールのどちらも守れる日だけを候補にする。
// それが1日も無い場合に限り、連勤解消（＝MAX_CONSECUTIVE_WORK_DAYSを守ること）を優先する最終手段として、
// 「資格カバレッジ」だけは上書きしてでも候補に含める（呼び出し元で、何を上書きしたか警告に出すため
// hardReasonsに上書きした理由を入れている）。
// 院長ルールは連勤解消のためでも絶対に上書きしない（院長ルールに違反する日は、この最終手段でも常に除外する）。
// どちらの段階でも、連休(公休の連続)にならない日を優先し、その中で「その時点で最も休んでいる人数が少ない日」を
// 優先する（pickDayForStaffと同じ考え方。位置ではなく混雑度で選ぶことで、全スタッフが同じ日に集中するのを防ぐ）。
// 同条件の候補が複数ある場合はランダムに選ぶ。戻り値: { index, consecutive, hardReasons } | null
function pickBreakDayInStreak(streak, staffName, days, roster, qualifiedByQual, directorNames, directorEarlyWeekCount) {
  const buildCandidates = (allowQualificationOverride) => {
    const list = [];
    for (let i = streak.start; i <= streak.end; i++) {
      const day = days[i];
      const { absolute, overridable } = hardConstraintReasons(
        day,
        staffName,
        roster,
        qualifiedByQual,
        directorNames,
        directorEarlyWeekCount
      );
      if (absolute.length) continue; // 院長ルールは最終手段でも絶対に上書きしない
      if (overridable.length && !allowQualificationOverride) continue;
      list.push({
        index: i,
        consecutive: wouldViolateConsecutiveOff(days, i, staffName),
        crowding: day.filledNames.size,
        hardReasons: overridable, // 上書きが発生した場合のみ中身が入る（呼び出し元で警告表示に使う）
      });
    }
    return list;
  };

  let candidates = buildCandidates(false);
  if (!candidates.length) {
    // 資格カバレッジを守れる日が1日も無い場合の最終手段：資格カバレッジだけは上書きしてでも連勤を解消する
    // （院長ルールは buildCandidates 内で常に除外されているため、ここでも上書きされることはない）
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
// 資格カバレッジ・院長ルールを守れる位置に公休を差し込んで解消する（この処理は①の希望休の状態に対して先に行い、
// その後に残りの公休予算を通常のラウンドロビン割当(pickDayForStaff)で埋める）。
function breakLongWorkStreaks(
  needs,
  days,
  roster,
  qualifiedByQual,
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
        qualifiedByQual,
        directorNames,
        directorEarlyWeekCount
      );

      if (!picked) {
        // 院長ルールは最終手段でも絶対に上書きしないため、区間内の全日が院長ルールに抵触する場合はここに来る
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
            // 資格カバレッジを守れる日が1日も無かったため、連勤解消を優先してやむを得ず上書きした
            // （院長ルールは pickBreakDayInStreak が常に除外しているため、ここに来ることはない）
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

// シート内の「名前」ヘッダー（スタッフ一覧欄の見出し）セルを検索
// （カレンダー内の週見出し「名前/休暇数」欄と区別するため、カレンダー下端(CALENDAR_BOTTOM_ROW)より
// 下、F列より左に絞って検索）
function findRosterHeaderCell(sheet) {
  const finder = sheet.createTextFinder('名前').matchEntireCell(true);
  const matches = finder.findAll();
  return matches.find((c) => c.getRow() > CALENDAR_BOTTOM_ROW && c.getColumn() <= 6) || null;
}

// 「名前」ヘッダーの下に並ぶスタッフ名一覧を取得
function findRoster(sheet) {
  const headerCell = findRosterHeaderCell(sheet);
  if (!headerCell) return [];

  const col = headerCell.getColumn();
  const startRow = headerCell.getRow() + 1;
  const values = sheet.getRange(startRow, col, 15, 1).getValues().flat();

  const names = values
    .map((v) => String(v).trim())
    .filter((v) => v && v !== '-');

  return [...new Set(names)];
}

// 「名前」ヘッダーの下のスタッフ一覧欄を、指定した名前リストで上書きする
// （それまで入っていた内容はクリアしてから書き込む）。ヘッダーが見つからなければ false を返す
function writeRosterNames(sheet, names) {
  const headerCell = findRosterHeaderCell(sheet);
  if (!headerCell) return false;

  const col = headerCell.getColumn();
  const startRow = headerCell.getRow() + 1;
  const clearRows = Math.max(names.length, 15);

  sheet.getRange(startRow, col, clearRows, 1).clearContent();
  if (names.length) {
    sheet.getRange(startRow, col, names.length, 1).setValues(names.map((n) => [n]));
  }
  return true;
}
