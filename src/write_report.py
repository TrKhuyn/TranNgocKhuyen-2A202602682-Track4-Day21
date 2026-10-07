"""Render the Vietnamese lab report directly from measured CSVs and metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', default='results')
    parser.add_argument('--out', default='report/REPORT.md')
    parser.add_argument('--class-name', default='AI20K-T4')
    args = parser.parse_args()
    results = Path(args.results)
    metadata = json.loads((results / 'run_metadata.json').read_text(encoding='utf-8'))
    summary = pd.read_csv(results / 'sweep_summary.csv')
    detection = pd.read_csv(results / 'detection_summary.csv')
    yaw = summary[(summary.dataset == 'kitti') & (summary.factor == 'yaw_deg')]
    clean = yaw[yaw.value == 0].iloc[0]
    drift1 = yaw[yaw.value == 1].iloc[0]
    drift3 = yaw[yaw.value == 3].iloc[0]
    threshold = metadata['threshold_pct']
    metric_failure, geometry_failure = metadata['metric_failure'], metadata['geometry_failure']
    versions = metadata['versions']
    runtime_label = 'Google Colab (Linux)' if metadata['runtime'] == 'google_colab' else 'máy Windows local; chưa xác nhận chạy Colab'
    table = ['| Yaw (°) | KITTI: alignment (%) | KITTI: FOV (%) | nuScenes: alignment (%) |',
             '|---:|---:|---:|---:|']
    for row in yaw.itertuples():
        match = summary[(summary.dataset == 'nuscenes') & (summary.factor == 'yaw_deg') & (summary.value == row.value)]
        other = f'{match.iloc[0].macro_box_pct:.2f}' if len(match) else 'Không chạy'
        table.append(f'| {row.value:+g} | {row.macro_box_pct:.2f} | {row.fov_pct:.2f} | {other} |')
    alarm1 = detection[detection.yaw_deg == 1].iloc[0].alarm_rate_pct
    alarmminus1 = detection[detection.yaw_deg == -1].iloc[0].alarm_rate_pct
    false_alarm = detection[detection.yaw_deg == 0].iloc[0].alarm_rate_pct
    demo_text = '; '.join(f"`{row['frame_id']}`: {row['depth_m']:.2f} m" for row in metadata['demo_depths'])
    kitti_ids = metadata['calibration_ids'] + metadata['evaluation_ids']
    nuscenes_text = '; nuScenes: `scene-0103_000…039`, `scene-1094_000…039`' if metadata['datasets']['nuscenes'] else ''
    if metadata['actual_missed_detection']:
        failure_text = (f"**Metric:** frame `{metric_failure['frame_id']}`, yaw {metric_failure['value']:+g}° "
                        f"dịch điểm median {metric_failure['median_shift_px']:.2f} px nhưng score "
                        f"{metric_failure['macro_box_pct']:.2f}% vẫn trên ngưỡng {threshold:.2f}% → bỏ sót drift. "
                        "Box 2D cho phép sai số vị trí bên trong box; trung bình qua object còn che mất một object bị lệch. "
                        "Kiểm tra score từng object, displacement và edge alignment để phát hiện.")
    else:
        failure_text = 'Không tìm được missed detection trong cấu hình đã chạy; không khẳng định metric hoàn hảo ngoài tập nhỏ này.'
    report = f'''# Báo cáo Day 6: Độ nhạy của LiDAR–camera projection với calibration drift

- **Họ tên:** Trần Ngọc Khuyến
- **MSSV:** 2A202602682
- **Lớp:** {args.class_name}
- **Link repo:** https://github.com/TrKhuyn/TranNgocKhuyen-2A202602682-Track4-Day21
- **Topic:** A — LiDAR-camera projection QA; Good + khảo sát alignment score/ngưỡng ở mức Advanced.
- **Dataset:** data/synthetic (kiểm tra geometry), data/kitti_mini{', data/nuscenes_mini_subset' if metadata['datasets']['nuscenes'] else ''}.
- **Các frame đã dùng:** KITTI: {', '.join(kitti_ids)}{nuscenes_text}; synthetic: 000000 cho kiểm tra điểm chuẩn.
- **Môi trường tạo số liệu hiện tại:** {runtime_label}; Python {metadata['python'].split()[0]}, NumPy {versions['numpy']}, OpenCV {versions['opencv']}, pandas {versions['pandas']}, matplotlib {versions['matplotlib']}.

## 1. Claim

Trên {int(clean.n_frames)} frame KITTI, lệch yaw +1° làm alignment trung bình theo object giảm từ **{clean.macro_box_pct:.2f}% xuống {drift1.macro_box_pct:.2f}%** (−{clean.macro_box_pct - drift1.macro_box_pct:.2f} điểm phần trăm), trong khi tỉ lệ điểm trong FOV chỉ đổi từ {clean.fov_pct:.2f}% thành {drift1.fov_pct:.2f}%.
Ở +3°, alignment còn {drift3.macro_box_pct:.2f}%; vì vậy FOV ratio một mình không đủ để kiểm tra calibration.
Đây là kết quả thực nghiệm trên subset, không phải ngưỡng bảo đảm an toàn cho mọi sensor hoặc scene.

## 2. Evidence

Mỗi lần chỉ thay đổi một yếu tố: yaw −3…+3° trên hai dataset; pitch 0/0.5/1/2/3°, roll 0/1/2/3°, translation theo y LiDAR KITTI 0/±2/±5/±10 cm. Seed 42, không có phép lấy mẫu ngẫu nhiên trong benchmark.
Tập điểm object được chọn **một lần** bằng box 3D GT và calibration gốc, cố định qua mọi mức drift; mỗi object có ≥{metadata['min_object_points']} điểm, kể cả điểm ra khỏi FOV sau perturb vẫn nằm trong mẫu số.
`alignment = 100 × mean_object(n_points_inside_own_2D_box / n_reference_object_points)`; bảng dùng trung bình theo object, score cảnh báo dùng trung bình object trong từng frame. FOV dùng số điểm XYZ hữu hạn làm mẫu số; CSV còn có micro average theo điểm.

{chr(10).join(table)}

![Yaw sweep](../results/figures/yaw_sweep.png)
![Các trục khác](../results/figures/other_axes.png)
![Range và class](../results/figures/range_class_sweep.png)

Demo ở ba độ sâu target khác nhau: {demo_text}. Target được đánh dấu đỏ; các box còn lại màu xanh. Màu điểm theo depth của starter: đỏ gần, xanh xa.

![Demo gần](../results/figures/overlay_000011.png)
![Demo trung gian](../results/figures/overlay_000019.png)
![Demo xa](../results/figures/overlay_000004.png)

**Ngưỡng Advanced:** lấy percentile 5 của score clean trên {len(metadata['calibration_ids'])} frame KITTI đầu theo frame ID: **{threshold:.2f}%**; alarm khi score thấp hơn ngưỡng. Không dùng frame evaluation hoặc các mức perturb để chọn ngưỡng.
Trên {len(metadata['evaluation_ids'])} frame còn lại: alarm +1° = {alarm1:.0f}%, −1° = {alarmminus1:.0f}%, clean = {false_alarm:.0f}%; chi tiết trong `results/detection_summary.csv`. Với tập test nhỏ và các perturb của cùng frame, không xem đây là ước lượng độc lập hay bảo đảm tổng quát.

![Score và ngưỡng](../results/figures/drift_threshold.png)

**[B5]** Cùng yaw sweep trên hai dataset thật: bảng trên và `results/sweep_summary.csv` là bằng chứng. KITTI 64 beam, ảnh hẹp 1242×375; nuScenes 32 beam, ảnh 1600×900 và hai scene ngày/đêm. Khác focal length, FOV, object mix và số điểm tạo ra mức dịch pixel/score khác nhau; không quy toàn bộ khác biệt cho số beam.
nuScenes đã bù ego motion nhưng chưa bù chuyển động riêng từng object. Box 2D của loader nuScenes **được sinh từ box 3D**, nên kết quả này là kiểm tra nhạy với perturb trong cùng hình học, không phải đối chiếu annotation 2D độc lập như KITTI.
Nguồn ảnh: **KITTI Vision Benchmark Suite**; dữ liệu nuScenes: **nuScenes (Motional)**.

CSV tái lập: `results/frame_metrics.csv`, `object_metrics.csv`, `sweep_summary.csv`, `drift_detection.csv`, `detection_summary.csv`, `demo_depths.csv`; cấu hình, phiên bản và SHA-256 nằm trong `results/run_metadata.json`.

## 3. Failure case

**Geometry:** frame `{geometry_failure['frame_id']}` ở yaw {geometry_failure['value']:+g}° còn alignment {geometry_failure['macro_box_pct']:.2f}% và dịch median {geometry_failure['median_shift_px']:.2f} px. Extrinsic sai làm điểm rơi khỏi object; FOV vẫn {geometry_failure['fov_pct']:.2f}% nên không chỉ nhìn tổng số điểm trong ảnh.

![Geometry failure](../results/figures/fail_01_large_drift.png)

{failure_text}

![Metric failure](../results/figures/fail_02_score_blind_spot.png)

Điểm pixel displacement cần calibration tham chiếu, còn containment score cần box GT và tập điểm đã chọn từ calibration gốc. Cả hai là công cụ QA **offline**, chưa phải bộ phát hiện drift tự động khi chạy thật không có GT.
Object <{metadata['min_object_points']} điểm bị loại nên chưa đánh giá được vật cực xa/thưa; occlusion/truncation và box GT vốn có sai số cũng có thể làm score clean thấp. Dùng scene độc lập lớn hơn, score theo class/range và edge alignment để kiểm chứng thêm.

## 4. Khuyến nghị nếu triển khai thật

Use-case: QA sau lắp sensor hoặc sau va chạm nhẹ trên xe ADAS; theo dõi drift trước khi sử dụng kết quả camera–LiDAR fusion.
Log invalid ratio, FOV, alignment theo object/class/range, camera–LiDAR time offset và latency; ảnh overlay cần được giữ ở các frame alarm để review.
Containment tính nhanh nhưng bỏ sót dịch trong box lớn; edge alignment hoặc correspondence độc lập tốn thêm xử lý và dễ nhiễu do texture, ban đêm và occlusion.
Không tự hiệu chỉnh calibration chỉ từ threshold trong lab: cần cảnh báo liên tiếp nhiều frame, kiểm tra chuyển động object, scene đa dạng và quy trình xác nhận calibration.

## 5. Cách chạy lại

Từ thư mục gốc repo đã clone, Python ≥3.10:

```bash
pip install -r requirements.txt
python tools/verify_data.py --data-root data/kitti_mini
python tools/verify_data.py --data-root data/nuscenes_mini_subset
python -m unittest src.test_projection -v
python -m src.topic_a
python -m src.write_report
python tools/check_submission.py
```

**[B4]** Tool dùng lại được: `python -m src.topic_a --help` mô tả mọi tham số và giá trị mặc định; `python -m src.topic_a` chạy toàn bộ thí nghiệm, hoặc thêm `--skip-nuscenes --out-dir results/kitti_only` để chạy KITTI riêng. Bằng chứng: `src/topic_a.py` và CSV/ảnh đã tạo. B4/B5 có thể được chấm tối đa +5 điểm nếu tiêu chí liên quan đạt; không khai báo B1/B2/B3/B6.
**Colab extension:** mở `src/topic_a_colab.ipynb` → Select Kernel → Colab → Auto Connect → Run All. Cell cuối tạo `results.zip` và gửi yêu cầu tải qua widget; nếu trình duyệt/VS Code chặn tải tự động, bấm **Tải results.zip**. ZIP chứa `results/` và REPORT của runtime đó; không cần push code trước khi chạy. Xem `src/COLAB.md` để lấy kết quả về máy.
Notebook sẽ ghi runtime thực vào metadata và tạo lại REPORT từ CSV của runtime đó; không gọi kết quả local là kết quả Colab.
Sáu kiểm tra geometry gồm điểm chuẩn (10,0,0), rigid transform + rectification, cột translation của P2, NaN/Inf/depth/FOV, input rỗng và membership box xoay có bottom-center.

## 6. Khai báo sử dụng AI

| Công cụ | Dùng cho việc gì | Cách kiểm chứng |
|---|---|---|
| Codex | Phân tích đề, hỗ trợ viết projection, benchmark, notebook Colab và báo cáo từ CSV | Kiểm tra geometry độc lập; chạy thật trên dữ liệu gốc, xem overlay/failure và đối chiếu bảng với CSV; ghi đúng runtime trong metadata |

Học viên cần tự đọc code, đối chiếu kết quả và giải thích được metric cùng các failure trước khi nộp/vấn đáp.
'''
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding='utf-8')
    print(f'Report written: {output}; runtime={metadata["runtime"]}')


if __name__ == '__main__':
    main()
