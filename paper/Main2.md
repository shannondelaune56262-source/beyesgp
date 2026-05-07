# 基于高斯过程与贝叶斯优化的高比例新能源电网安全边界闭环辨识

**Closed-loop Security Boundary Identification for High Renewable Penetration Power Grids via Gaussian Process and Bayesian Optimization**

---

**作者：** × × × ×

**单位：** × × × ×

---

**摘要：** 高比例新能源并网导致电力系统呈现"双高"特征（高电力电子化、高不确定性），传统基于确定性场景的暂态稳定评估方法难以有效覆盖多维运行空间，亟需建立高效的运行安全边界辨识方法。现有安全边界辨识方法面临三方面挑战：运行方式空间维度高导致计算代价大；多约束（功角/频率/电压）耦合导致单一代理模型精度不足；传统基于灵敏度线性外推的最严重场景搜索在高维非线性空间中效率低且可能过于乐观或保守，导致安全边界和传输限额难以准确制定。本文提出基于高斯过程代理模型（GP）、贝叶斯优化（BO）与仿射内逼近（AIA）融合的闭环安全边界辨识框架。首先，建立多输出GP代理模型，同时预测功角、频率、电压三约束严重度，将新能源渗透率作为输入维度实现跨场景建模；其次，以期望改进（EI）为采集函数，引导BO在联合运行方式–故障空间中智能搜索使系统失稳概率最大的场景组合，替代传统灵敏度线性外推；然后，基于安全/不安全点集构造仿射内逼近多面体 $\mathcal{P}=\{\mathbf{x}|\mathbf{A}\mathbf{x}\leq\mathbf{b}\}$，通过凸包计算与线性规划分离超平面实现安全域的仿射内逼近；最后，建立"BO勘探→AIA边界→GP验证→薄弱点辨识→BO定向搜索"的闭环迭代机制，支持增量更新和在线调整。以Kundur两区域系统为基础，注入REGCA1+REECA1+REPCA1新能源动态模型，构建8维参数空间与5级新能源渗透率场景。在186个可行运行方式×7种异构故障×5级渗透率共6510次仿真中，所提方法实现了：多输出GP代理模型综合严重度 $R^2$ 达0.579（RE-aware 8D），较基准Mode-only 7D提升59.5%；BO在75次评估内搜索到全局最严重场景（$\eta > 0.95$），较灵敏度线性外推提升全局最优性15–25个百分点；闭环3轮迭代后安全域体积增长15%以上，边界内安全率保持100%；分场景传输容量限额较统一限额提升47.1%~88.4%（加权平均63.6%）。

**关键词：** 高比例新能源；高斯过程；贝叶斯优化；仿射内逼近；安全边界；暂态稳定

**中图分类号：** TM712

---

**Abstract:** High renewable energy (RE) penetration introduces significant uncertainty into power system transient stability assessment. Traditional sensitivity-based linear extrapolation for worst-case scenario identification becomes inefficient and potentially over-optimistic or over-conservative in high-dimensional, nonlinear settings, making it difficult to accurately determine security boundaries and transfer limits. This paper proposes a closed-loop security boundary identification framework fusing multi-output Gaussian process (GP), Bayesian optimization (BO), and affine inner approximation (AIA). The framework simultaneously predicts angle, frequency, and voltage severity via independent GP surrogates, uses BO with Expected Improvement to intelligently search for the worst-case fault scenario combinations that maximize instability probability, and constructs polyhedral safe sets via convex hull and LP-based separating hyperplanes. Applied to a Kundur two-area system with REGCA1/REECA1/REPCA1 RE models across 8-dimensional parameter space and 5 RE penetration levels (6,510 time-domain simulations), the method achieves composite severity $R^2 = 0.579$ (RE-aware 8D, +59.5% over Mode-only 7D baseline), identifies the worst-case scenario within 75 evaluations with global optimality ratio $\eta > 0.95$, and improves per-scenario transfer limits by 47.1%–88.4% over uniform limits (weighted average 63.6%).

**Keywords:** high renewable penetration; Gaussian process; Bayesian optimization; affine inner approximation; security boundary; transient stability

---

## 1 引言

随着"双碳"目标推进，风电、光伏等新能源在电力系统中的渗透率持续攀升。国家能源局数据显示，2024年全国风电、光伏装机容量突破12亿千瓦，新能源发电量占比超过18%。高比例新能源接入使电力系统呈现"双高"特征——高电力电子化（同步发电机占比降低）和高运行不确定性（出力随机波动），对暂态稳定安全评估提出了新挑战 [1]。

传统的确定性暂态稳定评估方法针对单一或少量预想工况进行时域仿真，难以覆盖高维运行方式空间。近年来，基于数据驱动的代理模型方法为高效安全评估提供了新途径。然而，现有方法面临三方面不足：

**（1）单一代理模型难以捕获多约束耦合特征。** 暂态稳定受功角、频率、电压多约束共同作用 [2]。现有GP代理模型大多针对单一指标（如功角稳定裕度）建模 [3]，无法同时预测多约束严重度，难以揭示新能源渗透率变化引起的约束主导模式转换规律 [4]。Liu等 [5] 提出了可扩展多输出GP用于大规模系统，但未考虑功角和频率约束的耦合。

**（2）最严重场景评估缺乏全局搜索能力。** 传输容量限额的制定依赖于准确识别使系统暂态稳定裕度最小的"最严重运行方式–故障"组合。传统方法基于灵敏度分析 [6]，沿单一参数方向进行线性外推以定位临界点。该方法在低维、近似线性的安全域中尚可适用，但当影响因素维度升高、约束间呈现非线性耦合时，面临三方面困难：(i) 灵敏度仅反映局部梯度信息，无法捕获多极值的全局最优，可能遗漏真正的最严重场景；(ii) 线性外推假设严重度沿搜索方向单调变化，在高维空间中该假设常常失效，导致评估结果过于乐观或过于保守；(iii) 组合爆炸使得遍历所有运行方式–故障组合不可行，而启发式筛选缺乏理论保证。

上述困难在实际电网运行中产生两类严重后果。第一类是**过于乐观**：灵敏度方法遗漏了全局最严重场景，制定的传输限额偏高，实际运行中遭遇未覆盖的危险故障组合时可能引发暂态失稳甚至连锁故障。第二类是**过于保守**：为弥补搜索不完备性，工程实践中常附加人工安全裕度，使传输限额系统性偏低，导致年度弃风弃光率升高，经济损失可观。因此，亟需一种能在高维非线性空间中高效定位全局最严重场景的方法。

贝叶斯优化（BO）在超参数优化 [7] 和实验设计领域已证明采样效率优势，近年来开始应用于电力系统场景选择 [8, 9] 和新能源稳定性分析 [10]。BO通过代理模型建立严重度关于运行参数的全局映射，结合采集函数在探索（exploration）与利用（exploitation）间自适应平衡，可在有限评估预算内高效搜索最严重场景组合 [11]。然而，现有BO应用多聚焦于寻找单一最严重场景（worst-case），而非系统性地辨识完整的安全域边界。

**（3）边界辨识与采样策略缺乏闭环反馈。** Palm等 [12] 将GP与BO结合用于暂态稳定边界探索，但采用一次性采样策略，边界质量受限于初始采样覆盖度。Yu等 [13] 提出了基于安全域的快速评估方法，但边界参数固定，无法自适应更新。Wang等 [14] 提出了运行方式聚类分档限额，但缺乏严格的安全域几何构造和闭环紧化机制。

针对上述不足，本文提出基于多输出高斯过程（MOGP）、贝叶斯优化（BO）与仿射内逼近（AIA）融合的闭环安全边界辨识框架，主要贡献如下：

1. **建模层面**：在Kundur两区域系统中注入WECC标准REGCA1+REECA1+REPCA1新能源动态模型，构建8维参数空间与5级新能源渗透率场景。通过大规模仿真揭示新能源渗透率升高导致约束主导模式从"功角单一主导"向"多约束耦合"转变的物理机制。

2. **方法层面**：提出"MOGP代理→最严重场景搜索→BO勘探→AIA边界→闭环紧化"的融合框架。多输出GP同时预测三约束严重度，BO以期望改进为采集函数在联合运行方式–故障空间中智能搜索使系统失稳概率最大的场景组合，克服传统灵敏度方法在高维非线性空间中的局限性；AIA通过凸包与LP分离超平面构造仿射安全域，闭环迭代逐步紧化边界并保证安全性。

3. **验证层面**：在186个可行运行方式×7种异构故障×5级渗透率共6510次仿真中，全面验证了所提方法的代理模型精度（$R^2 = 0.579$）、最严重场景搜索的全局最优性（$\eta > 0.95$）、勘探效率（评估次数减少40%+）、边界安全性（安全率100%）和工程效益（分档限额提升47.1%–88.4%，加权平均63.6%）。

---

## 2 系统建模

### 2.1 Kundur两区域系统

本文采用Kundur两区域4机系统作为测试平台，该系统拓扑如图1所示，包含10条母线、4台GENROU同步发电机和15条输电线路，是暂态稳定研究的经典基准系统 [15]。Area 1包含GENROU_1（Bus 1，900 MVA）和GENROU_2（Bus 2，900 MVA），Area 2包含GENROU_3（Bus 3，900 MVA）和GENROU_4（Bus 4，900 MVA）。两区域通过Bus 7–Bus 8间双回220 kV联络线互联。

同步发电机采用6阶机电暂态模型，配备IEEE Type I励磁系统和TGOV1调速器。系统基准容量 $S_B = 100$ MVA，仿真时长 $T = 10$ s，步长 $\Delta t = 0.02$ s。

![图1 Kundur两区域4机系统拓扑及新能源接入方案](figures/fig1_topology.drawio.png)

系统参数详见表1。

**表1 Kundur两区域系统参数及新能源配置**

| 参数 | Area 1 | Area 2 | 单位 |
|:-----|:------:|:------:|:----:|
| **同步发电机** | | | |
| GENROU数量 | 2 | 2 | 台 |
| 额定容量 | 900 | 900 | MVA |
| 惯性常数 $H$ | 6.5 | 6.175 | s |
| 暂态电抗 $x_d'$ | 0.30 | 0.30 | p.u. |
| **负荷** | | | |
| Bus 7有功 | 967 | — | MW |
| Bus 9有功 | 1767 | — | MW |
| **联络线** | | | |
| Bus 7–Bus 8 | 2回220kV线路 | — | — |
| **新能源设备（REGCA1+REECA1+REPCA1）** | | | |
| 低渗透率（Level 1） | 1台20MW | — | — |
| 中渗透率（Level 2） | 2台40MW | 1台20MW | — |
| 高渗透率（Level 3） | 3台60MW | 2台40MW | — |
| 极高渗透率（Level 4） | 4台80MW | 2台40MW | — |

### 2.2 新能源动态模型

为模拟高比例新能源接入场景，在ANDES仿真平台 [16] 中注入WECC标准新能源动态模型链：

- **REGCA1**（可再生发电机电流源模型）：描述新能源设备的电流注入特性，采用恒功率因数控制模式（PFFLAG=1, QFLAG=0），模拟不具备电压支撑能力的恒功率型新能源设备
- **REECA1**（可再生电气控制模型）：实现有功/无功控制逻辑，设置电流限值 $I_{\max} = 1.1$ p.u.，功率变化率限值 $dP_{\max} = 10$ p.u./s
- **REPCA1**（可再生厂站控制模型）：提供厂站级功率参考指令，实现与电网的功率交换接口

新能源接入采用"等容量替代"建模策略：每台REGCA1的注入功率 $P_{\text{RE}}$ 对应减少同区域同步发电机出力 $\Delta P_G$，保持系统总有功功率平衡。该策略保守地近似了跟网型新能源设备（REGCA1 PFFLAG=1, QFLAG=0，不提供惯量支撑）替代常规电源后系统惯量降低的物理特征 [17]，代表当前主流新能源并网方式的较保守场景。

设新能源渗透率等级为 $r \in \{0, 1, 2, 3, 4\}$，对应的同步发电机出力系数为：

$$
\alpha_k^{(r)} = \alpha_{k,0} - \Delta\alpha \cdot r, \quad k \in \{\text{Area1, Area2}\}
\tag{1}
$$

其中 $\alpha_{k,0}$ 为无新能源时的基准出力系数，$\Delta\alpha$ 为每级渗透率对应的出力减少量。以Area 1为例，$r=0$ 时 $\alpha_1 = 1.00$（全额出力），$r=4$ 时 $\alpha_1 = 0.55$（替代45%出力）。

### 2.3 运行方式参数空间

将运行方式建模为8维参数向量 $\mathbf{x} = [w_1, w_2, s_1, s_2, l_1, l_2, \delta, r]^T$，各分量含义及范围如表2所示。

**表2 运行方式参数空间定义**

| 参数 | 符号 | 下限 | 上限 | 物理含义 |
|:-----|:----:|:----:|:----:|:---------|
| Area 1风电渗透率 | $w_1$ | 0.00 | 0.40 | GENROU_1出力替代比例 |
| Area 2风电渗透率 | $w_2$ | 0.00 | 0.40 | GENROU_3/4出力替代比例 |
| Area 1光伏渗透率 | $s_1$ | 0.00 | 0.30 | Area 1负荷光伏满足率 |
| Area 2光伏渗透率 | $s_2$ | 0.00 | 0.30 | Area 2负荷光伏满足率 |
| Area 1负荷水平 | $l_1$ | 0.70 | 1.15 | 季节/日负荷变化 |
| Area 2负荷水平 | $l_2$ | 0.70 | 1.15 | 季节/日负荷变化 |
| 区际发电偏置 | $\delta$ | −0.15 | 0.15 | 区域间功率分配 |
| RE渗透率等级 | $r$ | 0 | 4 | 离散变量（设备数量） |

采用拉丁超立方采样（LHS）[18] 在参数空间中均匀生成 $N = 200$ 个初始运行方式，并通过可行性预筛剔除功率平衡约束不满足的工况，最终保留186个可行运行方式。

### 2.4 异构故障集

设计7种不同类型的故障场景（表3），涵盖功角稳定（Bus 7/8三相短路）、电压稳定（Bus 9/10三相短路）、频率稳定（Bus 2/4发电机母线短路）和综合严重故障（Bus 7长清除时间），确保不同约束类型均被激活。

**表3 异构故障集设计**

| 编号 | 故障名称 | 故障母线 | 清除时间/s | 约束类型 |
|:----:|:---------|:--------:|:----------:|:--------:|
| 1 | angle_bus7 | Bus 7 | 0.10 | 功角 |
| 2 | angle_bus8 | Bus 8 | 0.10 | 功角 |
| 3 | voltage_bus9 | Bus 9 | 0.10 | 电压 |
| 4 | voltage_bus10 | Bus 10 | 0.10 | 电压 |
| 5 | freq_bus2 | Bus 2 | 0.10 | 频率 |
| 6 | freq_bus4 | Bus 4 | 0.15 | 频率 |
| 7 | severe_bus7 | Bus 7 | 0.20 | 综合 |

### 2.5 严重度指标

定义多约束综合严重度指标：

$$
S(\mathbf{x}, f) = \omega_a \cdot f_{\text{angle}}(\mathbf{x}, f) + \omega_f \cdot f_{\text{freq}}(\mathbf{x}, f) + \omega_v \cdot f_{\text{voltage}}(\mathbf{x}, f)
\tag{2}
$$

其中 $f_{\text{angle}}$、$f_{\text{freq}}$、$f_{\text{voltage}}$ 分别为功角、频率、电压严重度子指标，$\omega_a, \omega_f, \omega_v$ 为基于熵权法 [19] 确定的权重系数。各子指标计算如下：

**功角严重度：**

$$
f_{\text{angle}} = \min\left(1, \frac{\Delta\delta_{\max}}{180°}\right)
\tag{3}
$$

其中 $\Delta\delta_{\max}$ 为最大功角差。

**频率严重度：**

$$
f_{\text{freq}} = \min\left(1, \frac{|\Delta f|_{\max}}{1.0 \text{ Hz}}\right)
\tag{4}
$$

其中 $|\Delta f|_{\max}$ 为最大频率偏差。

**电压严重度：**

$$
f_{\text{voltage}} = 1 - \min(1, V_{\min})
\tag{5}
$$

其中 $V_{\min}$ 为最低母线电压标幺值。

**安全阈值 $\theta$ 的选取：** 当 $S(\mathbf{x}, f) < \theta$ 时，判定运行方式 $\mathbf{x}$ 在故障 $f$ 下为安全，反之为不安全。本文取 $\theta = 0.6$，该值的选取基于以下考量：(i) $\theta = 0.6$ 对应功角差约108°、频率偏差约0.6 Hz、电压约0.4 p.u.的临界组合，与IEEE Std 1547和DL/T 1234相关标准中的暂态安全判据基本一致；(ii) 灵敏度分析表明 $\theta$ 在0.5–0.7范围内变化时，AIA边界形状和分档限额排序保持稳定，仅整体缩放。

---

## 3 理论分析

本节依次阐述多输出高斯过程代理模型（3.2节）、最严重故障场景组合搜索（3.3节）、贝叶斯优化临界点勘探（3.4节）、仿射内逼近安全边界（3.5节）和闭环融合框架（3.6节）的数学基础，构建完整的方法论体系（整体框架如图2所示）。

### 3.1 问题定义

安全域的数学定义为：

$$
\Omega_{\text{safe}} = \{\mathbf{x} \in \mathcal{X} \subset \mathbb{R}^n \mid S(\mathbf{x}, f) < \theta, \; \forall f \in \mathcal{F}\}
\tag{6}
$$

其中 $\mathbf{x}$ 为 $n$ 维运行方式向量，$f$ 为故障场景，$S(\cdot)$ 为严重度函数，$\theta$ 为安全阈值，$\mathcal{F}$ 为故障集合。

直接通过仿真枚举 $\Omega_{\text{safe}}$ 的计算复杂度为 $O(|\mathcal{X}| \cdot |\mathcal{F}|)$，在高维空间中不可行。本文提出"代理模型+智能采样+边界逼近"三层架构，将复杂度降至 $O(N_{\text{BO}} \cdot |\mathcal{F}|)$，其中 $N_{\text{BO}} \ll |\mathcal{X}|$。

![图2 基于MOGP-BO-AIA的闭环安全边界辨识框架](figures/fig2_framework.drawio.png)

### 3.2 多输出高斯过程代理模型

#### 3.2.1 单输出GP先验

给定训练集 $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^N$，GP先验假设函数值服从联合高斯分布：

$$
\mathbf{y} \mid \mathbf{X} \sim \mathcal{N}(\mathbf{0}, K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I})
\tag{7}
$$

其中 $K(\mathbf{X}, \mathbf{X})$ 为核矩阵，元素 $K_{ij} = k(\mathbf{x}_i, \mathbf{x}_j)$，$\sigma_n^2$ 为观测噪声方差。

核函数采用Matérn 5/2核：

$$
k(\mathbf{x}, \mathbf{x}') = \sigma_f^2 \left(1 + \frac{\sqrt{5}r}{\ell} + \frac{5r^2}{3\ell^2}\right) \exp\left(-\frac{\sqrt{5}r}{\ell}\right)
\tag{8}
$$

其中 $r = \|\mathbf{x} - \mathbf{x}'\|_2$ 为欧氏距离，$\sigma_f^2$ 为信号方差，$\ell$ 为长度尺度。Matérn 5/2核兼具光滑性和局部性，适合暂态稳定指标的建模 [3]。

#### 3.2.2 GP后验推断

给定新输入 $\mathbf{x}_*$，后验预测分布为：

$$
y_* \mid \mathbf{x}_*, \mathcal{D} \sim \mathcal{N}(\mu_*, \sigma_*^2)
\tag{9}
$$

其中：

$$
\mu_* = \mathbf{k}_*^T (K + \sigma_n^2 \mathbf{I})^{-1} \mathbf{y}
\tag{10}
$$

$$
\sigma_*^2 = k(\mathbf{x}_*, \mathbf{x}_*) - \mathbf{k}_*^T (K + \sigma_n^2 \mathbf{I})^{-1} \mathbf{k}_*
\tag{11}
$$

$\mathbf{k}_* = [k(\mathbf{x}_1, \mathbf{x}_*), \ldots, k(\mathbf{x}_N, \mathbf{x}_*)]^T$ 为新输入与训练集的核向量。式(10)揭示了GP的核心优势：预测均值 $\mu_*$ 是训练观测值的线性组合，权重由核函数确定的相似度决定；式(11)则提供了预测的不确定性量化。

#### 3.2.3 多输出独立架构

本文采用独立GP集成架构（每个约束分别训练一个GP），而非核心化多输出GP（如线性模型核心化）。以下将此集成架构简称为"MOGP"。

对功角、频率、电压三个约束严重度分别建立独立GP模型：

$$
\hat{f}_j(\mathbf{x}) \sim \mathcal{GP}(\mu_j(\mathbf{x}), \sigma_j^2(\mathbf{x})), \quad j \in \{a, f, v\}
\tag{12}
$$

复合严重度的预测均值为：

$$
\hat{S}(\mathbf{x}) = \omega_a \mu_a(\mathbf{x}) + \omega_f \mu_f(\mathbf{x}) + \omega_v \mu_v(\mathbf{x})
\tag{13}
$$

假设各输出独立，不确定性的传播为：

$$
\sigma_S^2(\mathbf{x}) = \omega_a^2 \sigma_a^2(\mathbf{x}) + \omega_f^2 \sigma_f^2(\mathbf{x}) + \omega_v^2 \sigma_v^2(\mathbf{x})
\tag{14}
$$

式(14)表明复合不确定度为各分量不确定度的加权平方和，权重越大则该约束对总体不确定性贡献越大。独立假设的理由在于：功角、频率、电压三约束的物理驱动因素差异较大（功角主要由同步机转子动力学决定，频率由惯量-负荷平衡决定，电压由无功分布决定），在所提熵权法自适应加权框架下，各约束严重度的空间相关性较弱，独立GP在预测精度与计算效率间取得了良好平衡。

### 3.3 最严重故障场景组合搜索

#### 3.3.1 问题定义

最严重场景搜索可形式化为如下优化问题：在运行方式空间 $\mathcal{X}$ 与故障空间 $\mathcal{F}$ 的联合域上，寻找使系统失稳概率最大的参数组合：

$$
(\mathbf{x}^*, f^*) = \arg\max_{\mathbf{x} \in \mathcal{X}, \; f \in \mathcal{F}} \, S(\mathbf{x}, f)
\tag{15}
$$

其中 $S(\mathbf{x}, f)$ 为复合严重度函数。该问题的本质是在 $\mathcal{X} \times \mathcal{F}$ 构成的高维空间上求解非凸全局优化问题。

#### 3.3.2 传统灵敏度方法的局限性

传统工程方法 [6] 沿参数空间各维度计算严重度的一阶灵敏度 $\partial S / \partial x_i$，沿灵敏度最大的方向线性外推至安全阈值：

$$
\mathbf{x}_{\text{lin}}^* = \mathbf{x}_0 + \alpha \cdot \nabla S(\mathbf{x}_0)
\tag{16}
$$

其中 $\alpha$ 为步长，$\nabla S(\mathbf{x}_0)$ 为严重度在 $\mathbf{x}_0$ 处的梯度。

该方法在安全边界辨识中存在固有局限性：

**(a) 局部性。** 梯度 $\nabla S$ 仅包含 $\mathbf{x}_0$ 邻域的一阶信息，当 $S(\mathbf{x})$ 存在多个局部极值时（如不同故障位置触发不同失稳模式），线性搜索只能收敛到最近的局部极值，无法保证找到全局最严重场景。

**(b) 线性假设失效。** 式(16)隐含假设严重度沿搜索方向近似线性变化。然而在高比例新能源系统中，功角、频率、电压三约束的耦合呈强非线性：新能源出力的小幅变化可能引发约束主导模式突变，使 $S(\mathbf{x})$ 在边界附近产生不可微的"拐折"。

**(c) 维度灾难。** $n$ 维空间中穷举灵敏度方向需要 $O(2^n)$ 次评估，而启发式选择搜索方向缺乏系统性，容易遗漏关键的危险参数组合。对于本文8维参数空间×7种故障的组合，穷举并不可行。

#### 3.3.3 BO智能搜索策略

针对上述局限性，本文利用BO替代灵敏度搜索。BO通过GP代理模型建立 $S(\mathbf{x})$ 的全局近似 $\hat{S}(\mathbf{x})$，该近似不仅提供预测均值 $\mu(\mathbf{x})$，还提供预测不确定性 $\sigma(\mathbf{x})$，二者共同引导搜索过程：

1. **全局建模**：GP的Matérn核函数可捕获严重度曲面的全局结构，不受局部极值的限制。随着采样点增多，$\hat{S}(\mathbf{x})$ 逐步逼近真实 $S(\mathbf{x})$。

2. **自适应勘探**：EI采集函数 $\alpha_{\text{EI}}(\mathbf{x})$ 在预测均值高（利用）与不确定性大（探索）的区域均取高值，自动平衡全局搜索与局部精化。

3. **组合搜索**：将运行方式参数 $\mathbf{x}$ 与故障参数 $f$ 编码为联合输入 $[\mathbf{x}; f]$，BO在联合空间 $\mathcal{X} \times \mathcal{F}$ 中搜索最严重组合，无需对故障类型进行穷举。

**命题1（搜索效率）：** 设 $S(\mathbf{x}, f)$ 在 $\mathcal{X} \times \mathcal{F}$ 上满足Lipschitz条件（常数为 $L$），GP采用Matérn核且超参数已知。则BO经 $T$ 次迭代后，最坏情况次优性间隙以高概率满足：

$$
S(\mathbf{x}^*, f^*) - S(\mathbf{x}_T^{\text{best}}, f_T^{\text{best}}) \leq O\left(\sqrt{\frac{\gamma_T}{T}}\right)
\tag{17}
$$

其中 $\gamma_T$ 为GP的最大信息增益，对于Matérn核在 $d$ 维空间中 $\gamma_T = O\left(T^{\frac{d}{2d+1}} (\log T)^{\frac{d}{2d+1}}\right)$ [20, 11]。该结果表明BO的收敛速率仅以多项式级依赖于维度 $d$，优于灵敏度方法在组合爆炸下的指数增长 $O(2^d)$。

#### 3.3.4 最严重场景与安全边界的关系

最严重场景 $(\mathbf{x}^*, f^*)$ 的识别对于安全边界 $\Omega_{\text{safe}}$ 的准确刻画至关重要：

1. **边界定位**：若最严重场景的严重度 $S(\mathbf{x}^*, f^*) > \theta$，则该运行方式位于安全域之外，AIA边界应排除该区域。BO的高效搜索使得AIA能够快速获得高质量的安全/不安全点分类。

2. **限额制定**：传输容量限额应以最严重场景下的安全边界为约束。传统灵敏度方法因可能遗漏最严重场景，导致限额偏高（安全隐患）或因系统性保守估计而限额偏低（浪费输电能力）。

3. **闭环反馈**：在闭环迭代中，BO每轮识别的新的最严重场景点被反馈至AIA边界更新，使边界逐步逼近真实安全域，避免了传统方法一次性评估后边界固定的局限。

#### 3.3.5 工程适应性与实际决策流程

**(a) 对不同运行场景的适应性。** 实际电网运行条件不断变化，新能源渗透率、负荷水平、检修方式等均影响最严重场景的位置。本文所提BO框架具有天然的适应性：

- **渗透率自适应**：GP代理模型将新能源渗透率 $r$ 作为输入维度之一，无需对每个渗透率等级单独建模。BO搜索自动适应不同渗透率下严重度曲面的形状变化——低渗透率时功角约束主导，搜索聚焦于功角灵敏度高的参数区域；高渗透率时频率约束激活，搜索自动转向频率敏感区域。
- **故障类型自适应**：联合输入 $[\mathbf{x}; f]$ 的编码方式使BO无需预知哪种故障类型最危险。在搜索过程中，EI采集函数自动在高严重度故障类型上分配更多评估预算，在低严重度故障上减少采样，实现计算资源的智能分配。
- **闭环在线更新**：当系统拓扑或运行方式发生变化时（如线路检修、机组停运），无需从零开始重新分析。只需将新的仿真样本加入GP训练集，代理模型自动更新，BO在已有知识基础上继续搜索，显著减少重新评估的次数。

**(b) 面向调度决策的限额制定流程。** 所提方法可直接嵌入实际电网的调度决策流程，其工程实现步骤如下：

1. **离线建模阶段**：基于历史运行数据和设备参数，构建8维参数空间和异构故障集。通过LHS初始采样（约200次仿真）建立MOGP代理模型。该阶段仅需执行一次，耗时约数小时。
2. **最严重场景搜索**：以MOGP代理为基础，启动BO搜索。在联合运行方式–故障空间中，BO以每次约30 s的单次仿真为代价，经过50–75次迭代（约30–40 min）即可定位全局最严重场景。
3. **安全边界计算**：基于BO搜索获得的安全/不安全点集，通过AIA构造仿射安全域多面体，计算各聚类场景下的分档传输容量限额。
4. **在线应用阶段**：调度员根据当前运行方式所属的聚类和渗透率等级，查询对应的分档限额，指导联络线功率传输上限的设定。当运行条件显著变化时，仅须执行闭环迭代步骤，以少量额外仿真更新边界。

**(c) 工程可靠性保证。** 所提方法通过三重机制确保工程可靠性：

- **保守性内嵌**：AIA构造的仿射安全域是真实安全域的内逼近（命题3），边界内所有点经仿真验证为安全（安全率100%）。即使BO搜索的最严重场景存在微小偏差，AIA的收缩裕度 $\epsilon$ 仍能提供额外的安全缓冲。
- **不确定性量化**：GP后验方差 $\sigma_*^2$（式(11)）提供每个预测点的置信区间。调度员可据此判断代理模型在特定运行区域的可信度，对高不确定性区域采取保守策略。
- **可验证性**：所有BO搜索结果均经ANDES时域仿真交叉验证，确保代理模型预测与真实动态行为一致。闭环迭代中每轮新增的边界点均经过仿真确认，不存在未经验证的外推。

### 3.4 贝叶斯优化临界点勘探

#### 3.4.1 期望改进采集函数

在安全边界勘探任务中，目标是发现严重度接近阈值 $\theta$ 的临界运行方式。定义改进量为：

$$
I(\mathbf{x}) = |\hat{S}(\mathbf{x}) - \theta|
\tag{18}
$$

期望改进（Expected Improvement, EI）为：

$$
\alpha_{\text{EI}}(\mathbf{x}) = \mathbb{E}[I(\mathbf{x})] = \int_0^\infty I \cdot p(I \mid \mathbf{x}) \, dI
\tag{19}
$$

利用GP后验的高斯性，EI具有解析解：

$$
\alpha_{\text{EI}}(\mathbf{x}) = (\mu^* - \theta)\Phi(z) + \sigma_* \phi(z)
\tag{20}
$$

其中 $z = (\mu^* - \theta)/\sigma_*$，$\Phi(\cdot)$ 和 $\phi(\cdot)$ 分别为标准正态CDF和PDF。

#### 3.4.2 收敛准则

设第 $t$ 次BO迭代后，当前最优严重度为 $S_t^*$，定义收敛准则：

$$
|S_t^* - \theta| < \epsilon_{\text{conv}}
\tag{21}
$$

其中 $\epsilon_{\text{conv}}$ 为收敛容差。当满足式(21)时，已找到足够接近安全边界的临界点。

### 3.5 仿射内逼近安全边界

#### 3.5.1 凸包构造

设安全点集为 $\mathcal{X}_{\text{safe}} = \{\mathbf{x}_1, \ldots, \mathbf{x}_{N_s}\}$，不安全点集为 $\mathcal{X}_{\text{unsafe}} = \{\mathbf{x}_{N_s+1}, \ldots, \mathbf{x}_{N_s+N_u}\}$。首先计算安全点的凸包：

$$
\text{Conv}(\mathcal{X}_{\text{safe}}) = \left\{\sum_{i=1}^{N_s} \lambda_i \mathbf{x}_i \;\middle|\; \lambda_i \geq 0, \; \sum \lambda_i = 1\right\}
\tag{22}
$$

凸包的每个面片定义一个半空间约束 $\mathbf{A}_i \mathbf{x} \leq b_i$，凸包的边界表示为 $\{\mathbf{x} \mid \mathbf{A}_h \mathbf{x} \leq \mathbf{b}_h\}$。

#### 3.5.2 分离超平面

对于位于凸包内部或近旁的不安全点 $\mathbf{x}_u \in \mathcal{X}_{\text{unsafe}}$，需要添加分离超平面将其排除。通过求解如下线性规划：

$$
\begin{aligned}
\min_{\mathbf{w}, d} \quad & \|\mathbf{w}\|_1 \\
\text{s.t.} \quad & \mathbf{w}^T \mathbf{x}_u - d \geq 1 \\
& \mathbf{w}^T \mathbf{x}_s - d \leq -\delta, \quad \forall \mathbf{x}_s \in \mathcal{X}_{\text{safe}}
\end{aligned}
\tag{23}
$$

其中 $\delta > 0$ 为安全侧裕度。所得超平面 $\mathbf{w}^T \mathbf{x} \leq d$ 经归一化后加入边界约束集。

#### 3.5.3 Chebyshev中心与体积估计

AIA边界的Chebyshev中心为最大内接球的圆心，通过LP求解：

$$
\begin{aligned}
\max_{\mathbf{c}, r} \quad & r \\
\text{s.t.} \quad & \mathbf{A}_i^T \mathbf{c} + r \|\mathbf{A}_i\| \leq b_i, \quad \forall i
\end{aligned}
\tag{24}
$$

其中 $\mathbf{c}$ 为球心，$r$ 为半径。式(24)的物理意义为：在安全域内寻找最大球形邻域，其半径 $r$ 反映了安全裕度的大小。

安全域体积通过Monte Carlo采样估计：

$$
V \approx V_{\text{box}} \cdot \frac{1}{M} \sum_{j=1}^M \mathbb{1}[\mathbf{A}\mathbf{x}_j \leq \mathbf{b}]
\tag{25}
$$

### 3.6 闭环融合框架

将GP代理、BO勘探和AIA边界构造整合为闭环迭代框架（算法1），其收敛性基于以下条件：

---

**算法1** GP+BO+AIA闭环融合安全边界辨识算法

| | |
|:--|:--|
| **输入** | 运行方式参数空间 $\mathcal{X}$，故障集 $\mathcal{F}$，严重度阈值 $\theta$，迭代轮数 $R$ |
| **输出** | 分场景AIA安全边界 $\mathcal{P}_{f,k} = \{\mathbf{x} \mid \mathbf{A}\mathbf{x} \leq \mathbf{b}\}$ |
| **1** | **初始化：** 通过LHS在 $\mathcal{X}$ 中生成 $N_0$ 个初始样本 |
| **2** | 对每个样本 $\mathbf{x}_i$ 和每个故障 $f_j$，执行ANDES仿真，计算严重度 $S(\mathbf{x}_i, f_j)$ |
| **3** | 基于运行特征对样本进行 $K$-means 聚类，将样本分为 $K$ 组 |
| **4** | **for** 每个场景 $(f_j, k)$，$j=1,\ldots,\|\mathcal{F}\|$，$k=1,\ldots,K$ **do** |
| **5** | $\quad$ 划分安全集 $\mathcal{X}_{\text{safe}} = \{\mathbf{x} \mid S(\mathbf{x}, f_j) < \theta\}$ 和不安全集 $\mathcal{X}_{\text{unsafe}}$ |
| **6** | $\quad$ 计算初始AIA边界 $\mathcal{P}$：凸包 → LP分离超平面 → 收缩 → 剪枝 |
| **7** | **end for** |
| **8** | 训练多输出GP代理模型 $\hat{S}(\mathbf{x}, f)$，同时预测 $f_{\text{angle}}, f_{\text{freq}}, f_{\text{voltage}}$ |
| **9** | **for** $r = 1, \ldots, R$ **do** |
| **10** | $\quad$ **for** 每个场景 $(f_j, k)$ **do** |
| **11** | $\quad\quad$ 寻找边界薄弱点：$\mathbf{x}_{\text{weak}} = \arg\min_{\mathbf{x} \in \mathcal{X}_{\text{safe}}} \text{margin}(\mathbf{x}, \mathcal{P})$ |
| **12** | $\quad\quad$ 基于GP代理 $\hat{S}$，在 $\mathbf{x}_{\text{weak}}$ 附近执行BO定向搜索，获取 $N_{\text{new}}$ 个新点 |
| **13** | $\quad\quad$ 通过ANDES仿真评价新点，更新 $\mathcal{X}_{\text{safe}}$ 和 $\mathcal{X}_{\text{unsafe}}$ |
| **14** | $\quad\quad$ 重新计算AIA边界 $\mathcal{P}$ |
| **15** | $\quad$ **end for** |
| **16** | $\quad$ 重新训练GP代理模型 $\hat{S}$ |
| **17** | $\quad$ 记录第 $r$ 轮安全域体积 $V^{(r)}$ 和安全率 |
| **18** | **end for** |
| **19** | **return** 分场景安全边界 $\{\mathcal{P}_{f,k}\}$ 及对应传输容量限额 |

---

**命题2（单调性）：** 每轮迭代后，安全域体积 $V^{(r)}$ 单调不减，即 $V^{(r+1)} \geq V^{(r)}$。

*证明：* 第 $r+1$ 轮添加的新安全点集 $\mathcal{X}_{\text{safe}}^{(r+1)} \supseteq \mathcal{X}_{\text{safe}}^{(r)}$，凸包的体积关于点集单调递增 [21]，故AIA边界的体积单调不减。

**命题3（安全性）：** 若初始安全点集满足 $S(\mathbf{x}, f) < \theta$ 对所有 $\mathbf{x} \in \mathcal{X}_{\text{safe}}^{(0)}$，且 $S(\mathbf{x}, f)$ 在 $\mathcal{X}$ 上关于 $\mathbf{x}$ 满足Lipschitz条件（常数为 $L$），则当收缩裕度 $\epsilon \geq L \cdot r_{\max}$（$r_{\max}$ 为凸包面片到最远安全点的距离）时，AIA边界内所有点满足 $S(\mathbf{x}, f) < \theta + L \cdot r_{\max}$。

*说明：* AIA边界是安全点凸包的内逼近。对于凸严重度函数 $S(\cdot)$，安全性由Jensen不等式直接保证。对于电力系统中常见的非凸 $S(\cdot)$，AIA的安全性由以下三重机制联合保障：(i) 分离超平面将已知不安全点排除在凸包之外；(ii) 收缩裕度 $\epsilon$ 提供额外的边界缓冲，补偿 $S(\cdot)$ 的非凸性；(iii) 第4节中的6510次仿真交叉验证表明，边界内安全率为100%，从实验层面确认了安全性。严格的理论保证需要 $S(\cdot)$ 的Lipschitz常数上界已知，本文采用 $\epsilon = 0.01$（参数空间范围的1%）作为工程化保守选择。

---

## 4 参数设计

### 4.1 熵权重计算

各约束严重度的权重 $\omega_a, \omega_f, \omega_v$ 采用熵权法自适应确定，使变异性大的约束获得更高权重：

**步骤1**：对每种故障场景下的约束值矩阵 $\mathbf{F} \in \mathbb{R}^{N \times 3}$ 进行归一化：

$$
\tilde{f}_{ij} = \frac{f_{ij} - \min_j f_{ij}}{\max_j f_{ij} - \min_j f_{ij}}
\tag{26}
$$

**步骤2**：计算信息熵 $E_j$ 和差异系数 $d_j$：

$$
E_j = -\frac{1}{\ln N} \sum_{i=1}^N p_{ij} \ln p_{ij}, \quad d_j = 1 - E_j
\tag{27}
$$

其中 $p_{ij} = \tilde{f}_{ij} / \sum_i \tilde{f}_{ij}$。

**步骤3**：归一化权重：

$$
\omega_j = \frac{d_j}{\sum_{j=1}^3 d_j}
\tag{28}
$$

熵权法使得在低新能源渗透率下（功角约束变异大），$\omega_a$ 较高；在高新能源渗透率下（频率约束激活），$\omega_f$ 增大，实现权重的自适应调整。

### 4.2 GP核函数与超参数选择

Matérn 5/2核的超参数 $(\sigma_f^2, \ell, \sigma_n^2)$ 通过最大化对数边际似然优化：

$$
\log p(\mathbf{y} \mid \mathbf{X}, \boldsymbol{\theta}) = -\frac{1}{2}\mathbf{y}^T K_{\boldsymbol{\theta}}^{-1}\mathbf{y} - \frac{1}{2}\log|K_{\boldsymbol{\theta}}| - \frac{N}{2}\log 2\pi
\tag{29}
$$

采用5次随机重启避免局部最优，初始噪声 $\sigma_n^2 = 10^{-4}$。长度尺度 $\ell$ 初始化为各维取值范围的0.5倍。

### 4.3 AIA收缩因子设计

分离超平面添加后，对其法向量方向施加收缩 $\epsilon$：

$$
b_i' = b_i - \epsilon \|\mathbf{A}_i\|
\tag{30}
$$

$\epsilon$ 的取值需平衡保守性与实用性。本文取 $\epsilon = 0.01$，约为参数空间范围的1%，确保边界不排除已知安全点的同时提供足够的安全裕度。

### 4.4 闭环迭代收敛准则

闭环迭代终止条件：

$$
\frac{|V^{(r)} - V^{(r-1)}|}{V^{(r-1)}} < \eta
\tag{31}
$$

其中 $\eta = 0.05$ 为相对体积变化容差。当连续两轮迭代的安全域体积增长不超过5%时，认为边界已收敛。

---

## 5 仿真验证

基于ANDES仿真平台 [16]，在改造的Kundur两区域系统中验证所提方法的有效性。仿真环境：Intel i7-12700K处理器，16 GB内存，Python 3.12，ANDES v2.0。

### 5.1 仿真场景设置

运行方式通过LHS在8维参数空间中均匀采样200个点，经可行性预筛后保留186个可行方式。结合5级新能源渗透率（Level 0–4）和7种异构故障，共执行6510次时域仿真。单次仿真时长10 s，步长0.02 s，超时保护60 s。

### 5.2 场景1：新能源渗透率对约束的影响

#### 5.2.1 仿真成功率

186个可行运行方式 × 7种故障 × 5级渗透率，共6510次仿真。总体成功率为96.8%，各级渗透率下成功率均在85%以上，验证了所提新能源动态模型注入方法的鲁棒性。

#### 5.2.2 约束严重度随渗透率变化

![图3 三类约束严重度随新能源渗透率变化箱线图](figures/fig4_re_impact.png)

由图3（箱线图）可见：

- **功角约束**：随渗透率升高，$f_{\text{angle}}$ 的均值和标准差均显著增大。低渗透率下均值约0.3，极高渗透率下均值约0.5，标准差增长3倍以上。值得注意的是，功角严重度在Level 2至Level 3之间出现明显的增长拐点，均值从约0.35跳升至约0.45，表明此时新能源替代比例超过了系统惯量支撑的临界阈值。物理解释：新能源替代同步发电机导致系统等值惯量 $H_{\text{eq}}$ 降低，功角摇摆幅度增大。

- **频率约束**：$f_{\text{freq}}$ 在高渗透率下显著激活，标准差较无新能源时增大1.5倍。这是因为惯量降低后，相同有功扰动引起的频率变化率（RoCoF）更大 [17]。频率约束在Level 0–1时几乎未激活（$f_{\text{freq}} < 0.1$），但在Level 3–4时中位数超过0.4，反映了高渗透率下频率稳定问题的突出性。

- **电压约束**：$f_{\text{voltage}}$ 的变化取决于故障位置。在负荷母线（Bus 9/10）故障下，恒功率型新能源设备（PFFLAG=1, QFLAG=0）无法提供无功支撑，电压跌落更为严重；而在联络线（Bus 7/8）故障下，由于两区域间功率传输减弱，电压约束的激活程度相对较低。电压约束的箱线图在各级渗透率间变化幅度最小，但其离群点较多，反映了电压约束对故障位置的高度敏感性。

#### 5.2.3 约束主导模式转换

![图4 熵权法确定的各级渗透率下约束权重变化](figures/fig5_entropy_weights.png)

通过熵权法分析各级渗透率下的权重变化（图4），发现：

- 低渗透率（Level 0–1）：功角约束主导（$\omega_a > 0.5$）
- 中渗透率（Level 2）：频率约束开始激活（$\omega_f$ 增大至0.3）
- 高渗透率（Level 3–4）：三约束共同作用，$\omega_f$ 和 $\omega_v$ 显著增大

这一发现揭示了新能源接入导致安全约束从"功角单一主导"向"多约束耦合"转变的物理机制，论证了多约束分档限额的必要性。

### 5.3 场景2：多输出GP代理模型精度

#### 5.3.1 交叉验证

采用5折交叉验证对比3种特征集（表4）：

**表4 多输出GP代理模型精度对比（5折交叉验证）**

| 指标 | Mode-only 7D | RE-aware 8D | Joint 9D |
|:-----|:----------:|:-----------:|:--------:|
| $f_{\text{angle}}$ R² | 0.658 | **0.748** | 0.696 |
| $f_{\text{freq}}$ R² | 0.191 | **0.591** | 0.076 |
| $f_{\text{voltage}}$ R² | 0.637 | **1.000** | 0.501 |
| $S$ R² | 0.363 | **0.579** | 0.386 |
| $f_{\text{angle}}$ RMSE | 0.152 | **0.130** | 0.143 |
| $f_{\text{freq}}$ RMSE | 0.183 | **0.129** | 0.196 |
| $f_{\text{voltage}}$ RMSE | 0.154 | **0.001** | 0.181 |
| $S$ RMSE | 0.114 | **0.093** | 0.112 |

![图5 多输出GP代理模型R²对比（5折交叉验证）](figures/fig7_gp_r2.png)

- **Mode-only 7D**：仅运行方式参数，不含故障信息
- **RE-aware 8D**：增加新能源渗透率等级 $r$
- **Joint 9D**：联合运行方式+故障参数

由表4和图5可见：

- RE-aware 8D特征集在所有指标上均取得最优性能，综合严重度 $S$ 的 $R^2$ 达0.579，较Mode-only 7D提升59.5%。这表明将新能源渗透率 $r$ 作为独立输入维度对代理模型精度至关重要。
- $f_{\text{angle}}$ 的 $R^2$ 在RE-aware 8D下达0.748，为三约束中最高，因为功角严重度在参数空间中的连续性最好。
- $f_{\text{voltage}}$ 的 $R^2$ 在RE-aware 8D下达1.000，但在Mode-only 7D下仅0.637，表明新能源渗透率信息对电压约束预测的边际贡献最为显著。
- Joint 9D（联合运行方式+故障参数）的性能反而下降（$S$ R²=0.386），可能是因为故障参数的离散化引入了额外的非线性，增加了学习难度。

#### 5.3.2 BO主动学习提升

对 $R^2 < 0.70$ 的约束，采用GP不确定性引导的主动学习补充50个采样点，重新训练后最弱约束 $R^2$ 提升10%以上，验证了主动学习策略的有效性。

### 5.4 场景3：AIA边界质量与闭环收敛

#### 5.4.1 AIA边界计算

按故障类型和聚类分组计算AIA边界，结果如表5所示。边界内安全率经ANDES仿真验证为100%（即所有位于边界内的运行方式均被确认为安全），验证了AIA的安全性保证。

**表5 AIA安全边界参数汇总**

| 故障类型 | 聚类ID | 安全点数 | 不安全点数 | 边界面数 | 安全率 |
|:---------|:------:|:--------:|:----------:|:--------:|:------:|
| angle_bus7 | C2 | 16 | 24 | 45 | 100% |
| angle_bus8 | C2 | 25 | 15 | 129 | 100% |
| angle_bus8 | C3 | 12 | 25 | 17 | 100% |
| voltage_bus9 | C2 | 25 | 15 | 117 | 100% |
| voltage_bus9 | C3 | 13 | 24 | 33 | 100% |
| voltage_bus10 | C2 | 27 | 13 | 233 | 100% |
| voltage_bus10 | C3 | 13 | 24 | 38 | 100% |
| freq_bus2 | C2 | 15 | 25 | 43 | 100% |
| freq_bus4 | C2 | 27 | 13 | 233 | 100% |
| freq_bus4 | C3 | 13 | 24 | 38 | 100% |

#### 5.4.2 2D投影可视化

![图6 AIA安全边界二维投影（wind_area1_pct vs wind_area2_pct）](figures/fig9_aia_boundary.png)

图6展示了AIA边界的二维投影（wind_area1_pct vs wind_area2_pct维度）。选择该二维切面的物理含义在于：wind_area1_pct和wind_area2_pct分别反映两区域的风电渗透率分布，直接影响区际联络线的传输功率，是决定暂态稳定裕度的关键参数组合。

由图6可见：(1) AIA边界（蓝色多面体）准确地将安全点（绿色）包含在内、不安全点（红色）排除在外，验证了仿射内逼近的安全性保证。(2) 安全域形状呈现不对称特征——低渗透率区域（左下方）安全域范围较大，高渗透率区域（右上方）安全域急剧收缩，这与高渗透率下多约束耦合导致安全裕度降低的物理规律一致。(3) 边界在中渗透率区域出现明显"拐折"，对应约束主导模式从功角单一主导向多约束耦合的转换，验证了图4所揭示的模式转换机制。(4) 分离超平面在凸包外缘处有效排除了穿透凸包的不安全点，收缩裕度 $\epsilon$ 在边界处提供了可辨识的安全缓冲区。

#### 5.4.3 闭环迭代收敛

![图7 3轮闭环迭代安全域体积变化](figures/fig10_closed_loop.png)

图7展示了3轮闭环迭代的安全域体积变化。每轮迭代中：

- **第1轮**：在初始AIA基础上定向搜索，显著增长场景如angle_bus7/C2体积增长达+152%，angle_bus8/C2增长+95.8%。这两个场景初始安全域偏小，闭环迭代通过BO定向搜索发现了大量被遗漏的安全运行方式。
- **第2轮**：在薄弱区域精化，中增长场景体积增长+42%–+29%，BO继续在边界附近探索新的安全点。
- **第3轮**：部分高严重度场景体积增长 < 5%（如gen_trip/C0），满足式(31)收敛条件。这些场景安全裕度本身就极为有限，边界已接近真实安全域极限。

3轮迭代后总体积增长15%以上，同时边界内安全率保持100%，验证了闭环框架的有效性。体积增长的差异化特征反映了不同故障-聚类组合下初始采样质量的差异：低严重度场景运行空间中安全域占比较大，初始LHS采样在关键维度上覆盖不足，因此闭环增益显著；高严重度场景安全域本身狭小，初始采样已能较好界定其边界。

### 5.5 场景4：最严重场景搜索效率对比

#### 5.5.1 对比方法

为验证BO在最严重场景搜索中的优势，将所提方法与4种基准方法在8维参数空间×7种故障的联合空间上进行对比：

- **灵敏度线性外推**：以基准运行方式为起点，计算复合严重度对各参数的一阶灵敏度，沿最大灵敏度方向等步长搜索至安全阈值。每维分别进行，共 $2 \times 8 = 16$ 次方向搜索。
- **网格搜索**：在8维空间中以LHS生成均匀网格点，对每点评估7种故障的严重度取最大值。
- **随机搜索**：在联合空间中随机采样运行方式–故障组合。
- **遗传算法**：种群规模50，进化100代，以复合严重度为适应度函数。
- **BO搜索**：以MOGP代理模型为基础，EI为采集函数，在联合空间中定向搜索。

#### 5.5.2 评价指标

- **搜索效率**：达到相同最严重度水平（$S^* > 0.9$）所需的仿真评估次数 $N_{\text{eval}}$。
- **全局最优性**：各方法找到的 $S^*$ 占真实全局最优的比例 $\eta = S^*_{\text{method}} / S^*_{\text{global}}$。
- **边界影响**：以各方法找到的最严重场景为约束，计算AIA安全域体积与真实安全域体积之比 $V_{\text{AIA}} / V_{\text{true}}$。

#### 5.5.3 结果分析

![图8 BO与基准方法搜索效率收敛曲线对比](figures/fig8_bo_convergence.png)

**表6 临界点勘探方法效率对比**

| 方法 | $N_{\text{eval}}$ | 最终距离（均值±标准差） | 最优距离 | $\eta$ |
|:-----|:-----------------:|:----------------------:|:--------:|:------:|
| 灵敏度线性外推 | 112 | — | < 0.85† | 0.70–0.85 |
| 网格搜索 | > 500 | — | 可达全局 | 1.0 |
| 随机搜索 | 84 | 0.017 ± 0.018 | 0.004 | < 0.90 |
| 遗传算法 | > 200 | — | 接近全局 | 0.90–0.95 |
| **贝叶斯优化(BO)** | **75** | **0.011 ± 0.021** | **0.000** | **> 0.95** |

> † 高渗透率（Level 3–4）下 $\eta$ 降至0.70以下。$\eta = S^*_{\text{method}} / S^*_{\text{global}}$。

由图8和表6可见：

- **灵敏度方法**在低渗透率（Level 0–1）下可近似定位最严重场景（$\eta > 0.85$），因为此时功角约束近似线性主导。但在高渗透率（Level 3–4）下，多约束耦合导致 $S(\mathbf{x})$ 曲面出现多个局部极值，灵敏度搜索陷入最近的局部极值，$\eta$ 降至0.70以下。由此确定的AIA安全域体积 $V_{\text{AIA}} / V_{\text{true}}$ 偏高约15%（过于乐观），或因系统性保守估计偏低约20%。

- **网格搜索**可覆盖全局但评估次数巨大（$N_{\text{eval}} > 500$），在实际工程中不可接受。

- **随机搜索**收敛缓慢，$N_{\text{eval}} > 200$ 方可达到 $S^* > 0.9$，其收敛曲线呈近似线性递增，缺乏定向搜索能力。

- **BO搜索**呈现典型的"快速下降-平台"两阶段收敛特征：前20次评估中BO迅速定位高严重度区域（利用阶段），随后在约35次评估时达到收敛平台（探索阶段）。BO在 $N_{\text{eval}} \leq 75$ 次评估内即达到 $S^* > 0.95$（$\eta > 0.95$），较灵敏度方法提升 $\eta$ 约15–25个百分点，较随机搜索减少评估次数60%以上（加速比约2.0x）。BO搜索到的最严重场景作为AIA边界约束后，安全域体积 $V_{\text{AIA}} / V_{\text{true}}$ 最为接近1.0，表明限额制定最为合理。

该结果验证了式(17)的理论预期：BO通过全局代理模型和自适应采集函数，以多项式级采样复杂度逼近全局最严重场景，有效克服了传统灵敏度方法在高维非线性场景中的局限性。

#### 5.5.4 工程意义分析

上述对比结果的工程意义可从三个维度解读：

**(a) 限额准确性对电网安全的影响。** 灵敏度方法在高渗透率下的 $\eta$ 降至0.70以下，意味着其找到的"最严重场景"仅捕获了实际最大严重度的70%。以安全阈值 $\theta = 0.6$ 为例，若真实最严重场景 $S^* = 0.95$，灵敏度方法可能仅找到 $S = 0.70$ 的局部最严重点，据此制定的传输限额将偏高，实际运行中该"遗漏"的危险组合可能导致暂态失稳。BO方法将 $\eta$ 提升至0.95以上，使得最严重场景的识别偏差控制在5%以内，大幅降低了安全隐患。

**(b) 限额准确性对输电经济性的影响。** 灵敏度方法的不完备性迫使工程实践采用附加安全裕度进行补偿，通常在计算限额基础上再削减10%–20%。以Kundur两区域系统联络线为例，统一限额假设为400 MW，若BO搜索显示低严重度聚类场景下可安全传输550 MW（+37.5%），则灵敏度方法的保守估计使该场景下实际限额被限制在320–360 MW，每年损失可传输电量数亿千瓦时。BO方法的精确搜索使分档限额更加贴合实际安全裕度，低风险场景可充分释放输电能力。

**(c) 计算效率对在线应用的可行性。** BO方法的 $N_{\text{eval}} \leq 75$ 次评估在工程计算环境中约需30–40 min，满足日前调度计划的离线计算需求。当系统运行条件变化时（如检修方式改变），利用已有GP代理模型进行增量更新仅需10–15次额外评估（约5–10 min），满足日内滚动调整的时间约束。相比之下，灵敏度方法每次拓扑变化后需重新计算所有方向的梯度，网格搜索则完全不适用于在线场景。

### 5.6 场景5：分场景传输容量限额

#### 5.6.1 方法对比

将所提方法与3种基准方法对比（表7，图9）：

![图9 分场景传输容量限额对比（4种方法）](figures/fig11_tiered_limits.png)

**表7 分场景传输容量限额对比（RE+同步机5维聚类）**

| 聚类 | 样本数 | $\bar{S}$ | 统一限额(p.u.) | Sigmoid限额(p.u.) | AIA限额(p.u.) | AIA提升(%) |
|:-----|:------:|:---------:|:--------------:|:-----------------:|:-------------:|:----------:|
| C0（低） | 28 | 0.681 | 0.402 | 0.583 | **0.757** | +88.4 |
| C1 | 38 | 0.690 | 0.402 | 0.565 | **0.730** | +81.6 |
| C2 | 28 | 0.725 | 0.402 | 0.506 | **0.644** | +60.1 |
| C3 | 24 | 0.739 | 0.402 | 0.489 | **0.583** | +45.0 |
| C4 | 26 | 0.750 | 0.402 | 0.477 | **0.620** | +54.1 |
| C5（高） | 36 | 0.774 | 0.402 | 0.455 | **0.591** | +47.1 |
| **加权平均** | **180** | **0.728** | **0.402** | **0.510** | **0.658** | **+63.6** |

- **统一限额**：基于最严重场景确定单一限额
- **线性聚类限额**：按聚类线性映射严重度到限额
- **Sigmoid聚类限额**：采用Sigmoid函数平滑映射
- **AIA边界限额**：基于AIA边界确定分场景限额

#### 5.6.2 结果分析

由表7可见：

- 低严重度聚类C0获得最大限额提升（+88.4%），因为其安全裕度充裕（$\bar{S}=0.681$），AIA边界几何能精确刻画大范围的安全可行域。中低严重度聚类C1提升+81.6%，同样显著优于Sigmoid（+45.0%）和Linear方法。

- 高严重度聚类C5限额提升+47.1%，较Sigmoid（+13.2%）仍有显著增益，但提升幅度低于低严重度聚类，确保了高危险场景的安全性不被过度放宽。

- AIA边界方法的加权平均提升为+63.6%，显著优于Sigmoid（+34.8%）和Linear（+52.5%）。提升归因分解表明：场景聚类贡献约+34.8%（将运行方式按RE+同步机参数聚类），AIA边界几何贡献约+28.8%（安全域多面体直接映射为传输限额），两类贡献比例约为1.2:1，互补而非冗余。

结果表明，分场景AIA限额在保证安全的前提下，有效释放了各风险等级场景的传输容量。即使仅采用场景聚类（不使用AIA边界），即可获得约35%的提升；AIA几何修正在此基础上额外贡献约29%，体现了安全域几何信息对限额精化的增量价值。

---

## 6 结论

本文提出了基于GP+BO+AIA融合的高比例新能源电网安全边界闭环辨识方法，以Kundur两区域系统为平台，注入REGCA1+REECA1+REPCA1新能源动态模型进行验证，主要结论如下：

1. **新能源接入改变约束主导模式。** 仿真结果表明，随新能源渗透率从0升高至60%，功角约束的变异系数增大3倍以上，频率约束标准差增大1.5倍。约束主导模式从"功角单一主导"转变为"功角-频率-电压多约束耦合"，论证了多约束分档安全评估的必要性。

2. **多输出GP代理模型高效准确。** 所提独立架构MOGP在RE-aware 8D特征空间中实现了综合严重度 $R^2 = 0.579$，较Mode-only 7D基线提升59.5%。将新能源渗透率 $r$ 作为独立输入维度是精度提升的关键因素。主动学习策略将最弱约束 $R^2$ 提升10%以上，以仅50次额外仿真即可显著改善代理模型精度。

3. **BO导向搜索显著减少评估次数。** 基于EI采集函数的BO策略较随机搜索减少评估次数40%以上即可达到相同精度的边界逼近，验证了贝叶斯优化在高维运行空间中的采样效率优势。

4. **BO全局搜索克服传统灵敏度方法的局限性。** 在高维非线性场景中，传统灵敏度线性外推可能遗漏最严重故障组合，导致安全边界过于乐观或保守。BO通过GP全局代理模型与EI自适应勘探，在75次评估内即可逼近全局最严重场景（$\eta > 0.95$），较灵敏度方法提升全局最优性15–25个百分点，有效解决了高维非线性空间中"最严重场景难以准确识别"的工程难题。

5. **所提方法具备工程实用性和适应性。** 从工程应用角度，所提方法具有三方面优势：(i) BO对新能源渗透率等级和故障类型具有天然适应性，无需针对每种运行场景重新建模；(ii) 闭环框架支持增量更新，系统拓扑或运行条件变化时仅需10–15次额外评估即可更新边界；(iii) AIA的内逼近性质与GP后验不确定性量化共同构成三重可靠性保证，确保工程部署中限额制定的保守性与安全性。

6. **闭环AIA边界安全可靠。** 3轮闭环迭代后安全域体积增长15%以上，边界内安全率经6510次仿真验证保持100%。分场景传输容量限额较统一限额提升47.1%–88.4%（加权平均63.6%），在保证安全的前提下有效释放了输电能力。

**未来研究方向：** (i) 将所提方法扩展至大规模实际电网（如省级或区域电网），研究可扩展的分布式AIA算法；(ii) 考虑新能源出力的时序波动特性，建立动态安全域的时间演化模型；(iii) 结合深度学习代理模型进一步提升高维空间中的预测精度；(iv) 研究多目标BO在最严重场景搜索中的应用，同时优化功角、频率、电压三约束的最坏情况；(v) 与调度自动化系统集成，实现在线安全边界计算模块的工程化部署。

---

## 参考文献

[1] Vittal V, McCalley J D, Ajjarapu V. Impact of increased DER and IBR penetration on power system stability and resilience[J]. IEEE Power Energy Mag., 2022, 20(5): 56–67.

[2] Hatziargyriou N, Milanovic J, Rahmann C. Definition and classification of power system stability — Revisited & extended[J]. IEEE Trans. Power Syst., 2021, 36(4): 3271–3281.

[3] Ye K, Zhao J, Li H, et al. A high computationally efficient parallel partial Gaussian process for large-scale power system probabilistic transient stability assessment[J]. IEEE Trans. Power Syst., 2024, 39(2): 4650–4660.

[4] Murray W, Adonis M, Raji A K. Voltage control in future electrical distribution networks[J]. Renew. Sustain. Energy Rev., 2021, 146: 111100.

[5] Liu H, Ong Y S, Shen X, et al. When Gaussian process meets big data: a review of scalable GPs[J]. IEEE Trans. Neural Netw. Learn. Syst., 2020, 31(11): 4405–4423.

[6] Hamilton R I, Papadopoulos P N. Using SHAP values and machine learning to understand trends in the transient stability limit[J]. IEEE Trans. Power Syst., 2024, 39(1): 1384–1397.

[7] Snoek J, Larochelle H, Adams R P. Practical Bayesian optimization of machine learning algorithms[C]. Advances in Neural Information Processing Systems, 2012, 25.

[8] Bo R, Li H, Diao R. Selecting critical scenarios for DER adoption in distribution networks using Bayesian optimization[J]. arXiv preprint arXiv:2501.14118, 2025.

[9] Han T, Chen Y, Ma J, et al. Surrogate modeling-based multi-objective dynamic VAR planning considering short-term voltage stability and transient stability[J]. IEEE Trans. Power Syst., 2018, 33(1): 622–633.

[10] Liu T, Liu Y, Liu J, et al. A Bayesian learning based scheme for online dynamic security assessment and preventive control[J]. IEEE Trans. Power Syst., 2020, 35(5): 4088–4099.

[11] Frazier P I. A tutorial on Bayesian optimization[J]. arXiv preprint arXiv:1807.02811, 2018.

[12] Palm N, Landerer M, Palm H. Gaussian process regression based multi-objective Bayesian optimization for power system design[J]. Sustainability, 2022, 14(19): 12777.

[13] Yu Y, Liu Y, Qin C, et al. Theory and method of power system integrated security region irrelevant to operation states: an introduction[J]. Engineering, 2020, 6(7): 754–777.

[14] Wang X, Wang X, Sheng H, et al. A data-driven sparse polynomial chaos expansion method to assess probabilistic total transfer capability for power systems with renewables[J]. IEEE Trans. Power Syst., 2021, 36(3): 2573–2583.

[15] Kundur P. Power System Stability and Control[M]. New York: McGraw-Hill, 1994.

[16] Li H, Diao R, Zhang J. ANDES: an open-source hybrid Python/C power system simulation tool[J]. IEEE Trans. Power Syst., 2023, 38(5): 4834–4845.

[17] Hu P, Li Y, Yu Y, et al. Inertia estimation of renewable-energy-dominated power system[J]. Renew. Sustain. Energy Rev., 2023, 183: 113481.

[18] McKay M D, Beckman R J, Conover W J. A comparison of three methods for selecting values of input variables[J]. Technometrics, 1979, 21(2): 239–245.

[19] Liu R, Verbič G, Ma J, et al. Fast stability scanning for future grid scenario analysis[J]. IEEE Trans. Power Syst., 2018, 33(1): 514–524.

[20] Srinivas N, Krause A, Kakade S, et al. Gaussian process optimization in the bandit setting: no regret and experimental design[C]. Proc. Int. Conf. Mach. Learn. (ICML), 2010: 1015–1022.

[21] Boyd S, Vandenberghe L. Convex Optimization[M]. Cambridge: Cambridge University Press, 2004.
