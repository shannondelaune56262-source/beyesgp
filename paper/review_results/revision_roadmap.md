# Revision Roadmap

Auto-generated from deep-review on 2026-05-07.

## Phase 1: Submission Blockers (Must Fix Before Any Review)

### 1. Fill Tables 4-7 (ISS-001)
- **Files:** `tables/tab4_gp_accuracy.tex`, `tab5_bo_efficiency.tex`, `tab6_aia_boundary.tex`, `tab7_transfer_limits.tex`
- **Action:** Replace all `---` entries with actual experimental data
- **Verification:** Each table renders with complete numerical entries

### 2. Add missing bib entry (ISS-002)
- **File:** `references.bib`
- **Action:** Add `vittal2022re_stability` entry (or replace the \cite with an existing key)
- **Verification:** `grep -c "vittal2022re_stability" references.bib` returns ≥ 1

## Phase 2: Major Revisions

### 3. Revise Proposition 2 (ISS-004)
- **File:** `sections/03_theory_analysis.tex`
- **Action:** Change "证明" to "说明" for non-convex case; add conditions for formal guarantee; reference empirical validation
- **Suggested rewrite:** "命题2（安全性保证）：... 说明：当$S(\cdot)$为凸函数时，凸组合的安全性由Jensen不等式直接保证。对于非凸$S(\cdot)$，AIA的安全性由以下机制联合保障：(i) 分离超平面排除已知不安全点；(ii) 收缩裕度$\epsilon$提供边界缓冲；(iii) 仿真交叉验证确保边界内安全率100%。"

### 4. Fix numerical range (ISS-006)
- **Files:** `sections/00_abstract.tex`, `sections/06_conclusion.tex`
- **Action:** Update "15%--73%" to match actual data range (e.g., "15%--88%" or "63.6%加权平均")
- **Verification:** All three locations (abstract, simulation, conclusion) use consistent numbers

### 5. Rename citation keys (ISS-003)
- **Files:** `references.bib`, all `.tex` files with `\cite{}`
- **Action:** Rename 13+ keys to match first author
- **Mapping:**
  - `wang2023gp_transient` → `ye2023sparse_gp` (already exists!) — deduplicate
  - `chen2024mogp_voltage` → `liu2020scalable_gp`
  - `li2024bo_scenario` → `han2018surrogate_var`
  - `zhang2023bo_renewable` → `liu2020bayesian_security`
  - `liu2023security_region` → `yu2020security_region`
  - `liu2023inertia_re` → `hu2023inertia_re`
  - `wang2024voltage_re` → `murray2021voltage_control`
  - `sun2023clustering_security` → `liu2018fast_scanning`
  - `guo2024tiered_limit` → `wang2021sparse_pce`
  - `shahidinejad2024gp_bo_transient` → `palm2022gp_bo`
  - `li2021ensemble_severity` → `sarajcev2021ensemble`
  - `xu2023transfer_gp` → `li2023adaptive_transfer`

## Phase 3: Moderate Fixes

### 6. Fix BO bound citation (ISS-005)
- Add: `@article{srinivas2010gp_ucb, author={Srinivas, N. and Krause, A. and Kakade, S. and Seeger, M.}, title={Gaussian process optimization in the bandit setting}, journal={ICML}, year={2010}}`
- Update `\cite{frazier2018bo_tutorial}` to `\cite{srinivas2010gp_ucb}` at eq:bo_bound

### 7. Qualify equal-replacement claim (ISS-008)
- Change "准确反映了" to "保守地近似了"
- Add: "本文假设新能源设备采用跟网型控制(REGCA1 PFFLAG=1)，不提供惯量支撑，代表当前主流新能源并网方式的最保守场景。"

### 8. Justify θ=0.6 (ISS-009)
- Add 1-2 sentences: "θ=0.6的选取基于IEEE Std 1547和相关工程实践...灵敏度分析表明θ在0.5-0.7范围内结论稳定。"

### 9. Align Table 5 with text (ISS-010)
- Expand Table 5 to include all 5 methods or clarify which methods are compared in text vs table

### 10. Add single-output GP baseline (ISS-013)
- Add one row to Table 4 comparing single-output GP R² vs MOGP R²

## Phase 4: Minor Polish

### 11. Renumber propositions (ISS-007)
### 12. Clarify MOGP naming (ISS-014)
### 13. English abstract grammar (ISS-016)
### 14. Consider merging Section 3 into Section 2 (ISS-015)
