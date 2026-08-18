import assert from "node:assert/strict";
import test from "node:test";
import { BookOpen, BriefcaseBusiness, Plane, School, Users } from "lucide-react";

import { getTopicAccent, getTopicIcon } from "../src/features/learn/topicPresentation.ts";

test("topic presentation maps catalog topics to their matching Lucide icons", () => {
  assert.equal(getTopicIcon("Travel"), Plane);
  assert.equal(getTopicIcon("School"), School);
  assert.equal(getTopicIcon("Family"), Users);
  assert.equal(getTopicIcon("Work & Business"), BriefcaseBusiness);
  assert.equal(getTopicIcon("Unknown topic"), BookOpen);
});

test("topic presentation gives the same topic a stable accent", () => {
  assert.equal(getTopicAccent("Global Issues"), getTopicAccent(" global issues "));
});
