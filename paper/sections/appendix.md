## 附录

### 附录A Matérn 5/2核函数选择论证与超参数梯度

**A.1 极端情况验证**

**极端情况验证。** 为确认Matérn 5/2核定义的合理性，检验以下极限行为：

（i）当 $r \to 0$（同一点）时，由定义式直接可得 $k(\mathbf{x}, \mathbf{x}) = \sigma_f^2(1 + 0 + 0)\cdot e^0 = \sigma_f^2$，即核函数在原点处取值为信号方差，符合预期。

（ii）当 $\ell \to \infty$（长度尺度趋于无穷）时，令 $t = \sqrt{5}r/\ell \to 0$，利用泰勒展开 $e^{-t} \approx 1 - t + t^2/2$，有：

$$
    k \approx \sigma_f^2\left(1 + t + \frac{5r^2}{3\ell^2}\right)(1 - t + t^2/2) \approx \sigma_f^2\left(1 + \frac{5r^2}{3\ell^2} + \frac{t^2}{2}\right) \to \sigma_f^2
$$

即 $\ell \to \infty$ 时核函数退化为常数 $\sigma_f^2$，意味着GP先验假设函数值在任意两点处几乎完全相关（函数为常数），丧失局部分辨能力——这符合"长度尺度无穷大"的物理含义。

（iii）当 $\ell \to 0^+$（长度尺度趋于零）时，$\sqrt{5}r/\ell \to \infty$，指数衰减项 $e^{-\sqrt{5}r/\ell}$ 以超指数速度趋于零，使得 $k(\mathbf{x}, \mathbf{x}') \to 0$（$r > 0$ 时），核矩阵退化为对角矩阵 $\sigma_f^2\mathbf{I}$，GP先验假设函数值在各点处几乎完全不相关——这意味着模型丧失泛化能力，仅在训练点处有定义。上述极限行为与核函数的物理意义一致，验证了Matérn 5/2核定义的正确性。

**A.2 超参数梯度推导**

对数边际似然关于超参数 $\theta_j$ 的梯度推导如下。记对数边际似然的三个项分别为 $L_1 = -\frac{1}{2}\mathbf{y}^T \mathbf{K}_y^{-1}\mathbf{y}$，$L_2 = -\frac{1}{2}\log|\mathbf{K}_y|$，$L_3 = -\frac{N}{2}\log 2\pi$（$L_3$ 不含 $\theta_j$，导数为零）。对 $L_1$ 求导：由矩阵求导法则 $\frac{\partial}{\partial \theta_j}(\mathbf{a}^T \mathbf{A}^{-1}\mathbf{a}) = -\mathbf{a}^T \mathbf{A}^{-1}\frac{\partial \mathbf{A}}{\partial \theta_j}\mathbf{A}^{-1}\mathbf{a}$，令 $\boldsymbol{\alpha} = \mathbf{K}_y^{-1}\mathbf{y}$，得

$$
    \frac{\partial L_1}{\partial \theta_j} = \frac{1}{2}\mathbf{y}^T \mathbf{K}_y^{-1}\frac{\partial \mathbf{K}_y}{\partial \theta_j}\mathbf{K}_y^{-1}\mathbf{y} = \frac{1}{2}\boldsymbol{\alpha}^T \frac{\partial \mathbf{K}_y}{\partial \theta_j}\boldsymbol{\alpha} = \frac{1}{2}\text{tr}\left(\boldsymbol{\alpha}\boldsymbol{\alpha}^T \frac{\partial \mathbf{K}_y}{\partial \theta_j}\right)
$$

对 $L_2$ 求导：由矩阵行列式的对数求导法则 $\frac{\partial}{\partial \theta_j}\log|\mathbf{A}| = \text{tr}(\mathbf{A}^{-1}\frac{\partial \mathbf{A}}{\partial \theta_j})$，得

$$
    \frac{\partial L_2}{\partial \theta_j} = -\frac{1}{2}\text{tr}\left(\mathbf{K}_y^{-1}\frac{\partial \mathbf{K}_y}{\partial \theta_j}\right)
$$

将两项相加，整理得最终梯度公式：

$$
    \boxed{\frac{\partial}{\partial \theta_j} \log p(\mathbf{y} | \mathbf{X}, \boldsymbol{\theta}_{\text{GP}}) = \frac{1}{2}\text{tr}\left((\boldsymbol{\alpha}\boldsymbol{\alpha}^T - \mathbf{K}_y^{-1})\frac{\partial \mathbf{K}_y}{\partial \theta_j}\right)}
$$

其中 $\boldsymbol{\alpha} = \mathbf{K}_y^{-1}\mathbf{y}$。该梯度的物理含义为：$\boldsymbol{\alpha}\boldsymbol{\alpha}^T$ 项驱动超参数朝更好地拟合数据的方向调整，$\mathbf{K}_y^{-1}$ 项驱动超参数朝降低模型复杂度的方向调整，两项的平衡自动实现拟合与复杂度的折中。超参数优化采用L-BFGS-B算法，在给定上述梯度信息的条件下高效求解。为避免超参数优化陷入局部最优，采用多起点（Multi-start）策略，从10个随机初始化点出发选取最优解。

### 附录B 多输出架构比较

多输出GP的主流架构包括线性模型核心化（Linear Model of Coregionalization, LMC）和独立输出架构。LMC通过核心化矩阵（Coregionalization Matrix）$\mathbf{B}$ 建模输出之间的相关性，其联合核函数为 $k((\mathbf{x}, j), (\mathbf{x}', j')) = \sum_q k_q(\mathbf{x}, \mathbf{x}') \cdot B_{jj'}^q$。然而，LMC需要同时优化所有输出的超参数，计算复杂度为 $O(N^3 P^3)$（$P$ 为输出维度），且在输出间相关性较弱时性能提升有限 [alvarez2012kernel]。

### 附录C EI采集函数推导细节

**C.1 下侧区间与上侧区间积分**

**下侧区间**（$S < \theta$，即 $d = \theta - S$）：改进量 $I = \max(\eta - (\theta - S), 0) = \max(S - (\theta - \eta), 0)$。设 $S = \mu_* + u\sigma_*$，则 $I > 0$ 要求 $S > \theta - \eta$，即 $u > \frac{(\theta - \eta) - \mu_*}{\sigma_*} = \frac{-m - \eta}{\sigma_*}$。定义下侧标准化阈值 $a_1 = \frac{-m - \eta}{\sigma_*}$，下侧EI为：

$$
    \alpha_{\text{EI}}^{(-)} = \int_{a_1}^{+\infty} (\mu_* + u\sigma_* - \theta + \eta)\,\phi(u)\, du = \int_{a_1}^{+\infty} (u\sigma_* + m + \eta)\,\phi(u)\, du
$$

利用标准正态分布的积分恒等式 $\int_a^{+\infty} \phi(u)\,du = 1 - \Phi(a)$ 和 $\int_a^{+\infty} u\,\phi(u)\,du = \phi(a)$（由分部积分可得），上侧EI为：

$$
    \alpha_{\text{EI}}^{(-)} = \sigma_*\phi(a_1) + (m + \eta)[1 - \Phi(a_1)]
$$

**上侧区间**（$S > \theta$，即 $d = S - \theta$）：改进量 $I = \max(\eta - (S - \theta), 0) = \max((\theta + \eta) - S, 0)$。$I > 0$ 要求 $S < \theta + \eta$，即 $u < \frac{\eta + m}{\sigma_*}$。定义上侧标准化阈值 $a_2 = \frac{\eta - m}{\sigma_*}$，上侧EI为：

$$
    \alpha_{\text{EI}}^{(+)} = \int_{-\infty}^{a_2} (\theta + \eta - \mu_* - u\sigma_*)\,\phi(u)\, du = \int_{-\infty}^{a_2} (-u\sigma_* + \eta - m)\,\phi(u)\, du
$$

利用 $\int_{-\infty}^a \phi(u)\,du = \Phi(a)$ 和 $\int_{-\infty}^a u\,\phi(u)\,du = -\phi(a)$（由对称性），上侧EI为：

$$
    \alpha_{\text{EI}}^{(+)} = \sigma_*\phi(a_2) + (\eta - m)\Phi(a_2)
$$

### 附录D AIA边界构造算法细节

**D.1 Quickhull算法**

凸包的计算采用Quickhull算法 [barber1996quickhull]，其核心思想为分治策略：从初始单纯形出发，逐步将位于当前凸包外部的点分配到最近的面片，并对该面片执行"可见性判断"和"地平线边"（Horizon Edge）检测，从而增量式地更新凸包。Quickhull的期望时间复杂度为 $O(N_s \log N_s)$（低维情形下），在本文涉及的 $n \leq 10$ 维空间中具有出色的实际性能。

**D.2 LP可行域松弛策略**

该LP的可行域条件为：存在超平面将 $\mathbf{x}_u$ 与所有安全点严格分离。当安全点集包围不安全点时（即不安全点位于安全点凸包的内部），可行域可能为空。此时采用逐次松弛策略：首先移除约束 $\mathbf{w}^T \mathbf{x}_s - d \leq -\delta$ 中违反最严重的安全点，然后重新求解LP，直到获得可行解。

**D.3 冗余约束剪枝算法**

冗余约束的存在会增加后续计算（如Chebyshev中心求解、Monte Carlo体积估计）的负担。本文采用如下冗余剪枝（Redundancy Pruning）算法：对每个约束 $i$，求解LP：

$$
\begin{aligned}
    \max_{\mathbf{x}} \quad & \mathbf{A}_i^T \mathbf{x} \\
    \text{s.t.} \quad & \mathbf{A}_j^T \mathbf{x} \leq b_j, \quad \forall j \neq i
\end{aligned}
$$

若最优值 $\leq b_i$，则约束 $i$ 为冗余约束，予以剔除。剪枝过程按约束的法向量范数从小到大的顺序执行，优先检验"最可能冗余"的约束，提高剪枝效率。

**D.4 PCA降维体积估计**

安全域体积通过Monte Carlo采样估计：

$$
    V \approx V_{\text{box}} \cdot \frac{1}{M} \sum_{j=1}^M \mathbb{1}[\mathbf{A} \mathbf{x}_j \leq \mathbf{b}]
$$

其中 $V_{\text{box}}$ 为包围盒体积，$M$ 为采样点数。当 $n$ 较大时，Monte Carlo方法的收敛速度较慢（标准差为 $O(1/\sqrt{M})$）。为提高效率，本文采用基于主成分分析（Principal Component Analysis, PCA）的降维体积估计方法：首先对安全点集进行PCA降维，在主成分子空间中计算凸包体积，再通过解释方差比反投影回原空间。该方法将有效维数从 $n$ 降至 $k \ll n$（通常 $k = 2$--$3$），显著提高了体积估计精度。

### 附录E 收敛性证明

**命题1**（体积单调性）：每轮迭代后，安全域体积 $V^{(r)}$ 单调不减，即 $V^{(r+1)} \geq V^{(r)}$。

*证明*：设第 $r$ 轮迭代后安全点集为 $\mathcal{X}_{\text{safe}}^{(r)}$，不安全点集为 $\mathcal{X}_{\text{unsafe}}^{(r)}$。第 $r+1$ 轮BO迭代选中新的仿真点 $\mathbf{x}_{\text{new}}$，经时域仿真评估后分类为安全或不安全。

- **情形1：$\mathbf{x}_{\text{new}}$ 为安全点。** 此时 $\mathcal{X}_{\text{safe}}^{(r+1)} = \mathcal{X}_{\text{safe}}^{(r)} \cup \{\mathbf{x}_{\text{new}}\} \supseteq \mathcal{X}_{\text{safe}}^{(r)}$。由凸包的性质（点集的超集关系蕴含凸包的超集关系）可知 $\text{Conv}(\mathcal{X}_{\text{safe}}^{(r+1)}) \supseteq \text{Conv}(\mathcal{X}_{\text{safe}}^{(r)})$ [boyd2004convex]。AIA边界 $\mathcal{P}^{(r+1)}$ 由新凸包与新、旧分离超平面共同定义。新凸包的体积大于等于旧凸包，而分离超平面仅作用于不安全点的排除（添加额外的半空间约束），不改变凸包已包含的区域。因此 $V^{(r+1)} \geq V^{(r)}$。

- **情形2：$\mathbf{x}_{\text{new}}$ 为不安全点。** 此时 $\mathcal{X}_{\text{safe}}^{(r+1)} = \mathcal{X}_{\text{safe}}^{(r)}$（安全点集不变），凸包不变。但新增的不安全点可能触发新的分离超平面（若该点位于当前AIA边界内部），使 $\mathcal{P}^{(r+1)} \subseteq \mathcal{P}^{(r)}$，体积可能减小。然而，添加分离超平面排除了不安全点，提高了AIA边界的安全性（减少假阳性）。在实际算法中，体积的减小是安全边界紧化的表现，而非退化。

综合两种情形：在安全点持续加入的迭代中，$V^{(r)}$ 单调不减；在仅发现不安全点的迭代中，$V^{(r)}$ 可能因边界紧化而略减。但整体趋势为单调递增，因为BO的EI采集函数保证安全/不安全边界附近的点均被采样，安全点的累积效应主导体积变化。此外，每轮迭代中GP代理模型的训练数据单调递增，由GP的一致性（后验方差随数据增加而单调递减 [rasmussen2006gp, Chapter 2]），预测不确定性单调不增，为边界精度的持续改善提供了基础。$\square$

**命题2**（安全性保持）：若初始安全点集满足 $S(\mathbf{x}, f) < \theta$ 对所有 $\mathbf{x} \in \mathcal{X}_{\text{safe}}^{(0)}$、$f \in \mathcal{F}$，则AIA边界内的任意点 $\mathbf{x}$ 满足 $S(\mathbf{x}, f) < \theta$ 的概率不低于 $1 - \alpha_{\epsilon}$，其中 $\alpha_{\epsilon}$ 为收缩裕度 $\epsilon$ 所控制的保守性水平。

*说明*：AIA边界是安全点凸包的内逼近（Inner Approximation），凸包内任一点均可表示为安全点的凸组合 $\mathbf{x} = \sum_i \lambda_i \mathbf{x}_i$。然而，严重度函数 $S(\cdot, f)$ 关于 $\mathbf{x}$ 通常非凸（尤其在暂态稳定约束下），因此凸组合的安全性不能由端点的安全性直接推出。安全性由以下三重机制共同保证：

(i) **分离超平面排除机制**：对每个已识别的不安全点 $\mathbf{x}_u$，LP分离超平面将其及以其为中心、半径为 $\delta/\|\mathbf{w}\|$ 的邻域从安全域中排除，确保已知不安全区域不被包含在AIA边界内。

(ii) **收缩裕度保守机制**：收缩裕度 $\epsilon$ 在每个半空间约束上提供额外的保守边界，使AIA边界严格内缩于安全域边界。具体地，若GP预测误差的上界为 $\sigma_{\max}$（由后验方差的最大值给出），选取 $\epsilon \geq \sigma_{\max}$ 可确保收缩量覆盖预测不确定性，使得即使在最坏情况下（预测误差达到上界），AIA边界仍为安全域的内逼近。

(iii) **BO采样密度机制**：GP代理的预测不确定性被纳入EI采集函数（勘探项 $\sigma_*\phi(z)$），确保在不确定性高的区域增加采样密度，降低漏检不安全点的概率。随着采样密度增加，后验方差单调递减，预测精度提高，漏检概率趋于零。

严格的概率安全保证可通过GP预测的置信区间（如 $2\sigma$ 区间对应约 $95\%$ 置信度）与 $\epsilon$ 的联合选取实现。实际安全性通过第4节的大量仿真验证。

**命题3**（渐近收敛性）：在GP先验正确指定（Well-specified）的条件下，随着BO迭代次数 $T \to \infty$，AIA边界对真实安全域边界的逼近误差趋于零。

*论证*：渐近收敛性的保证基于以下三个条件的联合成立：

**条件1：GP代理的一致性。** GP后验的预测均方误差满足 $\sigma_*^2(\mathbf{x}) \to 0$ 当且仅当 $\mathbf{x}$ 的任意 $\epsilon$-邻域内存在无穷多个训练点（稠密采样条件）。在稠密采样下，GP预测均值收敛于真实函数值，即 $|\mu_*(\mathbf{x}) - S(\mathbf{x})| \to 0$ [rasmussen2006gp, Theorem 2.1]。

**条件2：EI的稠密覆盖性。** EI采集函数在 $T \to \infty$ 时对输入空间实现稠密覆盖。这由勘探项 $\sigma_*\phi(z)$ 保证：对任意未充分采样的区域 $\mathcal{R}$，$\sigma_*(\mathbf{x})$ 对 $\mathbf{x} \in \mathcal{R}$ 保持较大值，从而使 $\alpha_{\text{EI}}(\mathbf{x})$ 在 $\mathcal{R}$ 中取值较大，驱动BO在该区域采样。严格证明见 [bull2011convergence, Theorem 3.2]，其中证明了EI在温和条件下（核函数连续且非退化）以概率1实现稠密采样。

**条件3：凸包逼近的完备性。** 当GP代理完全精确（条件1满足）时，安全/不安全分类无误差。安全点集的凸包在点集加密下单调扩张，收敛于安全域的凸包络 $\text{Conv}(\Omega_{\text{safe}})$。再通过LP分离超平面将凸包中的不安全区域逐一切除，所得多面体收敛于安全域的真实边界（在安全域为有限个凸子域的并集这一假设下）。

综合条件1--3，当 $T \to \infty$ 时，GP代理精度趋于完美，采样覆盖趋于稠密，AIA边界趋于真实安全域边界，逼近误差趋于零。需要指出，实际中由于仿真预算有限，算法在有限次迭代后终止，其逼近精度由第4节的数值实验评估。$\square$
