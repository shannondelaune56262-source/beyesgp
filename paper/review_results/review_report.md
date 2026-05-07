# Deep Review Report

**Paper:** 基于高斯过程与仿射内逼近的高比例新能源电网安全边界辨识
**Date:** 2026-05-07
**Mode:** deep-review (5-role Academic Pre-Review Committee)

---

## Overall Assessment

This paper proposes a closed-loop framework combining multi-output Gaussian process (MOGP), Bayesian optimization (BO), and affine inner approximation (AIA) for security boundary identification in high renewable penetration power systems. The technical approach is sound in concept, and the integration of BO for worst-case scenario search is a meaningful contribution. However, the manuscript has **critical gaps** that must be addressed before submission: four simulation tables are empty shells, a bibliography entry is missing, the safety proof is incomplete, and citation keys do not match authors. Additionally, several quantitative claims in the text cannot be verified against the presented evidence.

**Issue counts:** 5 major, 7 moderate, 4 minor

---

## Major Issues

### MAJ-1: Tables 4-7 are empty placeholder shells
- **Source:** [Script] `tables/tab4_gp_accuracy.tex`, `tab5_bo_efficiency.tex`, `tab6_aia_boundary.tex`, `tab7_transfer_limits.tex`
- **Location:** Simulation section (Tables 4-7)
- **Detail:** All four tables contain only `---` entries. The simulation text makes specific numerical claims (R² > 0.85, +88.4%, +63.6%, 100% safety rate) that should be backed by these tables. Without data, the paper's core validation is unverifiable.
- **Fix:** Populate all tables with experimental data. If data is not yet available from experiments, generate it before submission.

### MAJ-2: Missing bibliography entry `vittal2022re_stability`
- **Source:** [Script] `01_introduction.tex` L5
- **Detail:** The introduction's opening paragraph cites `\cite{vittal2022re_stability}` but this key does not exist in `references.bib`. This will produce `[?]` in the compiled PDF.
- **Fix:** Add the corresponding bib entry. Suggested replacement: the IEEE/CIGRE stability classification paper (Hatziargyriou et al., 2021) already cited as `hatziargyriou2020severity`, or find an appropriate Vittal-authored paper on RE stability.

### MAJ-3: Citation keys mismatch actual authors in 13+ entries
- **Source:** [LLM] `references.bib` full file
- **Detail:** The bib header admits references were "replaced with real, verified papers" but keys were not updated. Examples:
  - `wang2023gp_transient` → Ye, Ketian et al.
  - `chen2024mogp_voltage` → Liu, Haitao et al.
  - `li2024bo_scenario` → Han, Tong et al.
  - `zhang2023bo_renewable` → Liu, Tingjian et al.
  - `guo2024tiered_limit` → Wang, Xiaoting et al.
  - `shahidinejad2024gp_bo_transient` → Palm, Nicolai et al.
- **Impact:** Readers and reviewers who check references will find author mismatches, raising credibility concerns.
- **Fix:** Rename all citation keys to match first author + year. Update all `\cite{}` references throughout the paper.

### MAJ-4: Proposition 2 safety proof is logically incomplete
- **Source:** [LLM] `03_theory_analysis.tex` L252-254
- **Detail:** The paper acknowledges S(·) is non-convex, then claims AIA safety via (i) separating hyperplanes and (ii) epsilon margin. However, for non-convex S, a convex combination of safe points can have S > θ. The "proof" actually relies on empirical verification (100% safety rate in simulation), which is a different type of guarantee.
- **Fix:** Either (a) relabel Proposition 2 as "Empirically Validated Safety Conjecture" with proper caveats, or (b) add conditions under which the AIA safety can be formally proven (e.g., Lipschitz continuity + appropriate epsilon bound).

### MAJ-5: Transfer limit improvement range contradicts simulation data
- **Source:** [LLM] Abstract/Conclusion vs Simulation section
- **Detail:** Abstract and conclusion state "提升15%--73%" but simulation reports C0 at +88.4%, which exceeds the 73% upper bound. The 73% figure appears nowhere in the simulation section.
- **Fix:** Update range in abstract and conclusion to match simulation data, or clarify what the 73% figure represents.

---

## Moderate Issues

### MOD-1: BO convergence bound cites wrong source (ISS-005)
- **Location:** `03_theory_analysis.tex` L126
- **Detail:** The γ_T bound for Matérn kernels is from Srinivas et al. (2010) GP-UCB paper, not Frazier (2018).
- **Fix:** Add Srinivas et al. (2010) citation.

### MOD-2: 'Equal capacity replacement' overclaims (ISS-008)
- **Location:** `02_system_modeling.tex` L32
- **Detail:** Grid-forming inverters can provide synthetic inertia; REGCA1 with PFFLAG=1, QFLAG=0 is one specific control mode.
- **Fix:** Qualify as "a conservative worst-case assumption for grid-following RE devices without inertial support."

### MOD-3: Severity threshold θ=0.6 lacks justification (ISS-009)
- **Location:** `02_system_modeling.tex` L85
- **Detail:** This critical parameter controls all downstream boundaries and limits.
- **Fix:** Add a brief sensitivity analysis or engineering justification.

### MOD-4: Text-table method count mismatch (ISS-010)
- **Location:** `05_simulation.tex` vs `tab5_bo_efficiency.tex`
- **Detail:** Text lists 5 methods; table has 3 with different names.
- **Fix:** Align table content with text description.

### MOD-5: Independent GP ignores cross-constraint correlation (ISS-011)
- **Location:** `03_theory_analysis.tex` L61-65
- **Fix:** Add a paragraph discussing why independence is a reasonable approximation, or cite evidence that cross-correlation is weak.

### MOD-6: No sensitivity analysis for key hyperparameters (ISS-012)
- **Location:** `04_parameter_design.tex`
- **Fix:** Add at minimum a discussion of how results vary with θ and ε.

### MOD-7: MOGP 59.5% improvement claim unverifiable (ISS-013)
- **Location:** `06_conclusion.tex` L10
- **Detail:** No table compares MOGP vs single-output GP. Table 4 compares feature sets, not architectures.
- **Fix:** Either add a single-output GP baseline to Table 4, or remove the 59.5% claim.

---

## Minor Issues

### MIN-1: Proposition numbering non-sequential (ISS-007)
- 命题1,2 in Section 2.6; 命题3 in Section 2.3. Renumber sequentially.

### MIN-2: MOGP naming misleading for independent architecture (ISS-014)
- Add footnote or parenthetical clarifying "multi-output" means ensemble of independent GPs.

### MIN-3: Section 3 (parameter design) disrupts flow (ISS-015)
- Consider merging into Section 2 or moving to appendix.

### MIN-4: English abstract has grammatical issues (ISS-016)
- "reduces BO evaluations" → "reduces evaluation count"; restructure opening sentence.

---

## Strengths

1. **Clear methodological integration**: The GP→BO→AIA→closed-loop pipeline is well-structured and novel in the power systems security domain.
2. **Comprehensive worst-case search analysis**: Section 2.3 provides a rigorous comparison of BO vs sensitivity methods with proper theoretical backing.
3. **Engineering relevance**: The paper clearly connects methodological contributions to practical grid operation challenges (transfer limits, curtailment).
4. **Systematic validation design**: 6510 simulations across 5 RE levels and 7 fault types is a thorough experimental setup.
5. **Well-written Chinese prose**: The paper is clearly written with proper technical terminology.

---

## Revision Roadmap

| Priority | Issue ID | Action | Effort |
|----------|----------|--------|--------|
| 1 | ISS-001 | Populate Tables 4-7 with experimental data | High |
| 2 | ISS-002 | Add vittal2022re_stability bib entry | Low |
| 3 | ISS-004 | Revise Proposition 2 proof/scope | Medium |
| 4 | ISS-006 | Fix numerical range in abstract/conclusion | Low |
| 5 | ISS-003 | Rename citation keys to match authors | Medium |
| 6 | ISS-005 | Add Srinivas 2010 citation for BO bound | Low |
| 7 | ISS-010 | Align Table 5 with text method list | Low |
| 8 | ISS-013 | Add single-output GP baseline or remove claim | Medium |
| 9 | ISS-009 | Justify θ=0.6 threshold | Low |
| 10 | ISS-007 | Renumber propositions sequentially | Low |
