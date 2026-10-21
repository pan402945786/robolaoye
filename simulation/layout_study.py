"""Illustrative mass and coplanar gravity-projection study; Python stdlib only.

This is not a stair-contact solver or a manufacturing/safety release tool.
All dimensions are mm, masses kg and angles degrees. Run from any directory.
"""

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-9


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: expected a finite number")
    return float(value)


def vector(value, length, label):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label}: expected {length} coordinates")
    return [number(v, label) for v in value]


def weighted_cog(items):
    """items: (mass, xyz) pairs. Zero mass is allowed, negative mass is not."""
    checked = []
    for mass, xyz in items:
        mass = number(mass, "mass")
        if mass < 0:
            raise ValueError("mass must be nonnegative")
        checked.append((mass, vector(xyz, 3, "cog")))
    total = sum(m for m, _ in checked)
    if total <= EPS:
        raise ValueError("total mass must be positive")
    return total, [sum(m * p[i] for m, p in checked) / total for i in range(3)]


def rotate_seat(point, pivot, angle_deg):
    """Positive seat pitch raises its forward (+x) end, about the chassis y axis."""
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = [point[i] - pivot[i] for i in range(3)]
    return [pivot[0] + c * x - s * z, pivot[1] + y, pivot[2] + s * x + c * z]


def gravity_projection(cog, pitch_deg, roll_deg):
    """Intersect a vertical gravity ray with chassis support plane z=0.

    Chassis->world rotation: Ry(-pitch) Rx(roll), right handed matrices.
    +pitch raises the front, +roll raises the left side. Returns chassis xy.
    """
    pitch, roll = map(math.radians, (pitch_deg, roll_deg))
    # R.T @ world_down, expressed in chassis coordinates.
    down = [-math.sin(pitch), -math.cos(pitch) * math.sin(roll),
            -math.cos(pitch) * math.cos(roll)]
    if down[2] >= -EPS or cog[2] < 0:
        raise ValueError("gravity projection requires an upward support plane and cog z >= 0")
    t = -cog[2] / down[2]
    return [cog[i] + t * down[i] for i in (0, 1)]


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    points = sorted(set(tuple(vector(p, 2, "support point")) for p in points))
    if len(points) < 3:
        raise ValueError("support needs at least three non-collinear points")
    lower, upper = [], []
    for half, sequence in ((lower, points), (upper, reversed(points))):
        for p in sequence:
            while len(half) >= 2 and cross(half[-2], half[-1], p) <= EPS:
                half.pop()
            half.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        raise ValueError("support polygon is degenerate")
    return hull


def signed_margin(point, polygon):
    """Minimum signed perpendicular distance to CCW hull edge lines (mm)."""
    return min(cross(a, b, point) / math.dist(a, b)
               for a, b in zip(polygon, polygon[1:] + polygon[:1]))


def validate(layout, inputs):
    if layout.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    if layout.get("units") != {"mass": "kg", "length": "mm", "angle": "deg"}:
        raise ValueError("units must be kg/mm/deg")
    vector(layout["seat_pivot_mm"], 3, "seat pivot")
    vector(layout["occupant_cog_mm"], 3, "occupant cog")
    ids = set()
    if not layout["components"]:
        raise ValueError("components cannot be empty")
    for c in layout["components"]:
        if c["id"] in ids or c["id"] == "occupant":
            raise ValueError("component ids must be unique; occupant is reserved")
        ids.add(c["id"])
        mass = number(c["mass_kg"], "component mass")
        low, high = vector(c["mass_range_kg"], 2, "mass range")
        if not 0 <= low <= mass <= high:
            raise ValueError("mass must be within its nonnegative range")
        if c["group"] not in ("seat", "chassis"):
            raise ValueError("component group must be seat or chassis")
        vector(c["cog_mm"], 3, "component cog")
        if any(v <= 0 for v in vector(c["size_mm"], 3, "size")):
            raise ValueError("component sizes must be positive")
    for points in layout["support_sets_mm"].values():
        convex_hull(points)
    for key, value in occupant_masses(inputs).items():
        if number(value, key) < 0 or (key != "empty" and value <= 0):
            raise ValueError("occupant mass must be positive (except empty)")
    ids = set()
    if not layout["scenarios"]:
        raise ValueError("scenarios cannot be empty")
    for s in layout["scenarios"]:
        if s["id"] in ids:
            raise ValueError("scenario ids must be unique")
        ids.add(s["id"])
        if s["occupant"] not in ("empty", "actual", "design"):
            raise ValueError("unknown occupant source")
        if s["support"] not in layout["support_sets_mm"]:
            raise ValueError("unknown support set")
        for key in ("pitch_deg", "roll_deg", "seat_pitch_deg"):
            if abs(number(s[key], key)) >= 90:
                raise ValueError("study angles must be between -90 and +90 degrees")
        vector(s["occupant_offset_mm"], 3, "occupant offset")


def occupant_masses(inputs):
    return {"empty": 0, "actual": inputs["user_confirmed"]["mass_kg"],
            "design": inputs["provisional_analysis"]["design_occupant_mass_kg"]}


def evaluate(layout, inputs):
    validate(layout, inputs)
    results = []
    for s in layout["scenarios"]:
        items = []
        for c in layout["components"]:
            position = c["cog_mm"]
            if c["group"] == "seat":
                position = rotate_seat(position, layout["seat_pivot_mm"], s["seat_pitch_deg"])
            items.append((c["mass_kg"], position))
        occupant_mass = occupant_masses(inputs)[s["occupant"]]
        # Body offset is defined in the seat's neutral frame and rotates with it.
        occupant = [a + b for a, b in zip(layout["occupant_cog_mm"], s["occupant_offset_mm"])]
        occupant = rotate_seat(occupant, layout["seat_pivot_mm"], s["seat_pitch_deg"])
        items.append((occupant_mass, occupant))
        total, cog = weighted_cog(items)
        projection = gravity_projection(cog, s["pitch_deg"], s["roll_deg"])
        hull = convex_hull(layout["support_sets_mm"][s["support"]])
        margin = signed_margin(projection, hull)
        results.append({"id": s["id"], "name": s["name"], "occupant_kg": occupant_mass,
                        "total_kg": total, "cog_mm": cog, "projection_mm": projection,
                        "signed_margin_mm": margin,
                        "projection_region": "inside" if margin > EPS else "outside" if margin < -EPS else "boundary",
                        "support_hull_mm": hull,
                        "pitch_deg": s["pitch_deg"], "roll_deg": s["roll_deg"],
                        "seat_pitch_deg": s["seat_pitch_deg"]})
    return results


def layout_svg(layout, inputs):
    """Neutral chassis side/top block schematic. Boxes may overlap; not CAD."""
    # The block layout is always drawn in its neutral pose, independently of
    # the named scenarios that a caller may add, remove or tilt.
    neutral = dict(layout)
    neutral["scenarios"] = [{"id": "neutral_layout", "name": "70 kg 中立布局" if inputs["user_confirmed"]["mass_kg"] == 70 else "实际乘员中立布局",
                             "occupant": "actual", "pitch_deg": 0, "roll_deg": 0,
                             "seat_pitch_deg": 0, "occupant_offset_mm": [0, 0, 0],
                             "support": "full" if "full" in layout["support_sets_mm"] else next(iter(layout["support_sets_mm"]))}]
    actual = evaluate(neutral, inputs)[0]
    boxes = layout["components"]
    xvals = [v for c in boxes for v in (c["cog_mm"][0] - c["size_mm"][0] / 2,
                                       c["cog_mm"][0] + c["size_mm"][0] / 2)]
    yvals = [v for c in boxes for v in (c["cog_mm"][1] - c["size_mm"][1] / 2,
                                       c["cog_mm"][1] + c["size_mm"][1] / 2)]
    zvals = [v for c in boxes for v in (c["cog_mm"][2] - c["size_mm"][2] / 2,
                                       c["cog_mm"][2] + c["size_mm"][2] / 2)]
    xmin, xmax, ymin, ymax, zmin, zmax = min(xvals), max(xvals), min(yvals), max(yvals), min(0, min(zvals)), max(zvals)
    scale = min(550 / (xmax - xmin), 360 / (ymax - ymin), 400 / (zmax - zmin))
    def xx(x):
        return 100 + (x - xmin) * scale
    def zz(z):
        return 600 - (z - zmin) * scale
    def yy(y):
        return 720 + (ymax - y) * scale
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1160" viewBox="0 0 1200 1160">',
           '<rect width="1200" height="1160" fill="#f5f7fa"/>',
           '<g font-family="Microsoft YaHei,Arial,sans-serif" fill="#18283a">',
           '<text x="40" y="45" font-size="25">RoboLaoye — 参数化布局占位图</text>',
           '<text x="40" y="78" font-size="17">全部部件尺寸与质量均为示例；方框为占位包络，非加工图、非防干涉结果。</text>',
           f'<text x="40" y="108" font-size="16">中立座椅坐标；示例方框总包络 {xmax-xmin:g} × {ymax-ymin:g} × {zmax-zmin:g} mm，不含完整乘员包络。</text>',
           '<text x="40" y="145" font-size="18">侧视：+x 向前 →，+z 向上 ↑</text>',
           '<text x="40" y="685" font-size="18">俯视：+x 向前 →，+y 向左侧 ↑</text>']
    for index, c in enumerate(boxes):
        x, y, z = c["cog_mm"]
        dx, dy, dz = c["size_mm"]
        color = f'hsl({(index * 37) % 360},45%,65%)'
        for top, height in ((zz(z + dz / 2), dz * scale), (yy(y + dy / 2), dy * scale)):
            out.append(f'<rect x="{xx(x-dx/2):.2f}" y="{top:.2f}" width="{dx*scale:.2f}" height="{height:.2f}" fill="{color}" fill-opacity=".18" stroke="{color}" stroke-width="2"/>')
        out.append(f'<text x="{xx(x):.2f}" y="{zz(z):.2f}" text-anchor="middle" font-size="13">{index+1}</text>')
    hull = actual["support_hull_mm"]
    points = " ".join(f"{xx(x):.2f},{yy(y):.2f}" for x, y in hull)
    out.append(f'<polygon points="{points}" fill="none" stroke="#174b68" stroke-width="3" stroke-dasharray="8 5"/>')
    x, y, z = actual["cog_mm"]
    out += [f'<circle cx="{xx(x):.2f}" cy="{zz(z):.2f}" r="7" fill="#d24735"/>',
            f'<circle cx="{xx(x):.2f}" cy="{yy(y):.2f}" r="7" fill="#d24735"/>',
            '<text x="700" y="180" font-size="16">图号 / 部件 / 示例质量</text>']
    for i, c in enumerate(boxes):
        out.append(f'<text x="700" y="{210+i*25}" font-size="15">{i+1}. {html.escape(c["name"])} / {c["mass_kg"]:g} kg</text>')
    out.append(f'<text x="40" y="1105" font-size="16">红点：{html.escape(actual["name"])}整机重心。虚线：该工况手工假设的支撑凸包。</text>')
    out.append('<text x="40" y="1135" font-size="16">400 mm 单级登沿的接触、机构展开和载荷转移不在本图中表达。</text></g></svg>')
    return "\n".join(out)


def support_svg(results):
    points = [p for r in results for p in r["support_hull_mm"] + [r["projection_mm"]]]
    span = max(600, max(abs(v) for p in points for v in p) * 1.15)
    scale = 135 / span
    height = 120 + math.ceil(len(results) / 3) * 320
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
           f'<rect width="1200" height="{height}" fill="#f5f7fa"/>',
           '<g font-family="Microsoft YaHei,Arial,sans-serif" fill="#18283a">',
           '<text x="30" y="38" font-size="24">共面支撑重力投影示例</text>',
           '<text x="30" y="70" font-size="16">+x 向右，+y 向上；蓝面为假设支撑区，点为重力线落点。正裕量仅表示投影在内部。</text>',
           '<text x="30" y="97" font-size="16">全部工况为演示参数；不能表示楼梯、400 mm 单级或单故障验证通过。</text>']
    for i, r in enumerate(results):
        ox, oy = 200 + i % 3 * 400, 275 + i // 3 * 320
        def point(p):
            return f"{ox+p[0]*scale:.2f},{oy-p[1]*scale:.2f}"
        polygon = " ".join(point(p) for p in r["support_hull_mm"])
        px, py = r["projection_mm"]
        color = "#b83f32" if r["signed_margin_mm"] <= 0 else "#174b68"
        out += [f'<text x="{ox-180}" y="{oy-140}" font-size="16">{html.escape(r["name"])}</text>',
                f'<polygon points="{polygon}" fill="#d4e7ee" stroke="#48819b" stroke-width="2"/>',
                f'<circle cx="{ox+px*scale:.2f}" cy="{oy-py*scale:.2f}" r="6" fill="{color}"/>',
                f'<text x="{ox-180}" y="{oy+137}" font-size="15">{r["total_kg"]:g} kg / 边线裕量 {r["signed_margin_mm"]:.1f} mm</text>']
    return "\n".join(out + ['</g></svg>'])


def report(layout, results, hashes):
    mass = sum(c["mass_kg"] for c in layout["components"])
    low = sum(c["mass_range_kg"][0] for c in layout["components"])
    high = sum(c["mass_range_kg"][1] for c in layout["components"])
    lines = ["# 质量预算与共面支撑示例计算", "", "由 simulation/layout_study.py 生成。全部布局尺寸、部件质量、人体重心、角度和接触点均为假设，不是实测或加工输入。", "",
             f"示例设备质量：**{mass:g} kg**；逐项假设上下限直接求和为 {low:g}–{high:g} kg，非统计置信区间。重心结果只用名义质量，未对质量上下限求最坏组合。", "",
             "## 质量表", "", "| 部件 | 名义 kg | 假设范围 kg | 中立姿态重心 x/y/z mm |", "|---|---:|---:|---|"]
    for c in layout["components"]:
        lines.append(f'| {c["name"]} | {c["mass_kg"]:g} | {c["mass_range_kg"][0]:g}–{c["mass_range_kg"][1]:g} | ' + "/".join(f"{v:g}" for v in c["cog_mm"]) + " |")
    lines += ["", "## 示例工况", "", "| 工况 | 总质量 kg | 重心 x/y/z mm | 重力落点 x/y mm | 最小有符号边线裕量 mm | 投影区域 |", "|---|---:|---|---|---:|---|"]
    regions = {"inside": "内部", "outside": "外部", "boundary": "边界"}
    for r in results:
        cog = "/".join(f"{v:.1f}" for v in r["cog_mm"])
        projection = "/".join(f"{v:.1f}" for v in r["projection_mm"])
        lines.append(f'| {r["name"]} | {r["total_kg"]:g} | {cog} | {projection} | {r["signed_margin_mm"]:.1f} | {regions[r["projection_region"]]} |')
    lines += ["", "正值仅表示重力落点位于给定支撑凸包内部；零值处于边界，负值在外部。该值是到各边延长线的最小有符号垂距，外部点处不等于到多边形的最短距离。没有设定合格裕量，也没有试验通过结论。", "",
              "后段/单侧接触是手工构造的反例，并非从真实机构推导的故障工况。调平卡住仅改变座椅角度，未计算故障承载路径。", "",
              "## 模型边界", "", "只处理刚体、重力和 z=0 共面支撑点；忽略滑移、摩擦锥、驱动力、加减速、碰撞、变形及接触反力上限。座椅组绕固定铰点俯仰，乘员为一个集中质量。支撑面随底盘俯仰/侧倾；多层台阶接触不能投到此平面后直接套用。", "",
              "用户已确认的 400 mm 单级高差不在这个求解器的适用范围内，尚未生成登沿可行性结论。门洞、电梯、平台净空与人体完整包络也未验证。", "",
              "## 图示", "", "![中立姿态布局](layout.svg)", "", "![支撑区示例](support-cases.svg)", "",
              "## 输入追溯", "", f'- 布局输入文件 SHA-256: `{hashes["layout_sha256"]}`', f'- 乘员及需求输入文件 SHA-256: `{hashes["inputs_sha256"]}`', "",
              "改变输入后重新运行生成器；正式模型需测量重心、导入机构运动学和真实接触，再单独完成动力/防滑/强度与故障保持分析。", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, default=ROOT / "config/layout-study.json")
    parser.add_argument("--inputs", type=Path, default=ROOT / "config/design-inputs.json")
    parser.add_argument("--output", type=Path, default=ROOT / "simulation/results/layout-study")
    args = parser.parse_args()
    try:
        layout_bytes, input_bytes = args.layout.read_bytes(), args.inputs.read_bytes()
        layout, inputs = json.loads(layout_bytes), json.loads(input_bytes)
        results = evaluate(layout, inputs)
        hashes = {"layout_sha256": hashlib.sha256(layout_bytes).hexdigest(),
                  "inputs_sha256": hashlib.sha256(input_bytes).hexdigest()}
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    output = {"status": "illustrative_not_validated", "units": layout["units"],
              "input_hashes": hashes, "scenarios": results}
    (args.output / "results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output / "scenarios.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "name", "occupant_kg", "total_kg", "cog_x_mm", "cog_y_mm", "cog_z_mm", "projection_x_mm", "projection_y_mm", "signed_margin_mm", "projection_region", "pitch_deg", "roll_deg", "seat_pitch_deg"])
        for r in results:
            writer.writerow([r["id"], r["name"], r["occupant_kg"], r["total_kg"], *r["cog_mm"], *r["projection_mm"], r["signed_margin_mm"], r["projection_region"], r["pitch_deg"], r["roll_deg"], r["seat_pitch_deg"]])
    (args.output / "report.md").write_text(report(layout, results, hashes), encoding="utf-8")
    (args.output / "layout.svg").write_text(layout_svg(layout, inputs), encoding="utf-8")
    (args.output / "support-cases.svg").write_text(support_svg(results), encoding="utf-8")
    print(f"Generated {len(results)} illustrative scenarios in {args.output}")


if __name__ == "__main__":
    main()
