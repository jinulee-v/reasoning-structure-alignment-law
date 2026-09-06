/* --------------  Statutory rules that apply to this case -------------- */

/* Base checked-bag fees for a Basic-Economy customer on a journey
   "within / between the U.S., Puerto Rico and U.S. Virgin Islands".      */
bag_base_fee(1,40).
bag_base_fee(2,45).
bag_base_fee(3,150).
bag_base_fee(N,200) :- N>=4.

/* Oversize fees for travel within the U.S.                                */
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size > 62, Size =< 65.
oversize_fee(Size,200) :- Size > 65, Size =< 115.

/* Over-weight fees for travel within the U.S.                             */
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W > 50,  W =< 53.
overweight_fee(W,100)  :- W > 53,  W =< 70.
overweight_fee(W,200)  :- W > 70,  W =< 100.

/* The extra charge for a bag that is both over-size and over-weight is
   the higher of the two individual surcharges.                           */
extra_fee(W,Size,Extra) :-
        overweight_fee(W,OW), oversize_fee(Size,OS),
        (OW >= OS -> Extra = OW ; Extra = OS).

/* --------------  Facts for Patricia's journey -------------- */

/* unchecked (free) personal item is not represented - it has no cost.    */
/* Four chargeable checked bags, already in the order they will be paid.   */
bag(1, 39,15,13, 66).   /* luggage box   */
bag(2, 49,29,21, 88).   /* large backpack*/
bag(3, 38,15,11, 98).   /* large backpack*/
bag(4, 38,16, 9, 55).   /* luggage box   */

/* Flight ticket price                                                     */
flight_ticket(144).

/* --------------  Derived calculations -------------- */

/* Size of a bag (L+W+H)                                                   */
bag_size(Index,Size) :-
        bag(Index,L,W,H,_),
        Size is L+W+H.

/* Total fee for a single checked bag                                      */
bag_total_fee(Index,Fee) :-
        bag(Index,_,_,_,Weight),
        bag_size(Index,Size),
        bag_base_fee(Index,Base),
        extra_fee(Weight,Size,Extra),
        Fee is Base + Extra.

/* Sum fees for all checked bags                                           */
checked_bags_total(Total) :-
        findall(F, bag_total_fee(_,F), List),
        sumlist(List,Total).

/* Overall amount Patricia must pay                                        */
total_cost(Total) :-
        checked_bags_total(Bags),
        flight_ticket(Ticket),
        Total is Ticket + Bags.

/* --------------  Query to show the answer -------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.