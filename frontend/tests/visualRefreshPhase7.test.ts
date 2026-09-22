import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path: string) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("brand tokens use the restored purple palette", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /--primary:\s*#6658e8/);
  assert.match(css, /--primary-hover:\s*#5044c8/);
  assert.match(css, /--accent:\s*#a89df7/);
  assert.match(css, /--background:\s*#f6f5fb/);
  assert.match(css, /--ink:\s*#19182b/);
  assert.match(css, /--hero-gradient-start:\s*#f1efff/);
  assert.match(css, /--hero-gradient-end:\s*#ebe8ff/);
});

test("dashboard combines the penguin brand with the purple background", async () => {
  const [css, dashboard] = await Promise.all([
    source("src/styles.css"),
    source("src/pages/AppHomePage.tsx"),
  ]);

  assert.match(css, /\.dashboard-page\s*{[^}]*--dashboard-warm:\s*#f1efff;[^}]*--dashboard-warm-soft:\s*#f6f4ff;[^}]*display:\s*grid;/s);
  assert.match(css, /\.dashboard-learning-hero\s*{[^}]*linear-gradient\(135deg, var\(--hero-gradient-start\) 0%, #f6f4ff 58%, var\(--hero-gradient-end\) 100%\)/s);
  assert.match(dashboard, /PenguinMark size=\{224\} variant="scholar"/);
  assert.doesNotMatch(dashboard, /DolphinMark|BeeMark/);
});

test("homepage hero uses the scholar penguin and useful summary cards", async () => {
  const [mark, dashboard] = await Promise.all([
    source("src/components/PenguinMark.tsx"),
    source("src/pages/AppHomePage.tsx"),
  ]);

  assert.match(mark, /variant === "scholar" \|\| variant === "learning"/);
  assert.match(mark, /penguin-mark-scholar/);
  assert.match(mark, /Mascot scholar penguin/);
  assert.match(dashboard, /activeTrack\.name/);
  assert.match(dashboard, /dashboard\.words_due_for_review/);
  assert.match(dashboard, /dashboard\.total_vocabulary/);
  assert.match(dashboard, /Công việc bây giờ/);
  assert.match(dashboard, /<b>10<\/b> phút/);
  assert.match(dashboard, /hasStudiedToday/);
  assert.match(dashboard, /today-date-copy/);
  assert.match(dashboard, /<span>Hôm nay<\/span>\s*<strong>\{today\.weekday\}<\/strong>\s*<time>\{today\.dayAndMonth\}<\/time>/);
  assert.match(dashboard, /today-action-row/);
  assert.match(dashboard, /Ôn ngay/);
});

test("homepage uses a track-scoped navigable monthly study calendar", async () => {
  const [dashboard, calendar, client] = await Promise.all([
    source("src/pages/AppHomePage.tsx"),
    source("src/components/StudyActivityCalendar.tsx"),
    source("src/api/client.ts"),
  ]);

  assert.match(dashboard, /getStudyCalendar\(activeTrack\.id, calendarCursor\.year, calendarCursor\.month\)/);
  assert.match(dashboard, /onPreviousMonth=\{\(\) => moveCalendarMonth\(-1\)\}/);
  assert.match(dashboard, /onNextMonth=\{\(\) => moveCalendarMonth\(1\)\}/);
  assert.doesNotMatch(dashboard, /streak-calendar|activityWeek/);
  assert.match(calendar, /Array\.from\(\{ length: 42 \}/);
  assert.match(calendar, /Tháng trước/);
  assert.match(calendar, /Tháng sau/);
  assert.match(calendar, /isActive \? "active"/);
  assert.match(calendar, /isToday \? "today"/);
  assert.match(calendar, /study-calendar-body/);
  assert.match(client, /\/dashboard\/study-calendar\?/);
});

test("calendar uses a denser readable seven-column rhythm", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /\.study-calendar-weekdays,[\s\S]*?grid-template-columns:\s*repeat\(7, minmax\(0, 1fr\)\);[\s\S]*?column-gap:\s*2px;/);
  assert.match(css, /\.study-calendar-grid time\s*{[^}]*width:\s*100%;[^}]*height:\s*30px;[^}]*font-size:\s*11\.5px;/s);
});

test("dashboard track context avoids duplicate progress metrics and renders language flags", async () => {
  const [dashboard, css, ukFlag, chinaFlag] = await Promise.all([
    source("src/pages/AppHomePage.tsx"),
    source("src/styles.css"),
    source("public/flags/gb.svg"),
    source("public/flags/cn.svg"),
  ]);

  assert.match(dashboard, /Trình độ hiện tại/);
  assert.match(dashboard, /activeTrack\.name.*Lộ trình/s);
  assert.match(dashboard, /Mốc tiếp theo/);
  assert.match(dashboard, /en:\s*"\/flags\/gb\.svg"/);
  assert.match(dashboard, /zh:\s*"\/flags\/cn\.svg"/);
  assert.match(dashboard, /<img[\s\S]*?className="track-language-flag"[\s\S]*?src=\{languageFlag\(track\.language\.code\)\}/);
  assert.match(css, /\.track-language-flag\s*{[^}]*width:\s*30px;[^}]*height:\s*20px;[^}]*object-fit:\s*cover;/s);
  assert.match(css, /\.dashboard-learning-hero \.dashboard-track-controls\s*{[^}]*grid-template-columns:\s*minmax\(0, 1fr\) minmax\(150px, 180px\);/s);
  assert.match(ukFlag, /<svg[\s\S]*?Flag of the United Kingdom/);
  assert.match(chinaFlag, /<svg[\s\S]*?Flag of China/);
});

test("desktop account control is top-right and logout remains in its menu", async () => {
  const [layout, css] = await Promise.all([
    source("src/components/AppLayout.tsx"),
    source("src/styles.css"),
  ]);

  assert.match(layout, /desktop-account-bar/);
  assert.match(layout, /aria-haspopup="menu"/);
  assert.match(layout, /desktop-account-dropdown/);
  assert.doesNotMatch(layout, /className="account-summary"/);
  assert.match(css, /\.desktop-account-bar\s*{[^}]*position:\s*fixed;[^}]*top:\s*16px;[^}]*right:/s);
});

test("retired warm yellow brand values are absent from active frontend styles", async () => {
  const css = (await source("src/styles.css")).toLowerCase();
  // Warm-theme token values only; semantic amber accents such as the practice icon predate the refresh.
  for (const retiredColor of ["#92400e", "#fdba74", "#fff4cc", "#fffcf5", "#f5e4b8", "#efd394", "#fffdf7", "#fff3d6"]) {
    assert.equal(css.includes(retiredColor), false, retiredColor);
  }
});

test("penguin mark is used at primary brand and learning moments", async () => {
  const [mark, auth, dashboard, layout, review, practice] = await Promise.all([
    source("src/components/PenguinMark.tsx"),
    source("src/pages/AuthPage.tsx"),
    source("src/pages/AppHomePage.tsx"),
    source("src/components/AppLayout.tsx"),
    source("src/pages/ReviewPage.tsx"),
    source("src/pages/PracticePage.tsx"),
  ]);

  assert.match(mark, /aria-label=\{decorative \? undefined : "Mascot scholar penguin"\}/);
  assert.match(mark, /<svg/);
  assert.match(auth, /PenguinMark/);
  assert.match(dashboard, /PenguinMark/);
  assert.match(layout, /PenguinMark/);
  assert.match(review, /PenguinMark/);
  assert.match(practice, /PenguinMark/);
});

test("favicon uses the penguin mark", async () => {
  const index = await source("index.html");

  assert.match(index, /type="image\/svg\+xml" href="\/favicon\.svg"/);
});

test("mascot mark keeps a transparent, blend-free base style", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /\.penguin-mark\s*{[^}]*object-fit:\s*contain;[^}]*background:\s*transparent;/s);
  assert.doesNotMatch(css, /\.penguin-mark\s*{[^}]*mix-blend-mode:/s);
});

test("chat positioning and responsive viewport bounds remain intact", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /\.ai-chat-widget\s*{[^}]*position:\s*fixed;[^}]*bottom:\s*24px;[^}]*right:\s*24px;/s);
  assert.match(css, /\.ai-chat-drawer-container\s*{[^}]*max-width:\s*calc\(100vw - 32px\);[^}]*max-height:\s*min\(70vh, calc\(100vh - 100px\)\);/s);
});
