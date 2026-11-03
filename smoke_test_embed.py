import torch
from sentence_transformers import SentenceTransformer

MODEL_PATH = "./models/nemotron-3.5-embed-1b"

model = SentenceTransformer(
    MODEL_PATH,
    device="cuda",
    model_kwargs={
        "dtype": torch.bfloat16,
        "attn_implementation": "sdpa",
    },
)

model.max_seq_length = 512

query = model.encode_query(
    ["Điều kiện đơn phương chấm dứt hợp đồng lao động là gì?"],
    batch_size=1,
)

document = model.encode_document(
    ["Người lao động có quyền đơn phương chấm dứt hợp đồng lao động theo quy định của pháp luật."],
    batch_size=1,
)

print("Query shape:", query.shape)
print("Document shape:", document.shape)
print("Allocated VRAM:", torch.cuda.memory_allocated() / 1024**3, "GiB")
print("Peak reserved VRAM:", torch.cuda.max_memory_reserved() / 1024**3, "GiB")