import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("deleting a word asks inside the page, not with a native dialog", async () => {
  const page = await readFile(new URL("../src/pages/VocabularyPage.tsx", import.meta.url), "utf8");
  // Embedded browsers can block window.confirm, which silently cancelled every delete.
  assert.doesNotMatch(page, /window\.confirm/);
  assert.match(page, /setConfirmingId\(item\.id\)/);
  assert.match(page, /onClick=\{\(\) => void handleDelete\(item\)\}/);
});

test("no page uses native confirm or alert dialogs", async () => {
  for (const page of ["VocabularyPage", "AdminUsersPage", "AdminUserDetailPage"]) {
    const source = await readFile(new URL(`../src/pages/${page}.tsx`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /window\.confirm|window\.alert|[^.\w]alert\(/, page);
  }
  const admin = await readFile(new URL("../src/pages/AdminUsersPage.tsx", import.meta.url), "utf8");
  assert.match(admin, /<ConfirmDialog/);
});

test("the floating account bar slides away on scroll instead of covering cards", async () => {
  const [layout, css] = await Promise.all([
    readFile(new URL("../src/components/AppLayout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/styles.css", import.meta.url), "utf8"),
  ]);
  assert.match(layout, /isAccountBarHidden && !isAccountMenuOpen \? " is-hidden"/);
  assert.match(css, /\.desktop-account-bar\.is-hidden:not\(:focus-within\)\s*{[^}]*transform:/s);
});
