# Implementation Plan — Self-host NVIDIA Nemotron 3.5 Embed 1B

Model weights available

RTX 3050 6 GB — cần benchmark

Không cần Cloud Run

Mình đề xuất triển khai Nemotron 3.5 Embed 1B BF16 thành một embedding microservice riêng, sau đó tích hợp vào hệ thống Legal AI Assistant tại [G1_Web_Design](https://github.com/teddywristh/G1_Web_Design?utm_source=chatgpt.com).

Mục tiêu cuối cùng:

- Bỏ giới hạn request của OpenRouter đối với embedding.
- Sử dụng RTX 3050 6 GB để xử lý embedding local.
- Giữ nguyên phần lớn kiến trúc RAG, Firestore và frontend hiện tại.
- Hỗ trợ PDF tối đa 300 trang thông qua pipeline ingestion.
- Cho thầy truy cập Firebase Web App để test, trong khi toàn bộ engine chạy trên máy bạn.

## 1. Quyết định kỹ thuật

| Thành phần           | Lựa chọn                                           |
| -------------------- | -------------------------------------------------- |
| Model                | `nvidia/Nemotron-3.5-Embed-1B-BF16`                |
| Model source         | Hugging Face NVIDIA                                |
| Inference            | PyTorch + Sentence Transformers                    |
| Precision            | BF16 trước, thử FP16 nếu cần                       |
| Attention            | SDPA trước; FlashAttention 2 nếu môi trường hỗ trợ |
| GPU                  | RTX 3050 6 GB                                      |
| Initial batch size   | 1                                                  |
| Initial max sequence | 512 tokens                                         |
| Embedding dimensions | 1536 để tương thích Firestore hiện tại             |
| Local inference API  | FastAPI, port 8010                                 |
| Backend API          | FastAPI hiện tại, port 8000                        |
| Vector DB            | Firestore                                          |
| Public access        | Firebase Hosting + HTTPS Tunnel                    |

NVIDIA phát hành checkpoint BF16 với khoảng 1,55 tỷ tham số, weights khoảng 3,13 GB trên Hugging Face và embedding gốc 2048 chiều. Model hỗ trợ tiếng Việt và tối đa 32.768 tokens về mặt kiến trúc, nhưng 32.768 tokens không phải cấu hình thực tế phù hợp với GPU 6 GB.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



Mình không chọn NVIDIA NIM hoặc vLLM làm runtime đầu tiên vì RTX 3050 chưa nằm trong danh sách cấu hình Nemotron 3.5 mà NVIDIA đã kiểm chứng. PyTorch cho phép kiểm soát memory, batch size và CPU offloading dễ hơn trong giai đoạn thử nghiệm.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.nvidia.com\&sz=32)

NeMo Retriever Embedding NIM



## 2. Kiến trúc sau khi triển khai

\#chatgpt-mermaid-\_r_2pn\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;fill:rgb(13, 13, 13);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_2pn\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_2pn\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_2pn\_ .error-icon{fill:rgb(243, 243, 243);}#chatgpt-mermaid-\_r_2pn\_ .error-text{fill:rgb(13, 13, 13);stroke:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_2pn\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_2pn\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_2pn\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_2pn\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_2pn\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_2pn\_ .marker.cross{stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_2pn\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:16px;}#chatgpt-mermaid-\_r_2pn\_ p{margin:0;}#chatgpt-mermaid-\_r_2pn\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .cluster-label text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .cluster-label span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_2pn\_ .label text,#chatgpt-mermaid-\_r_2pn\_ span{fill:rgb(13, 13, 13);color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .node rect,#chatgpt-mermaid-\_r_2pn\_ .node circle,#chatgpt-mermaid-\_r_2pn\_ .node ellipse,#chatgpt-mermaid-\_r_2pn\_ .node polygon,#chatgpt-mermaid-\_r_2pn\_ .node path{fill:rgb(222, 234, 251);stroke:rgb(83, 154, 248);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .rough-node .label text,#chatgpt-mermaid-\_r_2pn\_ .node .label text,#chatgpt-mermaid-\_r_2pn\_ .image-shape .label,#chatgpt-mermaid-\_r_2pn\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_2pn\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .rough-node .label,#chatgpt-mermaid-\_r_2pn\_ .node .label,#chatgpt-mermaid-\_r_2pn\_ .image-shape .label,#chatgpt-mermaid-\_r_2pn\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_2pn\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_2pn\_ .root .anchor path{fill:rgb(143, 143, 143)!important;stroke-width:0;stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_2pn\_ .arrowheadPath{fill:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_2pn\_ .edgePath .path{stroke:rgb(143, 143, 143);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .flowchart-link{stroke:rgb(143, 143, 143);fill:none;}#chatgpt-mermaid-\_r_2pn\_ .edgeLabel{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_2pn\_ .edgeLabel p{background-color:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_2pn\_ .edgeLabel rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_2pn\_ .labelBkg{background-color:rgba(252, 252, 252, 0.5);}#chatgpt-mermaid-\_r_2pn\_ .cluster rect{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .cluster text{fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ .cluster span{color:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";font-size:12px;background:rgb(243, 243, 243);border:1px solid rgba(0, 0, 0, 0.1);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_2pn\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(13, 13, 13);}#chatgpt-mermaid-\_r_2pn\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_2pn\_ .icon-shape,#chatgpt-mermaid-\_r_2pn\_ .image-shape{background-color:rgb(252, 252, 252);text-align:center;}#chatgpt-mermaid-\_r_2pn\_ .icon-shape p,#chatgpt-mermaid-\_r_2pn\_ .image-shape p{background-color:rgb(252, 252, 252);padding:2px;}#chatgpt-mermaid-\_r_2pn\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_2pn\_ .image-shape .label rect{opacity:0.5;background-color:rgb(252, 252, 252);fill:rgb(252, 252, 252);}#chatgpt-mermaid-\_r_2pn\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_2pn\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_2pn\_ .node .neo-node{stroke:rgb(83, 154, 248);}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_2pn\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_2pn\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node .neo-line path{stroke:rgb(83, 154, 248);filter:none;}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_2pn\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_2pn\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_2pn\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_2pn\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_2pn\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_2pn\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(65, 65, 65);}#chatgpt-mermaid-\_r_2pn\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_2pn\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_2pn\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(252, 252, 252);stroke:rgb(219, 219, 219);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .node rect,#chatgpt-mermaid-\_r_2pn\_ .node circle,#chatgpt-mermaid-\_r_2pn\_ .node ellipse,#chatgpt-mermaid-\_r_2pn\_ .node polygon,#chatgpt-mermaid-\_r_2pn\_ .node path{fill:rgb(243, 243, 243);stroke:rgba(0, 0, 0, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_2pn\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_2pn\_ .mermaid-decision .label-container{fill:rgb(249, 249, 249);stroke:rgb(219, 219, 219);stroke-dasharray:2,2;}#chatgpt-mermaid-\_r_2pn\_ .edgePaths .flowchart-link{stroke:rgb(143, 143, 143);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_2pn\_ .marker{fill:rgb(143, 143, 143);stroke:rgb(143, 143, 143);}#chatgpt-mermaid-\_r_2pn\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,"Segoe UI",Helvetica,"Apple Color Emoji",Arial,sans-serif,"Segoe UI Emoji","Segoe UI Symbol";}Firebase HostingLegal AI FrontendCloudflare TunnelFastAPI Backend:8000RAG RetrievalLLM Provider APIPDF Ingestion WorkerLocal Embedding Service:8010RTX 3050 6 GBNemotron 3.5Firestore / Storage

Lưu ý quan trọng: endpoint `8010` chỉ cần phục vụ các process local. Không public nó qua Cloudflare Tunnel. Browser chỉ giao tiếp với backend port 8000.

## 3. Các giai đoạn triển khai

1. Phase 0 — Environment & GPU preflight

   Kiểm tra CUDA, driver, PyTorch, bộ nhớ GPU và khả năng chạy inference.

   Chưa thay đổi repo
2. Phase 1 — Download weights & model smoke test

   Tải checkpoint BF16, load model, chạy embedding tiếng Việt, đo VRAM.

   Go/No-Go về 6 GB VRAM
3. Phase 2 — Local embedding service

   Tạo REST API tương thích với embedding client hiện tại, hỗ trợ query/passage, batch, dimensions và error handling.
4. Phase 3 — Backend integration

   Thêm embedding provider `local`, tích hợp vào ingestion worker và RAG API.
5. Phase 4 — Re-index & evaluation

   Xây lại embeddings, kiểm tra Firestore vector search, so sánh chất lượng retrieval và tốc độ xử lý.
6. Phase 5 — End-to-end Firebase demo

   Kiểm thử upload PDF → indexing → hỏi đáp → trích dẫn trên domain Firebase.

# Phase 0 — Chuẩn bị môi trường

Mình khuyên chạy embedding service trong một Python environment riêng, không cài trực tiếp vào environment của FastAPI backend.

Điều này tránh xung đột phiên bản Torch, Transformers và CUDA.

Nếu bạn dùng Windows, có thể thử native Windows với PyTorch CUDA. Ubuntu hoặc WSL2 cũng là lựa chọn phù hợp, đặc biệt nếu sau này muốn thử FlashAttention 2.

### Step 0.1 — Kiểm tra GPU

Mở terminal:

```
nvidia-smi
```

Cần xác nhận:

- GPU nhận đúng RTX 3050.
- VRAM tổng khoảng 6144 MiB.
- Driver hoạt động bình thường.
- GPU còn đủ bộ nhớ trống trước khi chạy model.

### Step 0.2 — Tạo virtual environment

Các lệnh dưới đây dành cho Bash trên Linux/WSL2. Nếu dùng PowerShell, lệnh kích hoạt môi trường sẽ khác.

```
python3.12 -m venv .venv-embed
source .venv-embed/bin/activate
python --version
```

Cài PyTorch bản CUDA theo [hướng dẫn chính thức của PyTorch](https://pytorch.org/get-started/locally/?utm_source=chatgpt.com).&#x20;

[image](https://www.google.com/s2/favicons?domain=https://pytorch.org\&sz=32)

PyTorch



Sau đó kiểm tra:

```
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Kết quả kỳ vọng:

```
True
NVIDIA GeForce RTX 3050 ...
```

### Step 0.3 — Cài thư viện inference

```
pip install "transformers==5.20.0"
pip install "sentence-transformers[image]>5.4"
pip install accelerate huggingface_hub
pip install fastapi "uvicorn[standard]" numpy httpx
```

NVIDIA công bố ví dụ Nemotron 3.5 với Python 3.12 và Transformers 5.20.0.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



Với RTX 3050, ban đầu nên thử SDPA để giảm độ phức tạp khi cài đặt. Nếu runtime không hỗ trợ, cần điều chỉnh dựa trên lỗi thực tế.

# Phase 1 — Download weights và benchmark GPU

## Step 1.1 — Download model từ Hugging Face

Model chính thức:

[NVIDIA Nemotron 3.5 Embed 1B BF16](https://huggingface.co/nvidia/Nemotron-3.5-Embed-1B-BF16?utm_source=chatgpt.com)

Cài Hugging Face CLI nếu chưa có:

```
pip install -U huggingface_hub
```

Sau đó tải weights:

```
hf download nvidia/Nemotron-3.5-Embed-1B-BF16 \
  --local-dir ./models/nemotron-3.5-embed-1b
```

Cú pháp `hf download --local-dir` được hỗ trợ bởi Hugging Face CLI.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



Checkpoint được tải một lần và lưu trên ổ đĩa. Những lần chạy tiếp theo có thể load trực tiếp từ đường dẫn local, không cần tải lại.

Không commit thư mục weights vào Git. Khi triển khai repo, nên đặt weights bên ngoài source tree hoặc thêm đường dẫn tương ứng vào `.gitignore`.

## Step 1.2 — Load model để kiểm tra VRAM

Ví dụ smoke test với Sentence Transformers:

```
import torchfrom sentence_transformers import SentenceTransformerMODEL_PATH = "./models/nemotron-3.5-embed-1b"model = SentenceTransformer(    MODEL_PATH,    device="cuda",    model_kwargs={        "dtype": torch.bfloat16,        "attn_implementation": "sdpa",    },)model.max_seq_length = 512query = model.encode_query(    ["Điều kiện đơn phương chấm dứt hợp đồng lao động là gì?"],    batch_size=1,)document = model.encode_document(    ["Người lao động có quyền đơn phương chấm dứt hợp đồng lao động theo quy định của pháp luật."],    batch_size=1,)print("Query shape:", query.shape)print("Document shape:", document.shape)print("Allocated VRAM:", torch.cuda.memory_allocated() / 1024**3, "GiB")print("Peak reserved VRAM:", torch.cuda.max_memory_reserved() / 1024**3, "GiB")
```

Đây là cấu hình thử nghiệm cho RTX 3050, không phải cấu hình đã benchmark thành công. Đặc biệt, cần xác nhận checkpoint hoạt động chính xác với `sdpa`.

Model gốc xuất vector 2048 chiều.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



## Step 1.3 — Xử lý nếu GPU hết VRAM

Thử theo thứ tự:

1. Đóng ứng dụng đang chiếm VRAM.
2. Giữ batch size bằng 1.
3. Giảm `max_seq_length` từ 512 xuống 384 hoặc 256 để kiểm tra khả năng chạy.
4. Thử FP16 nếu BF16 gặp vấn đề tương thích.
5. Thử CPU offloading nếu vẫn không load được.

Không nên quantize ngay từ đầu. Bản NVFP4 chính thức yêu cầu phần cứng có NVFP4 support, nên không dùng trực tiếp trên RTX 3050.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



Tiêu chí hoàn thành Phase 1:

- Model load được.
- Sinh được embedding query và passage.
- Không xuất hiện NaN/Inf.
- Không OOM trong ít nhất 20–50 request thử nghiệm.
- Đo được VRAM peak và latency.

Nếu không đạt bước này, chưa nên tích hợp vào repo.

# Phase 2 — Xây dựng local embedding service

Sau khi model chạy ổn trên GPU, chúng ta mới đóng gói thành API.

## Step 2.1 — Tổ chức source code

Đề xuất thêm một ứng dụng độc lập trong monorepo:

```
G1_Web_Design/
├── apps/
│   ├── api/                  # FastAPI backend hiện tại
│   ├── web/                  # Frontend
│   └── embedding/
│       ├── app/
│       │   ├── main.py       # FastAPI entrypoint
│       │   ├── model.py      # Load model, inference
│       │   ├── schemas.py    # Request/response validation
│       │   └── config.py     # Model path, dimensions, limits
│       ├── requirements.txt
│       └── README.md
```

Tách service sẽ có các lợi ích:

- Không phải load model lại mỗi request.
- FastAPI backend chính không phải mang các dependencies nặng của PyTorch.
- Có thể restart embedding service độc lập.
- Dễ chuyển embedding sang máy có GPU mạnh hơn sau này.

## Step 2.2 — Thiết kế API contract

Endpoint:

```
POST http://127.0.0.1:8010/v1/embeddings
```

Request:

```
{
  "model": "nvidia/Nemotron-3.5-Embed-1B-BF16",
  "input": [
    "Điều kiện đơn phương chấm dứt hợp đồng lao động"
  ],
  "input_type": "query",
  "dimensions": 1536
}
```

Response:

```
{
  "model": "nvidia/Nemotron-3.5-Embed-1B-BF16",
  "data": [
    {
      "index": 0,
      "object": "embedding",
      "embedding": [0.012, -0.031, 0.008]
    }
  ]
}
```

Vector trong ví dụ được rút gọn để minh họa; response thực tế phải chứa đúng 1536 giá trị.

Service cần hỗ trợ:

| Chức năng            | Yêu cầu                                                    |
| -------------------- | ---------------------------------------------------------- |
| `input_type=query`   | Dùng `encode_query()`                                      |
| `input_type=passage` | Dùng `encode_document()`                                   |
| Batch inference      | Ban đầu tối đa 1 input/lần                                 |
| Dimensions           | Xuất đúng 1536                                             |
| Normalization        | L2-normalized                                              |
| Concurrency          | Giới hạn 1 inference đồng thời lúc đầu                     |
| Health check         | `GET /health` và trạng thái model                          |
| Error handling       | OOM, model unavailable, invalid input                      |
| Logging              | Latency, số input, GPU memory; không log nội dung tài liệu |

### Cách giảm từ 2048 xuống 1536 dimensions

Sau khi sinh embedding:

```
import torch.nn.functional as F# Original: [batch_size, 2048]embeddings = embeddings[:, :1536]# Normalize again after truncationembeddings = F.normalize(    embeddings.float(),    p=2,    dim=-1,)
```

NVIDIA xác nhận model hỗ trợ rút gọn số chiều bằng prefix truncation và normalization.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://huggingface.co\&sz=32)

Hugging Face



Đối với trường hợp sử dụng text retrieval hiện tại, `encode_query()` và `encode_document()` sẽ áp dụng prompt tương ứng. Không nên tự thêm prefix `query:` hoặc `passage:` lần nữa nếu thư viện đã xử lý.

## Step 2.3 — Chạy embedding server

Lệnh dự kiến, sau khi đã tạo `apps/embedding/app/main.py`:

```
uvicorn app.main:app \
  --app-dir apps/embedding \
  --host 127.0.0.1 \
  --port 8010 \
  --workers 1
```

Không dùng nhiều Uvicorn workers vì mỗi worker có thể tạo một bản model riêng trong VRAM.

Kiểm tra:

```
curl http://127.0.0.1:8010/health
```

Tiếp theo thực hiện một request embedding và xác nhận:

- HTTP 200.
- Có đúng 1536 giá trị.
- Vector hữu hạn, norm xấp xỉ 1.
- Model không bị load lại giữa các request.

# Phase 3 — Tích hợp với repo hiện tại

Đây là phần quan trọng nhất về mặt software architecture.

Sau khi đọc các file hiện tại, mình khuyên dùng mô hình `EmbeddingProvider` có thể hoán đổi, giữ OpenRouter làm fallback thay vì xóa hoàn toàn code cũ.

## Step 3.1 — Mở rộng backend configuration

File:

[apps/api/app/core/config.py](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/core/config.py?utm_source=chatgpt.com)

Hiện tại:

```
embedding_provider: Literal["openai", "openrouter"]
```

Đề xuất:

```
embedding_provider: Literal[    "openai",    "openrouter",    "local",]
```

Các biến môi trường mới:

```
EMBEDDING_PROVIDER=local

LOCAL_EMBEDDING_URL=http://127.0.0.1:8010

LOCAL_EMBEDDING_MODEL=nvidia/Nemotron-3.5-Embed-1B-BF16

EMBEDDING_DIMENSIONS=1536
EMBEDDING_BATCH_SIZE=1
```

Đây là các biến cần bổ sung vào cấu hình; chưa thể chỉ copy vào `.env` là chạy nếu chưa implement adapter.

## Step 3.2 — Tạo LocalEmbedding adapter

File hiện tại:

[apps/api/app/services/embeddings.py](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/services/embeddings.py?utm_source=chatgpt.com)

Đề xuất interface:

```
class LocalEmbedding:    def __init__(self, settings, input_type):        self.settings = settings        self.input_type = input_type    def embed(self, texts: list[str]) -> list[list[float]]:        ...
```

Adapter sẽ:

1. Nhận danh sách text từ pipeline.
2. Ánh xạ input type sang `query` hoặc `passage`.
3. Gọi local endpoint.
4. Validate vector dimensions, thứ tự và giá trị.
5. Trả kết quả theo đúng format mà RAG hiện tại đang dùng.

Chú ý: Repo hiện đang truyền:

- `search_document` từ ingestion worker.
- `search_query` từ RAG API.

Trong khi convention của NVIDIA là `passage` và `query`. Adapter phải thực hiện ánh xạ chính xác.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://docs.nvidia.com\&sz=32)

NeMo Retriever Embedding NIM



Các giới hạn 40 request/ngày và reservation logic của OpenRouter free không nên áp dụng cho local provider.

## Step 3.3 — Kết nối PDF ingestion worker

File:

[apps/api/app/workers/ingestion.py](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/workers/ingestion.py?utm_source=chatgpt.com)

Hiện tại worker tạo `OpenRouterEmbedding` cho embedding tài liệu.

Thay đổi factory để hỗ trợ:

```
if settings.embedding_provider == "local":    return LocalEmbedding(        settings,        input_type="passage",    )
```

Trong `app/ingestion/pipeline.py`, giữ nguyên logic:

```
PDF
  → Parse
  → Segment
  → Embedding
  → Firestore vectors
  → Publish index generation
```

Chỉ thay nguồn thực thi của bước embedding.

Với batch size 1, mỗi chunk được xử lý tuần tự. Đây là cấu hình ban đầu nhằm tránh OOM; sau benchmark mới tăng batch size.

## Step 3.4 — Kết nối RAG query

File:

[apps/api/app/api/v1/rag.py](https://github.com/teddywristh/G1_Web_Design/blob/main/apps/api/app/api/v1/rag.py?utm_source=chatgpt.com)

Bổ sung local provider trong nhánh chọn embedder:

```
if settings.embedding_provider == "local":    embedder = LocalEmbedding(        settings,        input_type="query",    )
```

Phần retrieval, evidence selection và LLM answering có thể giữ nguyên.

Cũng cần rà soát nhánh ChatGPT OAuth trong file này: hiện code có điều kiện riêng chỉ cho semantic retrieval khi provider là OpenRouter. Nhánh đó phải được cập nhật nếu muốn dùng semantic retrieval với local provider.

# Phase 4 — Embedding profiles và re-index

Mình khuyên không sử dụng lại các vector đã index bằng OpenRouter ngay lập tức.

Dù cùng model family, kết quả có thể khác vì runtime, preprocessing, prompt và normalization.

Trong repo, embedding profile được tạo tại:

`apps/api/app/search/base.py`

Hiện cấu trúc profile gồm:

```
provider:model:dimensions:version
```

Nên tạo profile mới cho local embedding, bao gồm model/checkpoint revision và preprocessing version.

Ví dụ về mặt logic:

```
local:nemotron-3.5-embed-1b:1536:v1
```

Điều này đảm bảo không vô tình trộn hai loại vector.

### Có phải tạo lại Firestore vector index không?

Nếu giữ 1536 dimensions: không cần thay đổi kích thước index. File `infra/firebase/firestore.indexes.json` hiện đã khai báo vector dimension bằng 1536.

Tuy nhiên, vẫn cần chạy lại bước embedding và publish index generation mới.

Nếu chuyển sang 2048 dimensions sau này, phải cập nhật Firestore vector index tương ứng.

## 5. Benchmark trước khi cho thầy test

Benchmark Matrix

| Nhóm test        | Cấu hình / Metric                           |
| ---------------- | ------------------------------------------- |
| GPU memory       | Peak allocated/reserved VRAM                |
| Query latency    | p50, p95                                    |
| Batch size       | 1, 2, 4                                     |
| Sequence length  | 256, 512, 1024                              |
| PDF ingestion    | Một file 50 trang và một file 300 trang     |
| Retrieval        | Recall\@5, Recall\@10                       |
| Stability        | OOM, timeout, retry                         |
| Semantic quality | Câu hỏi luật tiếng Việt, có đối chiếu nguồn |

Mình đề xuất đo trên 30–50 câu hỏi pháp luật tiếng Việt có ground-truth điều/khoản, trong đó có câu hỏi diễn đạt khác với văn bản gốc.

Các tiêu chí Go/No-Go:

- Không OOM sau khi warm-up và xử lý nhiều request liên tiếp.
- Không sinh vector lỗi.
- Retrieval đạt mức chất lượng chấp nhận được so với OpenRouter hiện tại.
- Ingestion 300 trang hoàn thành mà không cần can thiệp thủ công.
- Sau khi đổi model, các tài liệu được re-index và có thể truy xuất bình thường.

Chưa nên đặt mục tiêu thời gian cụ thể trước khi có benchmark GPU thật.

# Phase 5 — Tích hợp với Firebase demo

Khi mọi thứ chạy ổn trên local, hệ thống sẽ có ba process:

| Process            | Port             | Public?          |
| ------------------ | ---------------- | ---------------- |
| Frontend           | Firebase Hosting | Có               |
| FastAPI backend    | 8000             | Qua HTTPS Tunnel |
| Nemotron embedding | 8010             | Không            |

Ingestion worker chạy riêng nhưng không cần HTTP port.

Trình tự bật demo:

1. Khởi động Nemotron embedding service.
2. Kiểm tra GPU và `/health`.
3. Khởi động ingestion worker.
4. Khởi động FastAPI backend.
5. Mở Cloudflare Tunnel đến backend/gateway.
6. Truy cập domain Firebase bằng một thiết bị khác.
7. Test login → upload PDF → xử lý → hỏi đáp → kiểm tra citation.

Lưu ý vấn đề session cookie cross-site đã trao đổi ở trên vẫn phải được giải quyết riêng. Việc self-host embedding không thay đổi vấn đề này.

## Rollback strategy

Nếu local embedding gặp OOM hoặc tốc độ không đạt:

- Giữ nguyên adapter OpenRouter hiện tại.
- Chuyển `EMBEDDING_PROVIDER` trở lại OpenRouter.
- Khôi phục cấu hình embedding profile và index generation tương ứng.
- Không xóa dữ liệu đã index trước khi local model được kiểm chứng.

Không nên silently fallback sang một embedding model khác trong khi truy vấn cùng vector index, vì điều đó có thể khiến chất lượng retrieval suy giảm mà khó phát hiện.

## Thứ tự thực hiện mình khuyến nghị

| Ưu tiên | Issue/Task                      | Điều kiện hoàn thành                       |
| ------- | ------------------------------- | ------------------------------------------ |
| P0      | GPU compatibility spike         | Nemotron 3.5 load và embed ổn trên 6 GB    |
| P0      | Local embedding server          | API trả vector 1536 chiều đúng chuẩn       |
| P0      | Embedding provider adapter      | Backend có thể chọn `local`                |
| P0      | Ingestion + RAG integration     | Cả document và query dùng cùng local model |
| P0      | Re-index + smoke tests          | Tìm kiếm, citation, PDF upload hoạt động   |
| P1      | Benchmark 300-page PDF          | Có báo cáo thời gian, VRAM, chất lượng     |
| P1      | Firebase end-to-end demo        | Máy khác truy cập và sử dụng thành công    |
| P2      | Batching, caching, quantization | Tối ưu sau khi có kết quả benchmark        |

Kết luận: Đây là một thay đổi có phạm vi tương đối gọn: thêm một embedding service và một provider adapter, sau đó nối vào hai luồng ingestion/retrieval. Thách thức kỹ thuật lớn nhất không phải endpoint hay FastAPI, mà là khả năng chạy Nemotron 3.5 ổn định trên 6 GB VRAM.

Mình sẽ coi Phase 1 là bước bắt buộc trước khi sửa kiến trúc repo. Nếu model không fit, cần biết rõ nguyên nhân OOM và giới hạn thực tế rồi mới quyết định có CPU offloading hoặc quantization hay không.