// Ghép các phần HTML trước khi khởi tạo chức năng.
async function start() {
  const slots = [...document.querySelectorAll("template[data-part]")];
  const parts = await Promise.all(
    slots.map(async (slot) => {
      const url = new URL(`../html/${slot.dataset.part}.html`, import.meta.url);
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Không tải được ${url.pathname}.`);
      return response.text();
    }),
  );

  slots.forEach((slot, index) => {
    const content = document.createElement("template");
    // Chỉ dùng các tệp HTML cố định của ứng dụng.
    content.innerHTML = parts[index];
    slot.replaceWith(content.content);
  });

  await import("./app.js");
  document.querySelector("#loading-status").remove();
}

start().catch((error) => {
  document.querySelector("#loading-status").textContent =
    `Không tải được giao diện. Hãy chạy bằng HTTP server và tải lại trang. ${error.message}`;
  console.error(error);
});
