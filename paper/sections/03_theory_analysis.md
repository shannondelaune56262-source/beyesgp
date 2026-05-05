## 2 理论分析

本节依次阐述多输出高斯过程代理模型（2.2节）、贝叶斯优化临界点勘探（2.3节）、仿射内逼近安全边界（2.4节）和闭环融合框架（2.5节）的数学基础，构建完整的方法论体系。

### 2.1 问题定义

安全域的数学定义为：

$$
    \Omega_{\text{safe}} = \{\bx \in \mathcal{X} \subset \mathbb{R}^n \mid S(\bx, f) < \theta, \forall f \in \mathcal{F}\}
$$

其中 $\bx$ 为 $n$ 维运行方式向量，$f$ 为故障场景，$S(\cdot)$ 为严重度函数，$\theta$ 为安全阈值，$\mathcal{F}$ 为故障集合。

直接通过仿真枚举 $\Omega_{\text{safe}}$ 的计算复杂度为 $O(|\mathcal{X}| \cdot |\mathcal{F}|)$，在高维空间中不可行。本文提出"代理模型+智能采样+边界逼近"三层架构，将复杂度降至 $O(N_{\text{BO}} \cdot |\mathcal{F}|)$，其中 $N_{\text{BO}} \ll |\mathcal{X}|$。

### 2.2 多输出高斯过程代理模型

#### 2.2.1 单输出GP先验

给定训练集 $\mathcal{D} = \{(\bx_i, y_i)\}_{i=1}^N$，GP先验假设函数值服从联合高斯分布：

$$
    \mathbf{y} | \mathbf{X} \sim \mathcal{N}(\mathbf{0}, K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I})
$$

其中 $K(\mathbf{X}, \mathbf{X})$ 为核矩阵（Kernel Matrix），元素 $K_{ij} = k(\bx_i, \bx_j)$，$\sigma_n^2$ 为观测噪声方差。

核函数采用Matérn 5/2核：

$$
    k(\bx, \bx') = \sigma_f^2 \left(1 + \frac{\sqrt{5}r}{\ell} + \frac{5r^2}{3\ell^2}\right) \exp\left(-\frac{\sqrt{5}r}{\ell}\right)
$$

其中 $r = \|\bx - \bx'\|_2$ 为欧氏距离，$\sigma_f^2$ 为信号方差（Signal Variance），$\ell$ 为长度尺度（Length Scale）。选择Matérn 5/2核而非径向基函数（Radial Basis Function, RBF）核的理由如下：RBF核对应无限可微的函数空间，其样本路径过于光滑，难以准确捕捉暂态稳定指标中可能存在的局部非光滑特征；而Matérn 5/2核对应的函数空间仅为二阶可微（$\nu = 5/2$），在保持足够光滑性的同时允许适度的局部变化，更符合电力系统暂态稳定指标的真实行为特性 [rasmussen2006gp]。此外，Matérn 5/2核的紧凑形式使其计算效率与RBF核相当，不会引入额外的计算负担。

核函数的超参数集合记为 $\boldsymbol{\theta}_{\text{GP}} = \{\sigma_f^2, \ell, \sigma_n^2\}$，通过最大化对数边际似然（Log Marginal Likelihood）进行优化：

$$
    \log p(\mathbf{y} | \mathbf{X}, \boldsymbol{\theta}_{\text{GP}}) = -\frac{1}{2}\mathbf{y}^T \mathbf{K}_y^{-1} \mathbf{y} - \frac{1}{2}\log|\mathbf{K}_y| - \frac{N}{2}\log 2\pi
$$

其中 $\mathbf{K}_y = K(\mathbf{X}, \mathbf{X}) + \sigma_n^2 \mathbf{I}$。上式第一项为数据拟合项，衡量模型对训练数据的拟合程度；第二项为复杂度惩罚项（Occam因子），自动避免过拟合。超参数优化采用L-BFGS-B算法，在给定梯度信息的条件下高效求解：

$$
    \frac{\partial}{\partial \theta_j} \log p(\mathbf{y} | \mathbf{X}, \boldsymbol{\theta}_{\text{GP}}) = \frac{1}{2}\text{tr}\left((\boldsymbol{\alpha}\boldsymbol{\alpha}^T - \mathbf{K}_y^{-1})\frac{\partial \mathbf{K}_y}{\partial \theta_j}\right)
$$

其中 $\boldsymbol{\alpha} = \mathbf{K}_y^{-1}\mathbf{y}$。为避免超参数优化陷入局部最优，采用多起点（Multi-start）策略，从10个随机初始化点出发选取最优解。

#### 2.2.2 GP后验推断与不确定性量化

给定新输入 $\bx_*$，后验预测分布为：

$$
    y_* | \bx_*, \mathcal{D} \sim \mathcal{N}(\mu_*, \sigma_*^2)
$$

其中：

$$
    \mu_* = \mathbf{k}_*^T (K + \sigma_n^2 \mathbf{I})^{-1} \mathbf{y}
$$

$$
    \sigma_*^2 = k(\bx_*, \bx_*) - \mathbf{k}_*^T (K + \sigma_n^2 \mathbf{I})^{-1} \mathbf{k}_*
$$

$\mathbf{k}_* = [k(\bx_1, \bx_*), \ldots, k(\bx_N, \bx_*)]^T$ 为新输入与训练集的核向量。上述预测公式的计算复杂度为 $O(N^2)$（利用Cholesky分解预计算 $\mathbf{K}_y^{-1}$），适用于中等规模训练集。

预测均值 $\mu_*$ 是训练观测值的核加权线性组合，权重由输入空间的相似度决定；预测方差 $\sigma_*^2$ 则提供了严格的不确定性量化（Uncertainty Quantification, UQ）。预测方差具有两个关键性质：（i）在训练数据密集的区域，$\sigma_*^2$ 较小，表明模型对该区域的预测具有较高置信度；（ii）在训练数据稀疏或远离训练集的区域，$\sigma_*^2$ 较大，表明模型预测不确定性高。这一性质是GP与贝叶斯优化（Bayesian Optimization, BO）之间建立桥梁的关键：BO的采集函数（Acquisition Function）正是利用 $\sigma_*$ 来驱动勘探（Exploration），主动探索模型不确定性高的区域。

#### 2.2.3 多输出独立架构与核心化方法比较

对功角稳定、频率稳定、电压稳定三个约束严重度分别建立独立GP模型：

$$
    \hat{f}_j(\bx) \sim \mathcal{GP}(\mu_j(\bx), \sigma_j^2(\bx)), \quad j \in \{a, f, v\}
$$

多输出GP的主流架构包括线性模型核心化（Linear Model of Coregionalization, LMC）和独立输出架构。LMC通过核心化矩阵（Coregionalization Matrix）$\mathbf{B}$ 建模输出之间的相关性，其联合核函数为 $k((\bx, j), (\bx', j')) = \sum_q k_q(\bx, \bx') \cdot B_{jj'}^q$。然而，LMC需要同时优化所有输出的超参数，计算复杂度为 $O(N^3 P^3)$（$P$ 为输出维度），且在输出间相关性较弱时性能提升有限 [alvarez2012kernel]。

本文采用独立输出架构（Independent Output Architecture），原因有三：（i）功角、频率、电压三个物理量表征不同的稳定机制，其函数形态差异显著，耦合建模可能引入虚假关联；（ii）独立架构的复杂度为 $O(N^3 P)$，可并行计算，适合高可再生能源渗透率场景下的大规模仿真需求；（iii）后续BO勘探需要独立控制各约束的不确定性传播，独立架构提供了更灵活的采样策略。

复合严重度的预测均值为各分量预测均值的加权和：

$$
    \hat{S}(\bx) = \omega_a \mu_a(\bx) + \omega_f \mu_f(\bx) + \omega_v \mu_v(\bx)
$$

其中权重 $\omega_a + \omega_f + \omega_v = 1$，由调度偏好或等权重方案确定。假设各输出独立，不确定性的传播为：

$$
    \sigma_S^2(\bx) = \omega_a^2 \sigma_a^2(\bx) + \omega_f^2 \sigma_f^2(\bx) + \omega_v^2 \sigma_v^2(\bx)
$$

式(2-1)表明复合不确定度为各分量不确定度的加权平方和。该性质意味着：(i) 权重越大的约束对总体不确定性贡献越大，因此BO应优先降低高权重约束在边界附近的不确定性；(ii) 任意一个约束的高不确定性即可导致复合不确定性增大，确保BO不会忽略任何维度的信息匮乏区域。

### 2.3 贝叶斯优化临界点勘探

#### 2.3.1 期望改进采集函数推导

在安全边界勘探任务中，目标并非传统BO中的全局最优化，而是发现严重度接近阈值 $\theta$ 的临界运行方式（Critical Operating Point）。定义边界距离函数：

$$
    d(\bx) = |S(\bx) - \theta|
$$

理想情况下，应寻找使 $d(\bx)$ 最小的 $\bx$，即位于安全边界上的点。由于 $S(\bx)$ 的真实值未知（需通过时域仿真获得），利用GP代理模型的后验分布对其进行估计。

给定当前最优（最接近阈值）的观测值对应的严重度 $\eta = \min_{i} |y_i - \theta|$，定义改进量（Improvement）为：

$$
    I(\bx) = \max\left(\eta - d(\bx),\, 0\right) = \max\left(\eta - |S(\bx) - \theta|,\, 0\right)
$$

由于GP后验给出的 $S(\bx)$ 服从高斯分布 $\mathcal{N}(\mu_*, \sigma_*^2)$，改进量 $I(\bx)$ 亦具有随机性。期望改进（Expected Improvement, EI）采集函数定义为：

$$
    \alpha_{\text{EI}}(\bx) = \mathbb{E}[I(\bx)] = \int_0^\infty I \cdot p(I | \bx) \, dI
$$

注意到 $|S(\bx) - \theta|$ 的分布在 $\mu_*$ 两侧不对称，需将问题转化为两个单侧EI的叠加。定义 $\mu_* - \theta$ 的符号情况，并引入标准化变量，经推导可得EI的解析表达式。在边界勘探的对称化处理下，最终得到：

$$
    \alpha_{\text{EI}}(\bx) = \sigma_* \left[ z\, \Phi(z) + \phi(z) \right]
$$

其中 $z = \eta / \sigma_*$（此处 $\eta$ 为当前最小边界距离），$\Phi(\cdot)$ 和 $\phi(\cdot)$ 分别为标准正态分布的累积分布函数（CDF）和概率密度函数（PDF）。

该解析形式的物理意义清晰：第一项 $z\, \Phi(z)$ 反映了预测均值接近边界的程度，称为**开发项**（Exploitation Term），在预测值已接近边界时取值大；第二项 $\sigma_* \phi(z)$ 反映了预测不确定性的大小，称为**勘探项**（Exploration Term），在模型不确定性高的区域取值大。两项的自动平衡使EI能够在已知边界区域和未知区域之间实现自适应权衡。

#### 2.3.2 勘探-开发权衡与边界搜索的适配性

在传统全局优化中，EI采集函数的目标是最小化目标函数值。本文将其改造为边界搜索工具，核心区别在于改进量的定义方式：以 $|S(\bx) - \theta|$ 替代 $S(\bx)$ 本身。这一改造使得EI同时关注两种有价值的区域：（i） $S(\bx) \approx \theta$ 的边界附近区域（开发），以及（ii） 模型预测不确定性高的区域（勘探）。

作为对比，GP-UCB（Gaussian Process Upper Confidence Bound）采集函数的形式为：

$$
    \alpha_{\text{UCB}}(\bx) = \mu_*(\bx) + \beta_t \, \sigma_*(\bx)
$$

其中 $\beta_t$ 为随迭代次数增长的调节参数。GP-UCB在纯优化场景中具有次线性遗憾界（Sublinear Regret Bound）的理论保证 [srinivas2010gaussian]，但在边界搜索中存在局限：UCB始终倾向于搜索预测值最大的区域，而非接近阈值的区域，需要额外设计双边界（上下界）搜索策略。相比之下，EI的改进量定义天然适配边界搜索，无需额外参数调节，因此本文选用EI作为主采集函数。

在每次BO迭代中，采集函数的全局优化采用多起点L-BFGS-B策略：从 $n_{\text{restart}} = 20$ 个随机初始点出发，分别进行局部优化，选取 $\alpha_{\text{EI}}$ 最大的点作为下一个仿真评估点。此外，为避免在已评估点附近重复采样，在采集函数中添加排斥惩罚项 $-\lambda \sum_{i=1}^N \exp(-\|\bx - \bx_i\|^2 / (2h^2))$，其中 $h$ 为排斥带宽参数。

#### 2.3.3 收敛准则

设第 $t$ 次BO迭代后，当前最优（最接近阈值的点）严重度为 $S_t^*$，定义收敛准则：

$$
    |S_t^* - \theta| < \epsilon_{\text{conv}}
$$

其中 $\epsilon_{\text{conv}}$ 为收敛容差。同时引入辅助收敛条件——最大迭代次数 $T_{\max}$ 和采集函数值衰减条件 $\max_{\bx} \alpha_{\text{EI}}(\bx) < \epsilon_{\alpha}$。当满足上述任一条件时终止BO循环，已找到足够接近安全边界的临界点。

### 2.4 仿射内逼近安全边界

#### 2.4.1 凸包构造与Quickhull算法

设安全点集为 $\mathcal{X}_{\text{safe}} = \{\bx_1, \ldots, \bx_{N_s}\}$，不安全点集为 $\mathcal{X}_{\text{unsafe}} = \{\bx_{N_s+1}, \ldots, \bx_{N_s+N_u}\}$。首先计算安全点的凸包（Convex Hull）：

$$
    \text{Conv}(\mathcal{X}_{\text{safe}}) = \left\{\sum_{i=1}^{N_s} \lambda_i \bx_i \mid \lambda_i \geq 0, \sum \lambda_i = 1\right\}
$$

凸包的计算采用Quickhull算法 [barber1996quickhull]，其核心思想为分治策略：从初始单纯形出发，逐步将位于当前凸包外部的点分配到最近的面片，并对该面片执行"可见性判断"和"地平线边"（Horizon Edge）检测，从而增量式地更新凸包。Quickhull的期望时间复杂度为 $O(N_s \log N_s)$（低维情形下），在本文涉及的 $n \leq 10$ 维空间中具有出色的实际性能。

凸包的每个面片（Facet）定义一个半空间约束 $\bA_i^T \bx \leq b_i$，凸包的边界表示为半空间交集：

$$
    \mathcal{P}_0 = \{\bx \mid \bA_h \bx \leq \bb_h\}
$$

其中 $\bA_h \in \mathbb{R}^{F \times n}$，$F$ 为面片数。凸包表示安全点集的最小凸包络，但在高维空间中，凸包的体积可能显著大于安全域的真实体积，导致不安全点被错误包含在凸包内部。因此需要通过添加分离超平面将不安全点排除。

#### 2.4.2 线性规划分离超平面

对于位于凸包内部或近旁的不安全点 $\bx_u \in \mathcal{X}_{\text{unsafe}}$，需要添加分离超平面将其排除。不同于直接利用凸包面片法向量，本文通过求解如下线性规划（Linear Programming, LP）问题，寻找最优分离超平面：

$$
\begin{aligned}
    \min_{\bw, d} \quad & \|\bw\|_1 \\
    \text{s.t.} \quad & \bw^T \bx_u - d \geq 1 \\
    & \bw^T \bx_s - d \leq -\delta, \quad \forall \bx_s \in \mathcal{X}_{\text{safe}}
\end{aligned}
$$

其中 $\delta > 0$ 为安全侧裕度（Safety Margin），确保安全点不会恰好位于新超平面上。目标函数采用 $\ell_1$ 范数最小化，其作用是实现超平面法向量的稀疏性（Sparsity），使分离超平面尽可能平行于坐标轴，提高边界表示的可解释性。上述LP问题的约束数为 $N_s + 1$，变量数为 $n + 1$，可在多项式时间内求解。

该LP的可行域条件为：存在超平面将 $\bx_u$ 与所有安全点严格分离。当安全点集包围不安全点时（即不安全点位于安全点凸包的内部），可行域可能为空。此时采用逐次松弛策略：首先移除约束 $\bw^T \bx_s - d \leq -\delta$ 中违反最严重的安全点，然后重新求解LP，直到获得可行解。所得超平面 $\bw^T \bx \leq d$ 经归一化后加入边界约束集。

#### 2.4.3 收缩裕度与冗余剪枝

为提高AIA边界的鲁棒性，在凸包面片和分离超平面上均施加收缩裕度 $\epsilon > 0$。具体而言，将半空间 $\bA_i^T \bx \leq b_i$ 修改为：

$$
    \bA_i^T \bx \leq b_i - \epsilon \|\bA_i\|_2
$$

收缩参数 $\epsilon$ 的选取需权衡安全性与保守性：$\epsilon$ 过大则安全域被过度收缩，可用运行空间显著减小；$\epsilon$ 过小则边界过于贴近安全/不安全分界线，可能因GP代理的预测误差导致不安全点被误判为安全点。本文推荐 $\epsilon \in [0.01, 0.05] \times \text{range}(\mathcal{X})$，并通过第4节的灵敏度分析验证其合理性。

随着迭代进行，边界约束集中可能包含冗余约束（Redundant Constraint），即去除该约束后AIA边界不发生变化的约束。冗余约束的存在会增加后续计算（如Chebyshev中心求解、Monte Carlo体积估计）的负担。本文采用如下冗余剪枝（Redundancy Pruning）算法：对每个约束 $i$，求解LP：

$$
\begin{aligned}
    \max_{\bx} \quad & \bA_i^T \bx \\
    \text{s.t.} \quad & \bA_j^T \bx \leq b_j, \quad \forall j \neq i
\end{aligned}
$$

若最优值 $\leq b_i$，则约束 $i$ 为冗余约束，予以剔除。剪枝过程按约束的法向量范数从小到大的顺序执行，优先检验"最可能冗余"的约束，提高剪枝效率。

#### 2.4.4 Chebyshev中心与体积估计

AIA边界的Chebyshev中心为最大内接超球的球心，通过LP求解：

$$
\begin{aligned}
    \max_{\mathbf{c}, r} \quad & r \\
    \text{s.t.} \quad & \bA_i^T \mathbf{c} + r \|\bA_i\| \leq b_i, \quad \forall i
\end{aligned}
$$

其中 $\mathbf{c}$ 为球心，$r$ 为半径。该LP的物理意义为：在安全域内寻找最大球形邻域，其半径 $r$ 反映了当前运行方式到安全域边界的最短距离，即安全裕度（Security Margin）。Chebyshev中心可作为推荐运行方式提供给调度人员。

安全域体积通过Monte Carlo采样估计：

$$
    V \approx V_{\text{box}} \cdot \frac{1}{M} \sum_{j=1}^M \mathbb{1}[\bA \bx_j \leq \bb]
$$

其中 $V_{\text{box}}$ 为包围盒体积，$M$ 为采样点数。当 $n$ 较大时，Monte Carlo方法的收敛速度较慢（标准差为 $O(1/\sqrt{M})$）。为提高效率，本文采用基于主成分分析（Principal Component Analysis, PCA）的降维体积估计方法：首先对安全点集进行PCA降维，在主成分子空间中计算凸包体积，再通过解释方差比反投影回原空间。该方法将有效维数从 $n$ 降至 $k \ll n$（通常 $k = 2$--$3$），显著提高了体积估计精度。

### 2.5 闭环融合框架

#### 2.5.1 算法框架

将GP代理、BO勘探和AIA边界构造整合为闭环迭代框架（算法1）。算法流程为：初始化阶段采用拉丁超立方采样（Latin Hypercube Sampling, LHS）生成 $N_0$ 个初始样本，通过时域仿真评估后分类为安全点和不安全点；迭代阶段每轮执行：(i) 更新GP代理模型，(ii) 基于EI采集函数选择新采样点并执行仿真，(iii) 更新安全/不安全点集，(iv) 重新构造AIA边界。当收敛准则满足或达到最大迭代次数时终止。

#### 2.5.2 收敛性保证

闭环框架的收敛性基于以下理论结果。

**命题1**（体积单调性）：每轮迭代后，安全域体积 $V^{(r)}$ 单调不减，即 $V^{(r+1)} \geq V^{(r)}$。

*证明*：第 $r+1$ 轮添加的新安全点集满足 $\mathcal{X}_{\text{safe}}^{(r+1)} \supseteq \mathcal{X}_{\text{safe}}^{(r)}$。由凸包的性质可知 $\text{Conv}(\mathcal{X}_{\text{safe}}^{(r+1)}) \supseteq \text{Conv}(\mathcal{X}_{\text{safe}}^{(r)})$，即凸包体积关于点集单调递增 [boyd2004convex]。AIA边界为凸包与分离半空间的交集，分离半空间仅作用于不安全点的排除，不减少凸包体积。此外，每轮迭代中GP代理模型的训练数据单调递增，边际似然单调不减，预测不确定性单调不增。因此 $V^{(r+1)} \geq V^{(r)}$。$\square$

该单调性保证了算法的稳定行为：安全域体积不会因新样本的加入而回缩，迭代过程始终朝着更完整的安全域描述方向演进。

**命题2**（安全性保持）：若初始安全点集满足 $S(\bx, f) < \theta$ 对所有 $\bx \in \mathcal{X}_{\text{safe}}^{(0)}$、$f \in \mathcal{F}$，则AIA边界内的任意点 $\bx$ 满足 $S(\bx, f) < \theta$ 的概率不低于 $1 - \alpha_{\epsilon}$，其中 $\alpha_{\epsilon}$ 为收缩裕度 $\epsilon$ 所控制的保守性水平。

*说明*：AIA边界是安全点凸包的内逼近（Inner Approximation），凸包内任一点均可表示为安全点的凸组合 $\bx = \sum_i \lambda_i \bx_i$。然而，严重度函数 $S(\cdot, f)$ 关于 $\bx$ 通常非凸（尤其在暂态稳定约束下），因此凸组合的安全性不能由端点的安全性直接推出。安全性由以下三重机制共同保证：(i) 分离超平面将已识别的不安全点及其邻域从安全域中排除；(ii) 收缩裕度 $\epsilon$ 在每个半空间约束上提供额外的保守边界，使AIA边界严格内缩于安全域边界；(iii) GP代理的预测不确定性被纳入BO采样策略，确保在不确定性高的区域增加采样密度，降低漏检不安全点的概率。严格的概率安全保证可通过GP预测的置信区间（如 $2\sigma$ 区间对应约 $95\%$ 置信度）与 $\epsilon$ 的联合选取实现。实际安全性通过第4节的大量仿真验证。

**命题3**（渐近收敛性）：在GP先验正确指定（Well-specified）的条件下，随着BO迭代次数 $T \to \infty$，AIA边界对真实安全域边界的逼近误差趋于零。

*论证*：GP代理的预测均方误差在稠密采样条件下收敛于零（一致性）[rasmussen2006gp]；EI采集函数在 $T \to \infty$ 时对输入空间实现稠密覆盖（由勘探项保证）[bull2011convergence]；当GP代理完全精确时，安全/不安全分类无误差，凸包+分离超平面所定义的多面体在点集加密下收敛于安全域的真实边界。需要指出，实际中由于仿真预算有限，算法在有限次迭代后终止，其逼近精度由第4节的数值实验评估。$\square$

上述三个命题共同构建了闭环框架的理论保证体系：体积单调性确保算法行为的稳定性，安全性保持确保AIA边界的保守性（工程可用性），渐近收敛性确保算法在理论上的一致性。
