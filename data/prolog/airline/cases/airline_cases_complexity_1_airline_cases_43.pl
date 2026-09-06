/* =========================================================
   Michael - Business Class
   Ottawa (Canada) -> Las Vegas (U.S.)
   Route category : Within / between U.S. and Canada
   Ticket price   : $233
   ========================================================= */

/* ------------  Flight ticket  --------------------------- */
flight_cost(233).

/* ------------  Checked bags only ------------------------ */
/* bag(Id, Length, Width, Height, Weight) */
bag(1,21,14,8,10).  /* Carry-on, not checked */
bag(2,35,19,9,89).
bag(3,42,29,20,72).
bag(4,43,22,16,53).
bag(5,35,18,12,55).
bag(6,44,23,15,88).
bag(7,37,17,12,63).
bag(8,37,12,14,68).

/* List of all checked-bag Ids (bag 1 is carry-on) */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ------------  Statutory fee rules ---------------------- */

/* Sum of outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fee within / between U.S. & Canada */
oversize_fee(Sum,Fee) :-
    (   Sum =< 62  -> Fee = 0
    ;   Sum =< 65  -> Fee = 30
    ;   Sum =< 115 -> Fee = 200
    ;   Fee = 200 % For bags over 115 inches
    ).

/* Overweight fee given the weight limit Thresh */
/* (Thresh = 70 lb for complimentary, 50 lb for charged) */
overweight_fee(W,Thresh,Fee) :-
    (   W =< Thresh -> Fee = 0
    ;   W =< 53     -> Fee = 30
    ;   W =< 70     -> Fee = 100
    ;   W =< 100    -> Fee = 200
    ;   Fee = 200 % For bags over 100 lbs
    ).

/* Penalty for a bag = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,70,OW),      % complimentary => 70-lb limit
    Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,50,OW),      % charged bag => 50-lb limit
    Pen is max(OS,OW).

/* Checked-bag base fees for Business Class on this route (US/Canada) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* ------------  Helper predicates ------------------------ */

/* Pick two distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
    append(_,[F1|Tail],List),
    member(F2,Tail).

/* Build ordered list where the 2 freebies go first */
ordered_list(F1,F2,Ordered) :-
    checked_bag_ids(All),
    select(F1,All,Rest1),
    select(F2,Rest1,Rest),
    Ordered = [F1,F2|Rest].

/* Accumulate fees and penalties over an ordered list */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
    (Idx =< 2 -> Kind = comp ; Kind = charged),
    bag_fee(Idx,BaseFee),
    penalty(Bag,Kind,Pen),
    NextIdx is Idx + 1,
    cost_bags(Bs,NextIdx,FeeRest,PenRest),
    FeeSum is BaseFee + FeeRest,
    PenSum is Pen + PenRest.

/* Total for a particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
    ordered_list(F1,F2,Ordered),
    cost_bags(Ordered,1,BaseFees,Penalties),
    flight_cost(Ticket),
    Total is Ticket + BaseFees + Penalties.

/* Minimal total over all ways of selecting the 2 freebies */
compute_total(MinTotal) :-
    checked_bag_ids(Bags),
    findall(T,
            ( choose_two(Bags,F1,F2),
              cost_for_choice(F1,F2,T) ),
            Totals),
    min_list(Totals,MinTotal).

/* ------------  Query & output --------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.