## 摘要

高比例新能源并网导致电力系统呈现"双高"特征（高电力电子化、高不确定性），传统基于确定性场景的暂态稳定评估方法难以有效覆盖多维运行空间，亟需建立高效的运行安全边界辨识方法。

现有安全边界辨识方法面临三方面挑战：运行方式空间维度高导致计算代价大；多约束（功角/频率/电压）耦合导致单一代理模型精度不足；边界辨识与采样策略缺乏闭环反馈，边界质量难以保证。

本文提出基于高斯过程代理模型（GP）、贝叶斯优化（BO）与仿射内逼近（AIA）融合的闭环安全边界辨识框架。首先，建立多输出GP代理模型，同时预测功角、频率、电压三约束严重度，采用Matérn 5/2核函数与独立输出架构；其次，以期望改进（EI）为采集函数，引导BO在安全边界附近定向勘探临界运行方式；然后，基于安全/不安全点集构造仿射内逼近多面体 $\mathcal{P}=\{\mathbf{x}|\mathbf{A}\mathbf{x}\leq\mathbf{b}\}$，通过凸包计算与线性规划分离超平面实现安全域的仿射内逼近；最后，建立"BO勘探$\to$AIA边界$\to$GP验证$\to$薄弱点辨识$\to$BO定向搜索"的闭环迭代机制，逐步紧化安全边界。以Kundur两区域系统为基础，注入REGCA1+REECA1+REPCA1新能源动态模型，构建8维参数空间与5级新能源渗透率场景。

在186个可行运行方式$\times$7种异构故障$\times$5级渗透率共6510次仿真中，所提方法实现了：多输出GP代理模型功角约束 $R^2$ 达0.748，频率约束达0.591，电压约束近1.0；BO较随机搜索评估次数减少40%以上；闭环3轮迭代后安全域体积增长15%以上，边界内安全率保持100%；分场景传输容量限额较统一限额提升15%$\sim$73%。

**关键词：** 高比例新能源；高斯过程；贝叶斯优化；仿射内逼近；安全边界；暂态稳定

**中图分类号：** TM712

---

## Abstract

High renewable energy (RE) penetration introduces significant uncertainty into power system transient stability assessment. This paper proposes a closed-loop security boundary identification framework fusing multi-output Gaussian process (GP), Bayesian optimization (BO), and affine inner approximation (AIA). The framework simultaneously predicts angle, frequency, and voltage severity via independent GP surrogates, uses BO with Expected Improvement to explore boundary-critical operating modes, and constructs polyhedral safe sets via convex hull and LP-based separating hyperplanes. Applied to a Kundur two-area system with REGCA1/REECA1/REPCA1 RE models across 8-dimensional parameter space and 5 RE penetration levels, the method achieves per-constraint $R^2$ of 0.59--1.00 and composite severity $R^2 = 0.58$, reduces BO evaluations by over 40% versus random search, and improves per-scenario transfer limits by 15%--73% over uniform limits.

**Keywords:** high renewable penetration; Gaussian process; Bayesian optimization; affine inner approximation; security boundary; transient stability
