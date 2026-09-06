/* =================  Facts describing Mary's trip  ================= */

/* ticket price */
flight_cost(180).

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,34,20,10,53).
bag(3,45,31,24,68).
bag(4,38,17,10,54).
bag(5,36,22,15,51).
bag(6,38,14,11,68).
bag(7,47,26,24,86).
bag(8,39,17,16,58).
bag(9,37,12,14,69).
bag(10,34,20,11,85).
bag(11,45,19,21,81).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* =================  Statutory rules for this itinerary  ================= */

/* helper: sum of the three outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between U.S. & Canada */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fee - parameterised by complimentary threshold          */
/* Threshold = 70 lbs for complimentary bags; 50 lbs for charged bags */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 200 ).

/* penalty for a bag: higher of oversize vs. overweight */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),   % complimentary -> 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),   % charged bag -> 50-lb limit
       Pen is max(OS,OW).

/* checked-bag fee by ordinal position for Business Class (domestic) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* =================  Helper predicates  ================= */

/* choose 2 distinct elements (E1<E2) from a list */
choose_two(List,E1,E2) :-
       append(_, [E1|Tail], List),
       member(E2, Tail).

/* place the 2 complimentary bags first in the ordered list */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* walk through ordered list accumulating bag-fees and penalties */
costs([],_,0,0).
costs([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       costs(Bs,Next,RestFee,RestPen),
       FeeSum is Fee + RestFee,
       PenSum is Pen + RestPen.

/* cost for a particular choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       costs(Ordered,1,BagFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BagFees + Penalties.

/* compute minimal total cost over all ways of picking the 2 freebies */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* =================  Query & output  ================= */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.