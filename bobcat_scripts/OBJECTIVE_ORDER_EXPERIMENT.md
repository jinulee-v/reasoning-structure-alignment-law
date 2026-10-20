# BOBCat objective ordering experiment

The `depth` mode orders source outcomes by their minimum number of enclosing
branch decisions along a route through the DCalc definition graph. Shared
definitions keep their minimum depth across uses. Equal depths use stable
lexical order. `legacy` uses the earlier source-file and branch-kind ranking.

We compared both modes on all 23 public wrapper scopes in the five datasets.
Each scope used the same compiler, demand compilation, input-list bound 5,
intermediate-list bound 5, initial Z3 timeout 2 seconds, maximum Z3 timeout 60
seconds, and a 60-second process cutoff. The modes ran sequentially per scope,
with eight scopes in parallel. The second pass reversed which mode ran first
within each pair. Both modes produced identical objective manifest sets for
every scope. A cutoff means these figures measure early coverage, not the
eventual reachable set.

| Dataset | Manifest outcomes | Legacy covered, pass 1 / pass 2 | Depth covered, pass 1 / pass 2 |
|---|---:|---:|---:|
| aides_logement | 4,973 | 808 / 808 | 882 / 882 |
| airline | 278 | 163 / 163 | 156 / 156 |
| allocations_familiales | 285 | 155 / 155 | 139 / 139 |
| nsw_community_gaming | 38 | 38 / 38 | 38 / 38 |
| sara | 2,140 | 253 / 278 | 293 / 266 |
| **All outcomes** | **7,714** | **1,417 / 1,442** | **1,508 / 1,481** |

The equal-weight mean of the five dataset coverage rates was 48.22% / 48.45%
for legacy and 47.26% / 47.01% for depth. Depth gained raw outcomes, mainly
from the large HousingAid scope, but lost coverage on Airline, Allocations
Familiales, and MovingGrant. The SARA results also varied between passes under
the shared 60-second cutoff.

## Full 1,800-second comparison

We repeated the paired comparison on the same 23 scopes with a 1,800-second
limit per BOBCat invocation. All other bounds and solver settings were the
same. The objective manifest sets matched between modes for every scope.

| Dataset | Manifest outcomes | Legacy covered | Depth covered |
|---|---:|---:|---:|
| aides_logement | 4,973 | 1,767 | 1,718 |
| airline | 278 | 243 | 243 |
| allocations_familiales | 285 | 168 | 167 |
| nsw_community_gaming | 38 | 38 | 38 |
| sara | 2,140 | 369 | 388 |
| **All outcomes** | **7,714** | **2,585** | **2,554** |

The equal-weight mean of the five dataset coverage rates was 59.83% for
legacy and 59.74% for depth. Depth improved six SARA scopes, lost one outcome
on FamilyAllowance and 49 on HousingAid, and tied on the other scopes.

These are validated outcomes obtained before each process stopped. In **both**
modes, seven SARA scopes reached the 1,800-second process limit. TaxableIncome,
FamilyAllowance, and HousingAid stopped earlier with Z3's `max. memory exceeded`
error in both modes. Thus the full-budget comparison includes partial runs;
it does not establish eventual coverage if memory were unbounded.

The full-budget run favors legacy slightly on both total outcomes and the
equal-weight dataset average. The earlier 60-second depth advantage did not
persist across all datasets. **Current default:** depth, selected as the
explicit breadth-first traversal policy; legacy remains available for the
source-file and branch-kind ranking. This default is a policy choice, not a
claim that depth improved measured coverage.

Reproduce with:

```sh
python3 bobcat_scripts/compare_objective_orders.py --timeout 60 --jobs 8
python3 bobcat_scripts/compare_objective_orders.py --timeout 60 --jobs 8 \
  --reverse --output .port/bobcat_order_experiment_reverse
python3 bobcat_scripts/compare_objective_orders.py --timeout 1800 --jobs 8 \
  --output .port/bobcat_order_experiment_full
```

The per-scope records and raw BOBCat streams are under
`.port/bobcat_order_experiment/` and
`.port/bobcat_order_experiment_reverse/`, with the full-budget results under
`.port/bobcat_order_experiment_full/`.
