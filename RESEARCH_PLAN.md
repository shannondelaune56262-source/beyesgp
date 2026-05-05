# beyesgp 研究计划

## 项目目标

基于贝叶斯优化（BO）的电力系统暂态稳定最坏场景搜索（WCS），以 Kundur 2 区域系统为测试平台，对比 BO 与随机搜索、拉丁超立方、遗传算法在 2D/4D/6D 搜索空间中的效率和效果。

## 当前系统状态

### 已修复的问题（2026-05-04）

| 问题 | 根因 | 修复 | 验证 |
|------|------|------|------|
| 系统卡死 | ANDES codegen Pool(32) + 缺少 `__init__.py` | `andes.prepare(nomp=True)` 单线程预热 | `andes.load()` 1.46s |
| 仿真全部失败 | `ss.add("Fault")` 在 `ss.setup()` 后调用 | 调整为先 add 后 setup | `success=True`, 508×4 转子角度 |
| 线程过载 | PyTorch 32 + OpenBLAS 48 = 80 线程 | `OMP_NUM_THREADS=4` + `torch.set_num_threads(4)` | 112→14 |
| BO tensor bug | `acq_values[0]` 对 0-dim tensor 报 IndexError | `.item()` 兼容处理 | BO 2+1 evals 1.59s |

### test_minimal.py 全流程验证结果

```
All steps passed!
  Imports:        2.2s
  Config:         0.174s
  ANDES load+PF:  0.26s
  Single sim:     24.81s (首次含预热)
  Severity calc:  0.0020s
  Random (3 ev):  1.66s (每 eval ~0.55s)
  BO (2+1 ev):    1.59s
  Mem leak delta: +3 MB over 5 evals
  Final memory:   427 MB
```

### 已知遗留问题

1. **Bus idx=11 越界**：部分场景映射到 Bus 11 时报错 `<Bus>: device not exist with idx=11.`，导致 severity=1.0（仿真失败返回最大值）。原因：Kundur 系统共 10 个 Bus（idx 1-10），但 `kundur.yaml` 配置了 fault_bus 包含 11。需检查 scenario_builder 的映射逻辑。
2. **Severity 全为 1.0 或 0.42**：test_minimal 的 BO 初始化中 2 个评估点都返回 severity=1.0，表明场景映射可能需要调整以确保覆盖有效的故障位置。

---

## 研究计划（4 个实验）

### 阶段 0：修复遗留问题（预计 1 小时）

**任务 0.1：修复 Bus idx 越界问题**

检查 `src/simulator/scenario_builder.py` 中 `fault_bus` 的映射逻辑和 `configs/test_systems/kundur.yaml` 中的 `fault_buses` 配置。确认 Kundur 系统实际 Bus 数量（10 个，idx 1-10），移除不存在的 idx=11。

**任务 0.2：验证场景映射覆盖度**

用均匀采样测试 20 个随机点，统计 `success=True` 的比例。目标：>80% 的场景应能成功仿真。如果成功率过低，需调整 `clear_time` 范围或 `load_scaling` 范围。

**任务 0.3：补充入口脚本环境变量**

修改 `scripts/run_experiment.py` 和 `scripts/run_all_experiments.py`，在文件最顶部添加：
```python
import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
```

**任务 0.4：清理旧的 ANDES 输出文件**

```powershell
del kundur_full_out.*
```

### 阶段 1：Experiment 1 — 2D 验证（预计 30 分钟）

**配置**：
- 搜索空间：2D（fault_bus + clear_time）
- 方法：bo, random, lhs, ga, grid
- 评估预算：50（BO: 10 init + 40 iter）
- 种子：3（42, 123, 456）
- 总仿真次数：5 方法 × 3 种子 × 50 = 750（grid 可能不同）

**执行命令**：
```powershell
python scripts/run_experiment.py --experiment exp1_kundur_2d
```

**预期输出**：
- `data/processed/exp1_kundur_2d/` 下各方法各种子的 `result.json`
- `data/processed/exp1_kundur_2d/summary.csv` 统计表
- 收敛曲线、2D 严重度热力图 + BO 轨迹

**验证检查点**：
- [ ] 全部 750 仿真完成，无卡死
- [ ] BO 的 best_severity 显著优于 random/lhs
- [ ] 热力图显示 BO 聚焦于高严重度区域
- [ ] 收敛曲线显示 BO 在 20 次评估内收敛

### 阶段 2：Experiment 2 — 4D 核心对比（预计 1.5 小时）

**配置**：
- 搜索空间：4D（fault_bus + clear_time + load_area1 + line_trip）
- 方法：bo, random, lhs, ga
- 评估预算：75（BO: 15 init + 60 iter）
- 种子：3
- 总仿真次数：4 × 3 × 75 = 900

**执行命令**：
```powershell
python scripts/run_experiment.py --experiment exp2_kundur_4d
```

**预期输出**：
- 4D 结果数据、收敛曲线、摘要统计表
- BO vs baseline 在 4D 空间中的效率对比

**验证检查点**：
- [ ] 全部 900 仿真完成
- [ ] BO 优势在 4D 中更明显（维度越高 BO 越有优势）
- [ ] GA 性能接近 random（因为 budget 有限，GA 种群进化代数不足）

### 阶段 3：Experiment 3 — 6D 高维挑战（预计 3 小时）

**配置**：
- 搜索空间：6D（4D + load_area2 + gen1_output）
- 方法：bo, random, lhs, ga
- 评估预算：125（BO: 25 init + 100 iter）
- 种子：3
- 总仿真次数：4 × 3 × 125 = 1500

**执行命令**：
```powershell
python scripts/run_experiment.py --experiment exp3_kundur_6d
```

**验证检查点**：
- [ ] 全部 1500 仿真完成
- [ ] BO 在高维中仍能找到比 baselines 更严重的场景
- [ ] 收敛曲线对比显示 BO 的采样效率优势

### 阶段 4：Experiment 4 — 采集函数消融（预计 1.5 小时）

**配置**：
- 搜索空间：4D（同 Exp2）
- 方法：bo_ei, bo_ucb, bo_pi
- 评估预算：75（15 init + 60 iter）
- 种子：3
- 总仿真次数：3 × 3 × 75 = 675

**执行命令**：
```powershell
python scripts/run_experiment.py --experiment exp4_ablation
```

**验证检查点**：
- [ ] 全部 675 仿真完成
- [ ] EI 与 LogEI 的对比（当前代码使用 EI，BoTorch 建议用 LogEI）
- [ ] UCB 在探索 vs 利用上的表现差异

### 阶段 5：结果分析（预计 2 小时）

**任务 5.1：生成论文图表**

使用 `src/visualization/paper_figures.py` 批量生成：
- 收敛曲线（mean ± std，多方法对比）
- 2D 严重度热力图 + BO 采样轨迹
- 各实验摘要统计表

**任务 5.2：统计分析**

- Wilcoxon 检验：BO vs 各 baseline 的 best_severity 差异显著性
- Friedman 检验：多方法整体差异
- 计算各方法的加速比：达到相同 severity 所需评估次数之比

**任务 5.3：撰写实验报告**

整理为论文/报告格式，包含：
- 研究背景与方法
- 实验设计与配置
- 结果分析与讨论
- 结论与展望

---

## 总仿真预算估算

| 实验 | 方法数 | 种子数 | 评估/方法 | 总仿真 | 预计时间 |
|------|--------|--------|-----------|--------|----------|
| Exp1 (2D) | 5 | 3 | ~50 | ~750 | 30 min |
| Exp2 (4D) | 4 | 3 | 75 | 900 | 1.5 h |
| Exp3 (6D) | 4 | 3 | 125 | 1500 | 3 h |
| Exp4 (ablation) | 3 | 3 | 75 | 675 | 1.5 h |
| **总计** | | | | **~3825** | **~6.5 h** |

基于 test_minimal 的测量：每 eval ~0.55s（含 ANDES load + PF + TDS），但 Exp3 的仿真可能更慢（6D 包含 load scaling 和 gen scaling，可能导致收敛困难的场景）。

**内存估算**：427 MB 基线 + 3 MB/eval 泄漏 → 运行 1500 eval 后约 427 + 1500×0.6 = 927 MB，在 32GB 系统上无问题。

---

## 风险与应对

| 风险 | 概率 | 应对措施 |
|------|------|----------|
| 某些极端场景导致 TDS 非常慢（>10s/eval） | 中 | `criteria=1` 启用早期终止；`timeout=60` 保底 |
| 内存持续增长导致 OOM | 低 | 泄漏仅 +3MB/eval；可定期重启进程 |
| BO 初始化点全在无效区域 | 中 | 修复 Bus idx 越界后应解决；否则扩大 init 样本数 |
| GA 在高维中表现极差 | 高（预期） | 作为基线对比，正是实验要展示的 |

---

## 一键运行全量实验（修复遗留问题后）

```powershell
# 确保在项目目录
cd C:\pscad\beyesgp

# 运行全部 4 个实验（串行，每个实验内部各方法×种子也串行）
python scripts/run_all_experiments.py
```

预计总运行时间 6-7 小时，之后进入结果分析阶段。
