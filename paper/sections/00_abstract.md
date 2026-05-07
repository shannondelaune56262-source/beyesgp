## 摘要

高比例新能源并网使系统惯量降低、运行不确定性增大，现有安全边界辨识方法面临多约束并发建模困难、高维采样效率不足和边界缺乏闭环反馈三方面挑战。提出基于多输出高斯过程（GP）、贝叶斯优化（BO）与仿射内逼近（AIA）融合的闭环安全边界辨识方法：独立输出架构的多输出GP代理模型分别预测功角、频率、电压三约束严重度并通过熵权法复合为统一指标；以期望改进采集函数引导BO定向勘探安全边界临界点；通过凸包与线性规划分离超平面构造仿射安全域多面体，结合自适应收缩因子机制闭环迭代逐步紧化边界。在Kundur两区域系统中经1302次仿真验证，分场景传输限额较统一限额加权平均提升63.6%，安全率经时域仿真验证为100%。在IEEE 39节点10机系统上的可扩展性验证进一步确认框架可无修改扩展至更大规模系统。

**关键词：** 高比例新能源；高斯过程；贝叶斯优化；仿射内逼近；安全边界；暂态稳定

**中图分类号：** TM712

---

## Abstract

High renewable energy penetration introduces substantial uncertainty into power system transient stability assessment. This paper proposes a closed-loop security boundary identification framework fusing multi-output Gaussian process (GP), Bayesian optimization (BO), and affine inner approximation (AIA). The framework predicts angle, frequency, and voltage severity via independent GP surrogates with entropy-weighted composite severity, uses BO with Expected Improvement to explore boundary-critical operating modes, and constructs polyhedral safe sets via convex hull and LP-based separating hyperplanes with an adaptive shrinkage factor for closed-loop refinement. Validated on a Kundur two-area system with 1,302 time-domain simulations, the method achieves per-scenario transfer limit improvements of 45%--89% over uniform limits (weighted average +63.6%) with 100% safety rate. Scalability validation on the IEEE 39-bus 10-machine system confirms the framework extends without modification to larger systems.

**Keywords:** high renewable penetration; Gaussian process; Bayesian optimization; affine inner approximation; security boundary; transient stability
