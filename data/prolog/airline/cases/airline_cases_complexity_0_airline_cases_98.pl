/*  ------------------------
    Statutory rules (excerpt)
    ------------------------  */

/* cabin class and itinerary for this case */
cabin_class(premium_economy).
itinerary(within_us).          /* Los Angeles - Salt Lake City */

/* ------------------------
   Bag-position-based base fees
   (Premium Economy, travel within the U.S.)
   ------------------------   */
/* 1st and 2nd checked bag: $0 */
base_checked_fee(Pos,0) :- member(Pos,[1,2]), !.
/* 3rd checked bag: $150      */
base_checked_fee(3,150)  :- !.
/* 4th bag and higher: $200   */
base_checked_fee(Pos,200) :- Pos>=4.

/* ------------------------
   Oversize fee (within U.S.)
   ------------------------   */
oversize_fee(DimSum,Fee) :-
    DimSum =< 62, Fee = 0, !.
oversize_fee(DimSum,30) :-
    DimSum  > 62,
    DimSum =< 65, !.
oversize_fee(_DimSum,200).     /* > 65 - 115 in. */

/* ------------------------
   Over-weight fee (within U.S.)
   ------------------------   */
overweight_fee(W,0)  :- W =< 50, !.      /* =< 50 lb  - no fee */
overweight_fee(W,30) :- W  > 50, W =< 53, !.
overweight_fee(W,100):- W  > 53, W =< 70, !.
overweight_fee(W,200):- W  > 70, W =<100.

/* ------------------------
   Choose higher of oversize / over-weight
   ------------------------   */
extra_fee(OS,OW,OS) :- OS>=OW, !.
extra_fee(_OS,OW,OW).

/* ------------------------
   Passenger's items
   ------------------------   */
/* bag(ID, Length, Width, Height, Weight) */
bag(1,19,11, 6, 10).   /* backpack - becomes carry-on */
bag(2,46,24,24, 51).   /* checked #1 */
bag(3,33,21,10, 99).   /* checked #2 */
bag(4,36,19, 9, 53).   /* checked #3 */
bag(5,36,14,14, 95).   /* checked #4 */

/* ------------------------
   Helper predicates
   ------------------------   */
dim_sum(ID,Sum) :-
    bag(ID,L,W,H,_),
    Sum is L+W+H.

weight(ID,W) :-
    bag(ID,_,_,_,W).

/* determine if a bag can be the free carry-on */
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* all checked bags for this itinerary */
checked_bag_id(ID) :-
    bag(ID,_,_,_,_),
    \+ carry_on(ID).

/* position (#1, #2 ...) of a checked bag */
checked_position(ID,Pos) :-
    findall(B,checked_bag_id(B),List),
    nth1(Pos,List,ID).

/* total fee for an individual checked bag */
bag_total_fee(ID,Total) :-
    checked_position(ID,Pos),
    base_checked_fee(Pos,Base),
    dim_sum(ID,Dim),
    oversize_fee(Dim,OSFee),
    weight(ID,W),
    overweight_fee(W,OWFee),
    extra_fee(OSFee,OWFee,Extra),
    Total is Base + Extra.

/* ------------------------
   Aggregate all costs
   ------------------------   */
bags_cost(Sum) :-
    findall(F, (checked_bag_id(ID), bag_total_fee(ID,F)), L),
    sum_list(L,Sum).

flight_ticket(70).

total_cost(Total) :-
    bags_cost(BagFees),
    flight_ticket(Tix),
    Total is BagFees + Tix.

/* ------------------------
   Query & print answer
   ------------------------   */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.