/* -------------  STATUTORY RULES (excerpt) ------------- */

/* free checked-bag entitlement for Main Plus on Europe <-> U.S. flights   */
/* Main Cabin allowance = 1 free bag; Main Plus gives 1 extra free bag   */
free_checked_bags(main_plus, europe_us, 2).

/* base checked-bag fee (Europe <-> U.S., Main Cabin / Main Plus)          */
base_checked_fee(BagIndex, Fee) :-
    BagIndex =< 2,                     % 1st & 2nd bag are free
    Fee  is 0.
base_checked_fee(BagIndex, Fee) :-
    BagIndex  > 2,                     % 3rd bag and beyond
    Fee is 200.

/* ---------------- SURCHARGE RULES -------------------- */

/* oversize surcharge (Europe <-> U.S.) */
oversize_surcharge(DimSum, Fee) :-
    DimSum > 65, DimSum =< 115, Fee is 150.
oversize_surcharge(DimSum, Fee) :-
    DimSum > 62, DimSum =< 65,  Fee is 30.
oversize_surcharge(DimSum, Fee) :-
    DimSum =< 62,                     Fee is 0.

/* overweight surcharge (Europe <-> U.S.) */
overweight_surcharge(W, Fee) :-
    W > 53,  W =< 70, Fee is 100.
overweight_surcharge(W, Fee) :-
    W > 50,  W =< 53, Fee is 30.
overweight_surcharge(W, Fee) :-
    W =< 50,           Fee is 0.

/* final surcharge for a bag = higher of the two */
bag_surcharge(DimSum, W, Fee) :-
    oversize_surcharge(DimSum, OS),
    overweight_surcharge(W,  OW),
    Fee is max(OS, OW).

/* ---------------  CASE FACTS  ------------------------ */

/* flight information */
route(europe_us).              % Athens -> Charlotte
passenger_class(main_plus).
ticket_price(333).

/* carry-on (does not incur checked-bag computation) */
carry_on(1,19,14,9,10).

/* checked bags: id, L, W, H, Weight */
checked_bag(1,48,30,20,60).
checked_bag(2,37,13,14,53).
checked_bag(3,38,16,10,70).
checked_bag(4,43,28,24,65).
checked_bag(5,33,21,11,53).
checked_bag(6,39,25,19,55).
checked_bag(7,39,26,15,53).

/* ---------------  COMPUTATIONS  ---------------------- */

bag_total_fee(BagIndex, Fee) :-
    checked_bag(BagIndex, L,W,H,Weight),
    DimSum is L+W+H,
    bag_surcharge(DimSum, Weight, Surcharge),
    base_checked_fee(BagIndex, BaseFee),
    Fee is BaseFee + Surcharge.

all_bag_fees(Total) :-
    findall(F, (checked_bag(I,_,_,_,_), bag_total_fee(I,F)), List),
    sum_list(List, Total).

total_cost(Total) :-
    ticket_price(T),
    all_bag_fees(BagFees),
    Total is T + BagFees.

/* ---------------  QUERY  ----------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.