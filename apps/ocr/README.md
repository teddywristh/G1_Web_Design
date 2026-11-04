# Dịch vụ PaddleOCR cục bộ

Dịch vụ chỉ nghe trên `127.0.0.1:8011`, xử lý một trang tại một thời điểm. API nội bộ `POST /v1/ocr` nhận PNG dưới dạng body và trả văn bản theo dòng cùng tọa độ. `GET /ready` chỉ thành công khi mô hình tiếng Việt đã nạp trên GPU. Không đưa dịch vụ này ra Internet.

Cần Python 3.12, NVIDIA CUDA tương thích, `poppler-utils`, và VRAM trống để chạy cùng embedding. Cài Paddle GPU theo CUDA từ hướng dẫn chính thức, sau đó:

```bash
python3.12 -m venv .data/paddle-ocr-venv
.data/paddle-ocr-venv/bin/pip install paddlepaddle-gpu==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
.data/paddle-ocr-venv/bin/pip install -r apps/ocr/requirements.txt
bash scripts/paddle-ocr-host.sh
```

Mô hình sẽ được tải về lần đầu vào `.data/paddle-models`. Worker dùng `OCR_SERVICE_URL=http://127.0.0.1:8011`, OCR trang có ảnh mà lớp chữ rỗng hoặc giống watermark; trang chữ bình thường vẫn được đọc trực tiếp. Khi OCR chưa sẵn sàng, job sẽ chờ/thử lại, không công bố văn bản thiếu. `FLAGS_allocator_strategy=auto_growth`, batch 1, một yêu cầu một lần và kích thước ảnh nhận diện giới hạn giúp giảm áp lực VRAM, nhưng không phải giới hạn cứng; kiểm tra VRAM thực tế khi chạy đồng thời embedding. OCR có thể sai dấu hoặc số điều, cần đối chiếu bản gốc.

Nếu văn bản Paddle có tỷ lệ dấu tiếng Việt thấp, worker so sánh với Tesseract `vie+eng` cục bộ và chọn bản có dấu rõ ràng hơn; cài Tesseract và dữ liệu ngôn ngữ để kích hoạt lớp dự phòng này. Cấu hình `OCR_FALLBACK_BINARY` nếu Tesseract không nằm trong PATH. Đây là kiểm tra kinh nghiệm, không bảo đảm tính chính xác pháp lý.
