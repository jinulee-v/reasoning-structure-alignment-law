/* ----------  RULES NEEDED FOR THIS CASE ONLY  ---------- */

/* flight information */
route(seattle, quito, us_to_south_america).
cabin(main_cabin).
flight_ticket_fee(429).

/* ---------------------  BAG LIST  ---------------------- */
/* bag(Id, Length, Width, Height, WeightLbs).              */
/* (Only the 7 checked bags are listed - Joseph's small    */
/*  18x13x6 backpack is his free personal item.)           */

bag(1, 43, 26, 17, 67).
bag(2, 43, 27, 19, 89).
bag(3, 38, 13, 12, 89).
bag(4, 50, 35, 29, 96).
bag(5, 35, 17, 11, 52).
bag(6, 36, 18, 11, 57).
bag(7, 40, 29, 16, 59).

/* ---------------  BASE CHECKED-BAG FEES  --------------- */
/* For a Main Cabin customer flying between the U.S. and   */
/* South America (ex-Guyana/Suriname):                     */
/*   1st bag: $0                                           */
/*   2nd bag: $100                                         */
/*   3rd bag: $200                                         */
/*   4th bag and beyond: $200 each                         */

base_fee(BagNo, 0   ) :- BagNo =:= 1.
base_fee(BagNo, 100 ) :- BagNo =:= 2.
base_fee(BagNo, 200 ) :- BagNo >= 3.

/* ---------------  OVERSIZE / OVERWEIGHT  --------------- */

/* size of a bag */
size_in(L, W, H, S) :- S is L + W + H.

/* oversize fee (South America rules) */
oversize_fee(Size, 0  ) :- Size =< 62.
oversize_fee(Size, 30 ) :- Size  > 62, Size =< 65.
oversize_fee(Size, 150) :- Size  > 65, Size =< 115.

/* overweight fee (U.S. <-> South America rules) */
overweight_fee(W, 0  ) :- W =< 50.
overweight_fee(W, 30 ) :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.

/* for a bag that is both oversize and overweight,         */
/* apply ONLY the higher of the two surcharges             */
extra_fee(Size, W, Fee) :-
    oversize_fee(Size, OF),
    overweight_fee(W, WF),
    (OF >= WF -> Fee = OF ; Fee = WF).

/* ---------------  TOTAL PER-BAG COST  ------------------ */
bag_total_cost(BagNo, Cost) :-
    bag(BagNo, L, W, H, Weight),
    size_in(L, W, H, Size),
    extra_fee(Size, Weight, Extra),
    base_fee(BagNo, Base),
    Cost is Base + Extra.

/* sum all bag costs */
total_bag_cost(Total) :-
    findall(C, (bag(BN,_,_,_,_), bag_total_cost(BN,C)), Cs),
    sum_list(Cs, Total).

/* overall trip cost = ticket + bags */
total_cost(Total) :-
    flight_ticket_fee(Ticket),
    total_bag_cost(Bags),
    Total is Ticket + Bags.

/* --------------------  QUERY  --------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.