/* ---------------  Statutory rules that apply to this case --------------- */

% overweight fee - route: China <-> U.S. (all classes)
overweight_fee(Weight,Fee) :-
        (Weight > 70 , Weight =< 100 -> Fee = 450
        ;Weight > 53 , Weight =< 70  -> Fee = 100
        ;Weight > 50 , Weight =< 53  -> Fee = 30
        ;                                   Fee = 0).

% oversize fee - route: China <-> U.S.
oversize_fee(Dim,Fee) :-
        (Dim > 65 ,  Dim =< 115 -> Fee = 200
        ;Dim > 62 , Dim =< 65  -> Fee = 30
        ;                         Fee = 0).

% the higher of the 2 applies (never both)
extra_fee(Index,Fee) :-
        bag(Index,L,W,H,Weight),
        Dim is L+W+H,
        overweight_fee(Weight,OW),
        oversize_fee(Dim,OS),
        max_list([OW,OS],Fee).

/* -----------------------  Baggage list (the facts) ----------------------- */

% bag(Index, Length, Width, Height, Weight).

bag(1, 20,13, 8,  9).      % carry-on - free
bag(2, 37,18, 9, 51).
bag(3, 38,16,10, 53).
bag(4, 41,24,15, 59).
bag(5, 35,19,10, 79).
bag(6, 43,22,21, 91).
bag(7, 48,33,26, 60).
bag(8, 51,33,23, 52).
bag(9, 35,19, 9, 51).
bag(10,42,20,15, 68).
bag(11,37,21,12, 65).

/* ------------------------  Checked-bag ordering -------------------------- */

checked_bag_indices([2,3,4,5,6,7,8,9,10,11]).

checked_bag_order(Index,Order) :-
        checked_bag_indices(List),
        nth1(Order,List,Index).

/* ----------------------  First-class base bag fees ----------------------- */

bag_base_fee(Order,Fee) :-
        (Order =< 3 -> Fee = 0       % 1st-3rd bag free
        ;               Fee = 200).  % 4th bag onwards

bag_total_fee(Index,Total) :-
        checked_bag_order(Index,Order),
        bag_base_fee(Order,Base),
        extra_fee(Index,Extra),
        Total is Base + Extra.

/* ----------------------------  Ticket price ----------------------------- */

flight_ticket(526).

/* -----------------------------  Aggregation ----------------------------- */

total_cost(Total) :-
        flight_ticket(Ticket),
        findall(F,bag_total_fee(_,F),Fees),
        sum_list(Fees,BagTotal),
        Total is Ticket + BagTotal.

/* -------------------------  Final query / output ------------------------ */

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.