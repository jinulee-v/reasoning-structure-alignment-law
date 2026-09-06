/* ------------- Statutory rules that apply to this case ------------- */

/*  Premium Economy customers : 1st-2nd checked bag free              */
/*  3rd bag and every bag after that when flying to / from China : $200 */

base_bag_fee(Order, 0)   :- Order =< 2.          /* 1st, 2nd bag      */
base_bag_fee(Order, 200) :- Order >  2.          /* 3rd bag and after */

/* -------- Over-WEIGHT fees for trips to / from China --------------- */

overweight_fee(Wt, 0)    :- Wt =< 50.
overweight_fee(Wt, 30)   :- Wt  > 50, Wt =< 53.
overweight_fee(Wt, 100)  :- Wt  > 53, Wt =< 70.
overweight_fee(Wt, 450)  :- Wt  > 70, Wt =< 100.

/* -------- Over-SIZE fees for trips to / from China ----------------- */

oversize_fee(Sz, 0)    :- Sz =< 62.
oversize_fee(Sz, 30)   :- Sz >  62, Sz =< 65.
oversize_fee(Sz, 200)  :- Sz >  65, Sz =< 115.

/*  When both over-size and over-weight apply we charge the higher fee */
extra_fee(Wt, Sz, Fee) :-
        overweight_fee(Wt, Fw),
        oversize_fee(Sz,   Fs),
        (Fw >= Fs -> Fee = Fw ; Fee = Fs).

/* ------------------- Facts taken from the case -------------------- */

flight_price(1470).                       /* ticket cost in USD */

/* checked_bag(Index, Size-inches, Weight-lbs) */
checked_bag(1, 63, 60).
checked_bag(2,102, 78).
checked_bag(3, 65, 53).
checked_bag(4,112, 93).
checked_bag(5, 64, 51).
checked_bag(6, 68, 93).
checked_bag(7, 64, 51).
checked_bag(8,110, 77).
checked_bag(9, 65, 52).
checked_bag(10,64, 53).

/* ------------------- Cost computation rules ----------------------- */

bag_fee(Index, Fee) :-
        checked_bag(Index, Sz, Wt),
        base_bag_fee(Index, Base),
        extra_fee(Wt, Sz, Extra),
        Fee is Base + Extra.

total_checked_bags_cost(Total) :-
        findall(F, bag_fee(_,F), List),
        sum_list(List, Total).

total_cost(Total) :-
        flight_price(Flight),
        total_checked_bags_cost(Bags),
        Total is Flight + Bags.

/* ------------------- Query to obtain the answer ------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.