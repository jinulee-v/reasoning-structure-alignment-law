/* =========================================================
   Facts that describe Thomas's trip
   ========================================================= */

/* price of the air ticket */
flight_cost(183).

/* list of checked bags:  bag(Id,Length,Width,Height,Weight) */
bag(2, 34,17,13, 68).
bag(3, 35,17,12, 52).
bag(4, 36,19, 9, 52).
bag(5, 33,21, 9, 51).
bag(6, 45,26,21, 62).
bag(7, 34,18,11, 51).
bag(8, 34,18,11, 51).
bag(9, 34,17,14, 53).
bag(10,49,27,20, 52).
bag(11,45,26,17, 52).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* =========================================================
   Statutory rules for - Business Class - U.S. <-> Europe
   ========================================================= */

/* ---------- size / weight helpers ---------- */
/* sum of the 3 linear dimensions of a bag */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------- oversize fees ------------------- */
/* Europe / U.S. route */
oversize_fee(Sum,Fee) :-
    (   Sum =< 62      -> Fee = 0
    ;   Sum =< 65      -> Fee = 30
    ;   Sum =< 115     -> Fee = 150 ).

/* ---------- overweight fees ----------------- */
/* Thresh = weight allowance (70 lb for complimentary,
   50 lb for charged bags)                            */
overweight_fee(W,Thresh,Fee) :-
    (   W =< Thresh    -> Fee = 0
    ;   W =< 53        -> Fee = 30
    ;   W =< 70        -> Fee = 100
    ;   W =< 100       -> Fee = 200 ).

/* ---------- penalty (the higher of two fees) ---------- */
penalty(BagId,complimentary,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,70,OW),           % 70-lb limit for complimentary
    Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,50,OW),           % 50-lb limit for charged
    Pen is max(OS,OW).

/* ---------- base checked-bag fees (Business, U.S. <-> Europe) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(N,200) :- N>=4.

/* =========================================================
   Helper predicates to enumerate which 2 bags are treated
   as the complimentary (1st & 2nd) pieces
   ========================================================= */

/* choose 2 different elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
    append(_,[F1|Tail],List),
    member(F2,Tail).

/* build an ordered list whose first 2 elements are the freebies */
ordered_list(F1,F2,Ordered) :-
    checked_bag_ids(All),
    select(F1,All,Rest1),
    select(F2,Rest1,Rest),
    Ordered = [F1,F2|Rest].

/* =========================================================
   Cost calculation for a given choice of the 2 freebies
   ========================================================= */
cost_for_choice(F1,F2,Total) :-
    ordered_list(F1,F2,Ordered),
    cost_bags(Ordered,1,CostBags,Penalties),
    flight_cost(Flight),
    Total is Flight + CostBags + Penalties.

/* walk through the ordered list accumulating fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
    (   Idx =< 2 -> Kind = complimentary
    ;   Kind = charged),
    bag_fee(Idx,Fee),
    penalty(Bag,Kind,Pen),
    NextIdx is Idx + 1,
    cost_bags(Bs,NextIdx,CostRest,PenRest),
    CostSum is Fee + CostRest,
    PenSum  is Pen + PenRest.

/* =========================================================
   Grand-total: pick the combination that minimises total cost
   ========================================================= */
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T,
            ( choose_two(L,F1,F2),
              cost_for_choice(F1,F2,T)),
            Totals),
    min_list(Totals,MinTotal).

/* =========================================================
   Produce the answer
   ========================================================= */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.