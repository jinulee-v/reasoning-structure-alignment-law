/* =================  Facts describing Jessica's trip  ================= */

/* ticket price */
flight_cost(139).

/* list of checked bags:  bag(Id,Length,Width,Height,Weight) */
bag(2,35,15,14,51).
bag(3,35,22,10,52).
bag(4,41,19,18,86).
bag(5,38,14,11,69).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* Passenger class */
passenger_class(first).

/* Route details - assuming US domestic as no specific countries mentioned beyond origin/destination */
route_type(us_domestic).

/* =================  Statutory rules for this itinerary  =============== */

/* sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
       (  Sum =< 62  -> Fee = 0
       ;  Sum =< 65  -> Fee = 30
       ;  Sum =< 115 -> Fee = 200 ).

/* overweight fees - complimentary bags use a 70-lb limit,
   charged bags use a 50-lb limit                                   */
overweight_fee(W,Thresh,Fee) :-
       (  W =< Thresh -> Fee = 0
       ;  W =< 53     -> Fee = 30
       ;  W =< 70     -> Fee = 100
       ;  W =< 100    -> Fee = 200 ).

/* penalty for a bag: the higher of oversize vs. overweight fee */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),       % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),       % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* checked-bag base fees for First Class on US domestic route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.


/* =================  Helper predicates  ================================ */

/* choose two different elements (F1<F2 with respect to the list order) */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* build an ordered list with the 2 complimentary bags first */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BagFees + Penalties.

/* walk through the bag list accumulating fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* minimal total cost over all ways of selecting 2 complimentary bags */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).


/* =================  Query and output  ================================ */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.