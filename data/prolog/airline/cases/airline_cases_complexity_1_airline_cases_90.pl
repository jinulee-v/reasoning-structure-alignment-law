/* ----------  Statutory rules that apply to this case  ---------- */

/* route and passenger class */
route(us_to_india).
passenger_class(main_cabin).

/* free-checked-bag entitlements for this route / class */
first_checked_bag_free :-
    route(us_to_india),
    passenger_class(main_cabin).

/* checked-bag base fee for bag #N (only rules we need for U.S. <-> India, Main Cabin) */
base_checked_fee(1,0)  :- first_checked_bag_free.
base_checked_fee(1,40) :- \+ first_checked_bag_free.      /* (not used here) */

base_checked_fee(2,100).
base_checked_fee(3,200).
base_checked_fee(N,200) :- N>=4.

/* ---------------  Oversize fees (to / from India) ---------------- */
oversize_fee(Size,0)                    :- Size =< 62.
oversize_fee(Size,30)                   :- Size > 62,  Size =< 65.
oversize_fee(Size,200)                  :- Size > 65,  Size =< 115.

/* ---------------  Over-weight fees (to / from India) ------------- */
overweight_fee(Weight,0)                :- Weight =< 50.
overweight_fee(Weight,30)               :- Weight > 50, Weight =< 53.
overweight_fee(Weight,100)              :- Weight > 53, Weight =< 70.
overweight_fee(Weight,450)              :- Weight > 70, Weight =< 100.

/* take the higher of the two surcharges, per statute */
surcharge(Size,Weight,S) :-
    oversize_fee(Size,OF),
    overweight_fee(Weight,WF),
    (OF >= WF -> S = OF ; S = WF).

/* --------------------  Facts from the case  ---------------------- */
/* We ignore item #1 (20x13x9, 10 lbs) because it is the free carry-on.
   Bags 1-7 below are the 1st-7th checked bags for fee purposes        */

bag(1, size(65),  weight(53)).   /* 34*22*9  */
bag(2, size(63),  weight(53)).   /* 37*13*13 */
bag(3, size(64),  weight(51)).   /* 35*20*9  */
bag(4, size(86),  weight(96)).   /* 42*28*16 */
bag(5, size(114), weight(61)).   /* 54*32*28 */
bag(6, size(99),  weight(59)).   /* 49*25*25 */
bag(7, size(65),  weight(53)).   /* 37*18*10 */

/* -------------------  Derived bag-cost calculation --------------- */
bag_cost(Index,Cost) :-
    bag(Index,size(Size),weight(W)),
    base_checked_fee(Index,Base),
    surcharge(Size,W,S),
    Cost is Base + S.

/* sum all bag costs */
total_bag_cost(Total) :-
    findall(C,bag_cost(_,C),List),
    sum_list(List,Total).

/* --------------------  Overall total cost  ----------------------- */
flight_ticket_cost(634).

total_cost(Total) :-
    flight_ticket_cost(Tix),
    total_bag_cost(Bags),
    Total is Tix + Bags.

/* ------------------------  Query / Output  ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.