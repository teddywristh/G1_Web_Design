export type LegalDocument = {
  id: string;
  title: string;
  number: string;
  category: string;
  authority: string;
  date: string;
  status: "ready" | "uploaded";
  saved: boolean;
  sample?: boolean;
};
export type Conversation = { id: string; title: string; date: string; notes: string[] };

// Illustrative metadata only: these records do not assert current legal validity.
export const initialDocuments: LegalDocument[] = [
  {
    id: "sample-1",
    title: "Bộ luật Lao động",
    number: "45/2019/QH14",
    category: "Bộ luật",
    authority: "Quốc hội",
    date: "2026-10-29",
    status: "ready",
    saved: true,
    sample: true,
  },
  {
    id: "sample-2",
    title: "Luật Doanh nghiệp",
    number: "59/2020/QH14",
    category: "Luật",
    authority: "Quốc hội",
    date: "2026-10-28",
    status: "ready",
    saved: false,
    sample: true,
  },
  {
    id: "sample-3",
    title: "Bộ luật Dân sự",
    number: "91/2015/QH13",
    category: "Bộ luật",
    authority: "Quốc hội",
    date: "2026-10-27",
    status: "ready",
    saved: false,
    sample: true,
  },
  {
    id: "sample-4",
    title: "Luật Bảo vệ dữ liệu cá nhân",
    number: "Tài liệu nghiên cứu",
    category: "Luật",
    authority: "Thư viện nội bộ",
    date: "2026-10-26",
    status: "uploaded",
    saved: true,
    sample: true,
  },
  {
    id: "sample-5",
    title: "Luật Giao dịch điện tử",
    number: "20/2023/QH15",
    category: "Luật",
    authority: "Quốc hội",
    date: "2026-10-25",
    status: "ready",
    saved: false,
    sample: true,
  },
];

export function readLocal<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function dateLabel(value: string) {
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}
