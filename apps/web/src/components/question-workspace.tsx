"use client";

import { useState } from "react";
import { ArrowUp, MessageSquare, Plus, Trash2 } from "lucide-react";
import type { Conversation } from "@/lib/workspace";

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
  onQuestion: (question: string) => void;
  onRename: (title: string) => void;
  onDelete: () => void;
};

export function QuestionWorkspace({
  conversations,
  active,
  onSelect,
  onNew,
  onQuestion,
  onRename,
  onDelete,
}: Props) {
  const [question, setQuestion] = useState("");
  const hasQuestions = Boolean(active?.notes.length);

  function submit() {
    const value = question.trim();
    if (!value) return;
    onQuestion(value);
    setQuestion("");
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
                </div>
              ))}
              <div className="assistant-status">
                <MessageSquare size={18} />
                <p>Câu hỏi đã được lưu trên thiết bị. Tính năng trả lời AI chưa được kết nối.</p>
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
            maxLength={5000}
            rows={3}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <div className="composer-bottom">
            <span>Enter để lưu · Shift + Enter để xuống dòng</span>
            <button
              type="submit"
              className="send-question"
              disabled={!question.trim()}
              aria-label="Lưu câu hỏi"
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
          Bản trải nghiệm: lưu câu hỏi trên trình duyệt, chưa tạo câu trả lời AI.
        </p>
      </section>
    </div>
  );
}
