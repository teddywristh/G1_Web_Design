"use client";

import { useEffect, useRef, useState } from "react";
import { useAiSession } from "@/lib/ai-session";
import { ArrowUp, MessageSquare, Plus, Trash2 } from "lucide-react";
import type { Conversation } from "@/lib/workspace";

type Reply = {
  answer: string;
  provider?: string;
  credential_source?: string;
  citations: { document_title: string; article?: string; page_number?: number }[];
};

const suggestions = [
  "Hợp đồng lao động cần có những nội dung gì?",
  "Tôi cần chuẩn bị gì khi thành lập doanh nghiệp?",
  "Làm thế nào để kiểm tra hiệu lực của một văn bản?",
];

type Props = {
  conversations: Conversation[];
  active?: Conversation;
  onSelect: (id: string) => void;
  onNew: () => void;
  onLogin: () => void;
  onConnectAI: () => void;
  onQuestion: (question: string) => string;
  onRename: (title: string) => void;
  onDelete: () => void;
};

export function QuestionWorkspace({
  conversations,
  active,
  onSelect,
  onNew,
  onLogin,
  onConnectAI,
  onQuestion,
  onRename,
  onDelete,
}: Props) {
  const [question, setQuestion] = useState("");
  const hasQuestions = Boolean(active?.notes.length);
  const { profile, choice, request } = useAiSession();
  const [replies, setReplies] = useState<Record<string, Reply | { error: string }>>({});
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const owner = useRef(profile?.id);
  owner.current = profile?.id;
  useEffect(() => {
    setReplies({});
  }, [profile?.id]);

  async function submit() {
    const value = question.trim();
    if (value.length < 3 || inFlight.current) return;
    const index = active?.notes.length || 0;
    const conversationId = onQuestion(value);
    setQuestion("");
    if (!profile) return;
    const account = profile.id;
    const key = `${conversationId}-${index}`;
    setPending(true);
    inFlight.current = true;
    try {
      const response = await request<Reply>("/api/v1/rag/ask", {
        method: "POST",
        signal: choice.engine === "opencode" ? AbortSignal.timeout(120000) : undefined,
        body: JSON.stringify({ question: value, ...choice, model: choice.model || undefined }),
      });
      if (owner.current === account) setReplies((items) => ({ ...items, [key]: response }));
    } catch (error) {
      if (owner.current === account)
        setReplies((items) => ({
          ...items,
          [key]: { error: error instanceof Error ? error.message : "Không nhận được câu trả lời." },
        }));
    } finally {
      setPending(false);
      inFlight.current = false;
    }
  }

  return (
    <div className="question-workspace">
      <div className="question-top">
        <span>
          <MessageSquare size={18} /> Hỏi đáp pháp luật
        </span>
        <button className="secondary-button" onClick={onNew}>
          <Plus size={16} /> Cuộc trò chuyện mới
        </button>
      </div>
      {!profile && (
        <div className="ai-onboarding" aria-label="Bắt đầu sử dụng AI">
          <div>
            <strong>Kết nối AI của bạn</strong>
            <p>Đăng nhập để dùng OpenAI hoặc Claude với key cá nhân hay key chung.</p>
          </div>
          <div className="ai-actions">
            <button className="secondary-button" onClick={onConnectAI}>
              Xem kết nối AI
            </button>
            <button className="header-account-button" onClick={onLogin}>
              Đăng nhập tài khoản
            </button>
          </div>
        </div>
      )}
      {conversations.length > 0 && (
        <div className="history-picker">
          <label htmlFor="conversation-history">Lịch sử</label>
          <select
            id="conversation-history"
            value={active?.id || ""}
            onChange={(event) => {
              onSelect(event.target.value);
              setQuestion("");
            }}
          >
            <option value="" disabled>
              Chọn cuộc trò chuyện
            </option>
            {conversations.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title || "Chưa đặt tên"}
              </option>
            ))}
          </select>
          {active && (
            <button className="icon-button" aria-label="Xóa cuộc trò chuyện" onClick={onDelete}>
              <Trash2 size={17} />
            </button>
          )}
        </div>
      )}
      <section className={`question-content ${hasQuestions ? "has-questions" : ""}`}>
        {hasQuestions ? (
          <>
            <input
              className="chat-title"
              aria-label="Tên cuộc trò chuyện"
              value={active!.title}
              maxLength={100}
              onChange={(event) => onRename(event.target.value)}
            />
            <div className="question-messages" role="log" aria-label="Các câu hỏi đã lưu">
              {active!.notes.map((note, index) => (
                <div className="question-message" key={`${active!.id}-${index}`}>
                  <span>Bạn</span>
                  <p>{note}</p>
                  {(() => {
                    const reply = replies[`${active!.id}-${index}`];
                    if (!reply) return null;
                    return (
                      <div className="ai-reply">
                        <strong>
                          {"error" in reply ? "Chưa nhận được câu trả lời" : "Trả lời AI"}
                        </strong>
                        <p>{"error" in reply ? reply.error : reply.answer}</p>
                        {!("error" in reply) && (
                          <>
                            <small>
                              {reply.provider} ·{" "}
                              {reply.credential_source === "chatgpt" ? "ChatGPT cá nhân" : reply.credential_source === "personal" ? "Key cá nhân" : "Key chung"}
                            </small>
                            <ul>
                              {reply.citations.map((citation, i) => (
                                <li key={i}>
                                  {citation.document_title}
                                  {citation.article ? ` · Điều ${citation.article}` : ""}
                                  {citation.page_number ? ` · Trang ${citation.page_number}` : ""}
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                      </div>
                    );
                  })()}
                </div>
              ))}
              <div className="assistant-status">
                <MessageSquare size={18} />
                <p>
                  {pending
                    ? "AI đang xử lý câu hỏi…"
                    : profile
                      ? "Câu hỏi và câu trả lời AI chỉ có trong phiên đăng nhập này."
                      : "Câu hỏi đã lưu trên thiết bị. Đăng nhập trong Thiết lập để sử dụng AI."}
                </p>
              </div>
            </div>
          </>
        ) : (
          <div className="question-welcome">
            <span className="welcome-symbol">
              <MessageSquare size={26} />
            </span>
            <p className="welcome-kicker">LEGAL AI</p>
            <h1>Bạn muốn tìm hiểu điều gì?</h1>
            <p>Đặt câu hỏi bằng cách mô tả tình huống của bạn.</p>
          </div>
        )}
        <form
          className="question-composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <textarea
            autoFocus
            aria-label="Nhập câu hỏi pháp luật"
            placeholder="Nhập câu hỏi của bạn…"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={4000}
            rows={3}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <div className="composer-bottom">
            <span>
              {profile ? "Enter để gửi AI" : "Enter để lưu"} · Shift + Enter để xuống dòng
            </span>
            <button
              type="submit"
              className="send-question"
              disabled={question.trim().length < 3 || pending}
              aria-label={profile ? "Gửi câu hỏi tới AI" : "Lưu câu hỏi"}
            >
              <ArrowUp size={20} />
            </button>
          </div>
        </form>
        {!hasQuestions && (
          <div className="question-suggestions">
            <p>Gợi ý để bắt đầu</p>
            {suggestions.map((item) => (
              <button
                key={item}
                onClick={() => {
                  setQuestion(item);
                  document
                    .querySelector<HTMLTextAreaElement>(".question-composer textarea")
                    ?.focus();
                }}
              >
                {item}
                <Plus size={15} />
              </button>
            ))}
          </div>
        )}
        <p className="chat-disclaimer">
          {profile
            ? "AI hỗ trợ tra cứu. Hãy kiểm tra nguồn trước khi sử dụng kết quả."
            : "Đăng nhập và chọn kết nối AI trong Thiết lập để nhận câu trả lời."}
        </p>
      </section>
    </div>
  );
}
