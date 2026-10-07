# Kịch bản demo Topic A — 3 phút

Mở sẵn `report/REPORT.md`, `results/figures/yaw_sweep.png` và hai ảnh failure.
Các con số dưới đây lấy từ CSV hiện có; đối chiếu sau khi nhận kết quả Colab.

| Thời gian | Nội dung |
|---|---|
| 0:00–0:20 | Tôi kiểm tra độ nhạy của phép chiếu LiDAR–camera với calibration drift. Trên 20 frame KITTI, yaw +1° làm alignment giảm từ 93,21% xuống 68,08%, nhưng FOV gần như không đổi. |
| 0:20–1:20 | Mỗi cấu hình chỉ đổi một tham số. Tập điểm mỗi object được chọn bằng calibration gốc và giữ cố định; điểm ra khỏi FOV vẫn tính trong mẫu số. Alignment là trung bình tỉ lệ điểm trong chính box 2D của từng object. Tôi chạy yaw sweep trên cả KITTI và nuScenes, cùng pitch/roll/translation trên KITTI. |
| 1:20–2:20 | Geometry failure: frame 000023 ở +3° có alignment 0%. Metric failure: frame 000049 ở +1° vẫn có score 87,82%, cao hơn ngưỡng 81,65%, dù điểm dịch khoảng 14,67 pixel. Box lớn và trung bình qua nhiều object có thể che giấu drift. |
| 2:20–3:00 | Dùng công cụ cho QA sau lắp sensor hoặc va chạm. Log alignment theo object/class/range, FOV và time offset; đối chiếu edge alignment khi cần. Score đang cần GT và calibration tham chiếu nên đây là kiểm tra offline, chưa phải cảnh báo tự động trên xe. |

## Câu hỏi cần tự trả lời

- **Ngưỡng 81,65% lấy từ đâu?** Percentile 5 của score clean trên 10 frame KITTI đầu; 10 frame còn lại dùng đánh giá, không chọn ngưỡng.
- **Lệch 1° có chắc phát hiện không?** Không. Trên tập evaluation, alarm +1° là 60%, −1° là 70%; có missed detection minh họa.
- **Vì sao KITTI và nuScenes khác nhau?** Khác tiêu cự, kích thước ảnh, FOV, số beam, object mix và thời gian chụp. Box 2D nuScenes được loader sinh từ box 3D nên không phải annotation 2D độc lập.
- **Code nào tính metric?** `points_in_box()` chọn tập điểm; `experiment()` đếm điểm trong box; `summarize()` tính trung bình theo object; `detection()` chọn ngưỡng clean-only.
- **Calibration bracket lệch 1° là quay quanh trục nào?** Yaw trong thí nghiệm quay quanh trục z-up của LiDAR; không phải trục z-forward của camera.

Học viên cần tự tập một lần với đồng hồ và giải thích được các con số; file này không xác nhận bạn đã tập hoặc đã demo.
