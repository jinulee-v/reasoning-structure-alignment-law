/* ----------------  Facts describing Daniel's trip ------------------ */

/* ticket price */
flight_cost(519).

/* Passenger class */
passenger_class(business).

/* Itinerary: Brussels to Philadelphia (Europe to US) */
itinerary(europe, us).

/* list of checked bags: bag(Id,Length,Width,Height,Weight). */
bag(2,36,17,12,64).
bag(3,37,22,12,51).
bag(4,40,21,20,51).
bag(5,33,21,10,65).

/* list (constant) of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* ----------------  Statutory rules for this itinerary -------------- */

/* Add the 3 dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Determine region for fee calculation */
region(europe, us, europe_us).
region(us, europe, europe_us).

/* Base bag fees for Business Class, Europe <-> U.S. */
bag_fee(1, 0).
bag_fee(2, 0).
bag_fee(3, 200).
bag_fee(N, 200) :- N >= 4.

/* Oversize fees - Europe <-> U.S. */
oversize_fee(Sum, Fee) :-
    (   Sum =< 62 -> Fee = 0
    ;   Sum =< 65 -> Fee = 30
    ;   Sum =< 115 -> Fee = 150
    ).

/* Overweight fees - Europe <-> U.S. */
overweight_fee(Weight, Thresh, Fee) :-
    (   Weight =< Thresh -> Fee = 0
    ;   Weight =< 53 -> Fee = 30
    ;   Weight =< 70 -> Fee = 100
    ;   Weight =< 100 -> Fee = 200
    ).

/* Calculate penalty for a bag */
penalty(BagId, comp, Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum, OS),
    overweight_fee(Weight, 70, OW), % Complimentary bags have 70 lb limit
    Pen is max(OS, OW).

penalty(BagId, charged, Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum, OS),
    overweight_fee(Weight, 50, OW), % Charged bags have 50 lb limit
    Pen is max(OS, OW).

/* ----------------  Helper predicates -------------------------------- */

/* Choose 2 distinct elements from a list */
choose_two(List, F1, F2) :-
    select(F1, List, Rest),
    select(F2, Rest, _).

/* Place the 2 freebies in positions 1 and 2 */
ordered_list(F1, F2, Ordered) :-
    checked_bag_ids(All),
    select(F1, All, Rest1),
    select(F2, Rest1, Rest2),
    Ordered = [F1, F2 | Rest2].

/* Compute total cost for a particular choice of free bags */
cost_for_choice(F1, F2, Total) :-
    ordered_list(F1, F2, Ordered),
    cost_bags(Ordered, 1, BagCost, PenaltyCost),
    flight_cost(Flight),
    Total is Flight + BagCost + PenaltyCost.

/* Walk through the ordered bag list */
cost_bags([], _, 0, 0).
cost_bags([Bag|Bs], Idx, CostSum, PenSum) :-
    (Idx =< 2 -> Type = comp ; Type = charged),
    bag_fee(Idx, Fee),
    penalty(Bag, Type, Pen),
    NextIdx is Idx + 1,
    cost_bags(Bs, NextIdx, RestCost, RestPen),
    CostSum is Fee + RestCost,
    PenSum is Pen + RestPen.

/* Find minimal total cost across all ways of picking 2 complimentary bags */
compute_total(MinTotal) :-
    checked_bag_ids(L),
    findall(T,
            ( choose_two(L,F1,F2),
              cost_for_choice(F1,F2,T)
            ),
            Totals),
    min_list(Totals, MinTotal).

/* ----------------  Query and report --------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.