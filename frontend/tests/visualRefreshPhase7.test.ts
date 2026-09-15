import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path: string) =>
  readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("brand tokens use the final warm yellow and orange palette", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /--primary:\s*#f59e0b/);
  assert.match(css, /--primary-hover:\s*#d97706/);
  assert.match(css, /--accent:\s*#fdba74/);
  assert.match(css, /--background:\s*#fffcf5/);
  assert.match(css, /--ink:\s*#1f2937/);
  assert.match(css, /--hero-gradient-start:\s*#fffdf7/);
  assert.match(css, /--hero-gradient-end:\s*#fff3d6/);
});

test("dashboard combines the bee brand with the selected warm background", async () => {
  const [css, dashboard] = await Promise.all([
    source("src/styles.css"),
    source("src/pages/AppHomePage.tsx"),
  ]);

  assert.match(css, /\.dashboard-page\s*{[^}]*--dashboard-warm:\s*#fffdf7;[^}]*--dashboard-warm-soft:\s*#fff8e8;[^}]*display:\s*grid;/s);
  assert.match(css, /\.dashboard-learning-hero\s*{[^}]*linear-gradient\(135deg, var\(--hero-gradient-start\) 0%, #fff8e8 58%, var\(--hero-gradient-end\) 100%\)/s);
  assert.match(dashboard, /BeeMark size=\{224\} variant="hero"/);
  assert.doesNotMatch(dashboard, /DolphinMark|PenguinMark/);
});

test("homepage hero uses a side-facing learning bee and useful summary cards", async () => {
  const [mark, dashboard] = await Promise.all([
    source("src/components/BeeMark.tsx"),
    source("src/pages/AppHomePage.tsx"),
  ]);

  assert.match(mark, /hero:\s*"\/mascot\/bee-hero\.png"/);
  assert.match(mark, /bee-mark-side/);
  assert.match(mark, /Mascot bee learning from a book/);
  assert.match(dashboard, /activeTrack\.name/);
  assert.match(dashboard, /dashboard\.words_due_for_review/);
  assert.match(dashboard, /dashboard\.total_vocabulary/);
  assert.match(dashboard, /Trọng tâm hôm nay/);
  assert.match(dashboard, /<b>10<\/b> phút/);
  assert.match(dashboard, /hasStudiedToday/);
  assert.match(dashboard, /today-date-copy/);
  assert.match(dashboard, /<span>Hôm nay<\/span>\s*<strong>\{today\.weekday\}<\/strong>\s*<time>· \{today\.dayAndMonth\}<\/time>/);
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

test("legacy purple brand values are absent from active frontend styles", async () => {
  const css = (await source("src/styles.css")).toLowerCase();
  for (const legacyColor of ["#6658e8", "#5044c8", "#7c3aed", "rgb(102 88 232"]) {
    assert.equal(css.includes(legacyColor), false, legacyColor);
  }
});

test("bee mark is used at primary brand and learning moments", async () => {
  const [mark, auth, dashboard, layout, review, practice] = await Promise.all([
    source("src/components/BeeMark.tsx"),
    source("src/pages/AuthPage.tsx"),
    source("src/pages/AppHomePage.tsx"),
    source("src/components/AppLayout.tsx"),
    source("src/pages/ReviewPage.tsx"),
    source("src/pages/PracticePage.tsx"),
  ]);

  assert.match(mark, /alt=\{decorative \? "" : "Mascot bee learning from a book"\}/);
  assert.match(mark, /default:\s*"\/mascot\/bee-mark\.png"/);
  assert.match(mark, /learning:\s*"\/mascot\/bee-learning\.png"/);
  assert.match(mark, /scholar:\s*"\/mascot\/bee-learning\.png"/);
  assert.match(mark, /hero:\s*"\/mascot\/bee-hero\.png"/);
  assert.doesNotMatch(mark, /<svg|<path|useId/);
  assert.match(auth, /BeeMark/);
  assert.match(dashboard, /BeeMark/);
  assert.match(layout, /BeeMark/);
  assert.match(review, /BeeMark/);
  assert.match(practice, /BeeMark/);
});

test("favicon uses the same graduate bee direction", async () => {
  const index = await source("index.html");

  assert.match(index, /type="image\/png" href="\/mascot\/favicon\.png"/);
});

test("external mascot images are ready for transparent replacement assets", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /\.bee-mark\s*{[^}]*object-fit:\s*contain;[^}]*background:\s*transparent;/s);
  assert.doesNotMatch(css, /\.bee-mark\s*{[^}]*mix-blend-mode:/s);
});

test("chat positioning and responsive viewport bounds remain intact", async () => {
  const css = await source("src/styles.css");

  assert.match(css, /\.ai-chat-widget\s*{[^}]*position:\s*fixed;[^}]*bottom:\s*24px;[^}]*right:\s*24px;/s);
  assert.match(css, /\.ai-chat-drawer-container\s*{[^}]*max-width:\s*calc\(100vw - 32px\);[^}]*max-height:\s*min\(70vh, calc\(100vh - 100px\)\);/s);
});
