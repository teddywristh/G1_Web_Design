# Kế hoạch tích hợp OpenCode cho Legal AI

## Mục tiêu và giới hạn

Tích hợp OpenCode như một lựa chọn engine cho tính năng hỏi đáp pháp luật. Người dùng có tài khoản dự án riêng và có thể sử dụng credential cá nhân; API key cá nhân và key chung của admin tiếp tục là lựa chọn. Mục tiêu lâu dài là mỗi người tự kết nối ChatGPT Plus, nhưng **không mặc định OpenAI đã cho phép ChatGPT plan usage trên website hosted**. Trước khi bật OAuth Plus cho website, cần OpenAI xác nhận quyền, phạm vi và contract cho ứng dụng này; gửi [interest form](https://openai.com/form/sign-in-with-chatgpt-interest/). Không dùng token của một người cho người khác hoặc tận dụng client/token của ứng dụng khác để vượt điều kiện hosted.

OpenCode hỗ trợ [ChatGPT Plus/Pro](https://opencode.ai/docs/providers/) và cung cấp [HTTP server](https://opencode.ai/docs/server/) với phiên và prompt. OpenAI có hướng dẫn Plus cho công cụ open-source/local, đồng thời yêu cầu ứng dụng remotely hosted đăng ký quan tâm: [OpenAI Docs](https://developers.openai.com/siwc/token-sharing-open-source). Việc OpenCode hỗ trợ OAuth không tự xác nhận quyền phân phối tính năng đó qua backend dùng chung. Hướng dẫn [self-hosted VM](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms) cũng không tự xác nhận mô hình SaaS nhiều người.

## Hiện trạng repo

- `POST /api/v1/rag/ask` đã xác thực tài khoản dự án, phân giải key cá nhân/key chung, tìm chunk Firestore rồi gọi OpenAI hoặc Anthropic. `answer_question` tạo trích dẫn từ chunk backend truy xuất.
- `ai_connections` lưu credential mã hóa theo owner/provider, hiện chỉ hỗ trợ API key. Chưa có cách tách account OAuth theo từng người cho OpenCode.
- Hybrid retrieval cần OpenAI embeddings; đăng nhập Plus không chứng minh có quyền embeddings. Keyword retrieval không phụ thuộc embeddings.
- Frontend Next.js đã có trang kết nối AI. Firebase Hosting hiện chưa triển khai website; FastAPI và OpenCode là tiến trình server riêng, không chạy chỉ nhờ Firebase Hosting.
- OpenCode là coding agent, có API sessions, file và shell. Không được coi server OpenCode mặc định là một dịch vụ RAG đã cách ly người dùng.

## Kiến trúc dự kiến

```text
Browser + Firebase Hosting
    -> FastAPI (auth, CSRF, phân quyền, RAG, giới hạn request)
        -> Firestore (tài khoản, kết nối, tài liệu, mapping phiên)
        -> OpenCode worker riêng tư, tách môi trường theo người dùng
            -> provider qua credential của đúng người dùng
```

FastAPI là cổng duy nhất cho trình duyệt. OpenCode không public trực tiếp; API của nó có quyền mạnh và server password dùng chung không phải cơ chế phân quyền theo người dùng. Mỗi worker cần cô lập filesystem, process, network, credential và session; chạy non-root, giới hạn CPU/RAM/thời gian, workspace tạm, không mount repo, ADC hay secrets của backend. Chỉ cho phép kết nối ra các endpoint provider cần thiết; tắt shell, sửa/đọc file tùy ý, web, MCP và plugin không cần cho hỏi đáp. Kiểm chứng giới hạn đó bằng kiểm thử thực tế; permission config trong app không thay thế cách ly OS/container.

## Giai đoạn 0 — Xác minh khả thi (chưa bật cho người dùng)

1. Chọn và pin một phiên bản OpenCode, xem giấy phép; kiểm tra HTTP contract `/session`, `/session/{id}/message`, định dạng model, xử lý lỗi và streaming cho đúng phiên bản. Không giả định docs server đời khác/v2 có cùng API.
2. Làm PoC local với API key thử nghiệm, không dùng dữ liệu thật: tạo worker và phiên, gửi câu hỏi + chunk, nhận câu trả lời; đo thời gian khởi tạo, tài nguyên, chi phí vận hành và khả năng đóng worker. Không giả định OpenCode nhanh hơn gọi model trực tiếp.
3. Kiểm tra cách OpenCode lưu/chọn credential và refresh token, ghi session/transcript; chứng minh hai người dùng có thể chạy đồng thời mà không lẫn credential hay lịch sử, kể cả sau restart và khi một phiên hết hạn. Không mặc định API credential global của OpenCode hỗ trợ multi-tenant.
4. Kiểm thử config deny tools và các lớp cách ly bằng request cố đọc file khác, chạy lệnh, truy cập metadata/credential và lấy session người khác. Nếu không chứng minh được cách ly, **dừng**, không đưa engine vào hosted.
5. Gửi interest form và nêu rõ website hosted, mỗi người tự OAuth, credential do backend lưu/xử lý. Nếu OpenAI duyệt, xác nhận thêm quyền truy cập, client và callback, phạm vi sử dụng, yêu cầu lưu/thu hồi token. Nếu không có xác nhận, Plus vẫn disabled cho hosted; API key vẫn dùng được.

Kết quả: bản ghi PoC, phiên bản đã kiểm, thông số benchmark, câu trả lời về quyền hosted và quyết định có triển khai tiếp hay không. Phần Plus cho môi trường cá nhân local có thể nghiên cứu độc lập theo đúng phạm vi OpenAI cho phép, không được mặc định áp dụng cho hosted.

## Giai đoạn 1 — Adapter OpenCode với API key

1. Giữ `rag/ask` và định dạng response tương thích; thêm `engine=direct|opencode`, mặc định `direct` để không đổi hành vi hiện hữu. Provider và credential source vẫn chọn rõ ràng; không tự đổi tài khoản thanh toán khi lỗi.
2. Định nghĩa adapter có giao diện `answer(question, chunks)`; `OpenCodeAdapter` gọi HTTP nội bộ với timeout, cancellation, giới hạn concurrent request, định dạng đáp án và mapping lỗi. Chỉ trả nội dung text đã hoàn tất; hạn chế log prompt, chunk, credential và response chứa dữ liệu riêng tư.
3. FastAPI tiếp tục truy xuất tài liệu và tạo citations như hiện tại; truyền duy nhất câu hỏi và chunk đã chọn cho worker, không cấp Firestore cho worker. Worker không tự đưa link ngoài hoặc quyết định nguồn pháp lý. Citation theo chunk chưa chứng minh mọi khẳng định thực sự có căn cứ; cần đánh giá chất lượng riêng.
4. Dùng API key cá nhân hoặc key chung đã có, nhưng chỉ khi PoC chứng minh được credential chuyển tới đúng worker theo cơ chế hỗ trợ của phiên bản OpenCode đã pin. Không gửi key cho browser hay URL; không đặt key dùng chung lên worker của người khác. Nếu không có cách quản lý credential riêng an toàn, giữ engine direct và dừng triển khai multi-tenant.
5. Mặc định `keyword` cho thử nghiệm engine mới, hoặc tiếp tục hybrid khi có OpenAI API key embeddings hợp lệ và nguồn thanh toán được chọn rõ. Không giả định OAuth Plus bao gồm embeddings.
6. Chọn phương án worker theo người dùng hoặc worker ngắn hạn theo request sau benchmark; định nghĩa vòng đời khởi tạo/dọn tài nguyên, readiness, quota, khôi phục sau restart và cleanup. Firebase Hosting phục vụ frontend; FastAPI/worker cần hạ tầng chạy container/process riêng và secret manager.

## Giai đoạn 2 — OAuth ChatGPT theo từng người, chỉ sau khi được cấp quyền hosted

1. Tạo kết nối gắn với UID tài khoản dự án; mở OAuth theo contract OpenAI cấp, với state, PKCE, nonce, callback cố định và xác thực chữ ký/issuer/audience/expiry. Không coi Google login của dự án là ChatGPT login.
2. Lưu credential theo từng user bằng secret manager hoặc mã hóa server-side; có khóa ổn định, xoay khóa, refresh đồng bộ tránh race, TTL cho giao dịch OAuth, thu hồi/ngắt kết nối và cơ chế xóa. Không đưa token lên trình duyệt, URL, localStorage, log hay analytics. Xác định rõ OpenCode có thể nhận credential theo cách được OpenAI và phiên bản OpenCode hỗ trợ hay không trước khi xây adapter.
3. Xác minh scope cho plan usage, danh sách model, endpoint và hạn mức theo contract được cấp. Nếu chỉ có quyền identity hoặc user từ chối plan usage, không hiển thị đã kết nối AI. Có trạng thái chờ duyệt, đã kết nối, hết hạn và thu hồi; không tự dùng API key chung khi Plus lỗi.
4. Tiếp tục hỗ trợ API key riêng/chung và lựa chọn nguồn rõ ràng. Chỉ admin được quản lý key chung; OAuth của user không là nguồn chung. Không cam kết gói Plus hỗ trợ mọi chức năng hoặc model đang có.

## Kiểm thử và tiêu chí hoàn thành

- Contract test với OpenCode phiên bản pin: session create/prompt/delete, timeout, cancellation, response thiếu/chưa hoàn thành, quá hạn và provider lỗi. Test hồi quy direct OpenAI/Claude API hiện tại.
- Integration: Firebase Emulator + OpenCode mock/worker cô lập; hai user song song, các tình huống cross-user, restart, logout, thu hồi và retry. Không dùng thông tin thật trong CI.
- Kiểm thử bảo mật: prompt cố gọi shell, đọc file/ADC, truy cập mạng nội bộ, lộ key/log và cross-session đều bị chặn; worker bị kill nếu hết hạn, dọn workspace và transcript theo chính sách.
- Kiểm thử UI: chọn engine/source, tình trạng kết nối, lỗi quota và disconnect; OAuth hosted không hiển thị khả dụng khi chưa được cấp quyền. Thử luồng OAuth thật chỉ với quyền OpenAI phù hợp và tài khoản thử nghiệm được cho phép.
- Benchmark và đánh giá chất lượng với cùng bộ câu hỏi/chunk: độ trễ p50/p95, lỗi, chi phí tài nguyên, kết quả và citations so với engine direct. Nếu kết quả kém hoặc chi phí vận hành không tương xứng, giữ direct.
- Triển khai sau PoC: cấu hình web/API/worker HTTPS, CORS, secrets, monitoring và rollback. Bật feature flag theo nhóm thử nghiệm trước khi mở rộng; kiểm tra Storage/Firebase Hosting và hạ tầng backend riêng.

## Kết quả PoC local — 2026-11-02

- Đã chạy OpenCode `1.17.11` trong container non-root, root filesystem read-only, capability bị bỏ, giới hạn process/memory, không mount workspace/credential Firebase và `--network none`. Kịch bản tại [scripts/opencode_poc](../scripts/opencode_poc/README.md).
- Hai container chạy đồng thời với hai API key **giả** riêng; cả hai tạo phiên, gọi provider **giả** qua `/v1/responses`, nhận text hoàn chỉnh và xóa phiên. Request tới provider giả chỉ mang key của worker tương ứng, không khai báo tool.
- Provider giả phát sinh tool call `bash` và `read` không được quảng cáo. Không tạo file hoặc làm lộ canary trong các lần thử; tuy nhiên OpenCode vẫn lặp nhiều request tới provider giả trước khi abort. Một lần chạy ghi nhận 57 request cho `bash` và 56 cho `read` trong thời gian thử; abort dừng request tiếp theo. Đây là một kiểm thử lỗi tổng hợp, không phải khẳng định về tần suất trên provider thật. Cần giới hạn số bước/lần gọi ở lớp đáng tin cậy trước khi dùng thật.
- Sau đó thử proxy giới hạn tổng hợp trong cùng container: mỗi ca chỉ chuyển tối đa 3 request tới provider giả và chặn request tiếp theo; abort dừng vòng lặp. Proxy dùng chung container này chỉ dùng để thử ý tưởng và **không phải** gateway cách ly tin cậy.
- Chưa xác minh worker chỉ được egress tới provider cho phép, chưa thử provider thật, refresh/restart credential hoặc đo tải p50/p95 và chi phí. PoC không mạng không chứng minh hệ thống hosted an toàn. Tại thời điểm kết thúc PoC, OpenCode chưa được nối vào FastAPI/UI hoặc triển khai worker hosted. Tiếp theo cần thiết kế và thử egress allowlist cùng quota/cancellation độc lập với agent; chỉ tiếp tục tích hợp sau khi các kiểm tra này đạt.
- ChatGPT OAuth hosted vẫn cần xác nhận OpenAI; chưa gửi form thay người dùng và chưa triển khai OAuth.

## Kiểm tra bổ sung — 2026-11-02

- OpenCode local đã có credential OpenAI loại OAuth. Một câu hỏi tổng hợp qua model `openai/gpt-5.6-luna` đã hoàn thành; không kiểm tra hay suy đoán gói của chủ credential. `openai/gpt-6-luna` không có trong danh sách model OpenCode hiện tại. Luna 6 kiểm thử PoC bằng provider/key giả.
- [PoC gateway tách container](../scripts/opencode_poc/README.md) tạo network Docker nội bộ riêng và gateway giả cho từng worker. Hai worker dùng đúng key giả, không truy cập được gateway của user còn lại, metadata `169.254.169.254` hay `1.1.1.1:443` trong phép thử. Với tool call giả lặp, gateway tách riêng chuyển tối đa 3 request; abort dừng phiên. Container và network tạm đã được dọn.
- Gateway vẫn chỉ trả dữ liệu giả. Chưa xác minh HTTPS tới provider thật theo allowlist, sandbox trên hạ tầng triển khai, cơ chế giữ/refresh credential sau restart, giới hạn chịu tải và cross-user session thực tế. Không coi PoC là worker production; tại thời điểm kiểm tra này OpenCode chưa nối vào FastAPI/UI.
- Người dùng xác nhận chưa được OpenAI cấp quyền ChatGPT plan usage cho website hosted. OAuth Plus trên website vẫn bị chặn theo phạm vi kế hoạch, kể cả khi đăng nhập OpenCode local đã thành công.

## Tích hợp local API key — 2026-11-02

- Đã thêm `engine=opencode` vào `POST /api/v1/rag/ask`, mặc định `direct`. UI có lựa chọn engine. OpenCode hiện chỉ nhận OpenAI API key cá nhân/key chung đã chọn; không dùng ChatGPT OAuth, không tự fallback và không hỗ trợ Anthropic qua OpenCode.
- Worker local mỗi request dùng container và mạng nội bộ riêng; gateway tách container cố định tới `api.openai.com`, kiểm tra IP công cộng/TLS, giới hạn ba request và output, không có Docker socket trong worker. Tính năng mặc định tắt, chỉ cho phép `APP_ENV=development/test` và request local; không được expose API development ra Internet hay public proxy. Xem [hướng dẫn cấu hình](ai-connections.md#engine-opencode-thử-nghiệm-local).
- Kiểm tra: controller OpenCode thật với provider giả; hai request đồng thời chạy toàn bộ adapter với fake key, nhận đúng câu trả lời tương ứng; gateway thật gửi key giả tới OpenAI và nhận lỗi xác thực; test API/guard/Firestore emulator và frontend build. Chưa thử inference bằng API key thật hoặc chứng minh phù hợp production. Plus OAuth hosted vẫn chờ OpenAI.

## Đối chiếu provider OpenCode — 2026-11-02

- OpenCode `1.17.11` cung cấp phương thức OpenAI OAuth ChatGPT Pro/Plus qua browser và headless. Máy local có credential OpenAI loại OAuth; đã thử câu hỏi tổng hợp thành công ở `openai/gpt-5.6-luna`. Tích hợp Legal AI hiện chưa hỗ trợ chuyển hoặc quản lý credential OAuth đó.
- Danh mục của OpenCode trên máy có các model miễn phí như `opencode/big-pickle`, `opencode/deepseek-v4.1-flash-free`, `opencode/glm-5.3-flash-free`. Đã thử Big Pickle và DeepSeek Flash bằng câu hỏi tổng hợp nhưng cả hai đều timeout; vì vậy chưa xác nhận inference free hoạt động trong môi trường này. Điều kiện/quota free có thể thay đổi. [Danh mục OpenCode](https://opencode.ai/v2/docs/console/models/).
- Cần phân biệt `openai/gpt-6-luna` (không có trong danh sách provider `openai` khi kiểm tra) với `opencode/gpt-6-luna` (có trong metadata catalog provider OpenCode, không phải model miễn phí; chưa xác nhận tài khoản được quyền dùng). Không khẳng định OpenCode hoàn toàn không có GPT-6 Luna.
- Adapter Legal AI hiện giới hạn `engine=opencode` với provider OpenAI API key, gateway cố định `api.openai.com/v1/responses`, và chưa hỗ trợ OpenCode free/Zen hay các provider khác qua engine. Đây là phạm vi phiên bản tích hợp, không phải giới hạn của OpenCode. Để mở rộng phải bổ sung provider/model allowlist, chính sách credential và gateway theo endpoint được cho phép; không tự chuyển sang model/key có phí. OpenCode ghi rõ free-tier chat models chỉ dùng trong OpenCode; cần xác minh khả năng cung cấp qua website hosted với OpenCode trước khi bật. [OpenCode Inference API](https://opencode.ai/v2/docs/console/api/inference/).
- OAuth ChatGPT cho ứng dụng local khác với quyền plan usage cho website remotely hosted. Người dùng xác nhận chưa được OpenAI cấp quyền hosted; chưa bật OAuth đó trên website. [OpenAI Docs](https://developers.openai.com/siwc/token-sharing-open-source).
