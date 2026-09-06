/* =====================  Statutory rules  ===================== */

/* ----- route category (used for the tariff tables) ----- */
route_category(dallas, berlin, us_europe).

/* ----- cabin carried by the passenger ----- */
cabin(premium_economy).

/* ----- limits that make a bag a free carry-on (inches) ----- */
carry_on_limit(22,14,9).

/* ========== checked-bag BASE fee for Premium-Economy, U.S-Europe ========== */
base_checked_fee(premium_economy, us_europe, 1, 0).   /* 1st bag */
base_checked_fee(premium_economy, us_europe, 2, 0).   /* 2nd bag */
base_checked_fee(premium_economy, us_europe, N, 200) :- N>=3.   /* 3rd & 4th+ */

/* ========== overweight fee (any route) ========== */
overweight_fee(Weight, _RouteCat, Fee) :-
    Weight =< 50,                    Fee = 0.
overweight_fee(Weight, _RouteCat, 30) :-
    Weight  > 50, Weight =< 53.
overweight_fee(Weight, us_europe, 100) :-
    Weight  > 53, Weight =< 70.

/* bags >70 lbs on U.S.-Europe flights are "not accepted"; not needed here */

/* ========== oversize fee (any route) ========== */
oversize_fee(DimSum, _RouteCat, 0) :-
    DimSum =< 62.
oversize_fee(DimSum, _RouteCat, 30) :-
    DimSum  > 62, DimSum =< 65.
oversize_fee(DimSum, _RouteCat, 150) :-
    DimSum  > 65, DimSum =< 115.

/* ========== surcharge (highest of over-weight or over-size) ========== */
surcharge(Weight, DimSum, RouteCat, Fee) :-
    overweight_fee(Weight, RouteCat, OW),
    oversize_fee(DimSum,  RouteCat, OS),
    Fee is max(OW,OS).

/* =====================  Case facts  ===================== */

flight(james, dallas, berlin, 400).           /* ticket price */

bag(1, 20,13, 8,  6).    /* backpack - carry-on           */
bag(2, 38,17,10, 65).    /* checked                       */
bag(3, 47,31,27, 52).    /* checked                       */
bag(4, 34,20,11, 53).    /* checked                       */
bag(5, 33,17,14, 51).    /* checked                       */

/* helper: is the bag a free carry-on? */
carry_on(BagId) :-
    bag(BagId,L,W,H,_),
    carry_on_limit(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

/* collect checked bags in their given order */
checked_bag_ordered(List) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), List).

/* fee for each checked bag (base + surcharge) */
bag_total_fee(Index, BagId, Fee) :-
    cabin(Cab), bag(BagId,L,W,H,Weight),
    route_category(dallas, berlin, RC),
    DimSum is L+W+H,
    surcharge(Weight,DimSum,RC,Surch),
    base_checked_fee(Cab,RC,Index,Base),
    Fee is Base + Surch.

/* grand total for all checked bags */
checked_bags_cost(Total) :-
    checked_bag_ordered(List),
    findall(F,
            (nth1(I,List,BagId), bag_total_fee(I,BagId,F)),
            Fees),
    sum_list(Fees,Total).

/* =====================  Final total cost  ===================== */
total_cost(All) :-
    flight(james, dallas, berlin, Ticket),
    checked_bags_cost(Bags),
    All is Ticket + Bags.

/* =====================  Query & output  ===================== */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.