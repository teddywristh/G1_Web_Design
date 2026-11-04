// Backend client: session cookie, CSRF header and Vietnamese error text. Keys and tokens never go to localStorage.
const API_BASE = (
  document.querySelector('meta[name="api-base"]')?.content || "http://127.0.0.1:8000"
).replace(/\/$/, "");
const API = `${API_BASE}/api/v1`;
let csrfToken = "";

class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const ERROR_TEXT = {
  unauthenticated: "Vui lòng đăng nhập.",
  ai_not_configured: "Chưa có khóa AI phù hợp. Hãy thêm khóa trong Thiết lập.",
  chatgpt_disconnected:
    "Phiên ChatGPT đã hết hạn hoặc không còn hợp lệ. Vào Thiết lập → Kết nối AI để kết nối lại.",
  ai_authentication_failed: "Nhà cung cấp AI từ chối khóa đã chọn.",
  ai_rate_limited: "Nhà cung cấp AI đang giới hạn lượt dùng. Thử lại sau.",
  ai_unavailable: "Dịch vụ AI tạm thời không phản hồi.",
  ai_incomplete: "Model chưa hoàn thành câu trả lời. Hãy thử lại hoặc chọn model khác.",
  opencode_unavailable: "OpenCode chưa được bật hoặc chưa sẵn sàng trong môi trường này.",
  oauth_exists: "Đã có phiên ChatGPT. Hãy ngắt kết nối trước khi kết nối lại.",
  invalid_model: "Chọn model cho nhà cung cấp này.",
  invalid_provider: "Kết nối đã chọn không phục vụ được model này. Hãy chọn lại model.",
  embedding_profile_mismatch:
    "Kho tài liệu dùng embedding model khác; cần lập lại chỉ mục trước khi tìm ngữ nghĩa.",
  embedding_public_input_required:
    "Model miễn phí chỉ chấp nhận nội dung không có dữ liệu cá nhân hoặc thông tin mật. Hãy xác nhận trước khi tiếp tục.",
  feature_disabled: "Tính năng này đang tắt trên máy chủ.",
  quota_exceeded: "Đã đạt giới hạn số kho riêng.",
  version_conflict: "Dữ liệu vừa thay đổi. Hãy tải lại rồi thử lại.",
  file_too_large: "PDF vượt quá giới hạn dung lượng.",
  storage_bucket_not_found:
    "Không tìm thấy bucket Firebase Storage. Kiểm tra cấu hình Storage và gói Firebase.",
  storage_permission_denied:
    "Backend không có quyền ghi Firebase Storage. Kiểm tra quyền và gói Firebase.",
  storage_unavailable:
    "Không tải được PDF lên Storage. Kiểm tra kết nối và cấu hình Firebase Storage.",
  csrf_failed: "Phiên không hợp lệ. Hãy đăng nhập lại.",
};

function setCsrf(token) {
  csrfToken = token || "";
}

async function request(method, path, { json, body, headers = {}, version, raw } = {}) {
  const timeout = path === "/ai/chatgpt/finish" ? 260000 : path === "/rag/ask" ? 120000 : 90000;
  const options = {
    method,
    credentials: "include",
    headers: { ...headers },
    signal: AbortSignal.timeout(timeout),
  };
  if (method !== "GET" && method !== "HEAD") options.headers["X-CSRF-Token"] = csrfToken;
  if (version !== undefined) options.headers["If-Match"] = `"${version}"`;
  if (json !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(json);
  }
  if (body !== undefined) options.body = body;
  let response;
  try {
    response = await fetch(API + path, options);
  } catch (error) {
    throw new ApiError(
      0,
      "network",
      error?.name === "TimeoutError"
        ? "Yêu cầu đã quá thời gian chờ. Hãy thử lại hoặc chọn model khác."
        : "Không kết nối được máy chủ hoặc gateway không phản hồi. Kiểm tra backend và tunnel.",
    );
  }
  if (!response.ok) {
    let info = {};
    try {
      info = (await response.json()).error || {};
    } catch {
      /* Response was not JSON. */
    }
    const code = info.code || "http_error";
    const gatewayError = [502, 503, 504].includes(response.status)
      ? `Máy chủ hoặc gateway tạm thời không phản hồi (HTTP ${response.status}). Hãy thử lại.`
      : "Có lỗi xảy ra.";
    throw new ApiError(response.status, code, ERROR_TEXT[code] || info.message || gatewayError);
  }
  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

const api = {
  get: (path) => request("GET", path),
  post: (path, json, options) => request("POST", path, { json, ...options }),
  put: (path, json, options) => request("PUT", path, { json, ...options }),
  patch: (path, json, options) => request("PATCH", path, { json, ...options }),
  del: (path, version) => request("DELETE", path, { version }),
  // Raw PDF body: the backend requires Content-Type application/pdf and If-Match.
  upload: (path, file, version) =>
    request("PUT", path, {
      body: file,
      headers: { "Content-Type": "application/pdf" },
      version,
    }),
  blob: async (path) => (await request("GET", path, { raw: true })).blob(),
};

export { api, setCsrf };
