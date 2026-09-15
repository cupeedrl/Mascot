import { useState, useRef, useEffect } from "react";
import { Sparkles, X, Send, Bot, User, AlertCircle, Loader2, Plus, Ban, History } from "lucide-react";
import {
  cancelAIAction,
  confirmAIAction,
  createAIConversation,
  getAIConversation,
  listAIConversations,
  postAIChat,
  type AIActionConfirmation,
  type AIConversationSummary,
  type ChatMessage,
} from "../api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  getActionErrorState,
  getChatErrorMessage,
  getChatProgressLabel,
} from "../ai/chatUiState";
import { useActiveLearningTrack } from "../learning/ActiveLearningTrackContext";
import { useAuth } from "../auth/AuthContext";

const ACTIVE_CONVERSATION_STORAGE_PREFIX = "mascot.aiConversationId";

export function AIChatDrawer() {
  const { activeTrack } = useActiveLearningTrack();
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  type ChatEntry = ChatMessage & {
    id?: string;
    confirmation?: AIActionConfirmation;
    actionStatus?: "pending" | "confirming" | "executed" | "canceled" | "expired" | "used";
  };

  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [conversations, setConversations] = useState<AIConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [progressLabel, setProgressLabel] = useState("AI đang suy nghĩ…");
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) {
      setMessages([]);
      setConversations([]);
      setActiveConversationId(null);
      setIsRestoring(false);
      return;
    }

    let active = true;
    const storageKey = `${ACTIVE_CONVERSATION_STORAGE_PREFIX}.${user.id}`;
    setIsRestoring(true);

    async function restoreConversation() {
      try {
        const available = await listAIConversations();
        if (!active) return;
        setConversations(available);
        const preferredId = localStorage.getItem(storageKey);
        const selected =
          available.find((conversation) => conversation.id === preferredId) ??
          available[0];
        if (!selected) {
          setMessages([]);
          setActiveConversationId(null);
          localStorage.removeItem(storageKey);
          return;
        }
        const detail = await getAIConversation(selected.id);
        if (!active) return;
        setActiveConversationId(detail.id);
        setMessages(detail.messages);
        localStorage.setItem(storageKey, detail.id);
      } catch (err) {
        if (active) setError(getChatErrorMessage(err));
      } finally {
        if (active) setIsRestoring(false);
      }
    }

    void restoreConversation();
    return () => {
      active = false;
    };
  }, [user]);

  async function handleNewChat() {
    if (!user || isLoading) return;
    setError(null);
    try {
      const conversation = await createAIConversation();
      setConversations((current) => [
        conversation,
        ...current.filter((item) => item.id !== conversation.id),
      ]);
      setActiveConversationId(conversation.id);
      setMessages([]);
      setIsHistoryOpen(false);
      localStorage.setItem(
        `${ACTIVE_CONVERSATION_STORAGE_PREFIX}.${user.id}`,
        conversation.id,
      );
    } catch (err) {
      setError(getChatErrorMessage(err));
    }
  }

  async function handleSelectConversation(conversationId: string) {
    if (!user || conversationId === activeConversationId || isLoading) {
      setIsHistoryOpen(false);
      return;
    }
    setError(null);
    setIsRestoring(true);
    try {
      const detail = await getAIConversation(conversationId);
      setActiveConversationId(detail.id);
      setMessages(detail.messages);
      setIsHistoryOpen(false);
      localStorage.setItem(
        `${ACTIVE_CONVERSATION_STORAGE_PREFIX}.${user.id}`,
        detail.id,
      );
    } catch (err) {
      setError(getChatErrorMessage(err));
    } finally {
      setIsRestoring(false);
    }
  }

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
      const result = await confirmAIAction(
        action.action_token,
        activeConversationId ?? undefined,
      );
      updateActionStatus(action.action_id, "executed");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.message },
      ]);
    } catch (err) {
      const failure = getActionErrorState(err);
      updateActionStatus(action.action_id, failure.state);
      setError(failure.message);
    }
  }

  async function handleCancel(action: AIActionConfirmation) {
    setError(null);
    updateActionStatus(action.action_id, "confirming");
    try {
      const result = await cancelAIAction(
        action.action_token,
        activeConversationId ?? undefined,
      );
      updateActionStatus(action.action_id, "canceled");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.message },
      ]);
    } catch (err) {
      const failure = getActionErrorState(err);
      updateActionStatus(action.action_id, failure.state);
      setError(failure.message);
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
    setProgressLabel(getChatProgressLabel(trimmed));
    setIsLoading(true);

    try {
      const response = await postAIChat(
        trimmed,
        activeTrack?.id,
        activeConversationId ?? undefined,
      );
      setActiveConversationId(response.conversation_id);
      if (user) {
        localStorage.setItem(
          `${ACTIVE_CONVERSATION_STORAGE_PREFIX}.${user.id}`,
          response.conversation_id,
        );
      }
      setMessages((prev) => [
        ...prev,
        {
          ...response.message,
          confirmation: response.confirmation_required ?? undefined,
          actionStatus: response.confirmation_required ? "pending" : undefined,
        },
      ]);
      const available = await listAIConversations();
      setConversations(available);
    } catch (err) {
      setError(getChatErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="ai-chat-widget">
      {isOpen && (
        <div className="ai-chat-drawer-container" role="dialog" aria-label="Khung trò chuyện Trợ lý AI Mascot">
          <header className="ai-chat-header">
            <div className="ai-chat-title">
              <div className="ai-badge-icon">
                <Sparkles size={16} />
              </div>
                <div>
                  <strong>Trợ lý AI Mascot</strong>
                  <div>
                    <small>Hỏi đáp {activeTrack?.language.name ?? "ngôn ngữ"} & hướng dẫn học tập</small>
                  </div>
                </div>
            </div>
            <div className="ai-chat-header-actions">
              <button
                className="icon-button"
                type="button"
                aria-label="Lịch sử trò chuyện"
                aria-expanded={isHistoryOpen}
                onClick={() => setIsHistoryOpen((current) => !current)}
              >
                <History size={17} />
              </button>
              <button
                className="icon-button ai-chat-close-button"
                type="button"
                aria-label="Đóng Trợ lý AI"
                onClick={() => setIsOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
          </header>

          {isHistoryOpen && (
            <div className="ai-chat-history-panel">
              <button
                type="button"
                className="ai-chat-new-button"
                onClick={() => void handleNewChat()}
              >
                <Plus size={14} /> New Chat
              </button>
              <div className="ai-chat-history-list" aria-label="Danh sách cuộc trò chuyện">
                {conversations.length === 0 ? (
                  <small>Chưa có cuộc trò chuyện.</small>
                ) : (
                  conversations.map((conversation) => (
                    <button
                      type="button"
                      key={conversation.id}
                      className={conversation.id === activeConversationId ? "active" : ""}
                      onClick={() => void handleSelectConversation(conversation.id)}
                    >
                      {conversation.title}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {error && (
            <div className="ai-chat-error-banner" role="alert">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="ai-chat-messages-list">
            {isRestoring ? (
              <div className="ai-chat-empty-state">
                <Loader2 size={24} className="spin-loader" />
                <small>Đang tải lịch sử trò chuyện…</small>
              </div>
            ) : messages.length === 0 ? (
              <div className="ai-chat-empty-state">
                <Bot size={32} />
                <p>Xin chào! Tôi là Mascot.</p>
                <small>Hãy đặt bất kỳ câu hỏi về kiến thức nào bạn thắc mắc nhé!</small>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={msg.id ?? index}
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
                        {msg.actionStatus === "pending" && (
                          <div className="ai-action-required-label">Confirmation required</div>
                        )}
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
                        {msg.actionStatus === "expired" && <div className="ai-action-card-status error">Expired</div>}
                        {msg.actionStatus === "used" && <div className="ai-action-card-status">Already used</div>}
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
                  <span>{progressLabel}</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="ai-chat-input-form" onSubmit={handleSend}>
            <input
              type="text"
              className="ai-chat-input-field"
              placeholder="Nhập câu hỏi..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading || isRestoring}
              maxLength={1000}
            />
            <button
              type="submit"
              className="ai-chat-send-button"
              disabled={!input.trim() || isLoading || isRestoring}
              aria-label="Gửi tin nhắn"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}

      <button
        className="ai-chat-trigger-button"
        type="button"
        aria-label="Mở Mascot Chatbot"
        onClick={() => setIsOpen(true)}
      >
        <Sparkles size={20} className="ai-sparkle-icon" />
        <span>Mascot AI</span>
      </button>
    </div>
  );
}
