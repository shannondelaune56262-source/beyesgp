## 摘要

高比例新能源并网使系统惯量降低、运行不确定性增大，现有安全边界辨识方法面临多约束耦合建模困难、高维采样效率不足和边界缺乏闭环反馈三方面挑战。提出基于多输出高斯过程（Gaussian Process, GP）、贝叶斯优化（Bayesian Optimization, BO）与仿射内逼近（Affine Inner Approximation, AIA）融合的闭环安全边界辨识方法：建立独立输出架构的多输出GP代理模型，同时预测功角、频率、电压三约束严重度；以期望改进（Expected Improvement, EI）采集函数引导BO定向勘探安全边界临界点；通过凸包与线性规划分离超平面构造仿射安全域多面体，并建立闭环迭代机制逐步紧化边界。提出运行方式空间物理分层策略，仅按新能源分布与渗透率等级进行场景聚类，使分场景传输限额具有明确的物理意义。在注入WECC标准新能源动态模型的Kundur两区域系统中，6510次仿真验证表明：GP代理模型综合严重度 $R^2$ 达0.579，BO评估次数减少46%，闭环3轮迭代后安全域体积增长超过50%且边界内安全率100%，联络线分场景传输限额较统一限额加权平均提升63.6%。

**关键词：** 高比例新能源；高斯过程；贝叶斯优化；仿射内逼近；安全边界；暂态稳定

**中图分类号：** TM712

---

## Abstract

High renewable energy (RE) penetration introduces substantial uncertainty into power system transient stability assessment, rendering deterministic methods inadequate for security boundary identification. This paper proposes a closed-loop security boundary identification framework fusing multi-output Gaussian process (GP), Bayesian optimization (BO), and affine inner approximation (AIA). The framework simultaneously predicts angle, frequency, and voltage severity via independent GP surrogates, uses BO with Expected Improvement to explore boundary-critical operating modes, and constructs polyhedral safe sets via convex hull and LP-based separating hyperplanes. A physical decomposition separates stability-determining factors (RE distribution and penetration level) from power-demanding factors (load levels), enabling scenario clustering on the 5D RE+sync subspace with load varying freely within each cluster. Applied to a Kundur two-area system with REGCA1/REECA1/REPCA1 RE models across 8-dimensional parameter space and 5 RE penetration levels, the method achieves per-constraint $R^2$ of 0.59--1.00, reduces BO evaluations by over 40% versus random search, and improves per-scenario transfer limits by 45%--89% over uniform limits (weighted average +63.6%).

**Keywords:** high renewable penetration; Gaussian process; Bayesian optimization; affine inner approximation; security boundary; transient stability
