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

  // Logo dùng file ảnh gốc, giữ chữ nhận diện khi chưa có ảnh.
  document.querySelectorAll("[data-logo]").forEach((image) => {
    const showLogo = () => {
      image.hidden = false;
      image.previousElementSibling.hidden = true;
    };
    image.addEventListener("load", showLogo);
    if (image.complete && image.naturalWidth) showLogo();
  });
  // Đánh dấu các trường bắt buộc theo thuộc tính của biểu mẫu.
  document
    .querySelectorAll("input[required], select[required], textarea[required]")
    .forEach((input) => {
      const label = input.closest("label") || document.querySelector(`label[for="${input.id}"]`);
      if (!label || label.querySelector(".required-mark")) return;
      const mark = document.createElement("span");
      mark.className = "required-mark";
      mark.textContent = " *";
      mark.setAttribute("aria-hidden", "true");
      const caption = document.createElement("span");
      while (label.firstChild && label.firstChild !== input) caption.append(label.firstChild);
      caption.append(mark);
      label.prepend(caption);
    });
  await import("./app.js");
  document.querySelector("#loading-status").remove();
}

start().catch((error) => {
  document.querySelector("#loading-status").textContent =
    `Không tải được giao diện. Hãy chạy bằng HTTP server và tải lại trang. ${error.message}`;
  console.error(error);
});
