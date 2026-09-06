/* -------------  Facts describing Karen's trip ------------------ */

/* ticket price */
flight_cost(287).

/* list of checked bags: bag(Id,Length,Width,Height,Weight).        */
/* (Bag 1 - 19x14x8, 5 lbs - is a carry-on and is therefore omitted) */
bag(2,53,29,30,77).
bag(3,35,18,10,51).
bag(4,34,18,13,65).
bag(5,50,23,26,98).

/* list of all checked-bag Ids (for easy iteration) */
checked_bag_ids([2,3,4,5]).

/* -------------  Statutory rules for this itinerary -------------- */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fees - domestic U.S. / Canada                         */
/* Threshold is 70 lbs for complimentary Business bags,             */
/* 50 lbs for charged bags                                          */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* penalty for a bag = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          % complimentary -> 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          % charged bag -> 50-lb limit
       Pen is max(OS,OW).

/* checked-bag base fees for Business Class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* -------------  Helper predicates --------------------------------*/

/* pick 2 different elements (F1 appears before F2 in the list) */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* build an ordered list putting the 2 free bags first */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for a particular choice of free bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* walk through ordered bag list, accumulating fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* minimal total cost over all ways of choosing the 2 complimentary bags */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* -------------  Query and output --------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.