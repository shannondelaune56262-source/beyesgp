## 2 理论分析

本节依次阐述多输出高斯过程代理模型（2.2节）、贝叶斯优化临界点勘探（2.3节）、仿射内逼近安全边界（2.4节）和闭环融合框架（2.5节）的数学基础，构建完整的方法论体系。

### 2.1 问题定义

安全域的数学定义为：

$$
    \Omega_{\text{safe}} = \{\mathbf{x} \in \mathcal{X} \subset \mathbb{R}^n \mid S(\mathbf{x}, f) < \theta, \forall f \in \mathcal{F}\}
$$    (7)

其中 $\mathbf{x}$ 为 $n$ 维运行方式向量，$f$ 为故障场景，$S(\cdot)$ 为严重度函数，$\theta$ 为安全阈值，$\mathcal{F}$ 为故障集合。直接通过仿真枚举 $\Omega_{\text{safe}}$ 的计算复杂度为 $O(|\mathcal{X}| \cdot |\mathcal{F}|)$，在高维空间中不可行。本文提出"代理模型+智能采样+边界逼近"三层架构，将复杂度降至 $O(N_{\text{BO}} \cdot |\mathcal{F}|)$，其中 $N_{\text{BO}} \ll |\mathcal{X}|$。

### 2.2 多输出高斯过程代理模型

代理模型的选择需满足三个核心需求：(i) 提供预测不确定性量化，以驱动后续BO的主动采样；(ii) 在少量样本下保持合理的预测精度，以适应时域仿真计算成本高的约束；(iii) 支持解析的梯度计算，以实现采集函数的高效优化。高斯过程（GP）天然满足上述三项需求——其后验分布同时给出预测均值和方差（不确定性），核函数在小样本下具有良好的泛化能力，且采集函数可解析求导 [rasmussen2006gp]。本问题面临高维黑箱、仿真成本高昂的挑战，GP模型恰好满足不确定性驱动主动采样（BO）和解析梯度的需求，是安全边界辨识场景下代理模型的自然选择。

#### 2.2.1 单输出GP先验

给定训练集 $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^N$，GP先验假设函数值服从联合高斯分布：

$$
    \mathbf{y} | \mathbf{X} \sim \mathcal{N}(\mathbf{0}, K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I})
$$    (8)

其中 $K(\mathbf{X}, \mathbf{X})$ 为核矩阵（Kernel Matrix），元素 $K_{ij} = k(\mathbf{x}_i, \mathbf{x}_j)$，$\sigma_n^2$ 为观测噪声方差。

核函数采用Matérn 5/2核：

$$
    k(\mathbf{x}, \mathbf{x}') = \sigma_f^2 \left(1 + \frac{\sqrt{5}r}{\ell} + \frac{5r^2}{3\ell^2}\right) \exp\left(-\frac{\sqrt{5}r}{\ell}\right)
$$    (9)

其中 $r = \|\mathbf{x} - \mathbf{x}'\|_2$ 为欧氏距离，$\sigma_f^2$ 为信号方差（Signal Variance），$\ell$ 为长度尺度（Length Scale）。选择Matérn 5/2核而非径向基函数（Radial Basis Function, RBF）核的理由如下：RBF核对应无限可微的函数空间，其样本路径过于光滑，难以准确捕捉暂态稳定指标中可能存在的局部非光滑特征；而Matérn 5/2核对应的函数空间仅为二阶可微（$\nu = 5/2$），在保持足够光滑性的同时允许适度的局部变化，更符合电力系统暂态稳定指标的真实行为特性 [rasmussen2006gp]。此外，Matérn 5/2核的紧凑形式使其计算效率与RBF核相当，不会引入额外的计算负担。

极端情况验证（$r \to 0$ 时 $k = \sigma_f^2$，$\ell \to \infty$ 时核退化为常数，$\ell \to 0^+$ 时核矩阵退化为对角矩阵）和超参数梯度公式参见附录A。

核函数的超参数集合记为 $\boldsymbol{\theta}_{\text{GP}} = \{\sigma_f^2, \ell, \sigma_n^2\}$，通过最大化对数边际似然进行优化：

$$
    \log p(\mathbf{y} | \mathbf{X}, \boldsymbol{\theta}_{\text{GP}}) = -\frac{1}{2}\mathbf{y}^T \mathbf{K}_y^{-1} \mathbf{y} - \frac{1}{2}\log|\mathbf{K}_y| - \frac{N}{2}\log 2\pi
$$    (10)

其中 $\mathbf{K}_y = K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I}$。超参数优化采用L-BFGS-B算法，配合多起点策略从10个随机初始化点出发选取最优解。

#### 2.2.2 GP后验推断与不确定性量化

给定训练集 $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^N$ 和新测试输入 $\mathbf{x}_*$，由GP先验假设与高斯条件分布公式（Schur补）[rasmussen2006gp, Chapter 2]，后验预测分布为 $y_* | \mathbf{x}_*, \mathcal{D} \sim \mathcal{N}(\mu_*, \sigma_*^2)$，其中：

$$
    \boxed{\mu_* = \mathbf{k}_*^T \mathbf{K}_y^{-1} \mathbf{y}}
$$    (11)

$$
    \boxed{\sigma_*^2 = k(\mathbf{x}_*, \mathbf{x}_*) - \mathbf{k}_*^T \mathbf{K}_y^{-1} \mathbf{k}_* + \sigma_n^2}
$$    (12)

其中 $\mathbf{k}_* = [k(\mathbf{x}_1, \mathbf{x}_*), \ldots, k(\mathbf{x}_N, \mathbf{x}_*)]^T$，$\mathbf{K}_y = K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I}$。

预测均值 $\mu_*$ 为训练观测值的核加权线性组合，权重由测试点与训练点的核函数相似度决定。预测方差 $\sigma_*^2$ 由先验方差 $k_{**}$ 减去信息增益项（因观测数据而减少的不确定性）构成：在训练数据密集的区域 $\sigma_*^2$ 较小（预测置信度高），在远离训练集的区域 $\sigma_*^2$ 接近先验不确定性。这一性质是GP与BO之间建立桥梁的关键——BO的EI采集函数正是利用 $\sigma_*$ 驱动勘探，主动探索模型不确定性高的区域。预测的计算复杂度为 $O(N^2)$（利用Cholesky分解预计算后）。

#### 2.2.3 多输出独立架构与核心化方法比较

对功角稳定、频率稳定、电压稳定三个约束严重度分别建立独立GP模型：

$$
    \hat{f}_j(\mathbf{x}) \sim \mathcal{GP}(\mu_j(\mathbf{x}), \sigma_j^2(\mathbf{x})), \quad j \in \{a, f, v\}
$$    (19)

本文采用独立输出架构而非线性模型核心化（LMC），原因有三：（i）功角、频率、电压三个物理量表征不同的稳定机制，其函数形态差异显著，耦合建模可能引入虚假关联；（ii）独立架构的复杂度为 $O(N^3 P)$，可并行计算；（iii）后续BO勘探需要独立控制各约束的不确定性传播。LMC与独立架构的详细比较见附录B。

复合严重度的预测均值为各分量预测均值的加权和：

$$
    \hat{S}(\mathbf{x}) = \omega_a \mu_a(\mathbf{x}) + \omega_f \mu_f(\mathbf{x}) + \omega_v \mu_v(\mathbf{x})
$$    (20)

其中权重 $\omega_a + \omega_f + \omega_v = 1$，由调度偏好或等权重方案确定。假设各输出独立，不确定性的传播为：

$$
    \sigma_S^2(\mathbf{x}) = \omega_a^2 \sigma_a^2(\mathbf{x}) + \omega_f^2 \sigma_f^2(\mathbf{x}) + \omega_v^2 \sigma_v^2(\mathbf{x})
$$    (21)

式(21)表明复合不确定度为各分量不确定度的加权平方和。该性质意味着：(i) 权重越大的约束对总体不确定性贡献越大，因此BO应优先降低高权重约束在边界附近的不确定性；(ii) 任意一个约束的高不确定性即可导致复合不确定性增大，确保BO不会忽略任何维度的信息匮乏区域。

### 2.3 贝叶斯优化临界点勘探

安全边界辨识的采样策略需在有限的仿真预算内高效发现临界点。均匀网格搜索在 $n$ 维空间中的复杂度为 $O(m^n)$（$m$ 为每维采样数），随维数指数增长，在本文8维参数空间中不可行。随机搜索和LHS虽无指数增长问题，但其采样与目标函数无关，无法利用已观测点的信息指导后续采样，导致大量仿真预算浪费在远离边界的区域。贝叶斯优化（BO）通过GP后验提供的目标函数概率模型，利用采集函数显式平衡"开发"（exploitation，在预测临界值附近精化）与"勘探"（exploration，在不确定性高的区域尝试），使每次仿真评估都指向最可能改善边界精度的位置。这一主动采样策略在昂贵黑箱函数优化中已被证明显著优于被动采样方法（BO在35次评估内收敛，较Random的65次减少46%）。

#### 2.3.1 期望改进采集函数推导

**步骤1：物理模型建立。** 在安全边界勘探任务中，目标并非传统BO中的全局最优化，而是发现严重度接近阈值 $\theta$ 的临界运行方式（Critical Operating Point）。定义边界距离函数：

$$
    d(\mathbf{x}) = |S(\mathbf{x}) - \theta|
$$    (22)

理想情况下，应寻找使 $d(\mathbf{x})$ 最小的 $\mathbf{x}$，即位于安全边界上的点。由于 $S(\mathbf{x})$ 的真实值未知（需通过时域仿真获得），利用GP代理模型的后验分布对其进行估计。GP在 $\mathbf{x}$ 处给出 $S(\mathbf{x})$ 的后验预测分布为 $S(\mathbf{x}) | \mathcal{D} \sim \mathcal{N}(\mu_*(\mathbf{x}), \sigma_*^2(\mathbf{x}))$。

给定当前已观测的 $N$ 个样本中，最接近阈值的边界距离为 $\eta = \min_{i=1}^{N} |y_i - \theta|$，即当前最优（最接近阈值）样本的严重度偏差。

**步骤2：基本方程列写——改进量定义。** 定义改进量（Improvement）为当前最小边界距离与新点边界距离之差的正部：

$$
    I(\mathbf{x}) = \max\left(\eta - d(\mathbf{x}),\, 0\right) = \max\left(\eta - |S(\mathbf{x}) - \theta|,\, 0\right)
$$    (23)

该定义的物理含义为：若新点 $\mathbf{x}$ 比当前已观测的最优点更接近阈值（即 $d(\mathbf{x}) < \eta$），则改进量为正，改进程度为 $\eta - d(\mathbf{x})$；否则改进量为零（该点不提供新的边界信息）。

由于GP后验给出的 $S(\mathbf{x})$ 服从高斯分布 $\mathcal{N}(\mu_*, \sigma_*^2)$，而 $d(\mathbf{x}) = |S(\mathbf{x}) - \theta|$ 是 $S(\mathbf{x})$ 的非线性变换，改进量 $I(\mathbf{x})$ 亦为随机变量。期望改进（Expected Improvement, EI）采集函数定义为改进量的期望值：

$$
    \alpha_{\text{EI}}(\mathbf{x}) = \mathbb{E}[I(\mathbf{x})] = \mathbb{E}\left[\max\left(\eta - |S(\mathbf{x}) - \theta|,\, 0\right)\right]
$$    (24)

**步骤3：变量替换化简——转化为可积形式。** 引入标准化变量 $u = (S(\mathbf{x}) - \mu_*)/\sigma_*$，定义偏移量 $m = \mu_* - \theta$。将EI的期望展开为关于 $S$ 的积分，利用变量替换 $S = \mu_* + u\sigma_*$：

$$
    \alpha_{\text{EI}}(\mathbf{x}) = \int_{-\infty}^{+\infty} \max\left(\eta - |\mu_* + u\sigma_* - \theta|,\, 0\right) \phi(u)\, du
$$    (25)

将积分按 $S$ 与 $\theta$ 的关系分为下侧区间和上侧区间，分别积分后相加（推导细节见附录C）。

**步骤4：核心结论导出——解析解。** 在对称化近似 $m = \mu_* - \theta \approx 0$（预测均值接近阈值）下，令 $z = \eta/\sigma_*$，利用标准正态分布的对称性化简得：

$$
    \boxed{\alpha_{\text{EI}}(\mathbf{x}) = \sigma_* \left[ z\, \Phi(z) + \phi(z) \right]}
$$    (26)

其中 $z = \eta / \sigma_*$，$\Phi(\cdot)$ 和 $\phi(\cdot)$ 分别为标准正态分布的CDF和PDF。该解析形式仅在预测均值接近阈值（$m = \mu_* - \theta \approx 0$）时严格成立。在算法实现中，本文始终使用完整的非对称公式（包含下侧区间和上侧区间的分别积分，见附录C），以确保在BO初始和中期阶段（$\mu_*$ 偏离 $\theta$ 较远时）采集函数的全局勘探能力不受损害。上述对称化形式仅用于物理意义阐释。

**步骤5：物理意义阐释。** 上述解析形式可揭示物理内涵：

$$
    \alpha_{\text{EI}}(\mathbf{x}) = \underbrace{\eta \Phi(z)}_{\text{开发项}} + \underbrace{\sigma_* \phi(z)}_{\text{勘探项}}
$$    (27)

- **开发项** $\eta\,\Phi(z)$：在预测值已接近边界的区域取值大，引导算法在已知边界附近精细搜索。
- **勘探项** $\sigma_*\phi(z)$：在模型不确定性高的区域取值大，引导算法主动探索未知区域。

两项的自动平衡使EI能够在已知边界区域和未知区域之间实现自适应权衡：初始阶段勘探项主导，算法全局搜索；后期阶段开发项主导，算法精细刻画边界。

#### 2.3.2 勘探-开发权衡与边界搜索的适配性

在传统全局优化中，EI采集函数的目标是最小化目标函数值。本文将其改造为边界搜索工具，核心区别在于改进量的定义方式：以 $|S(\mathbf{x}) - \theta|$ 替代 $S(\mathbf{x})$ 本身。这一改造使得EI同时关注两种有价值的区域：（i） $S(\mathbf{x}) \approx \theta$ 的边界附近区域（开发），以及（ii） 模型预测不确定性高的区域（勘探）。

相比之下，GP-UCB采集函数始终倾向于搜索预测值最大的区域而非接近阈值的区域，不适合边界搜索场景（详细比较见附录C）。

在每次BO迭代中，采集函数的全局优化采用多起点L-BFGS-B策略：从 $n_{\text{restart}} = 20$ 个随机初始点出发，分别进行局部优化，选取 $\alpha_{\text{EI}}$ 最大的点作为下一个仿真评估点。此外，为避免在已评估点附近重复采样，在采集函数中添加排斥惩罚项 $-\lambda \sum_{i=1}^N \exp(-\|\mathbf{x} - \mathbf{x}_i\|^2 / (2h^2))$，其中 $h$ 为排斥带宽参数。

#### 2.3.3 收敛准则

设第 $t$ 次BO迭代后，当前最优（最接近阈值的点）严重度为 $S_t^*$，定义收敛准则：

$$
    |S_t^* - \theta| < \epsilon_{\text{conv}}
$$    (28)

其中 $\epsilon_{\text{conv}}$ 为收敛容差。同时引入辅助收敛条件——最大迭代次数 $T_{\max}$ 和采集函数值衰减条件 $\max_{\mathbf{x}} \alpha_{\text{EI}}(\mathbf{x}) < \epsilon_{\alpha}$。当满足上述任一条件时终止BO循环，已找到足够接近安全边界的临界点。

### 2.4 仿射内逼近安全边界

#### 2.4.1 凸包构造与Quickhull算法

设安全点集为 $\mathcal{X}_{\text{safe}} = \{\mathbf{x}_1, \ldots, \mathbf{x}_{N_s}\}$，不安全点集为 $\mathcal{X}_{\text{unsafe}} = \{\mathbf{x}_{N_s+1}, \ldots, \mathbf{x}_{N_s+N_u}\}$。首先计算安全点的凸包（Convex Hull）：

$$
    \text{Conv}(\mathcal{X}_{\text{safe}}) = \left\{\sum_{i=1}^{N_s} \lambda_i \mathbf{x}_i \mid \lambda_i \geq 0, \sum \lambda_i = 1\right\}
$$    (29)

凸包计算采用Quickhull算法 [barber1996quickhull]，期望时间复杂度 $O(N_s \log N_s)$。算法细节见附录D。

凸包的每个面片（Facet）定义一个半空间约束 $\mathbf{A}_i^T \mathbf{x} \leq b_i$，凸包的边界表示为半空间交集：

$$
    \mathcal{P}_0 = \{\mathbf{x} \mid \mathbf{A}_h \mathbf{x} \leq \mathbf{b}_h\}
$$    (30)

其中 $\mathbf{A}_h \in \mathbb{R}^{F \times n}$，$F$ 为面片数。凸包表示安全点集的最小凸包络，其几何意义为：包含所有安全点的最小凸多面体，满足对安全点集的"外逼近"（Outer Approximation）。

然而，由于安全域 $\Omega_{\text{safe}}$ 通常是非凸的（暂态稳定约束下的安全域边界可能呈现凹入、缺口等非凸几何特征），凸包作为凸集必然会"过度包含"——在凹入区域，凸包会包含实际不安全的点。具体而言，若存在不安全点 $\mathbf{x}_u \in \mathcal{X}_{\text{unsafe}}$ 满足 $\mathbf{x}_u \in \text{Conv}(\mathcal{X}_{\text{safe}})$，则凸包对安全域的逼近存在"假阳性"（将不安全点误判为安全）。因此需要通过添加分离超平面将不安全点从凸包中排除，从而将凸包"切割"为更贴合真实安全域边界的内逼近多面体。

#### 2.4.2 线性规划分离超平面

**步骤1：物理模型建立。** 对于位于凸包内部或近旁的不安全点 $\mathbf{x}_u \in \mathcal{X}_{\text{unsafe}}$，需要构造分离超平面 $\mathbf{w}^T \mathbf{x} = d$（其中 $\mathbf{w} \in \mathbb{R}^n$ 为法向量，$d \in \mathbb{R}$ 为偏移量），使得不安全点位于超平面一侧（$\mathbf{w}^T \mathbf{x}_u > d$），而所有安全点位于另一侧（$\mathbf{w}^T \mathbf{x}_s < d$）。

**步骤2：基本方程列写。** 分离超平面的构造可形式化为如下优化问题：寻找 $(\mathbf{w}, d)$ 使得

$$
    \mathbf{w}^T \mathbf{x}_u - d \geq \gamma_u > 0 \quad (\text{不安全点位于正侧，距离超平面至少 } \gamma_u)
$$    (31)
$$
    \mathbf{w}^T \mathbf{x}_s - d \leq -\gamma_s < 0, \quad \forall \mathbf{x}_s \in \mathcal{X}_{\text{safe}} \quad (\text{安全点位于负侧，距离超平面至少 } \gamma_s)
$$    (32)

为保证分离的唯一性，对法向量进行归一化约束（等价于固定间隔宽度），取 $\gamma_u = 1$、$\gamma_s = \delta > 0$，得到如下线性规划问题：

$$
\begin{aligned}
    \min_{\mathbf{w}, d} \quad & \|\mathbf{w}\|_1 \\
    \text{s.t.} \quad & \mathbf{w}^T \mathbf{x}_u - d \geq 1 \\
    & \mathbf{w}^T \mathbf{x}_s - d \leq -\delta, \quad \forall \mathbf{x}_s \in \mathcal{X}_{\text{safe}}
\end{aligned}
$$    (33)

其中 $\delta > 0$ 为安全侧裕度（Safety Margin），确保安全点不会恰好位于新超平面上。目标函数采用 $\ell_1$ 范数最小化，其作用是实现超平面法向量的稀疏性（Sparsity），使分离超平面尽可能平行于坐标轴，提高边界表示的可解释性。

**步骤3：变量替换化简。** 上述LP问题可通过引入辅助变量转化为标准LP形式。令 $w_j = w_j^+ - w_j^-$（其中 $w_j^+, w_j^- \geq 0$），则 $\|\mathbf{w}\|_1 = \sum_j(w_j^+ + w_j^-)$。将约束中 $\mathbf{w}^T \mathbf{x} = \sum_j(w_j^+ - w_j^-)x_j$ 代入，得到纯线性目标和线性约束的标准LP，约束数为 $N_s + 1$，变量数为 $2n + 1$，可在多项式时间内求解。

**步骤4：核心结论。** LP求解所得超平面 $\mathbf{w}^T \mathbf{x} \leq d$ 经归一化（除以 $\|\mathbf{w}\|$）后加入边界约束集，将凸包 $\mathcal{P}_0$ 截断为 $\mathcal{P}_1 = \mathcal{P}_0 \cap \{\mathbf{x} \mid \mathbf{w}^T \mathbf{x} \leq d\}$，从而排除不安全点 $\mathbf{x}_u$。对每个不安全点重复执行此过程，最终得到AIA多面体 $\mathcal{P} = \mathcal{P}_0 \cap \bigcap_{u} \{\mathbf{x} \mid \mathbf{w}_u^T \mathbf{x} \leq d_u\}$。

该LP的可行域条件为：存在超平面将 $\mathbf{x}_u$ 与所有安全点严格分离。当可行域为空时的松弛策略见附录D。

#### 2.4.3 收缩裕度与冗余剪枝

为提高AIA边界的鲁棒性，在凸包面片和分离超平面上均施加收缩裕度 $\epsilon > 0$。具体而言，将半空间 $\mathbf{A}_i^T \mathbf{x} \leq b_i$ 修改为：

$$
    \mathbf{A}_i^T \mathbf{x} \leq b_i - \epsilon \|\mathbf{A}_i\|_2
$$    (34)

**推导过程：** 设超平面 $\mathbf{A}_i^T \mathbf{x} = b_i$ 的法向量为 $\mathbf{A}_i$，任意点 $\mathbf{x}$ 到该超平面的带符号距离为 $d_i(\mathbf{x}) = \frac{b_i - \mathbf{A}_i^T \mathbf{x}}{\|\mathbf{A}_i\|_2}$。将 $b_i$ 替换为 $b_i' = b_i - \epsilon\|\mathbf{A}_i\|_2$ 后，原超平面上各点到新超平面的距离为 $\frac{b_i' - b_i}{\|\mathbf{A}_i\|_2} = \frac{-\epsilon\|\mathbf{A}_i\|_2}{\|\mathbf{A}_i\|_2} = -\epsilon$，即新超平面沿法向量方向向内收缩了距离 $\epsilon$。由于收缩量为 $\epsilon$（而非 $\epsilon\|\mathbf{A}_i\|_2$），使用 $\epsilon\|\mathbf{A}_i\|_2$ 修正 $b_i$ 保证了各约束的收缩距离在几何上一致（不依赖于法向量的范数）。

收缩参数 $\epsilon$ 的选取需权衡安全性与保守性：$\epsilon$ 过大则安全域被过度收缩，可用运行空间显著减小；$\epsilon$ 过小则边界过于贴近安全/不安全分界线，可能因GP代理的预测误差导致不安全点被误判为安全点。本文推荐 $\epsilon \in [0.01, 0.05] \times \text{range}(\mathcal{X})$，并通过第4节的灵敏度分析验证其合理性。

冗余约束通过LP剪枝算法剔除（附录D）。

#### 2.4.4 Chebyshev中心与体积估计

AIA边界的Chebyshev中心为最大内接超球的球心，通过LP求解：

$$
\begin{aligned}
    \max_{\mathbf{c}, r} \quad & r \\
    \text{s.t.} \quad & \mathbf{A}_i^T \mathbf{c} + r \|\mathbf{A}_i\| \leq b_i, \quad \forall i
\end{aligned}
$$    (35)

其中 $\mathbf{c}$ 为球心，$r$ 为半径。该LP的物理意义为：在安全域内寻找最大球形邻域，其半径 $r$ 反映了当前运行方式到安全域边界的最短距离，即安全裕度（Security Margin）。Chebyshev中心可作为推荐运行方式提供给调度人员。

安全域体积通过Monte Carlo采样估计：

$$
    V \approx V_{\text{box}} \cdot \frac{1}{M} \sum_{j=1}^M \mathbb{1}[\mathbf{A} \mathbf{x}_j \leq \mathbf{b}]
$$    (36)

其中 $V_{\text{box}}$ 为包围盒体积，$M$ 为采样点数。为提高高维情形下的估计效率，本文采用基于PCA的降维体积估计方法（附录D）。

### 2.5 闭环融合框架

#### 2.5.1 算法框架

将GP代理、BO勘探和AIA边界构造整合为闭环迭代框架（算法1）。算法流程为：初始化阶段采用拉丁超立方采样（Latin Hypercube Sampling, LHS）生成 $N_0$ 个初始样本，通过时域仿真评估后分类为安全点和不安全点；迭代阶段每轮执行：(i) 更新GP代理模型，(ii) 基于EI采集函数选择新采样点并执行仿真，(iii) 更新安全/不安全点集，(iv) 重新构造AIA边界。当收敛准则满足或达到最大迭代次数时终止。

#### 2.5.2 收敛性保证

闭环框架的收敛性基于以下理论结果。

**命题1**（体积单调性）：每轮迭代后，安全域体积 $V^{(r)}$ 单调不减，即 $V^{(r+1)} \geq V^{(r)}$。证明思路：分析新采样点分别为安全点和不安全点两种情形下AIA边界的体积变化——安全点加入使凸包扩张（体积不减），不安全点触发分离超平面使边界紧化（体积略减但提高安全性），整体趋势为单调递增。该单调性保证了算法的稳定行为。详细证明见附录E。

**命题2**（安全性保持）：若初始安全点集满足 $S(\mathbf{x}, f) < \theta$ 对所有 $\mathbf{x} \in \mathcal{X}_{\text{safe}}^{(0)}$、$f \in \mathcal{F}$，且自适应收缩因子满足 $\epsilon^{(r)} \geq \alpha \cdot \sigma_{\max}^{(r)}$（$\alpha \geq 1$），则AIA边界内的任意点 $\mathbf{x}$ 满足 $S(\mathbf{x}, f) < \theta$ 的概率不低于 $1 - \alpha_{\epsilon}$，其中 $\alpha_{\epsilon}$ 由收缩裕度与置信缩放因子联合控制。安全性由三重机制保证：分离超平面排除已知不安全区域、自适应收缩裕度覆盖GP预测不确定性、BO采样密度降低漏检概率。详细说明见附录E。

**命题3**（渐近收敛性）：在GP先验正确指定的条件下，随着BO迭代次数 $T \to \infty$，AIA边界对真实安全域边界的逼近误差趋于零。论证基于三个条件的联合成立：GP代理的一致性（预测误差趋于零）、EI的稠密覆盖性（以概率1实现稠密采样）、凸包逼近的完备性（多面体收敛于真实边界）。详细证明见附录E。

上述三个命题为闭环框架的行为合理性提供了理论分析：体积单调性确保算法行为的稳定性，安全性保持为AIA边界的保守性提供了启发式论证（工程可用性），渐近收敛性在理想条件下确保算法的一致性。需要指出，命题2为基于三重机制的说明性论证而非严格证明，命题3依赖GP先验正确指定这一实际中难以严格验证的假设。
