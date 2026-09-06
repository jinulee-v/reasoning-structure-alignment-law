/* -----------------------------------------------------------
   Jennifer - Minneapolis (U.S.)  ->  San Juan (Puerto Rico)
   Cabin: First       Ticket price: $212
----------------------------------------------------------- */

/* ----------  Facts describing the trip ------------------- */

/* ticket price */
flight_cost(212).

/* checked bags: bag(Id,Length,Width,Height,Weight).         */
bag(2,34,17,14,64).
bag(3,37,17,10,53).
bag(4,44,25,19,65).
bag(5,49,24,23,93).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* ----------  Statutory rules (for this itinerary) -------- */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between U.S., Puerto Rico, U.S.V.I., Canada */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62  -> Fee = 0
       ;   Sum =< 65  -> Fee = 30
       ;   Sum =< 115 -> Fee = 200).

/* overweight fee - threshold 70 lb for complimentary bags,
                     50 lb for charged bags                    */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 200).

/* penalty for a bag = higher of oversize vs overweight fee   */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,50,OW),
       Pen is max(OS,OW).

/* checked-bag base fee for First Class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates --------------------------- */

/* choose 2 different elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* create ordered list with the 2 freebies first */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for a specific choice of freebies */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BaseFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BaseFees + Penalties.

/* walk through ordered list, accumulating costs */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* minimal total cost over all ways of selecting 2 freebies */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------  Query and output ---------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.