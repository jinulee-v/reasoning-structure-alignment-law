/* -------------  Statutory rules (only those relevant to this case) ------------- */

/* passenger data */
passenger_class(premium_economy).
route(to_from_china).          /* Austin - Shenzhen                         */
ticket_price(1096).

/* checked-bag facts - index starts with 1 for the FIRST checked bag      */
/* bag(Index, Weight_lbs, Length_in, Width_in, Height_in).                */
bag(1, 70, 45, 32, 23).   /* backpack (45 x 32 x 23 in, 70 lbs)  */
bag(2, 90, 42, 24, 14).   /* luggage box (42 x 24 x 14 in, 90 lbs) */
bag(3, 53, 41, 22, 14).   /* backpack (41 x 22 x 14 in, 53 lbs) */
bag(4, 51, 37, 23, 17).   /* backpack (37 x 23 x 17 in, 51 lbs) */

/* ---------------------------------------------------------------------- */
/* # complimentary checked-bag entitlement                               */
/* Premium-Economy customers get the 1st & 2nd checked bags free on all   */
/* itineraries (statute: "1st and 2nd checked bags are complimentary for */
/* Confirmed Premium Economy customers").                                */
free_checked_bags(premium_economy, 2).

/* -------------------  BASE BAG FEE  ----------------------------------- */
base_bag_fee(Index, Class, Route, 0) :-
    free_checked_bags(Class, Free),
    Index =< Free.

base_bag_fee(3, premium_economy, to_from_china, 200).
base_bag_fee(Index, premium_economy, to_from_china, 200) :-
    Index >= 4.

/* -------------------  WEIGHT SURCHARGE  ------------------------------- */
/* Over-50-53 lbs  -> $30 (all routes / classes)                          */
weight_fee(W, _, 30) :-
    W > 50, W =< 53.

/* Over-53-70 lbs (to / from China et al.) -> $100                        */
weight_fee(W, to_from_china, 100) :-
    W > 53, W =< 70.

/* Over-70-100 lbs (to / from China et al.) -> $450                       */
weight_fee(W, to_from_china, 450) :-
    W > 70, W =< 100.

/* =<50 lbs -> no weight surcharge                                         */
weight_fee(W, _, 0) :- W =< 50.

/* -------------------  SIZE SURCHARGE  --------------------------------- */
size_sum(L,W,H,S) :- S is L+W+H.

/* 62-65 in -> $30                                                        */
size_fee(S, _, 30) :-
    S > 62, S =< 65.

/* 65-115 in (to / from China et al.) -> $200                             */
size_fee(S, to_from_china, 200) :-
    S > 65, S =< 115.

/* =<62 in -> no size surcharge                                            */
size_fee(S, _, 0) :- S =< 62.

/* -------------------  EXTRA SURCHARGE PER BAG ------------------------- */
/* If both weight & size surcharges apply, charge only the HIGHER one.    */
extra_fee(Index, Fee) :-
    bag(Index, W, L, B, H),
    route(Route),
    weight_fee(W, Route, WF),
    size_sum(L,B,H,S),
    size_fee(S, Route, SF),
    (WF >= SF -> Fee = WF ; Fee = SF).

/* -------------------  TOTAL FEE PER BAG ------------------------------- */
bag_fee(Index, Fee) :-
    passenger_class(Class),
    route(Route),
    base_bag_fee(Index, Class, Route, Base),
    extra_fee(Index, Extra),
    Fee is Base + Extra.

/* -------------------  SUM ALL BAG FEES -------------------------------- */
total_bag_fees(Total) :-
    findall(F, (bag(Index,_,_,_,_), bag_fee(Index, F)), Fees),
    sum_list(Fees, Total).

/* -------------------  OVERALL COST ------------------------------------ */
total_cost(Total) :-
    ticket_price(Ticket),
    total_bag_fees(Bags),
    Total is Ticket + Bags.

/* -------------------  Query ------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.