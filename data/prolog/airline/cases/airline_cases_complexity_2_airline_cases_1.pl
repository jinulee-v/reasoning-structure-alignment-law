/* ----------  Facts describing the trip -------------------- */

/* ticket price */
flight_cost(235).

/* list of checked bags: bag(Id,Length,Width,Height,Weight). */
bag(2,36,22,14,55).
bag(3,37,18, 9,80).
bag(4,34,20,10,61).
bag(5,36,20, 9,95).
bag(6,44,28,21,78).
bag(7,33,20,10,83).
bag(8,38,16, 9,68).
bag(9,34,21, 9,99).
bag(10,33,21,10,81).
bag(11,44,31,21,72).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ----------  Statutory rules (for this itinerary) --------- */

/* sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee for: Within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62      -> Fee = 0
        ;   Sum =< 65      -> Fee = 30
        ;   Sum =< 115     -> Fee = 200 ).

/* overweight fee for: Within / between U.S. and Canada          */
/* Threshold is 50 lbs for CHARGED bags, 70 lbs for COMPLIMENTARY */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh        -> Fee = 0
        ;   W =< 53            -> Fee = 30
        ;   W =< 70            -> Fee = 100
        ;   W =< 100           -> Fee = 200 ).

/* penalty for a bag: higher of over-size vs over-weight */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),         % complimentary => 70-lb limit
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),         % charged bag => 50-lb limit
        Pen is max(OS,OW).

/* checked-bag fee by ordinal position for First Class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates ---------------------------- */

/* choose 2 different elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
        append(_,[F1|Tail],List),
        member(F2,Tail).

/* remove chosen freebies from the master list to build the ordered list */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1,All,Rest1),
        select(F2,Rest1,Rest),
        Ordered = [F1,F2|Rest].          % freebies go in positions 1 and 2

/* compute cost for a particular choice of freebies */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ordered),
        cost_bags(Ordered,1,CostBags,Penalties),
        flight_cost(Flight),
        Total is Flight + CostBags + Penalties.

/* walk through ordered list accumulating bag fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Type,Pen),
        NextIdx is Idx+1,
        cost_bags(Bs,NextIdx,CostRest,PenRest),
        CostSum is Fee + CostRest,
        PenSum  is Pen + PenRest.

/* compute minimal total cost over all ways of selecting 2 complimentary bags */
total_cost(MinTotal) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,MinTotal).

/* ----------  Run the query and print ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.