/* -------------  RULES (statutes) ------------- */

/* oversize fee - Canada <-> U.S. (same as general U.S./Canada rules)   */
oversize_fee(Size, 0)   :- Size =< 62.                    /* not oversize            */
oversize_fee(Size, 30)  :- Size  > 62, Size =< 65.        /* 62-65 in                */
oversize_fee(Size, 200) :- Size  > 65, Size =< 115.       /* 65-115 in               */

/* overweight fee - Canada <-> U.S. (Basic Economy rules)               */
overweight_fee(W, 0)    :- W =< 50.                       /* not overweight          */
overweight_fee(W, 30)   :- W  > 50, W =< 53.              /* 50-53 lb                */
overweight_fee(W, 100)  :- W  > 53, W =< 70.              /* 53-70 lb                */
overweight_fee(W, 200)  :- W  > 70, W =< 100.             /* 70-100 lb               */

/* surcharge for a bag that is either oversize, overweight or both      */
surcharge(Size, W, Fee) :-
    oversize_fee(Size, F1),
    overweight_fee(W,  F2),
    Fee is max(F1,F2).

/* base checked-bag fee for Basic Economy Canada <-> U.S.               */
base_fee(1,  35).
base_fee(2,  45).
base_fee(3, 150).
base_fee(N, 200) :- N >= 4.

/* total fee for a given checked bag number                              */
bag_total_fee(N, Size, W, Total) :-
    base_fee(N, B),
    surcharge(Size, W, S),
    Total is B + S.

/* -------------  FACTS (case data) ------------- */

/* carry-on (free) - not listed among checked bags                       */
/* checked bags: numbered in the order they will be processed            */
/* bag(No, SizeInInches, WeightInPounds).                                */
bag(1, 112, 53).   /* luggage box 54*30*28 */
bag(2,  79, 53).   /* backpack 41*24*14   */
bag(3, 106, 51).   /* backpack 47*34*25   */
bag(4,  64, 73).   /* backpack 33*18*13   */
bag(5,  63, 93).   /* luggage box 37*17*9 */
bag(6,  63, 51).   /* luggage box 34*18*11*/
bag(7,  73, 52).   /* backpack 38*23*12   */

flight_cost(211).

/* -------------  AGGREGATION ------------- */

bags_fee(Total) :-
    findall(Fee,
            (bag(N,SZ,W), bag_total_fee(N,SZ,W,Fee)),
            Fees),
    sum_list(Fees, Total).

total_cost(Total) :-
    flight_cost(FC),
    bags_fee(BF),
    Total is FC + BF.

/* -------------  QUERY ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.