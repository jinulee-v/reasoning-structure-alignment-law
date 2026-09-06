/* ----------  Statutory rules needed for this case  ---------- */

/* size helper */
bag_size(L,W,H,S) :- S is L+W+H.

/* oversize fee : Europe <-> U.S. rules                                */
/* 0-62 in : 0 ; 62-65 in : 30 ; 65-115 in : 150                     */
oversize_fee(Size,Fee) :-
    (   Size =< 62 -> Fee = 0
    ;   Size =< 65 -> Fee = 30
    ;   Size =<115 -> Fee = 150
    ;   Fee = 0           /* >115 not needed here (bag not accepted) */
    ).

/* overweight fee : Europe <-> U.S. rules                              */
/* 0-50 lb : 0 ; 50-53 lb : 30 ; 53-70 lb : 100                      */
overweight_fee(W,Fee) :-
    (   W =< 50 -> Fee = 0
    ;   W =< 53 -> Fee = 30
    ;   W =< 70 -> Fee = 100
    ;   Fee = 0            /* >70 not needed for this case           */
    ).

/* surcharge = max(oversize, overweight)                             */
surcharge(W,Size,S) :-
    oversize_fee(Size,OS),
    overweight_fee(W,OW),
    (OS >= OW -> S = OS ; S = OW).

/* base checked-bag fee for Premium Economy, Europe -> U.S.           */
/* bags 1-2 : $0 ; bag 3 : $200 ; bag 4+ : $200                      */
base_fee(N,0)  :- N =< 2.
base_fee(N,200):- N  > 2.

/* ----------  Facts for Robert's trip  ---------- */

/* checked bags only (carry-on not included)  */
bag(1,52,30,30,53).   /* L,W,H,Weight (lb) */
bag(2,34,17,13,51).
bag(3,34,17,12,56).
bag(4,33,20,10,53).
bag(5,42,26,21,68).
bag(6,45,22,21,66).
bag(7,38,13,14,52).

/* flight ticket price */
flight_ticket(409).

/* ----------  Derived costs  ---------- */

bag_cost(N,Cost) :-
    bag(N,L,W,H,Wt),
    bag_size(L,W,H,Size),
    surcharge(Wt,Size,Surch),
    base_fee(N,Base),
    Cost is Base + Surch.

total_bag_cost(Total) :-
    findall(C, bag_cost(_,C), Cs),
    sum_list(Cs,Total).

/* sum helper */
sum_list([],0).
sum_list([H|T],Sum) :- sum_list(T,S1), Sum is H+S1.

/* total trip cost */
total_cost(Total) :-
    flight_ticket(T),
    total_bag_cost(Bags),
    Total is T + Bags.

/* ----------  Query  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.