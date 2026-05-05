## 算法1 GP+BO+AIA闭环融合安全边界辨识算法
**Algorithm 1: GP+BO+AIA Closed-loop Security Boundary Identification**

---

**输入**：运行方式参数空间 $\mathcal{X}$，故障集 $\mathcal{F}$，严重度阈值 $\theta=0.6$，迭代轮数 $R=3$

**输出**：分场景AIA安全边界 $\mathcal{P}_{f,k} = \{\mathbf{x} \mid \mathbf{A}\mathbf{x} \leq \mathbf{b}\}$

---

1. **初始化**：通过LHS在 $\mathcal{X} \subset \mathbb{R}^7$ 中生成 $N_0$ 个初始运行方式样本
2. 对每个样本 $\mathbf{x}_i$ 和每个故障 $f_j \in \mathcal{F}$，执行ANDES暂态仿真，计算严重度指标：

$$S(\mathbf{x}_i, f_j) = 0.4 \cdot f_{\text{angle}}(\mathbf{x}_i, f_j) + 0.3 \cdot f_{\text{freq}}(\mathbf{x}_i, f_j) + 0.3 \cdot f_{\text{voltage}}(\mathbf{x}_i, f_j)$$

3. 基于运行方式特征（风电/光伏占比、负荷水平、出力分配偏差）对样本进行 $K$-means聚类，将样本分为 $K$ 个运行场景组
4. **FOR** 每个场景 $(f_j, k)$，$j=1,\ldots,|\mathcal{F}|$，$k=1,\ldots,K$：
   - (a) 划分安全集 $\mathcal{X}_{\text{safe}} = \{\mathbf{x} \mid S(\mathbf{x}, f_j) < \theta\}$ 和不安全集 $\mathcal{X}_{\text{unsafe}}$
   - (b) 计算初始AIA边界 $\mathcal{P}$：安全点凸包 → LP分离超平面 → 收缩 $\epsilon$ → 冗余面剪枝
5. 训练多输出GP代理模型 $\hat{S}(\mathbf{x})$，同时预测 $f_{\text{angle}}$、$f_{\text{freq}}$、$f_{\text{voltage}}$ 三个约束指标
6. **FOR** $r = 1, \ldots, R$（闭环迭代）：
   - **FOR** 每个场景 $(f_j, k)$：
     - (a) 寻找边界薄弱点：$\mathbf{x}_{\text{weak}} = \arg\min_{\mathbf{x} \in \mathcal{X}_{\text{safe}}} \text{margin}(\mathbf{x}, \mathcal{P})$
     - (b) 基于GP代理 $\hat{S}$ 和EI采集函数，在 $\mathbf{x}_{\text{weak}}$ 邻域执行BO定向搜索，获取 $N_{\text{new}}$ 个候选点
     - (c) 通过ANDES仿真评价新点，按严重度更新 $\mathcal{X}_{\text{safe}}$ 和 $\mathcal{X}_{\text{unsafe}}$
     - (d) 重新计算AIA边界 $\mathcal{P}^{(r)}$
   - 重新训练GP代理模型 $\hat{S}$
   - 记录第 $r$ 轮安全域体积 $V^{(r)}$ 和安全率
7. 将AIA边界映射为分场景传输容量限额

**RETURN** 分场景安全边界 $\{\mathcal{P}_{f,k}\}$ 及对应传输容量限额
