/* -------------  Facts describing James's trip ------------------- */

/* ticket price */
flight_cost(306).

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,35,17,13,53).
bag(3,36,15,14,52).
bag(4,36,15,12,59).
bag(5,47,34,23,61).
bag(6,44,29,22,66).
bag(7,33,16,14,54).
bag(8,35,14,14,54).

/* list of all checked-bag Ids (carry-on #1 is not listed) */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ---------------- Statutory rules for this itinerary ------------ */

/* sum of the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - Europe <-> U.S. */
oversize_fee(Sum,Fee) :-
        (   Sum =< 62  -> Fee = 0
        ;   Sum =< 65  -> Fee = 30
        ;   Sum =< 115 -> Fee = 150 ).

/* overweight fees (Thresh = 70 lb for complimentary, 50 lb for charged) */
overweight_fee(W,Thresh,Fee) :-
        (   W =< Thresh -> Fee = 0
        ;   W =< 53     -> Fee = 30
        ;   W =< 70     -> Fee = 100
        ;   W =< 100    -> Fee = 200 ).

/* penalty for 1 bag = higher of oversize vs overweight fee */
penalty(BagId,comp,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,70,OW),
        Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
        bag(BagId,L,W,H,Weight),
        dims_sum(L,W,H,Sum),
        oversize_fee(Sum,OS),
        overweight_fee(Weight,50,OW),
        Pen is max(OS,OW).

/* checked-bag base fee for Business Class on this route (Europe-US) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(4,200).
bag_fee(5,200).
bag_fee(6,200).
bag_fee(7,200).
bag_fee(8,200).

/* -------------  Helper predicates ------------------------------- */

/* choose 2 distinct elements (F1 precedes F2 in the list) */
choose_two(List,F1,F2) :-
        append(_, [F1|Tail], List),
        member(F2, Tail).

/* put the 2 complimentary bags first in the ordered list */
ordered_list(F1,F2,Ordered) :-
        checked_bag_ids(All),
        select(F1, All, R1),
        select(F2, R1, Rest),
        Ordered = [F1,F2|Rest].

/* walk through ordered list accumulating base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
        (Idx =< 2 -> Type = comp ; Type = charged),
        bag_fee(Idx,Fee),
        penalty(Bag,Type,Pen),
        Next is Idx+1,
        cost_bags(Bs,Next,CostRest,PenRest),
        CostSum is Fee + CostRest,
        PenSum  is Pen + PenRest.

/* total cost for one specific choice of the 2 freebies */
cost_for_choice(F1,F2,Total) :-
        ordered_list(F1,F2,Ord),
        cost_bags(Ord,1,BaseFees,Penalties),
        flight_cost(Tix),
        Total is Tix + BaseFees + Penalties.

/* minimal total cost over all ways of selecting the 2 freebies */
total_cost(Min) :-
        checked_bag_ids(L),
        findall(T,
                ( choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T)),
                Totals),
        min_list(Totals,Min).

/* ----------------  Query & output ------------------------------- */
compute_total(Cost) :-
    total_cost(Cost).

:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.