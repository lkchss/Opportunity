# Algorithm Bug Fixes Summary

## Bugs Identified and Fixed

### Bug #1: Admissibility Scores Too Low for High LSAT
**Problem:** 180 LSAT candidate scored only 49.4 admissibility at Harvard
**Cause:** Sigmoid curves were too gentle and centered poorly
**Fix:** Replaced sigmoid with percentile-based scoring
- Above 75th → 85-100
- 50th-75th → 60-85
- 25th-50th → 40-60
- Below 25th → 0-40

**Result:** 177 LSAT now scores 86-93 admissibility at T14 schools ✅

---

### Bug #2: GPA Weighted Equally to LSAT
**Problem:** LSAT and GPA had equal weight, but law schools prioritize LSAT for rankings
**Cause:** Both used in 50/50 weighted average
**Fix:** Changed to 70% LSAT, 30% GPA weighting

**Result:** Splitters (high LSAT, low GPA) now score appropriately higher ✅

---

### Bug #3: Tier Logic Broken
**Problem:** Required BOTH metrics at thresholds, penalizing splitters
**Cause:** Tier logic was `lsat_at_75 AND gpa_at_75` for safety
**Fix:** Changed to LSAT-weighted logic:
- Safety: `lsat_at_75 OR (lsat_at_50 AND gpa_at_75)`
- Target: `lsat_at_50 OR (lsat_at_25 AND gpa_at_50)`
- Reach: `lsat_at_25`
- Hard Reach: `lsat < 25th`

**Result:** Tier assignments now match real-world admissions expectations ✅

---

### Bug #4: Academia Goal Not Supported
**Problem:** Academia defaulted to low balanced average (20%), causing T14s to rank below regional schools
**Cause:** No employment data for academia placements
**Fix:** Created composite score from federal clerkships (60%) + BigLaw (40%) as prestige proxies

**Result:**
- Harvard academia score: 20.0 → 28.2
- Cornell academia score: added at 33.0
- Harvard and Michigan now rank #1-2 for academia candidates ✅

**Additional Goals Added:**
- In-house: Uses BigLaw * 0.8 (BigLaw is common path)
- Solo/Small Firm: Inverse of BigLaw (regional schools often better)

---

### Bug #5: No Prestige Dimension
**Problem:** Low-tier schools ranked above elite schools when candidate was overqualified
**Cause:** Algorithm only considered fit, not school quality
**Fix:** Added school quality score (10% weight) based on:
- Median LSAT (50% weight)
- Bar pass rate (30% weight)
- Acceptance rate/selectivity (20% weight)

**Result:**
- T14 schools now rank appropriately for strong candidates
- Vermont Law dropped in rankings (still appears for specific fits, but not as #1 universally)
- Profile 1 (177 LSAT) top 10 is now entirely T14 schools ✅

---

## Updated Composite Score Weights

**Before:**
- Admissibility: 30%
- Goal Fit: 30%
- Practice Area: 20%
- Scholarship: 10%
- Geographic: 10%

**After:**
- Admissibility: 30% (LSAT 70%, GPA 30%)
- Goal Fit: 25% (now supports 8 career goals)
- School Quality: 10% (NEW)
- Practice Area: 15%
- Scholarship: 10%
- Geographic: 10%

---

## Test Results Comparison

### Profile 1: Strong T14 Candidate (177 LSAT / 3.95 GPA / BigLaw)

**Before:**
- Top schools: Duke, Cornell, Michigan, Columbia, NYU
- Admissibility scores: ~50-70 (too low)
- Vermont Law in top 10

**After:**
- Top schools: Duke, Cornell, Michigan, Columbia, Penn, NYU, Northwestern, Berkeley, UVA
- Admissibility scores: 86-93 ✅
- All T14 schools in top 10 ✅

### Profile 4: Academia Goal (175 LSAT / 3.92 GPA)

**Before:**
- Harvard #1 with 20.0 goal fit
- Vermont Law in top 5
- Regional schools ranking above T14

**After:**
- Michigan #1 (68.1), Harvard #2 (68.0) ✅
- Harvard goal fit: 28.2 ✅
- Stanford now in top 10 ✅
- Much better distribution of elite schools

---

## Remaining Known Issues

1. **Duplicate Northwestern** in dataset (appears twice in top 10)
2. **Data quality issues**: Columbia LSAT 25th percentile too low
3. **Goal fit scores still relatively low** for some goals (limited by available employment data)
4. Vermont Law still ranks high for reverse splitters with PI goals (this is actually reasonable given their 22% PI placement)

---

## Unit Test Results

All 38 tests pass ✅

Updated 2 test assertions to match new percentile-based scoring ranges.
