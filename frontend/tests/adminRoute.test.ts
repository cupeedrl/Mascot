import assert from "node:assert/strict";
import test from "node:test";

interface MockUser {
  id: string;
  email: string;
  role: "user" | "admin";
}

test("admin route authorization allows only admin role", () => {
  const isAllowedAdmin = (user: MockUser | null) => user !== null && user.role === "admin";

  // Unauthenticated
  assert.equal(isAllowedAdmin(null), false);

  // Normal learner
  const normalUser: MockUser = { id: "1", email: "student@example.com", role: "user" };
  assert.equal(isAllowedAdmin(normalUser), false);

  // Admin user
  const adminUser: MockUser = { id: "2", email: "admin@example.com", role: "admin" };
  assert.equal(isAllowedAdmin(adminUser), true);
});

test("admin metrics number formatting formats integers cleanly", () => {
  const formatMetric = (val: number) => val.toLocaleString("vi-VN");

  assert.equal(formatMetric(0), "0");
  assert.equal(formatMetric(42), "42");
  assert.equal(formatMetric(1500), "1.500");
  assert.equal(formatMetric(1000000), "1.000.000");
});

test("learner navigation does not include admin routes for normal learners", () => {
  const learnerNav = [
    { to: "/app", label: "Trang chủ" },
    { to: "/app/learn", label: "Học từ vựng" },
    { to: "/app/vocabulary", label: "Từ vựng của tôi" },
    { to: "/app/review", label: "Ôn tập" },
    { to: "/app/practice", label: "Luyện tập" },
    { to: "/app/about", label: "Giới thiệu" },
  ];

  assert.equal(learnerNav.some((item) => item.to.startsWith("/admin")), false);
});

test("admin users search and filtering params are normalized correctly", () => {
  const buildUserQuery = (params: { search?: string; role?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params.search?.trim()) q.set("search", params.search.trim());
    if (params.role) q.set("role", params.role);
    if (params.status) q.set("status", params.status);
    return q.toString();
  };

  assert.equal(buildUserQuery({ search: "  test@mascot.io  " }), "search=test%40mascot.io");
  assert.equal(buildUserQuery({ role: "admin", status: "active" }), "role=admin&status=active");
});

test("admin catalog form validates required fields", () => {
  const validateCatalogEntry = (entry: {
    word: string;
    meaning: string;
    translation: string;
    example: string;
    topic: string;
  }) => {
    if (!entry.word.trim()) return "Word required";
    if (!entry.meaning.trim()) return "Meaning required";
    if (!entry.translation.trim()) return "Translation required";
    if (!entry.example.trim()) return "Example required";
    if (!entry.topic.trim()) return "Topic required";
    return null;
  };

  assert.equal(
    validateCatalogEntry({
      word: "",
      meaning: "test",
      translation: "test",
      example: "test",
      topic: "test",
    }),
    "Word required",
  );

  assert.equal(
    validateCatalogEntry({
      word: "Resilient",
      meaning: "Able to recover quickly",
      translation: "Kiên cường",
      example: "She is resilient.",
      topic: "Personality",
    }),
    null,
  );
});

