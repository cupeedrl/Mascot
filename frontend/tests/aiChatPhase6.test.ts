import assert from "node:assert/strict";
import test from "node:test";

import { ApiError } from "../src/api/client.ts";
import {
  getActionErrorState,
  getChatErrorMessage,
  getChatProgressLabel,
} from "../src/ai/chatUiState.ts";

test("chat progress labels distinguish thinking, reads, and action preparation", () => {
  assert.equal(getChatProgressLabel("Explain the word subtle"), "AI đang suy nghĩ…");
  assert.equal(getChatProgressLabel("Tiến độ của tôi thế nào?"), "Đang kiểm tra tiến độ học…");
  assert.equal(getChatProgressLabel("Từ nào cần ôn tập?"), "Đang kiểm tra lịch ôn tập…");
  assert.equal(getChatProgressLabel("Thêm resilient vào danh sách"), "Đang chuẩn bị thao tác…");
});

test("chat errors distinguish learning data and provider availability", () => {
  assert.match(
    getChatErrorMessage(new ApiError(502, "AI learning data is temporarily unavailable.")),
    /Dữ liệu học tập/,
  );
  assert.match(getChatErrorMessage(new ApiError(503, "upstream unavailable")), /Dịch vụ AI/);
});

test("action errors produce deterministic expired and replay states", () => {
  assert.deepEqual(getActionErrorState(new ApiError(400, "AI action has expired.")), {
    state: "expired",
    message: "Thao tác đã hết hạn. Hãy yêu cầu AI chuẩn bị lại.",
  });
  assert.equal(
    getActionErrorState(new ApiError(409, "AI action was already handled.")).state,
    "used",
  );
});
