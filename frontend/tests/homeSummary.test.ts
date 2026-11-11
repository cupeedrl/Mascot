import assert from "node:assert/strict";
import test from "node:test";

import {
  accuracyText,
  dailyIndex,
  estimateMinutes,
  greetingName,
  relativeDay,
  streakSentence,
  todayIso,
  todayPlan,
} from "../src/features/home/homeSummary.ts";

test("today's plan prefers due words, then practice, then a first topic", () => {
  const review = todayPlan({ wordsDue: 12, totalVocabulary: 40, practiceQuestions: 5 });
  assert.equal(review.kind, "review");
  assert.equal(review.title, "Ôn 12 từ đang chờ");
  assert.match(review.detail, /12 từ sắp bị quên/);
  assert.equal(review.minutes, 4); // 12 words x 20 s
  assert.equal(review.to, "/app/review");

  const many = todayPlan({ wordsDue: 75, totalVocabulary: 200, practiceQuestions: 5 });
  assert.equal(many.title, "Ôn 30 từ trước");
  assert.equal(many.minutes, 10);
  assert.match(many.detail, /75 từ đến hạn.*45 từ còn lại/);

  const practice = todayPlan({ wordsDue: 0, totalVocabulary: 40, practiceQuestions: 5 });
  assert.equal(practice.kind, "practice");
  assert.equal(practice.minutes, 4); // 5 questions x 40 s

  const start = todayPlan({ wordsDue: 0, totalVocabulary: 0, practiceQuestions: 5 });
  assert.equal(start.kind, "start");
  assert.equal(start.minutes, null);
  assert.equal(start.title, "Mở sổ từ đầu tiên");
});

test("time estimates round up and never show zero for real work", () => {
  assert.equal(estimateMinutes(0, 20), 0);
  assert.equal(estimateMinutes(1, 20), 1);
  assert.equal(estimateMinutes(3, 20), 1);
  assert.equal(estimateMinutes(4, 20), 2);
});

test("streak sentences read naturally", () => {
  assert.equal(streakSentence(0, false), "Học hôm nay để bắt đầu một chuỗi mới.");
  assert.equal(streakSentence(4, false), "Học hôm nay để giữ chuỗi 4 ngày.");
  assert.equal(streakSentence(1, true), "Bạn đã học hôm nay.");
  assert.equal(streakSentence(5, true), "Bạn đã học hôm nay, chuỗi 5 ngày liên tiếp.");
});

test("dates are relative in the learner's time zone", () => {
  const now = new Date("2026-11-11T03:00:00Z"); // 10:00 in Vietnam
  assert.equal(todayIso(now), "2026-11-11");
  assert.equal(todayIso(new Date("2026-11-10T18:30:00Z")), "2026-11-11"); // 01:30 next day in Vietnam
  assert.equal(relativeDay("2026-11-11T01:00:00Z", now), "Hôm nay");
  assert.equal(relativeDay("2026-11-10T08:00:00Z", now), "Hôm qua");
  assert.equal(relativeDay("2026-11-08T08:00:00Z", now), "3 ngày trước");
  assert.equal(relativeDay("2026-10-02T08:00:00Z", now), "02/10");
  assert.equal(relativeDay("2025-10-02T08:00:00Z", now), "02/10/2025");
});

test("accuracy shows a dash until an exercise is done", () => {
  assert.equal(accuracyText(0, 0), "—");
  assert.equal(accuracyText(80, 5), "80%");
  assert.equal(accuracyText(66.666, 3), "66.7%");
});

test("greeting uses the given name", () => {
  assert.equal(greetingName("Trần Minh Thư", "minhthu"), "Thư");
  assert.equal(greetingName(null, "minhthu"), "minhthu");
  assert.equal(greetingName("  ", null), null);
});

test("the word of the day is stable for a day and changes between days", () => {
  const first = dailyIndex("2026-11-11", "track:HSK3", 1000);
  assert.equal(dailyIndex("2026-11-11", "track:HSK3", 1000), first);
  assert.ok(first >= 0 && first < 1000);
  const week = new Set(
    ["2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"].map((day) => dailyIndex(day, "track:HSK3", 1000)),
  );
  assert.ok(week.size >= 4); // different days give (almost always) different words
  assert.equal(dailyIndex("2026-11-11", "x", 0), 0);
});
