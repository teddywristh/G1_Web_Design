# Thiết kế hỏi đáp khi tài liệu đang xử lý

## Mục tiêu

Người dùng có thể đặt câu hỏi ngay khi chưa có kho hoặc PDF còn đang parse, tạo embedding, chờ hạn mức hay lỗi. Worker tiếp tục xử lý nền độc lập. Hỏi đáp dùng nguồn khả dụng và công cụ tìm nguồn web; khi tài liệu được xuất bản, những câu hỏi sau tự dùng thêm chỉ mục mới. Không hứa trả lời theo nội dung PDF nếu chưa có nguồn tài liệu phù hợp.

## Hiện trạng trong workspace

- `workers/ingestion.py` đã xử lý job nền, có retry và lưu embedding theo lô. Giới hạn 200 chunk giữa tài liệu chỉ được bật trong script emulator local và phải được thông báo.
- `apps/web/script.js` không cho gửi câu hỏi nếu không chọn kho sẵn sàng. `qa.resolve_scope` ở backend có thể nhận danh sách kho rỗng, nhưng nếu không tìm thấy bằng chứng thì trả `insufficient_evidence`.
- `qa.gather` tra theo số hiệu/điều và vector trên các generation đã xuất bản. `structured.search` hiện không phải tìm kiếm toàn văn; không được gọi nó là tìm kiếm keyword tổng quát.
- `web_sources.py` có một luồng tìm web qua OpenAI Responses, bị tắt mặc định; không dùng chung được ngay với OpenCode, Anthropic hoặc OAuth ChatGPT. Code hiện tại chạy workflow cố định, không có vòng tool calling độc lập cho tất cả provider.
- Adapter OpenCode hiện chỉ cung cấp `answer(question, chunks)`, chạy trong môi trường local cô lập. Chưa có hợp đồng function calling của ứng dụng qua adapter này và không được giả định mọi model/provider đều hỗ trợ tools.

## Trải nghiệm

1. Bỏ điều kiện bắt buộc chọn kho trước khi gửi. Cho phép chọn kho đang xử lý, hiển thị trạng thái tương ứng; không mặc định báo kho đó đã được dùng.
2. Trong phần tùy chọn nguồn có **Tìm nguồn pháp luật trên web**. Khi bật, giải thích câu hỏi sẽ được gửi tới dịch vụ tìm kiếm; không gửi nguyên PDF hoặc token tới dịch vụ tìm kiếm. Người dùng có thể tắt. Ưu tiên nguồn chính thức.
3. Mỗi câu trả lời hiển thị nguồn thực tế đã dùng: tài liệu cá nhân, kho đã xuất bản hoặc web; kèm URL/trích dẫn và cảnh báo khi tài liệu còn xử lý, bị lỗi hoặc chỉ lập chỉ mục một phần. Câu trả lời trước đó không tự thay đổi khi job hoàn tất; người dùng có thể hỏi lại.
4. Nếu người dùng hỏi đích danh về PDF nhưng PDF chưa có bằng chứng truy xuất được, nói rõ chưa kiểm tra được nội dung PDF; có thể cung cấp thông tin từ web nếu đã bật và nêu rõ nguồn. Không nói đã đọc tài liệu dựa trên kết quả web.
5. Nếu web bị tắt, không có nguồn phù hợp, model không hỗ trợ công cụ hoặc dịch vụ tìm kiếm lỗi: phản hồi nêu giới hạn cụ thể, không dựng dẫn chứng. Cho phép hỏi thông tin chung khi có bằng chứng phù hợp; quy định pháp luật và kết luận áp dụng vẫn cần nguồn có thể kiểm chứng.

## Luồng backend đề xuất

`POST /api/v1/rag/ask` tiếp tục dùng schema hiện tại. `knowledge_base_ids: []` nghĩa là không chọn kho; `null` giữ ý nghĩa cũ chọn kho chung. `web_mode` giữ `off | official | examples`; giao diện gửi rõ giá trị. Không đổi ý nghĩa `hybrid`/`keyword` hoặc âm thầm thay đổi quyền truy cập.

1. Xác thực, kiểm tra quyền từng kho kể cả kho chưa sẵn sàng; từ chối kho không thuộc người dùng. Chụp generation đã xuất bản tại đầu request. Với kho chưa sẵn sàng, ghi chú `knowledge_base_not_ready`; nếu đã có generation cũ, vẫn dùng snapshot đó và ghi chú tài liệu mới đang xử lý.
2. Chỉ tạo query embedding khi thực sự có generation phù hợp và cần vector; kiểm tra consent NVIDIA nếu có gửi câu hỏi. Nếu embedding lỗi 429/503, giữ khả năng tra cứu có cấu trúc và web thay vì làm hỏng toàn bộ câu hỏi; trả `embedding_unavailable` trong limitations. Không tự thay model hay key.
3. Cung cấp công cụ backend có schema rõ ràng: `search_knowledge` tìm trong generation đã được cấp quyền; `search_official_web` tìm URL theo câu hỏi và danh sách domain; `fetch_official_source` đọc URL được kiểm tra. Backend tự ràng buộc số lần, timeout và phạm vi nguồn. Truyền query tối thiểu cần thiết, không đính kèm tài liệu riêng. Không cho model cung cấp ID người dùng, đường dẫn storage, credential hoặc URL tùy ý vào công cụ đặc quyền.
4. Agent chọn công cụ theo nhu cầu trong giới hạn tổng, nhận kết quả là dữ liệu không đáng tin và tổng hợp bằng chứng. Tra cứu web theo opt-in; nếu công cụ không sẵn sàng, báo giới hạn. Giữ bước kiểm tra `parse_output` và kiểm tra trích dẫn trước khi trả lời. Web phải có URL thật và đoạn nguồn đã fetch, không chỉ là URL model tự sinh; phân loại loại nguồn và tình trạng hiệu lực là chưa xác minh nếu chưa có dữ liệu.
5. Tạo response từ các nguồn thực tế; thêm `sources_used`, `knowledge_status` và `source_limitations` theo kiểu tùy chọn để giữ tương thích. `knowledge_status` liệt kê kho đã chọn, generation đã dùng và trạng thái `ready | processing | unavailable`; không để lộ thông tin kho chưa được phép. `sources_used` phân biệt `document | official_web | commentary`; không gắn nhãn `document` cho web. Có thể giữ cấu trúc citation hiện tại và bổ sung trường tùy chọn.

### Tool calling và provider

Định nghĩa một `ToolCallingAdapter` cho model có `plan/continue` với tool schema, kết quả và tool-call ID; backend là bên thực thi tool, quyết định timeout và quyền. Giới hạn ví dụ tối đa 3 vòng model, 2 lần search, 4 lần fetch, tổng deadline 40 giây; không chạy song song vô hạn. Kiểm tra capability thực tế trước khi chọn adapter.

- Với OpenAI trực tiếp: tích hợp function calling qua SDK hiện có và kiểm thử contract; dịch vụ search phải có credential/cấu hình riêng hoặc adapter web đã có nếu phù hợp, không giả định API key người dùng luôn cho phép web search.
- Với OpenCode: khảo sát và kiểm thử cơ chế nhận tool call từ SDK/server đang đóng gói, kể cả phiên OAuth. Hiện chưa thể cam kết cơ chế đó hoạt động với mọi provider. Không mở rộng network hay host filesystem của container để model tự chạy shell/browser tùy ý; nếu không triển khai được contract, dùng **workflow backend có điều kiện**: backend chủ động search rồi gửi evidence vào `answer`. Đây là fallback có hành vi tương tự nhưng không được gọi là model function calling.
- Model/provider không hỗ trợ function calling vẫn có thể dùng workflow backend có điều kiện nếu nguồn tìm kiếm đã cấu hình. Không thay engine hay tài khoản mà người dùng chọn.

Search provider cần chọn và cấu hình riêng khi triển khai: chi phí, quota, tiếng Việt, quyền sử dụng và tính sẵn sàng cần được xác minh; không mặc định một API miễn phí hoặc yêu cầu người dùng mua dịch vụ. Tách interface `SearchProvider.search(query, allowed_domains)` khỏi fetch và model. `web_sources.fetch` hiện có kiểm tra HTTPS, domain, DNS và redirect; khi triển khai cần xử lý rủi ro DNS rebinding bằng cách gắn địa chỉ IP đã xác minh với kết nối thực tế và kiểm tra mỗi redirect, giới hạn dung lượng, content type và thời gian. Nội dung trang là dữ liệu, không phải chỉ dẫn.

## Dùng PDF trước khi embedding xong

Giai đoạn đầu không xuất bản chunk đang tạo embedding: chỉ mục trung gian có thể thiếu, job có thể retry/hủy, và generation hiện tại được công bố theo giao dịch. Sau parse, có thể bổ sung **bước riêng** tìm theo số điều/số hiệu từ `provision_versions` của đúng tài liệu và chủ sở hữu, kể cả chưa có vector. Chỉ cho phép khi `fileState=available`, nguồn chưa bị xóa, parse hoàn tất và version/hash khớp job; trích dẫn tới version đó và ghi `document_processing`. Không quét toàn bộ nội dung Firestore theo substring, không dùng artifact chưa kiểm chứng hay index tạm của tài liệu người khác.

Nếu cần hỏi tự do trên văn bản vừa parse, thiết kế lexical index có giới hạn và kiểm soát truy cập riêng; chưa coi tra số điều hiện tại là thay thế tìm kiếm toàn văn. Với PDF scan chưa OCR hoặc parse thất bại, không hứa tra được nội dung.

## Các bước triển khai và kiểm thử

1. **Nguồn và giao diện:** cho phép gửi khi không chọn kho; thêm nút bật web và hiển thị trạng thái/nguồn. Kiểm thử request cũ, `[]`/`null`, kho đang xử lý, quyền truy cập và không rò dữ liệu.
2. **Workflow web có điều kiện:** tách search provider và fetch, bật qua cấu hình, giữ kiểm chứng và trích dẫn. Test giả lập search/fetch: có nguồn chính thức, web lỗi, domain sai, redirect nội bộ, output bịa nguồn và web tắt. Không gọi web thật trong unit test.
3. **Tài liệu parse xong:** thêm công cụ tra số điều trên version được cấp quyền; kiểm thử hủy, thay thế file, xóa, scan/OCR và hai người dùng. Chưa công bố vector chưa hoàn tất.
4. **Tool calling:** thêm adapter cho từng engine có thể chứng minh hỗ trợ, test chuỗi tool-call/result, quota, deadline, không hỗ trợ và fallback. Không chặn các bước 1–3 vì OpenCode chưa có tool contract.
5. **End-to-end:** thử upload PDF công khai, cố ý khiến embedding chờ 429, hỏi khi chờ với web bật/tắt, kiểm tra nguồn và cảnh báo; sau đó hoàn thành ingestion, hỏi lại và xác minh generation mới. Firebase Emulator không xác nhận được tìm kiếm vector thật; cần kiểm thử vector riêng trên môi trường hỗ trợ.

## Tiêu chí hoàn thành

- Không cần kho sẵn sàng để gửi câu hỏi; worker tiếp tục độc lập.
- Chưa có tài liệu hoặc embedding bị lỗi không ngăn nguồn web được phép, và 429 embedding không làm sập luồng hỏi đáp.
- Luôn thể hiện nguồn và tình trạng tài liệu; không bịa trích dẫn, không khẳng định đã đọc PDF chưa truy xuất được.
- Không lộ tài liệu riêng, API key hay nội dung PDF tới search provider; mỗi công cụ tuân thủ quyền, budget và thời gian.
- API và UI cũ tiếp tục hoạt động; provider thiếu tool calling có fallback đã mô tả, không hứa tính năng không được hỗ trợ.
