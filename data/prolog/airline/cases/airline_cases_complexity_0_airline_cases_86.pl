/* ----------  Facts about Sarah's trip ---------- */
flight_route(usa_to_korea).          /* Dallas (U.S.)  ->  Seoul (South Korea) */
passenger_class(main_cabin).
flight_ticket_price(366).

/* Carry-on - free, so not listed among checked bags */
carry_on(bag1).

/* Checked bags (chosen order that minimises the total)               */
/* bag(Name, Length, Width, Height, Weight).                          */
bag(bag3, 33, 21, 11, 81).    /* heavy - we'll make this the 1st checked bag (free base fee) */
bag(bag4, 41, 27, 15, 73).    /* 2nd checked bag                     */
bag(bag2, 36, 15, 14, 52).    /* 3rd checked bag                     */
bag(bag5, 34, 18, 12, 53).    /* 4th checked bag                     */

/* Order in which bags are checked (index -> BagName)                  */
bag_order(1, bag3).
bag_order(2, bag4).
bag_order(3, bag2).
bag_order(4, bag5).

/* ----------  Helper rules ---------- */

size_sum(L,W,H,Sum) :- Sum is L+W+H.

/* ---------  Base checked-bag fee for USA <-> South-Korea, Main Cabin  --------- */
/* 1st bag free, 2nd = $100, 3rd = $200, 4th = $200 (rules for "To / from ... South Korea") */

base_checked_fee(1, 0).
base_checked_fee(2,100).
base_checked_fee(3,200).
base_checked_fee(4,200).

/* ----------  Overweight fee (USA <-> South-Korea)  ---------- */
overweight_fee(W, 0)  :- W =< 50.
overweight_fee(W,30)  :- W > 50,  W =< 53.
overweight_fee(W,100) :- W > 53, W =< 70.
overweight_fee(W,450) :- W > 70, W =< 100.

/* ----------  Oversize fee (USA <-> South-Korea)  ---------- */
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S,30)   :- S > 62,  S =< 65.
oversize_fee(S,200)  :- S > 65,  S =< 115.

/* ----------  Fee for an individual checked bag ---------- */
bag_extra_fee(Bag, ExtraFee) :-
    bag(Bag,L,W,H,Weight),
    size_sum(L,W,H,Size),
    overweight_fee(Weight,OW),
    oversize_fee(Size,OS),
    (OW >= OS -> ExtraFee = OW ; ExtraFee = OS).

bag_total_cost(Index, Cost) :-
    bag_order(Index,Bag),
    base_checked_fee(Index,Base),
    bag_extra_fee(Bag,Extra),
    Cost is Base + Extra.

/* ----------  Total baggage cost ---------- */
total_baggage_cost(Total) :-
    findall(C, (bag_order(I,_), bag_total_cost(I,C)), Cs),
    sum_list(Cs, Total).

/* ----------  Grand total (ticket + bags) ---------- */
total_cost(Grand) :-
    flight_ticket_price(Tix),
    total_baggage_cost(Bags),
    Grand is Tix + Bags.

/* ----------  Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.