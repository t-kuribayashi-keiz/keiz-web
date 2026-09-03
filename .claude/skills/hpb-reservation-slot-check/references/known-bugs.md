# Known root causes (予約枠チェック)

Confirmed 2026-09-03, working on `START_DATE`/`END_DATE` = 2026-09-03/04. Symptom that led
to all of this: the sheet showed "-"/"○" for all ~142 shops, every run, regardless of date
range — i.e. the checker never actually found any real ✕, and looked "suspiciously all-fine."

## Bug #1 (root cause): zero-padded day-of-month never matches the lookup key

In `scrape_hpb_robust`, the calendar's date headers are read via:

```python
headers = await page.query_selector_all(".dayCellContainer th")
for header in headers:
    text = await header.inner_text()
    match = re.search(r'(\d+)', text)
    if match:
        date_to_col_idx[match.group(1)] = valid_idx   # BUG: raw match, can be "03"
        valid_idx += 1
```

...while the lookup key built from the target date is `day_num = str(dt.day)` — e.g. `"3"`,
never zero-padded. `"03" != "3"`, so the `if day_num in date_to_col_idx:` check in the date
loop **always failed**, `calendar_data` came back empty for literally every shop, and
`judge_occupancy_rate` had zero slots to evaluate → always returned `"-"` → `main_process`
folded that into a false "○" (see bug #2). This is why the sheet looked uniformly "fine" —
the scraper wasn't finding *anything*, not even the ✕ cases.

**Why this was hard to spot**: manually inspecting the calendar page's DOM in a real browser
(`element.innerText` in DevTools) showed short strings like `"3\n(木)"` for these `<th>`
elements. But **headless Playwright's `inner_text()` on the same selector returned a much
longer string** — `'Thu Sep 03 00:00:00 JST 2026\nThu Sep 03 00:00:00 JST 2026'` — presumably
because the page has both a visible short label and an accessibility/title-style full-date
string, and which one `inner_text()` surfaces differs between a real rendered browser and
headless. The regex still matched a numeric group either way, but from the headless string
it captured the zero-padded day out of `Sep 03`. **Lesson: when a headless scraper's parsed
values look wrong, don't just trust that headless `inner_text()` matches what you see in a
manual DevTools inspection of the "same" selector — dump `repr()` of the actual headless
value before assuming the selector or regex is the problem.**

**Fix**: normalize both sides to the same representation —

```python
date_to_col_idx[str(int(match.group(1)))] = valid_idx
```

Verified by reimplementing the header-parsing logic standalone against a live shop
(さかいし院, storeId=H000739485) and confirming real `×`/`◎` statuses came back once the
zero-padding was normalized, then applying the same one-line fix to the real function and
re-verifying end-to-end.

## Bug #2 (compounding, silent-failure risk): "no data at all" was indistinguishable from "checked, and it's fine"

Even independent of bug #1, `judge_occupancy_rate` returns `"-"` when there are no scoreable
slots for a half-day window (empty input, or every slot filtered out). `main_process`'s
final per-shop judgment was:

```python
if res == "✕": has_any_ng = True
...
final_judge = "✕" if has_any_ng else "○"
```

A shop where *every* half-day came back `"-"` (i.e. the scraper found genuinely zero usable
data — a scraping failure, not "no problems found") still produced `final_judge = "○"`. This
is a silent-failure trap: any future scraping regression (site structure change, blocked
request, bad URL — see bug #3) will keep reporting "everything's fine" instead of surfacing
that the tool couldn't check at all.

**Fix**: track whether *any* half-day actually produced real data, separately from whether
any of it was ✕:

```python
has_any_ng = has_any_ng or (res == "✕"); has_any_data = has_any_data or (res != "-")
...
final_judge = "✕" if has_any_ng else ("○" if has_any_data else "?")
```

A shop with zero real data across the whole window now reports `"?"` instead of a false
`"○"`, so someone notices "this one couldn't be checked" instead of trusting a clean bill of
health that was never actually earned. Applied to `has_any_ng = False` (add `has_any_data =
False` alongside it) and the `if res == "✕": has_any_ng = True` line, and to the
`final_judge = ...` line — three single-line edits total.

## Bug #3 (data quality, not a code bug): a stale/dead URL in the sheet reads identically to a scraping failure

One shop in row 3 of the sheet, たいよう鍼灸整骨院 深江橋
(`storeId=H000568996&couponId=CP00000009972021`), has a dead listing on HotPepper's side —
navigating there serves a "掲載エラー" (listing error) page, confirmed by opening the exact
`base_url` the sheet stores in a real browser tab. `scrape_hpb_robust` correctly detects the
missing `.timeTableLeft` and returns `{}` after its 3 retries, so with bug #2 fixed this now
correctly surfaces as `"?"` rather than a false `"○"` — but no amount of scraper fixing will
make a genuinely broken URL scrape successfully. **When a specific shop (not all shops)
comes back with zero data, check whether its stored URL actually resolves before assuming
the code has a per-shop bug** — open the URL directly and look at the page title/content.
The fix here is someone updating the sheet's stored URL for that shop, not a code change.
