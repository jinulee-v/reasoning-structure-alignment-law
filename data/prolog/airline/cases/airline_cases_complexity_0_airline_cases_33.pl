/*********************************************************************
*  American Airlines - Bag-fee rules (subset needed for Daniel's trip)
*********************************************************************/

% ---------- 1.  BASE FEE FOR A CHECKED BAG (Main Cabin, within U.S.) 
base_checked_fee(1, 40).
base_checked_fee(2, 45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N >= 4.          % 4th bag and every bag after

% ---------- 2.  SURCHARGE FOR OVERWEIGHT (lbs)
overweight_surcharge(W, 30) :- W > 50, W =< 53.
overweight_surcharge(W,100) :- W > 53, W =< 70.
overweight_surcharge(W,200) :- W > 70, W =< 100.
overweight_surcharge(W,  0) :- W =< 50.

% ---------- 3.  SURCHARGE FOR OVERSIZE (total inches = L+W+H)
oversize_surcharge(D, 30) :- D > 62, D =< 65.
oversize_surcharge(D,200) :- D > 65, D =< 115.
oversize_surcharge(D,  0) :- D =< 62.

% ---------- 4.  CHOOSE THE HIGHER OF OVERSIZE vs OVERWEIGHT
bag_surcharge(Dim, Wt, S) :-
    oversize_surcharge(Dim, SO),
    overweight_surcharge(Wt , SW),
    (SO >= SW -> S = SO ; S = SW).

/*********************************************************************
*  Daniel's facts
*********************************************************************/
% bag(ID, Length, Width, Height, Weight)
bag(bag1, 22,11, 7,  6).   % free carry-on
bag(bag2, 51,31,26, 67).
bag(bag3, 34,21, 9, 51).
bag(bag4, 47,22,22, 72).
bag(bag5, 47,31,24, 79).

% Order in which Daniel will check his bags
bag_order(1, bag2).
bag_order(2, bag4).
bag_order(3, bag5).
bag_order(4, bag3).

/*********************************************************************
*  Cost of every checked bag and of the whole trip
*********************************************************************/
bag_cost(Index, Cost) :-
    bag_order(Index, Id),
    bag(Id, L, W, H, Weight),
    Dim is L + W + H,
    bag_surcharge(Dim, Weight, Surcharge),
    base_checked_fee(Index, Base),
    Cost is Base + Surcharge.

total_checked_bag_fee(Total) :-
    findall(C, bag_cost(_, C), Cs),
    sum_list(Cs, Total).

% Flight ticket
ticket_price(250).

% Grand total Daniel must pay
total_cost(Total) :-
    ticket_price(Tix),
    total_checked_bag_fee(Bags),
    Total is Tix + Bags.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.