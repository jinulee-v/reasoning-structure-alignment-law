/* ------------  Statutory rules (subset needed for this case) ------------ */

/* base checked-bag fee for a Basic-Economy passenger on a wholly-domestic
   (U.S.) itinerary                                                  */
base_fee(1,40).
base_fee(2,45).
base_fee(3,150).
base_fee(N,200) :- N>=4.

/* overweight fees (within / between U.S., P.R., U.S.V.I., Canada) */
overweight_fee(W,200) :- W  > 70.
overweight_fee(W,100) :- W =< 70, W  > 53.
overweight_fee(W, 30) :- W =< 53, W  > 50.
overweight_fee(W, 0)  :- W =< 50.

/* oversize fees (between points in the U.S. / Canada / P.R. / U.S.V.I.)   */
oversize_fee(D,200) :- D  > 65, D =< 115.
oversize_fee(D, 30) :- D =< 65, D  > 62.
oversize_fee(D, 0)  :- D =< 62.

/* choose the higher of the two */
extra_fee(W,D,F) :- overweight_fee(W,OF), oversize_fee(D,SF),
                    (OF >= SF -> F = OF ; F = SF).

/* ------------  Case facts  ---------------------------------------------- */

flight_ticket(293).

/* bag(ID,Length,Width,Height,Weight). */
bag(1,18,11, 6,  9).
bag(2,37,16,10, 58).
bag(3,38,12,13, 80).
bag(4,38,16, 9, 71).
bag(5,37,15,11, 61).
bag(6,40,23,21, 56).
bag(7,45,24,19, 52).
bag(8,33,19,11, 52).

/* ------------  Bag classification --------------------------------------- */

/* linear dimension */
linear_dim(L,W,H,D) :- D is L+W+H.

/* personal item : 18 x 14 x 8 inches or smaller                           */
personal_item(ID) :-
    bag(ID,L,W,H,_),
    L =< 18, W =< 14, H =< 8.

/* everything that is not a personal item is treated as a checked bag
   (none of the remaining bags qualifies as carry-on given their size)      */
checked_bag(ID) :-
    bag(ID,_,_,_,_),
    \+ personal_item(ID).

/* list of checked-bag IDs in ascending order                               */
checked_bag_list(List) :-
    findall(ID,checked_bag(ID),L),
    sort(L,List).

/* position (1 = first checked bag, 2 = second, ...)                          */
bag_position(ID,Pos) :-
    checked_bag_list(List),
    nth1(Pos,List,ID).

/* cost for one checked bag                                                 */
bag_cost(ID,Cost) :-
    bag_position(ID,Pos),
    base_fee(Pos,Base),
    bag(ID,L,W,H,Weight),
    linear_dim(L,W,H,Dim),
    extra_fee(Weight,Dim,Extra),
    Cost is Base + Extra.

/* ------------  Totals ---------------------------------------------------- */

bags_total_cost(Total) :-
    findall(C, (checked_bag(ID), bag_cost(ID,C)), Cs),
    sum_list(Cs,Total).

total_cost(Total) :-
    flight_ticket(Ticket),
    bags_total_cost(Bags),
    Total is Ticket + Bags.

/* ------------  Query ----------------------------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.