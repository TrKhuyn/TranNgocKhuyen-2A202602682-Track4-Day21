"""Build a self-contained code snapshot for the official Colab VS Code extension.

The remote runtime clones original public dataset files. Updated student code is
embedded as plain text, so unpublished local code runs without a git push.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]


def markdown(source):
    return dict(cell_type='markdown', metadata={}, source=source.splitlines(keepends=True))


def code(source):
    return dict(cell_type='code', metadata={}, execution_count=None, outputs=[],
                source=textwrap.dedent(source).strip().splitlines(keepends=True))


def main():
    files = ['starter/projection.py', 'src/__init__.py', 'src/topic_a.py',
             'src/test_projection.py', 'src/write_report.py', 'src/export_results.py', 'src/COLAB.md']
    snapshots = {name: (ROOT / name).read_text(encoding='utf-8') for name in files}
    hashes = {name: hashlib.sha256((ROOT / 'data' / name / 'MANIFEST.json').read_bytes()).hexdigest()
              for name in ['kitti_mini', 'nuscenes_mini_subset']}
    bootstrap = '''
import os, sys, subprocess, platform, hashlib
from pathlib import Path

assert platform.system() == 'Linux' and Path('/content').is_dir(), (
    'Chọn Select Kernel > Colab > Auto Connect trước khi Run All. '
    'Notebook này yêu cầu runtime Colab để tránh nhầm số liệu local với remote.')
ROOT = Path('/content/topic_a_lab')
UPSTREAM = 'https://github.com/VinUni-AI20k/K4-Track4-Day06-3D-From-Point-Clouds.git'
if not (ROOT / '.git').is_dir():
    assert not ROOT.exists(), 'Thư mục /content/topic_a_lab đã tồn tại nhưng không phải repo; đổi ROOT.'
    subprocess.run(['git', 'clone', '--depth', '1', UPSTREAM, str(ROOT)], check=True)
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
'''
    bootstrap += '\nDATA_MANIFEST_SHA256 = ' + repr(hashes) + '\n'
    bootstrap += '''
for dataset, expected in DATA_MANIFEST_SHA256.items():
    actual = hashlib.sha256((ROOT / 'data' / dataset / 'MANIFEST.json').read_bytes()).hexdigest()
    assert actual == expected, f'Dataset {dataset} khác snapshot local; kiểm tra trước khi benchmark.'
print('Colab runtime:', platform.platform(), sys.version)
print('Working directory:', ROOT)
'''
    source_cell = 'STUDENT_FILES = ' + repr(snapshots) + '\n'
    source_cell += '''
for relative, content in STUDENT_FILES.items():
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
# Reload imports if this notebook has previously run in the same kernel.
for name in list(sys.modules):
    if name == 'starter' or name.startswith('starter.') or name == 'src' or name.startswith('src.'):
        del sys.modules[name]
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'anywidget>=0.9,<0.12'], check=True)
print('Student code snapshot installed; original data untouched.')
'''
    cells = [
        markdown('''# Lab 6 — Topic A: LiDAR–camera calibration QA

**Trần Ngọc Khuyến — 2A202602682**

Trong VS Code: **Select Kernel → Colab → Auto Connect → Run All**. CPU là đủ.
Notebook clone dữ liệu public của đề bài, cài snapshot code và chạy benchmark trên 20 KITTI + 80 nuScenes frame.
Không cần push code lên GitHub để chạy snapshot này. Runtime cần Internet để clone/install.
Outputs ban đầu để trống; các con số chỉ được tạo khi kernel chạy thật.

Nguồn: KITTI Vision Benchmark Suite, nuScenes (Motional).
'''),
        markdown('## 1. Kết nối và lấy dữ liệu gốc'), code(bootstrap),
        markdown('## 2. Cài snapshot code và thư viện\nCell dài chứa toàn bộ code cần thiết để runtime remote không dùng nhầm bản starter chưa sửa.'),
        code(source_cell),
        markdown('## 3. Xác minh dữ liệu và kiểm tra hình học'),
        code('''
for dataset in ['data/kitti_mini', 'data/nuscenes_mini_subset']:
    subprocess.run([sys.executable, '-B', 'tools/verify_data.py', '--data-root', dataset], check=True)
subprocess.run([sys.executable, '-B', '-m', 'unittest', 'src.test_projection', '-v'], check=True)
'''),
        markdown('''## 4. Thí nghiệm Topic A

Chỉ thay đổi một yếu tố mỗi cấu hình. Yaw 0/±0.5/±1/±2/±3° trên cả hai dataset;
pitch, roll và translation 2–10 cm trên KITTI. Tập điểm từng object chọn bằng calibration gốc, giữ cố định.
Alignment là trung bình tỉ lệ điểm nằm trong chính box 2D của object; FOV là tỉ lệ điểm hữu hạn trong ảnh.
Score cần GT: đây là QA offline, chưa phải sensor monitor khi chạy thật.
'''),
        code('''
subprocess.run([sys.executable, '-B', '-m', 'src.topic_a', '--seed', '42'], check=True)
import json
metadata = json.loads((ROOT / 'results/run_metadata.json').read_text(encoding='utf-8'))
assert metadata['runtime'] == 'google_colab'
print('Runtime đã xác minh:', metadata['runtime'])
'''),
        markdown('## 5. Đọc bảng và xem bằng chứng'),
        code('''
import pandas as pd
from IPython.display import display, Image
summary = pd.read_csv(ROOT / 'results/sweep_summary.csv')
display(summary[summary.factor == 'yaw_deg'])
display(pd.read_csv(ROOT / 'results/detection_summary.csv'))
for name in ['yaw_sweep.png', 'other_axes.png', 'range_class_sweep.png', 'drift_threshold.png',
             'overlay_000011.png', 'overlay_000019.png', 'overlay_000004.png',
             'fail_01_large_drift.png', 'fail_02_score_blind_spot.png']:
    print(name)
    display(Image(filename=str(ROOT / 'results/figures' / name), width=1000))
'''),
        markdown('## 6. Tạo báo cáo từ số liệu Colab và kiểm tra bài\nBổ sung tên lớp nếu đã biết; báo cáo ghi đúng runtime tạo số liệu.'),
        code('''
CLASS_NAME = 'AI20K-T4'
subprocess.run([sys.executable, '-B', '-m', 'src.write_report', '--class-name', CLASS_NAME], check=True)
subprocess.run([sys.executable, '-B', 'tools/check_submission.py'], check=True)
# check_submission scans git-tracked files; also inspect new student artifacts.
artifacts = [ROOT / path for path in STUDENT_FILES] + list((ROOT / 'results').rglob('*'))
assert all(path.stat().st_size <= 20_000_000 for path in artifacts if path.is_file())
from IPython.display import Markdown
display(Markdown((ROOT / 'report/REPORT.md').read_text(encoding='utf-8')))
'''),
        markdown('''## 7. Xuất kết quả về repo local

Cell dưới tạo **results.zip** chứa `results/` và `report/REPORT.md`, rồi gửi yêu cầu tải về máy qua widget.
Nếu tải tự động bị chặn, bấm **Tải results.zip** trong cell; cách dự phòng là **Colab → Contents → results.zip → Download**.
Giải nén vào repo local để thay kết quả local bằng kết quả Colab, rồi Save notebook để giữ outputs trong VS Code.
ZIP được truyền qua widget khi kernel đang kết nối, không nhúng dữ liệu ZIP vào outputs của notebook.
'''),
        code('''
from src.export_results import make_archive, show_download
archive = make_archive(ROOT, '/content/results.zip')
print(f'Download: {archive} ({archive.stat().st_size / 1e6:.1f} MB)')
print('Không commit ZIP; chỉ commit các file đã giải nén và notebook đã Save.')
download_widget = show_download(archive)
'''),
    ]
    notebook = dict(cells=cells, metadata=dict(kernelspec=dict(display_name='Python 3', language='python', name='python3'),
                    language_info=dict(name='python'), colab=dict(name='topic_a_colab.ipynb', provenance=[])),
                    nbformat=4, nbformat_minor=5)
    for i, cell in enumerate(cells):
        cell['id'] = f'topic-a-{i:02d}'
    target = ROOT / 'src/topic_a_colab.ipynb'
    if target.exists():
        previous = json.loads(target.read_text(encoding='utf-8'))
        previous_cells = {cell.get('id'): cell for cell in previous['cells']}
        for i, cell in enumerate(cells):
            old = previous_cells.get(cell['id'])
            if old is not None:
                if old.get('source') == cell['source']:
                    cells[i] = old
                else:
                    cell['metadata'] = old.get('metadata', {})
        notebook['metadata'] = previous.get('metadata', notebook['metadata'])
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'Built {target}; {len(cells)} cells, {target.stat().st_size / 1000:.1f} KB')


if __name__ == '__main__':
    main()
