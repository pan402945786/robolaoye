# 仿真目录

用于保存：

- 静态受力计算；
- 车架和铰点有限元模型；
- 重心和稳定性计算；
- 履带牵引力估算；
- 调平机构运动学；
- 电机和减速机选型计算。

建议每次仿真记录模型版本、边界条件、载荷、材料、网格和结论。

## 已有可运行模型

`layout_study.py` 使用 Python 3 标准库，读取 `config/design-inputs.json` 中的乘员质量和 `config/layout-study.json` 的假设质量、尺寸、座椅姿态及共面接触点。

```powershell
python simulation/layout_study.py
```

默认输出到 `simulation/results/layout-study/`：`report.md`、`results.json`、`scenarios.csv`、`layout.svg`、`support-cases.svg`。可使用 `--layout`、`--inputs` 和 `--output` 指定路径。仓库内示例快照保存在 [examples/v0.3](examples/v0.3/report.md)。

该模型只求质量、重心与共面支撑的重力投影边线裕量，不能计算 400 mm 单级的高低两层接触、滑移、动力或结构强度。详细坐标约定和假设见 [工程基线](../docs/10-engineering-baseline.md)。
