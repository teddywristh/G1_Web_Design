import { api } from "./api.js";

const API_KB_LIMIT = 5;

// API nhận từng nhóm kho nên UI tra cứu lần lượt toàn bộ phạm vi
async function askSources(body, knowledgeBases, onProgress, isCurrent) {
  const groups = [];
  for (let index = 0; index < knowledgeBases.length; index += API_KB_LIMIT)
    groups.push(knowledgeBases.slice(index, index + API_KB_LIMIT));
  if (!groups.length) groups.push([]);
  const results = [];
  const errors = [];
  for (const [index, group] of groups.entries()) {
    if (!isCurrent()) return null;
    onProgress(
      `Đã gửi yêu cầu ${index + 1}/${groups.length}${group.length ? ` · ${group.map((kb) => kb.title).join(", ")}` : " · tìm nguồn web nếu được bật"}. Đang chờ máy chủ trả kết quả.`,
    );
    try {
      const data = await api.post("/rag/ask", {
        ...body,
        knowledge_base_ids: group.map((kb) => kb.id),
      });
      if (!isCurrent()) return null;
      results.push({ data, group });
      onProgress(
        `Đã nhận kết quả ${index + 1}/${groups.length} · ${data.citations?.length || 0} nguồn tham khảo.`,
      );
    } catch (error) {
      if (!isCurrent()) return null;
      if (
        ["chatgpt_disconnected", "ai_authentication_failed", "ai_not_configured"].includes(
          error.code,
        )
      )
        throw error;
      errors.push(`${group.map((kb) => kb.title).join(", ") || "Nguồn web"}: ${error.message}`);
      onProgress(`Yêu cầu ${index + 1}/${groups.length} chưa hoàn tất: ${error.message}`);
    }
  }
  if (!results.length) throw new Error(errors.join("\n") || "Không nhận được kết quả.");
  if (results.length === 1 && !errors.length) return results[0].data;
  const combined = {
    ...results[0].data,
    answer: "",
    citations: [],
    assumptions: [],
    missing_facts: [],
    source_limitations: [],
    scope_errors: errors,
  };
  combined.answer = results
    .map(({ data, group }) => {
      const offset = combined.citations.length;
      const answer = data.answer.replace(/\[(\d+)\]/g, (match, number) =>
        Number(number) >= 1 && Number(number) <= (data.citations?.length || 0)
          ? `[${Number(number) + offset}]`
          : match,
      );
      combined.citations.push(...(data.citations || []));
      for (const key of ["assumptions", "missing_facts", "source_limitations"])
        combined[key].push(...(data[key] || []));
      return `${group.map((kb) => kb.title).join(" · ")}\n${answer}`;
    })
    .join("\n\n");
  combined.answer =
    "Kết quả tra cứu theo từng nhóm kho. Hãy đối chiếu các nguồn giữa các nhóm.\n\n" +
    combined.answer;
  if (errors.length) combined.status = "temporarily_unavailable";
  else if (results.some(({ data }) => data.status === "conflicting_sources"))
    combined.status = "conflicting_sources";
  else if (results.some(({ data }) => data.status !== "answered"))
    combined.status = "insufficient_evidence";
  for (const key of ["assumptions", "missing_facts", "source_limitations"]) combined[key] = [...new Set(combined[key])];
  combined.has_sufficient_evidence = combined.status === "answered";
  return combined;
}

export { askSources };
