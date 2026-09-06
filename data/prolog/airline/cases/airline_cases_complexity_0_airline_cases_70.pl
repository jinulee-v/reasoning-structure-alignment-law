/* ----------  Statutory rules relevant to this case  ---------- */

/* This itinerary is between South America (Ecuador) and the U.S.         */
route(south_america_us).

/* ----------------  Facts about Robert's bags  ---------------- */

/* bag(Index, LinearSizeInches, WeightLbs).  (Only checked bags listed) */
bag(1,112,79).              /* 52+34+26   */
bag(2,63,53).               /* 37+12+14   */
bag(3,64,52).               /* 35+15+14   */
bag(4,112,93).              /* 49+34+29   */

/* Flight ticket price                                                  */
flight_ticket(314).

/* --------------  Base checked-bag fee (Premium Economy) -------------- */
/* 1st & 2nd bag free on this route; 3rd and every bag after = $200      */
base_checked_bag_fee(Index,0)   :- Index =:= 1 ; Index =:= 2.
base_checked_bag_fee(3,200).
base_checked_bag_fee(Index,200) :- Index >= 4.

/* ---------------------  Oversize fee (inches)  ----------------------- */
oversize_fee(Size,30)  :- Size > 62, Size =< 65.                               /* 62-65 in  */
oversize_fee(Size,150) :- Size > 65, Size =< 115, route(south_america_us).     /* 65-115 in */
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,0)   :- Size > 115.   /* (Not relevant here) */

/* --------------------  Over-weight fee (pounds) ---------------------- */
overweight_fee(W,200) :- W > 70,  W =< 100.            /* 70-100 lb */
overweight_fee(W,100) :- W > 53,  W =< 70.             /* 53-70 lb  */
overweight_fee(W,30)  :- W > 50,  W =< 53.             /* 50-53 lb  */
overweight_fee(W,0)   :- W =< 50.

/* --------------  Total fee for one checked bag  ---------------------- */
bag_fee(Index,TotalFee) :-
    bag(Index,Size,Weight),
    base_checked_bag_fee(Index,Base),
    oversize_fee(Size,Oversize),
    overweight_fee(Weight,Overweight),
    Extra is max(Oversize,Overweight),        /* only the higher of the 2 */
    TotalFee is Base + Extra.

/* -------------  Sum of all checked-bag fees for Robert  -------------- */
total_bag_cost(Sum) :-
    findall(F,bag_fee(_,F),List),
    sum_list(List,Sum).

/* ----------------------  Grand total owed  --------------------------- */
total_cost(Total) :-
    flight_ticket(T),
    total_bag_cost(Bags),
    Total is T + Bags.

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.