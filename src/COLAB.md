# Chạy Topic A qua Google Colab extension trong VS Code

Notebook: `src/topic_a_colab.ipynb`. Extension Google Colab đã có trên máy.
Notebook chứa snapshot code đã sửa, tự clone dữ liệu gốc và kiểm tra manifest; không cần push trước khi chạy.

1. Mở notebook trong VS Code.
2. Bấm **Select Kernel → Colab → Auto Connect**; đăng nhập Google nếu extension yêu cầu. CPU đủ cho topic A.
3. Bấm **Run All**. Cell đầu kiểm tra runtime Colab; chọn nhầm Python local sẽ báo lỗi rõ ràng.
4. Kiểm tra bảng, overlay và failure; điền `CLASS_NAME` ở cell tạo báo cáo nếu biết tên lớp.
5. Cell cuối tự tạo **results.zip** và gửi yêu cầu tải về máy qua widget. Nếu VS Code/trình duyệt chặn tải tự động, bấm **Tải results.zip** trong cell. Dự phòng: mở **Colab → Contents** → refresh, chuột phải `results.zip` trong `/content` → **Download**.
6. Giải nén ZIP vào thư mục repo local. ZIP chứa kết quả mới trong `results/` và `report/REPORT.md`; không chứa dữ liệu gốc.
7. **Save** notebook để giữ outputs được tạo trên Colab. Chạy `python tools/check_submission.py` trong repo local.

Lưu ý: Colab là máy remote, không tự thấy ổ `D:` và không tự đồng bộ file repo local.
`google.colab.files.download()` không được hỗ trợ trực tiếp qua extension; notebook dùng widget theo hướng dẫn Google. Widget cần `anywidget`, được cài ở cell setup. ZIP được truyền tạm qua comm buffers, không lưu trong notebook.
Cập nhật snapshot notebook sau khi sửa code bằng `python -m src.build_colab_notebook`; outputs/metadata của các cell không đổi được giữ nguyên, outputs của cell có source đổi được xoá để tránh nhầm kết quả cũ.

Kết quả đang có sẵn trong repo được tạo bằng CPU Windows local và được ghi đúng trong `results/run_metadata.json`.
Sau khi chạy notebook và giải nén ZIP, metadata/REPORT sẽ ghi `google_colab` và môi trường Linux thực tế.
Chưa được phép coi một notebook chưa chạy là bằng chứng Colab.

Nguồn thao tác extension: [Google Colab User Guide](https://github.com/googlecolab/colab-vscode/wiki/User-Guide),
[Known Issues and Workarounds](https://github.com/googlecolab/colab-vscode/wiki/Known-Issues-and-Workarounds).
