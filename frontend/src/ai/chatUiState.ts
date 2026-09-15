export type ActionFailureState = "expired" | "used" | "pending";

type ApiFailure = Error & { status: number };

function isApiFailure(error: unknown): error is ApiFailure {
  return error instanceof Error && "status" in error && typeof error.status === "number";
}

export function getChatProgressLabel(message: string): string {
  const normalized = message.toLocaleLowerCase("vi");
  if (/\b(add|save)\b|thêm|lưu/.test(normalized)) {
    return "Đang chuẩn bị thao tác…";
  }
  if (/review|due|ôn tập|cần ôn|đến hạn/.test(normalized)) {
    return "Đang kiểm tra lịch ôn tập…";
  }
  if (/progress|stats|statistics|tiến độ|thống kê/.test(normalized)) {
    return "Đang kiểm tra tiến độ học…";
  }
  return "AI đang suy nghĩ…";
}

export function getChatErrorMessage(error: unknown): string {
  if (!isApiFailure(error)) {
    return error instanceof Error
      ? error.message
      : "Không thể kết nối với Trợ lý AI.";
  }
  if (error.message === "AI learning data is temporarily unavailable.") {
    return "Dữ liệu học tập tạm thời chưa khả dụng. Vui lòng thử lại.";
  }
  if (error.status === 502 || error.status === 503 || error.status === 504) {
    return "Dịch vụ AI tạm thời chưa khả dụng. Vui lòng thử lại sau.";
  }
  return error.message;
}

export function getActionErrorState(error: unknown): {
  state: ActionFailureState;
  message: string;
} {
  if (isApiFailure(error)) {
    if (error.message === "AI action has expired.") {
      return { state: "expired", message: "Thao tác đã hết hạn. Hãy yêu cầu AI chuẩn bị lại." };
    }
    if (error.message === "AI action was already handled.") {
      return { state: "used", message: "Thao tác này đã được xử lý trước đó." };
    }
  }
  return {
    state: "pending",
    message: error instanceof Error ? error.message : "Không thể xử lý thao tác.",
  };
}
