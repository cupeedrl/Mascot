import { useState, useRef, useEffect } from "react";
import { Sparkles, X, Send, Bot, User, AlertCircle, Loader2, Plus, Ban } from "lucide-react";
import {
  cancelAIAction,
  confirmAIAction,
  postAIChat,
  type AIActionConfirmation,
  type ChatMessage,
} from "../api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function AIChatDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  type ChatEntry = ChatMessage & {
    confirmation?: AIActionConfirmation;
    actionStatus?: "pending" | "confirming" | "executed" | "canceled";
  };

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  function updateActionStatus(
    actionId: string,
    actionStatus: ChatEntry["actionStatus"],
  ) {
    setMessages((current) =>
      current.map((message) =>
        message.confirmation?.action_id === actionId
          ? { ...message, actionStatus }
          : message,
      ),
    );
  }

  async function handleConfirm(action: AIActionConfirmation) {
    setError(null);
    updateActionStatus(action.action_id, "confirming");
    try {
      const result = await confirmAIAction(action.action_token);
      updateActionStatus(action.action_id, "executed");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.message },
      ]);
    } catch (err) {
      updateActionStatus(action.action_id, "pending");
      setError(err instanceof Error ? err.message : "Không thể xác nhận thao tác.");
    }
  }

  async function handleCancel(action: AIActionConfirmation) {
    setError(null);
    updateActionStatus(action.action_id, "confirming");
    try {
      const result = await cancelAIAction(action.action_token);
      updateActionStatus(action.action_id, "canceled");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.message },
      ]);
    } catch (err) {
      updateActionStatus(action.action_id, "pending");
      setError(err instanceof Error ? err.message : "Không thể hủy thao tác.");
    }
  }

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    if (trimmed.length > 1000) {
      setError("Tin nhắn không được vượt quá 1000 ký tự.");
      return;
    }

    setError(null);
    const userMessage: ChatMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, userMessage];

    setMessages(nextMessages);
    setInput("");
    setIsLoading(true);

    try {
      const response = await postAIChat(
        nextMessages.map(({ role, content }) => ({ role, content })),
      );
      setMessages((prev) => [
        ...prev,
        {
          ...response.message,
          confirmation: response.confirmation_required ?? undefined,
          actionStatus: response.confirmation_required ? "pending" : undefined,
        },
      ]);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Không thể kết nối với Trợ lý AI.";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="ai-chat-widget">
      {!isOpen && (
        <button
          className="ai-chat-trigger-button"
          type="button"
          aria-label="Mở Trợ lý AI Mascot"
          onClick={() => setIsOpen(true)}
        >
          <Sparkles size={20} className="ai-sparkle-icon" />
          <span>Trợ lý AI</span>
        </button>
      )}

      {isOpen && (
        <div className="ai-chat-drawer-container" role="dialog" aria-label="Khung trò chuyện Trợ lý AI Mascot">
          <header className="ai-chat-header">
            <div className="ai-chat-title">
              <div className="ai-badge-icon">
                <Sparkles size={16} />
              </div>
              <div>
                <strong>Trợ lý AI Mascot</strong>
                <small>Hỏi đáp tiếng Anh & hướng dẫn học tập</small>
              </div>
            </div>
            <button
              className="icon-button ai-chat-close-button"
              type="button"
              aria-label="Đóng Trợ lý AI"
              onClick={() => setIsOpen(false)}
            >
              <X size={18} />
            </button>
          </header>

          {error && (
            <div className="ai-chat-error-banner" role="alert">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="ai-chat-messages-list">
            {messages.length === 0 ? (
              <div className="ai-chat-empty-state">
                <Bot size={32} />
                <p>Xin chào! Tôi là Trợ lý AI Mascot.</p>
                <small>Hãy đặt câu hỏi bất kỳ về từ vựng hoặc lộ trình học tập của bạn!</small>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={index}
                  className={`ai-chat-message-bubble ${
                    msg.role === "user" ? "user-bubble" : "assistant-bubble"
                  }`}
                >
                  <div className="avatar-icon">
                    {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
                  </div>
                  <div className="message-content">
                    {msg.role === "assistant" ? (
                      <div className="ai-chat-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      msg.content
                    )}
                    {msg.confirmation && (
                      <div className="ai-action-confirmation-card">
                        <div className="ai-action-card-title">
                          <Plus size={15} />
                          <strong>{msg.confirmation.summary}</strong>
                        </div>
                        <dl>
                          <div><dt>Word</dt><dd>{msg.confirmation.vocabulary.word}</dd></div>
                          <div><dt>Meaning</dt><dd>{msg.confirmation.vocabulary.meaning}</dd></div>
                          <div><dt>Vietnamese</dt><dd>{msg.confirmation.vocabulary.translation}</dd></div>
                          <div><dt>Level</dt><dd>{msg.confirmation.vocabulary.level_code}</dd></div>
                        </dl>
                        {msg.actionStatus === "pending" && (
                          <div className="ai-action-card-buttons">
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() => void handleCancel(msg.confirmation!)}
                            >
                              <Ban size={14} /> Cancel
                            </button>
                            <button
                              type="button"
                              className="primary-button"
                              onClick={() => void handleConfirm(msg.confirmation!)}
                            >
                              <Plus size={14} /> Confirm
                            </button>
                          </div>
                        )}
                        {msg.actionStatus === "confirming" && (
                          <div className="ai-action-card-status"><Loader2 size={14} className="spin-loader" /> Processing…</div>
                        )}
                        {msg.actionStatus === "executed" && <div className="ai-action-card-status success">Confirmed</div>}
                        {msg.actionStatus === "canceled" && <div className="ai-action-card-status">Canceled</div>}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="ai-chat-message-bubble assistant-bubble loading-bubble">
                <div className="avatar-icon">
                  <Bot size={14} />
                </div>
                <div className="message-content loading-content">
                  <Loader2 size={16} className="spin-loader" />
                  <span>Đang suy nghĩ...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="ai-chat-input-form" onSubmit={handleSend}>
            <input
              type="text"
              className="ai-chat-input-field"
              placeholder="Nhập câu hỏi của bạn..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              maxLength={1000}
            />
            <button
              type="submit"
              className="ai-chat-send-button"
              disabled={!input.trim() || isLoading}
              aria-label="Gửi tin nhắn"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
