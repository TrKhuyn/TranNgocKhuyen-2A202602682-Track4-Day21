"""Calibration QA with fixed object point sets and reproducible one-factor sweeps.

Run: python -m src.topic_a --help
Geometry conventions come from the provided starter/kitti_io.py and projection.py.
All measurements are computed from original data; no source data are overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from starter.datasets import list_frames, load_frame
from starter.projection import (draw_box2d, overlay_points, perturb_extrinsic,
                                project_velo_to_image, velo_to_cam)


def points_in_box(camera_xyz, obj):
    """Undo camera yaw; KITTI location is bottom center, local y lies in [-h, 0]."""
    h, w, length = obj.dimensions
    c, s = np.cos(obj.rotation_y), np.sin(obj.rotation_y)
    rotation = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    local = (camera_xyz - obj.location) @ rotation
    return (np.isfinite(local).all(axis=1)
            & (np.abs(local[:, 0]) <= length / 2 + 1e-6)
            & (local[:, 1] >= -h - 1e-6) & (local[:, 1] <= 1e-6)
            & (np.abs(local[:, 2]) <= w / 2 + 1e-6))


def configurations(dataset):
    """Each entry changes one axis; all other components stay at zero."""
    configs = [('yaw_deg', v) for v in [-3, -2, -1, -.5, 0, .5, 1, 2, 3]]
    if dataset == 'kitti':
        configs += [('pitch_deg', v) for v in [0, .5, 1, 2, 3]]
        configs += [('roll_deg', v) for v in [0, 1, 2, 3]]
        configs += [('ty_m', v) for v in [-.1, -.05, -.02, 0, .02, .05, .1]]
    return configs


def drifted(calib, factor, value):
    if factor == 'ty_m':
        return perturb_extrinsic(calib, t_xyz_m=(0, value, 0))
    return perturb_extrinsic(calib, **{factor: value})


def indexed_projection(points, calib, image_shape):
    uv, depth, mask = project_velo_to_image(points, calib, image_shape)
    indexed = np.full((len(points), 2), np.nan)
    indexed[mask] = uv
    return indexed, uv, depth, mask


def in_image_box(uv, bbox):
    x1, y1, x2, y2 = bbox
    return (np.isfinite(uv).all(axis=1) & (uv[:, 0] >= x1)
            & (uv[:, 0] <= x2) & (uv[:, 1] >= y1) & (uv[:, 1] <= y2))


def selected_objects(fr, min_points):
    reference_cam = velo_to_cam(fr['points'][:, :3], fr['calib'])
    objects = []
    for number, obj in enumerate(fr['labels']):
        if not (np.isfinite(obj.dimensions).all() and (obj.dimensions > 0).all()
                and np.isfinite(obj.location).all() and np.isfinite(obj.rotation_y)
                and np.isfinite(obj.bbox).all()):
            continue
        indices = np.flatnonzero(points_in_box(reference_cam, obj))
        if len(indices) >= min_points:
            objects.append((number, obj, indices))
    return objects


def experiment(root, dataset, min_points, frame_limit=None):
    frames = list_frames(root)
    if frame_limit:
        frames = frames[:frame_limit]
    frame_rows, object_rows = [], []
    for fid in frames:
        fr = load_frame(root, fid)
        objects = selected_objects(fr, min_points)
        baseline_uv, _, _, _ = indexed_projection(fr['points'], fr['calib'], fr['image'].shape)
        n_finite = int(np.isfinite(fr['points'][:, :3]).all(axis=1).sum())
        for factor, value in configurations(dataset):
            calib = drifted(fr['calib'], factor, value)
            indexed, _, _, mask = indexed_projection(fr['points'], calib, fr['image'].shape)
            ratios, total_inside, total_points, displacement = [], 0, 0, []
            for number, obj, indices in objects:
                inside = int(in_image_box(indexed[indices], obj.bbox).sum())
                ratio = inside / len(indices)
                pair_ok = (np.isfinite(indexed[indices]).all(axis=1)
                           & np.isfinite(baseline_uv[indices]).all(axis=1))
                delta = np.linalg.norm(indexed[indices][pair_ok] - baseline_uv[indices][pair_ok], axis=1)
                displacement.extend(delta.tolist())
                ratios.append(ratio)
                total_inside += inside
                total_points += len(indices)
                object_rows.append(dict(dataset=dataset, frame_id=fid, factor=factor, value=value,
                                        object_id=number, class_name=obj.type,
                                        range_m=float(np.linalg.norm(obj.location)),
                                        depth_m=float(obj.location[2]), occluded=obj.occluded,
                                        truncated=obj.truncated, reference_points=len(indices),
                                        inside_box_points=inside, inside_box_pct=100 * ratio,
                                        median_shift_px=float(np.median(delta)) if len(delta) else np.nan))
            frame_rows.append(dict(dataset=dataset, frame_id=fid, factor=factor, value=value,
                                   finite_points=n_finite, fov_points=int(mask.sum()),
                                   fov_pct=100 * mask.sum() / n_finite if n_finite else np.nan,
                                   eligible_objects=len(objects), object_points=total_points,
                                   inside_box_points=total_inside,
                                   macro_box_pct=100 * np.mean(ratios) if ratios else np.nan,
                                   micro_box_pct=100 * total_inside / total_points if total_points else np.nan,
                                   median_shift_px=float(np.median(displacement)) if displacement else np.nan))
        print(f'{dataset}/{fid}: {len(objects)} eligible objects', flush=True)
    return frame_rows, object_rows


def summarize(frames, objects):
    rows = []
    for (dataset, factor, value), group in frames.groupby(['dataset', 'factor', 'value'], sort=True):
        selected = objects[(objects.dataset == dataset) & (objects.factor == factor) & (objects.value == value)]
        total_points = int(group.object_points.sum())
        rows.append(dict(dataset=dataset, factor=factor, value=value, n_frames=len(group),
                         eligible_objects=int(group.eligible_objects.sum()),
                         fov_pct=100 * group.fov_points.sum() / group.finite_points.sum(),
                         macro_box_pct=selected.inside_box_pct.mean(),
                         micro_box_pct=100 * group.inside_box_points.sum() / total_points if total_points else np.nan,
                         median_frame_shift_px=group.median_shift_px.median()))
    return pd.DataFrame(rows)


def detection(frames, out):
    """Learn one absolute score threshold from clean calibration frames only.

    Lexicographic split: first half of KITTI frames calibrates the threshold;
    remaining frames evaluate all yaw levels. Reference GT is an offline diagnostic.
    """
    yaw = frames[(frames.dataset == 'kitti') & (frames.factor == 'yaw_deg')].copy()
    ids = sorted(yaw.frame_id.unique())
    calibration_ids = ids[:len(ids) // 2]
    evaluation_ids = ids[len(ids) // 2:]
    clean_scores = yaw[(yaw.frame_id.isin(calibration_ids)) & (yaw.value == 0)].macro_box_pct.dropna()
    if clean_scores.empty or not evaluation_ids:
        raise ValueError('Need at least two KITTI frames with eligible objects for threshold evaluation')
    threshold = float(np.percentile(clean_scores, 5))
    yaw['split'] = np.where(yaw.frame_id.isin(calibration_ids), 'calibration', 'evaluation')
    yaw['threshold_pct'] = threshold
    yaw['has_score'] = yaw.macro_box_pct.notna()
    yaw['alarm'] = yaw.macro_box_pct.lt(threshold) & yaw.has_score
    yaw.to_csv(out / 'drift_detection.csv', index=False, float_format='%.8f')
    eval_rows = yaw[yaw.split == 'evaluation']
    rows = []
    for value, group in eval_rows.groupby('value'):
        usable = group[group.has_score]
        rows.append(dict(yaw_deg=value, n_scored=len(usable), n_unscored=len(group) - len(usable),
                         alarm_rate_pct=100 * usable.alarm.mean(), threshold_pct=threshold))
    pd.DataFrame(rows).to_csv(out / 'detection_summary.csv', index=False, float_format='%.8f')
    return yaw, threshold, calibration_ids, evaluation_ids


def plots(summary, objects, detected, threshold, figures):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), constrained_layout=True)
    for dataset, group in summary[summary.factor == 'yaw_deg'].groupby('dataset'):
        group = group.sort_values('value')
        for axis, metric, title in zip(axes,
                ['macro_box_pct', 'fov_pct', 'median_frame_shift_px'],
                ['Object alignment (equal object weight)', 'Points inside image', 'Projected object point displacement']):
            axis.plot(group.value, group[metric], 'o-', label=dataset)
            axis.set(title=title, xlabel='LiDAR yaw drift (degrees)', ylabel='%' if metric != 'median_frame_shift_px' else 'pixels')
            axis.grid(alpha=.3)
            axis.legend()
    fig.savefig(figures / 'yaw_sweep.png', dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), constrained_layout=True)
    for axis, factor in zip(axes, ['pitch_deg', 'roll_deg', 'ty_m']):
        group = summary[(summary.dataset == 'kitti') & (summary.factor == factor)].sort_values('value')
        axis.plot(group.value, group.macro_box_pct, 'o-')
        axis.set(title=f'KITTI: {factor}', xlabel='meters' if factor == 'ty_m' else 'degrees', ylabel='Object alignment (%)')
        axis.grid(alpha=.3)
    fig.savefig(figures / 'other_axes.png', dpi=140)
    plt.close(fig)
    selected = objects[(objects.dataset == 'kitti') & (objects.factor == 'yaw_deg')].copy()
    selected['range_group'] = pd.cut(selected.depth_m, [0, 15, 30, float('inf')], labels=['0-15 m', '15-30 m', '>30 m'])
    grouped = selected.groupby(['range_group', 'value'], observed=True).inside_box_pct.mean().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for group_name, group in grouped.groupby('range_group', observed=True):
        axes[0].plot(group.value, group.inside_box_pct, 'o-', label=str(group_name))
    axes[0].set(title='KITTI alignment by camera depth', xlabel='Yaw (degrees)', ylabel='Object alignment (%)')
    axes[0].legend()
    for class_name in ['Car', 'Pedestrian', 'Cyclist']:
        group = selected[selected.class_name == class_name].groupby('value').inside_box_pct.mean()
        if len(group):
            axes[1].plot(group.index, group.values, 'o-', label=class_name)
    axes[1].set(title='KITTI alignment by class', xlabel='Yaw (degrees)', ylabel='Object alignment (%)')
    axes[1].legend()
    for axis in axes:
        axis.grid(alpha=.3)
    fig.savefig(figures / 'range_class_sweep.png', dpi=140)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    evaluation = detected[detected.split == 'evaluation']
    for fid, group in evaluation.groupby('frame_id'):
        axis.plot(group.value, group.macro_box_pct, alpha=.55, label=fid)
    axis.axhline(threshold, color='red', linestyle='--', label=f'Clean-only threshold = {threshold:.2f}%')
    axis.set(title='KITTI held-out drift detection', xlabel='Yaw (degrees)', ylabel='Frame alignment score (%)')
    axis.grid(alpha=.3)
    axis.legend(ncol=3, fontsize=7)
    fig.savefig(figures / 'drift_threshold.png', dpi=140)
    plt.close(fig)


def display_overlay(fr, value=0):
    uv, depth, _ = project_velo_to_image(fr['points'], drifted(fr['calib'], 'yaw_deg', value), fr['image'].shape)
    vis = overlay_points(fr['image'], uv, depth, radius=1)
    for obj in fr['labels']:
        vis = draw_box2d(vis, obj.bbox, label=obj.type)
    return vis


def demos(root, figures):
    """Three explicitly measured object depths: nearest eligible car in each frame."""
    rows = []
    for fid in ['000019', '000011', '000004']:
        if fid not in list_frames(root):
            continue
        fr = load_frame(root, fid)
        eligible = [(num, obj, indices) for num, obj, indices in selected_objects(fr, 5) if obj.type == 'Car']
        if not eligible:
            eligible = selected_objects(fr, 5)
        num, obj, _ = min(eligible, key=lambda item: item[1].location[2])
        vis = display_overlay(fr)
        vis = draw_box2d(vis, obj.bbox, color=(0, 0, 255), label=f'Target depth {obj.location[2]:.1f} m')
        cv2.imwrite(str(figures / f'overlay_{fid}.png'), vis)
        rows.append(dict(frame_id=fid, object_id=num, class_name=obj.type, depth_m=float(obj.location[2])))
    return rows


def failure_figure(root, row, figures, filename, title, threshold):
    fr = load_frame(root, row.frame_id)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), constrained_layout=True)
    for axis, value in zip(axes, [0, row.value]):
        axis.imshow(cv2.cvtColor(display_overlay(fr, value), cv2.COLOR_BGR2RGB))
        axis.set_title(f'{row.frame_id}: yaw {value:+g} degrees')
        axis.axis('off')
    fig.suptitle(f'{title}\nScore {row.macro_box_pct:.2f}% vs threshold {threshold:.2f}%; FOV {row.fov_pct:.2f}%')
    fig.savefig(figures / filename, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--kitti-root', default='data/kitti_mini', help='KITTI dataset directory')
    parser.add_argument('--nuscenes-root', default='data/nuscenes_mini_subset', help='nuScenes subset directory')
    parser.add_argument('--skip-nuscenes', action='store_true', help='Run KITTI only; omits the B5 comparison')
    parser.add_argument('--out-dir', default='results', help='Directory for CSVs, plots, overlays and run metadata')
    parser.add_argument('--min-object-points', type=int, default=5, help='Minimum reference LiDAR points per eligible GT object')
    parser.add_argument('--frame-limit', type=int, default=None, help='Optional smoke-run limit; omit for submission')
    parser.add_argument('--seed', type=int, default=42, help='Seed recorded for reproducibility')
    args = parser.parse_args()
    if args.min_object_points < 1:
        parser.error('--min-object-points must be positive')
    np.random.seed(args.seed)
    out = Path(args.out_dir)
    figures = out / 'figures'
    figures.mkdir(parents=True, exist_ok=True)
    rows, objs = experiment(args.kitti_root, 'kitti', args.min_object_points, args.frame_limit)
    if not args.skip_nuscenes:
        extra_rows, extra_objs = experiment(args.nuscenes_root, 'nuscenes', args.min_object_points, args.frame_limit)
        rows.extend(extra_rows)
        objs.extend(extra_objs)
    frames, objects = pd.DataFrame(rows), pd.DataFrame(objs)
    if objects.empty:
        raise ValueError('No eligible object points; check dataset and --min-object-points')
    summary = summarize(frames, objects)
    for name, table in [('frame_metrics', frames), ('object_metrics', objects), ('sweep_summary', summary)]:
        table.to_csv(out / f'{name}.csv', index=False, float_format='%.8f')
    detected, threshold, calibration_ids, evaluation_ids = detection(frames, out)
    plots(summary, objects, detected, threshold, figures)
    demo_rows = demos(args.kitti_root, figures)
    pd.DataFrame(demo_rows).to_csv(out / 'demo_depths.csv', index=False, float_format='%.8f')
    evaluation = detected[(detected.split == 'evaluation') & (detected.value != 0) & detected.has_score]
    worst = evaluation.sort_values('macro_box_pct').iloc[0]
    failure_figure(args.kitti_root, worst, figures, 'fail_01_large_drift.png', 'Geometry failure: displaced object points', threshold)
    missed = evaluation[(~evaluation.alarm) & (evaluation.value.abs() >= .5)]
    if len(missed):
        # Show the largest missed drift, then the largest measured pixel shift.
        selected_failure = missed.assign(abs_yaw=missed.value.abs()).sort_values(
            ['abs_yaw', 'median_shift_px'], ascending=False).iloc[0].drop('abs_yaw')
    else:
        selected_failure = worst
    failure_figure(args.kitti_root, selected_failure, figures, 'fail_02_score_blind_spot.png',
                   'Metric failure: nonzero drift below alarm sensitivity' if len(missed) else 'Metric limitation example', threshold)
    clean_false_alarms = detected[(detected.split == 'evaluation') & (detected.value == 0) & detected.alarm]
    if len(clean_false_alarms):
        failure_figure(args.kitti_root, clean_false_alarms.iloc[0], figures, 'fail_03_clean_false_alarm.png',
                       'Metric failure: clean frame triggers alarm', threshold)
    metadata = dict(seed=args.seed, platform=platform.platform(), python=sys.version,
                    versions=dict(numpy=np.__version__, opencv=cv2.__version__, pandas=pd.__version__, matplotlib=matplotlib.__version__),
                    runtime='google_colab' if Path('/content').exists() and platform.system() == 'Linux' else 'local',
                    min_object_points=args.min_object_points, frame_limit=args.frame_limit,
                    datasets=dict(kitti=args.kitti_root, nuscenes=None if args.skip_nuscenes else args.nuscenes_root),
                    threshold_pct=threshold, threshold_method='5th percentile of clean first-half KITTI frame scores; alarm score < threshold',
                    calibration_ids=calibration_ids, evaluation_ids=evaluation_ids,
                    geometry_failure=worst.to_dict(), metric_failure=selected_failure.to_dict(),
                    actual_missed_detection=bool(len(missed)), clean_false_alarm_frames=clean_false_alarms.frame_id.tolist(),
                    demo_depths=demo_rows,
                    sources=['KITTI Vision Benchmark Suite', 'nuScenes (Motional)'],
                    csv_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.csv'))})
    (out / 'run_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n' + summary.to_string(index=False), flush=True)
    print(f'\nThreshold: {threshold:.4f}%; missed detection found: {bool(len(missed))}', flush=True)


if __name__ == '__main__':
    main()
