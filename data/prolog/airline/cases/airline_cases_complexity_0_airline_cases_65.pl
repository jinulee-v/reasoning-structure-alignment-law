/* ----------  Rules derived from the statutes  ---------- */

/* base checked-bag fee (Main Cabin, U.S. <-> South America - Ecuador) */
base_bag_fee(1, main_cabin, south_america, 0).
base_bag_fee(2, main_cabin, south_america, 100).
base_bag_fee(N, main_cabin, south_america, 200) :- N>=3.

/* overweight fees - U.S. <-> South America (ex-Guyana, Suriname) */
overweight_fee(south_america, W, 200) :- W  > 70.
overweight_fee(south_america, W, 100) :- W =< 70, W > 53.
overweight_fee(south_america, W,  30) :- W =< 53, W > 50.
overweight_fee(_,             W,   0) :- W =< 50.

/* oversize fees - U.S. <-> South America (ex-Guyana, Suriname) */
oversize_fee(south_america, S, 150) :- S  > 65.
oversize_fee(south_america, S,  30) :- S =< 65, S > 62.
oversize_fee(_,            S,   0) :- S =< 62.

/* dimension helper */
dim_sum(L,W,H,S) :- S is L+W+H.

/* choose larger of oversize / overweight */
max_fee(A,B,A) :- A>=B.
max_fee(A,B,B) :- B> A.

/* total charge for one checked bag */
bag_charge(N, L,W,H, Weight, Charge) :-
    Route = south_america,
    base_bag_fee(N, main_cabin, Route, Base),
    dim_sum(L,W,H,Sum),
    oversize_fee(Route, Sum, OSFee),
    overweight_fee(Route, Weight, OWFee),
    max_fee(OSFee, OWFee, Extra),
    Charge is Base + Extra.

/* ----------  Facts describing the case  ---------- */

/* 4 checked bags (carry-on not listed here) */
bag(1, 45,19,20, 88).   /* Backpack - checked bag #1 */
bag(2, 43,22,16, 67).   /* Backpack - checked bag #2 */
bag(3, 33,19,13, 51).   /* Luggage box - checked bag #3 */
bag(4, 51,32,23, 52).   /* Luggage box - checked bag #4 */

ticket_cost(466).

/* ----------  Aggregate calculations  ---------- */

bags_total_cost(Total) :-
    findall(C,
            (bag(N,L,W,H,Weight),
             bag_charge(N,L,W,H,Weight,C)),
            Cs),
    sum_list(Cs, Total).

total_cost(Total) :-
    ticket_cost(T),
    bags_total_cost(B),
    Total is T + B.

/* ----------  Query to print the answer  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.