/* --------------------  Facts  -------------------- */
% bag(Index, Length, Width, Height, Weight).
bag(1,19,12,8,7).
bag(2,49,32,26,51).
bag(3,37,14,14,88).
bag(4,37,22,18,72).
bag(5,37,17,11,93).

% Bag 1 is used as the single free carry-on item
carry_on(1).

% checked_order(BagIndex, CheckedOrderNumber)
checked_order(2,1).
checked_order(3,2).
checked_order(4,3).
checked_order(5,4).

% Flight ticket price
flight_ticket(385).

/* --------------------  Helpers  -------------------- */
dim_sum(L,W,H,S)  :- S is L+W+H.

% Oversize fees for travel to / from Japan
oversize_fee(S,0)    :- S =< 62.
oversize_fee(S,30)   :- S  > 62, S  =< 65.
oversize_fee(S,200)  :- S  > 65, S =< 115.

% Overweight fees for travel to / from Japan
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W  > 50, W =< 53.
overweight_fee(W,100)  :- W  > 53, W =< 70.
overweight_fee(W,450)  :- W  > 70, W =< 100.

% Checked-bag base fee (Basic Economy, US <-> Japan)
checked_bag_fee(1,75).
checked_bag_fee(2,100).
checked_bag_fee(3,200).
checked_bag_fee(N,200) :- N >= 4.

/* --------------------  Bag cost calculation  -------------------- */
additional_fee(Index,Fee) :-
    bag(Index,L,W,H,Weight),
    dim_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,OW),
    ( OS >= OW -> Fee = OS ; Fee = OW ).

bag_cost(Index,0) :- carry_on(Index).               % free carry-on
bag_cost(Index,Cost) :-
    checked_order(Index,Order),
    checked_bag_fee(Order,Base),
    additional_fee(Index,Add),
    Cost is Base + Add.

/* --------------------  Totals  -------------------- */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,R), S is H+R.

baggage_total(Total) :-
    findall(C, (bag(I,_,_,_,_), bag_cost(I,C)), Cs),
    sum_list(Cs,Total).

total_cost(Total) :-
    flight_ticket(T),
    baggage_total(B),
    Total is T + B.

/* --------------------  Query / Output  -------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.