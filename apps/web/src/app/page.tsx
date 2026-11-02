"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BookOpen,
  Check,
  ChevronDown,
  FileText,
  FolderOpen,
  Menu,
  KeyRound,
  LogIn,
  UserRound,
  MessageSquare,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  dateLabel,
  initialDocuments,
  readLocal,
  type Conversation,
  type LegalDocument,
} from "@/lib/workspace";

import { QuestionWorkspace } from "@/components/question-workspace";
import { AiSettings } from "@/components/ai-settings";
import { AiSessionProvider, useAiSession } from "@/lib/ai-session";

type View = "library" | "saved" | "conversations" | "settings";
const categories = ["Tất cả", "Bộ luật", "Luật", "Nghị định", "Thông tư"];
const DOCUMENT_KEY = "le-luat.documents.v1";
const CONVERSATION_KEY = "le-luat.conversations.v1";

function Workspace() {
  const { profile } = useAiSession();
  const historyOwner = useRef("demo");
  const [documents, setDocuments] = useState(initialDocuments);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [view, setView] = useState<View>("conversations");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [settingsFocus, setSettingsFocus] = useState<{
    target: "account" | "ai";
    sequence: number;
  } | null>(null);
  const [category, setCategory] = useState("Tất cả");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("newest");
  const [ready, setReady] = useState(false);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selected, setSelected] = useState<LegalDocument | null>(null);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const urls = useRef<Record<string, string>>({});
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setDocuments(readLocal(DOCUMENT_KEY, initialDocuments));
    setConversations(readLocal<Conversation[]>(CONVERSATION_KEY, []));
    setReady(true);
    fetch("/api/health")
      .then((r) => r.json())
      .then((data) => setConnected(data.connected))
      .catch(() => setConnected(false));
    return () => {
      Object.values(urls.current).forEach(URL.revokeObjectURL);
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(DOCUMENT_KEY, JSON.stringify(documents));
    } catch {
      notify("Trình duyệt không thể lưu thay đổi. Hãy kiểm tra dung lượng lưu trữ.");
    }
  }, [documents, ready]);

  useEffect(() => {
    const owner = profile?.id || "demo";
    if (historyOwner.current !== owner) {
      historyOwner.current = owner;
      setConversations(owner === "demo" ? readLocal<Conversation[]>(CONVERSATION_KEY, []) : []);
      setActiveConversation(null);
      return;
    }
    if (ready && !profile) {
      try {
        localStorage.setItem(CONVERSATION_KEY, JSON.stringify(conversations));
      } catch {
        notify("Không lưu được ghi chép trên thiết bị.");
      }
    }
  }, [conversations, ready, profile]);

  function notify(message: string) {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4500);
  }

  function navigate(next: View) {
    setView(next);
    setQuery("");
    setMobileOpen(false);
  }
  function openSettings(target: "account" | "ai") {
    navigate("settings");
    setSettingsFocus((previous) => ({ target, sequence: (previous?.sequence || 0) + 1 }));
  }

  function openAccount(mode: "login" | "register" = "login") {
    setAuthMode(mode);
    openSettings("account");
  }

  useEffect(() => {
    if (view !== "settings" || !settingsFocus) return;
    const section = document.getElementById(
      settingsFocus.target === "account" ? "account-settings" : "ai-settings",
    );
    section?.scrollIntoView({ block: "start", behavior: "instant" });
    const focus =
      settingsFocus.target === "account" && !profile
        ? document.getElementById("account-email")
        : section;
    focus?.focus({ preventScroll: true });
  }, [view, settingsFocus, profile, authMode]);

  function toggleSaved(id: string) {
    setDocuments((current) =>
      current.map((doc) => (doc.id === id ? { ...doc, saved: !doc.saved } : doc)),
    );
  }
  function openDocument(doc: LegalDocument) {
    setSelected(doc);
    setPdfUrl(urls.current[doc.id] || null);
  }
  function removeDocument(id: string) {
    setDocuments((current) => current.filter((doc) => doc.id !== id));
    if (urls.current[id]) {
      URL.revokeObjectURL(urls.current[id]);
      delete urls.current[id];
    }
    setSelected(null);
    notify("Đã xóa tài liệu khỏi thư viện trải nghiệm.");
  }
  function newConversation() {
    const id = crypto.randomUUID();
    setConversations((current) => [
      { id, title: "Cuộc trò chuyện mới", date: new Date().toISOString(), notes: [] },
      ...current,
    ]);
    setActiveConversation(id);
    navigate("conversations");
  }

  const filtered = documents
    .filter(
      (doc) =>
        (view !== "saved" || doc.saved) &&
        (category === "Tất cả" || category === doc.category) &&
        `${doc.title} ${doc.number} ${doc.authority}`
          .toLocaleLowerCase("vi")
          .includes(query.toLocaleLowerCase("vi")),
    )
    .sort((a, b) =>
      sort === "name" ? a.title.localeCompare(b.title, "vi") : b.date.localeCompare(a.date),
    );
  const active = conversations.find((item) => item.id === activeConversation);
  const heading = view === "saved" ? "Tài liệu đã lưu" : "Thư viện tài liệu";

  return (
    <div className="workspace">
      {mobileOpen && (
        <button
          className="sidebar-shade"
          aria-label="Đóng điều hướng"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "is-open" : ""}`}>
        <a className="brand" href="/" aria-label="Legal AI, trang chủ">
          <span className="brand-mark">
            l<span>l</span>
          </span>
          <span>
            Legal AI<small>LEGAL ASSISTANT</small>
          </span>
        </a>
        <button className="new-research" onClick={newConversation}>
          <Plus size={18} /> Cuộc trò chuyện mới
        </button>
        <p className="nav-label">KHÔNG GIAN CỦA BẠN</p>
        <nav aria-label="Điều hướng chính">
          <button
            className={view === "library" ? "active" : ""}
            onClick={() => navigate("library")}
          >
            <BookOpen size={19} /> Thư viện tài liệu{" "}
            <span>{documents.length.toString().padStart(2, "0")}</span>
          </button>
          <button
            className={view === "conversations" ? "active" : ""}
            onClick={() => navigate("conversations")}
          >
            <MessageSquare size={19} /> Hỏi đáp{" "}
            <span>{conversations.length.toString().padStart(2, "0")}</span>
          </button>
          <button className={view === "saved" ? "active" : ""} onClick={() => navigate("saved")}>
            <Bookmark size={19} /> Đã lưu{" "}
            <span>
              {documents
                .filter((doc) => doc.saved)
                .length.toString()
                .padStart(2, "0")}
            </span>
          </button>
          <button onClick={() => openSettings("ai")}>
            <KeyRound size={19} /> Kết nối AI
          </button>
        </nav>
        <div className="sidebar-bottom">
          <button
            onClick={() => navigate("settings")}
            className={view === "settings" ? "active" : ""}
          >
            <Settings2 size={18} /> Tài khoản & thiết lập
          </button>
          <button
            className="profile account-profile"
            aria-label="Mở tài khoản dự án"
            onClick={() => openSettings("account")}
          >
            <span className="avatar">{profile?.displayName.slice(0, 1) || "M"}</span>
            <div>
              {profile?.displayName || "Không gian cá nhân"}
              <small>
                {profile
                  ? profile.role === "admin"
                    ? "Quản trị viên"
                    : "Đã đăng nhập"
                  : "Phiên trải nghiệm · Local"}
              </small>
            </div>
            <span className="profile-dot" />
          </button>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Mở menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb-context">Không gian làm việc</span>
            <span className="slash breadcrumb-context">/</span>
            <strong>
              {
                {
                  library: "Thư viện tài liệu",
                  saved: "Đã lưu",
                  conversations: "Hỏi đáp",
                  settings: "Thiết lập",
                }[view]
              }
            </strong>
          </div>
          <div className="topbar-actions">
            <div className="preview-label">
              <span /> Bản trải nghiệm
            </div>
            <button
              className="header-ai-button"
              aria-label="Kết nối AI"
              onClick={() => openSettings("ai")}
            >
              <KeyRound size={16} />
              <span className="connection-label-desktop">Kết nối AI</span>
              <span className="connection-label-mobile">AI</span>
            </button>
            {!profile && (
              <button className="header-ai-button" onClick={() => openAccount("register")}>
                Đăng ký
              </button>
            )}
            <button
              className="header-account-button"
              aria-label={profile ? "Tài khoản" : "Đăng nhập"}
              title={profile?.email || "Đăng nhập tài khoản dự án"}
              onClick={() => openAccount("login")}
            >
              {profile ? <UserRound size={16} /> : <LogIn size={16} />}
              <span>{profile ? "Tài khoản" : "Đăng nhập"}</span>
            </button>
          </div>
        </header>
        <main>
          {(view === "library" || view === "saved") && (
            <>
              <section className="page-heading">
                <div>
                  <p className="eyebrow">
                    <span /> TỦ SÁCH PHÁP LÝ CỦA BẠN
                  </p>
                  <h1>{heading}</h1>
                  <p className="subtitle">Tìm kiếm, lưu và đọc tài liệu PDF của bạn.</p>
                </div>
                <button className="primary-button" onClick={() => setUploadOpen(true)}>
                  <Plus size={18} /> Thêm tài liệu
                </button>
              </section>
              <section className="library-section">
                <div className="section-title">
                  <h2>
                    {view === "saved" ? "Bộ sưu tập đã lưu" : "Tất cả tài liệu"}{" "}
                    <span>{filtered.length}</span>
                  </h2>
                  <span className="section-caption">NGĂN NẮP HƠN. DỄ TÌM HƠN.</span>
                </div>
                <div className="filterbar">
                  <div className="tabs" aria-label="Lọc loại tài liệu">
                    {categories.map((item) => (
                      <button
                        key={item}
                        aria-pressed={category === item}
                        className={category === item ? "selected" : ""}
                        onClick={() => setCategory(item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <div className="search-sort">
                    <label className="search-box">
                      <Search size={17} />
                      <input
                        id="document-search"
                        placeholder="Tìm tên, số hiệu văn bản…"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        aria-label="Tìm tài liệu"
                      />
                      {query && (
                        <button onClick={() => setQuery("")} aria-label="Xóa tìm kiếm">
                          <X size={14} />
                        </button>
                      )}
                    </label>
                    <label className="sort-box">
                      <select
                        aria-label="Sắp xếp tài liệu"
                        value={sort}
                        onChange={(event) => setSort(event.target.value)}
                      >
                        <option value="newest">Mới nhất</option>
                        <option value="name">Tên A → Z</option>
                      </select>
                      <ChevronDown size={14} />
                    </label>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>TÊN TÀI LIỆU</th>
                        <th>LOẠI VĂN BẢN</th>
                        <th>NGÀY THÊM</th>
                        <th>TRẠNG THÁI DỮ LIỆU</th>
                        <th>
                          <span className="sr-only">Thao tác</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((doc, index) => (
                        <tr key={doc.id}>
                          <td>
                            <button className="document-title" onClick={() => openDocument(doc)}>
                              <span className={`file-icon file-color-${index % 3}`}>
                                <FileText size={22} />
                                <small>PDF</small>
                              </span>
                              <span>
                                <strong>{doc.title}</strong>
                                <small>
                                  {doc.number}
                                  <span>·</span>
                                  {doc.authority}
                                </small>
                              </span>
                            </button>
                          </td>
                          <td>
                            <span className="type-badge">{doc.category}</span>
                          </td>
                          <td className="date-cell">{dateLabel(doc.date)}</td>
                          <td>
                            <span className={`status-badge ${doc.status}`}>
                              <span />
                              {doc.status === "ready" ? "Sẵn sàng xem" : "Đã thêm"}
                            </span>
                          </td>
                          <td>
                            <div className="row-actions">
                              <button
                                className={`icon-button ${doc.saved ? "is-saved" : ""}`}
                                aria-label={doc.saved ? `Bỏ lưu ${doc.title}` : `Lưu ${doc.title}`}
                                onClick={() => toggleSaved(doc.id)}
                              >
                                <Bookmark size={18} fill={doc.saved ? "currentColor" : "none"} />
                              </button>
                              <button
                                className="icon-button"
                                aria-label={`Xem ${doc.title}`}
                                onClick={() => openDocument(doc)}
                              >
                                <ArrowUpRight size={19} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filtered.length === 0 && (
                    <div className="empty-state">
                      <Search size={30} />
                      <h3>Chưa tìm thấy tài liệu</h3>
                      <p>Thử từ khóa khác hoặc thêm tài liệu đầu tiên của bạn.</p>
                      <button
                        className="secondary-button"
                        onClick={() => {
                          setQuery("");
                          setCategory("Tất cả");
                        }}
                      >
                        Xóa bộ lọc
                      </button>
                    </div>
                  )}
                </div>
                <div className="table-footer">
                  <span>
                    Hiển thị {filtered.length} /{" "}
                    {view === "saved"
                      ? documents.filter((doc) => doc.saved).length
                      : documents.length}{" "}
                    tài liệu
                  </span>
                  <span>
                    <ShieldCheck size={14} /> Metadata mẫu · Không xác nhận hiệu lực pháp lý
                  </span>
                </div>
              </section>
            </>
          )}

          {view === "conversations" && (
            <QuestionWorkspace
              conversations={conversations}
              active={active}
              onSelect={setActiveConversation}
              onNew={newConversation}
              onLogin={() => openAccount("login")}
              onConnectAI={() => openSettings("ai")}
              onQuestion={(question) => {
                if (active) {
                  setConversations((items) =>
                    items.map((item) =>
                      item.id === active.id ? { ...item, notes: [...item.notes, question] } : item,
                    ),
                  );
                  return active.id;
                } else {
                  const id = crypto.randomUUID();
                  setConversations((items) => [
                    {
                      id,
                      title: question.slice(0, 70),
                      date: new Date().toISOString(),
                      notes: [question],
                    },
                    ...items,
                  ]);
                  setActiveConversation(id);
                  return id;
                }
              }}
              onRename={(title) =>
                setConversations((items) =>
                  items.map((item) => (item.id === active?.id ? { ...item, title } : item)),
                )
              }
              onDelete={() => {
                setConversations((items) => items.filter((item) => item.id !== active?.id));
                setActiveConversation(null);
              }}
            />
          )}

          {view === "settings" && (
            <>
              <section className="page-heading">
                <div>
                  <p className="eyebrow">
                    <span /> KHÔNG GIAN RIÊNG CỦA BẠN
                  </p>
                  <h1>Tài khoản & kết nối AI</h1>
                  <p className="subtitle">Thông tin kết nối và cách dữ liệu được lưu trữ.</p>
                </div>
              </section>
              <div className="settings-grid">
                <AiSettings
                  connected={connected}
                  onLogin={() => openAccount("login")}
                  onConnect={() => openSettings("ai")}
                  authMode={authMode}
                  setAuthMode={setAuthMode}
                />
                <section className="settings-card">
                  <FolderOpen size={28} />
                  <h2>Dữ liệu trên thiết bị</h2>
                  <p>
                    Tài liệu mẫu và ghi chép khi chưa đăng nhập được lưu trên thiết bị. Khi đăng
                    nhập, câu hỏi và câu trả lời AI chỉ có trong phiên hiện tại. PDF cần chọn lại
                    khi mở trang.
                  </p>
                  <button
                    className="secondary-button"
                    onClick={() => {
                      setDocuments(initialDocuments.map((doc) => ({ ...doc })));
                      setConversations([]);
                      Object.values(urls.current).forEach(URL.revokeObjectURL);
                      urls.current = {};
                      notify("Đã khôi phục dữ liệu trải nghiệm ban đầu.");
                    }}
                  >
                    Khôi phục dữ liệu mẫu
                  </button>
                </section>
              </div>
            </>
          )}
          <footer className="page-footer">
            <span className="footer-wordmark">Legal AI</span>
            <span>Đọc kỹ hơn. Hiểu sâu hơn.</span>
            <span>Được tạo cho những góc nhìn độc lập.</span>
          </footer>
        </main>
      </div>

      {uploadOpen && (
        <UploadDialog
          onClose={() => setUploadOpen(false)}
          onSave={(doc, file) => {
            urls.current[doc.id] = URL.createObjectURL(file);
            setDocuments((items) => [doc, ...items]);
            setUploadOpen(false);
            notify("Đã thêm PDF vào phiên trải nghiệm. File chưa được gửi lên Firebase.");
          }}
        />
      )}
      {selected && (
        <Dialog label="Chi tiết tài liệu" onClose={() => setSelected(null)} wide>
          <div className="detail-top">
            <span className="eyebrow">HỒ SƠ TÀI LIỆU</span>
            <h2>{selected.title}</h2>
            <p>
              {selected.number} · {selected.authority}
            </p>
          </div>
          <div className="detail-toolbar">
            <button className="secondary-button" onClick={() => toggleSaved(selected.id)}>
              <Bookmark size={16} />
              {documents.find((doc) => doc.id === selected.id)?.saved ? "Bỏ đánh dấu" : "Đánh dấu"}
            </button>
            {pdfUrl && (
              <a className="secondary-button" href={pdfUrl} download={`${selected.title}.pdf`}>
                <ArrowDownToLine size={16} /> Tải PDF
              </a>
            )}
            <button
              className="icon-button danger"
              aria-label="Xóa tài liệu"
              onClick={() => removeDocument(selected.id)}
            >
              <Trash2 size={18} />
            </button>
          </div>
          {pdfUrl ? (
            <iframe className="pdf-viewer" title={`PDF ${selected.title}`} src={pdfUrl} />
          ) : (
            <div className="pdf-empty">
              <FileText size={44} />
              <h3>{selected.sample ? "Bản ghi minh họa thư viện" : "Chọn lại PDF để đọc"}</h3>
              <p>
                {selected.sample
                  ? "Tài liệu mẫu chỉ có metadata, không đính kèm văn bản pháp luật. Thêm PDF của bạn để trải nghiệm trình đọc."
                  : "Để bảo vệ dung lượng trình duyệt, file PDF không được lưu sau khi tải lại trang."}
              </p>
              <label className="primary-button">
                {" "}
                <Upload size={17} /> Chọn PDF để xem
                <input
                  className="sr-only"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    const error = await validatePdf(file);
                    if (error) {
                      notify(error);
                      return;
                    }
                    if (urls.current[selected.id]) URL.revokeObjectURL(urls.current[selected.id]);
                    const url = URL.createObjectURL(file);
                    urls.current[selected.id] = url;
                    setPdfUrl(url);
                  }}
                />
              </label>
            </div>
          )}
          <p className="small-print">
            Thông tin trải nghiệm không thay thế nguồn văn bản chính thức hoặc tư vấn pháp lý.
          </p>
        </Dialog>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          {toast}
          <button aria-label="Đóng thông báo" onClick={() => setToast("")}>
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

function Dialog({
  children,
  label,
  onClose,
  wide = false,
}: {
  children: React.ReactNode;
  label: string;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "dialog-wide" : ""}`}
      aria-label={label}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
    >
      <button className="icon-button dialog-close" aria-label="Đóng cửa sổ" onClick={onClose}>
        <X size={21} />
      </button>
      {children}
    </dialog>
  );
}

async function validatePdf(file: File) {
  if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf"))
    return "Vui lòng chọn một file PDF.";
  if (file.size > 20 * 1024 * 1024) return "PDF vượt quá giới hạn 20 MB.";
  if ((await file.slice(0, 5).text()) !== "%PDF-") return "File không có định dạng PDF hợp lệ.";
  return null;
}

function UploadDialog({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (doc: LegalDocument, file: File) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Hãy chọn file PDF trước khi thêm tài liệu.");
      return;
    }
    const data = new FormData(event.currentTarget);
    const title = String(data.get("title") || "").trim();
    if (!title) {
      setError("Vui lòng nhập tên tài liệu.");
      return;
    }
    setBusy(true);
    try {
      const validation = await validatePdf(file);
      if (validation) {
        setError(validation);
        return;
      }
      onSave(
        {
          id: crypto.randomUUID(),
          title,
          number: String(data.get("number") || "").trim() || "Chưa có số hiệu",
          category: String(data.get("category")),
          authority: String(data.get("authority") || "").trim() || "Tài liệu cá nhân",
          date: new Date().toISOString(),
          status: "uploaded",
          saved: false,
        },
        file,
      );
    } catch {
      setError("Không đọc được file. Vui lòng chọn lại PDF.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog label="Thêm tài liệu PDF" onClose={onClose}>
      <p className="eyebrow">THÊM MỘT NGUỒN TRI THỨC</p>
      <h2>Thêm tài liệu PDF</h2>
      <p className="subtitle">Chọn file và nhập thông tin tài liệu.</p>
      <form onSubmit={submit}>
        <label
          className="upload-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setFile(event.dataTransfer.files[0] || null);
            setError("");
          }}
        >
          <span className="upload-icon">
            <Upload size={24} />
          </span>
          <strong>{file ? file.name : "Kéo thả PDF vào đây"}</strong>
          <span>
            {file
              ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Nhấn để chọn lại`
              : "hoặc nhấn để chọn từ thiết bị"}
          </span>
          <small>PDF · Tối đa 20 MB</small>
          <input
            type="file"
            accept="application/pdf,.pdf"
            className="sr-only"
            aria-label="Chọn file PDF"
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              setError("");
            }}
          />
        </label>
        <label className="form-field">
          Tên tài liệu{" "}
          <input
            name="title"
            placeholder="Ví dụ: Tài liệu nghiên cứu lao động"
            maxLength={180}
            required
          />
        </label>
        <div className="form-grid">
          <label className="form-field">
            Loại văn bản
            <select name="category">
              {categories.slice(1).map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Số hiệu
            <input name="number" placeholder="Số / năm / cơ quan" maxLength={80} />
          </label>
        </div>
        <label className="form-field">
          Cơ quan ban hành
          <input name="authority" placeholder="Nhập cơ quan hoặc nguồn tài liệu" maxLength={120} />
        </label>
        <p className="form-notice">
          <ShieldCheck size={16} /> Chế độ trải nghiệm: metadata lưu trên trình duyệt, PDF chỉ giữ
          trong phiên này. Chưa upload lên Firebase.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose}>
            Để sau
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "Đang kiểm tra…" : "Thêm tài liệu"}
            <ArrowRight size={17} />
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export default function WorkspacePage() {
  return (
    <AiSessionProvider>
      <Workspace />
    </AiSessionProvider>
  );
}
