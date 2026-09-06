/* -------------  Statutory rules that apply to Patricia's trip ------------- */

% overweight fees for the China <-> U.S. region
overweight_fee(W, 0)    :- W =< 50.
overweight_fee(W, 30)   :- W > 50,  W =< 53.
overweight_fee(W, 100)  :- W > 53,  W =< 70.
overweight_fee(W, 450)  :- W > 70,  W =< 100.

% oversize fees for the China <-> U.S. region
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S > 62,  S =< 65.
oversize_fee(S, 200) :- S > 65,  S =< 115.

% choose the higher of the two
extra_fee(W, S, Fee) :-
    overweight_fee(W, OW),
    oversize_fee(S, OS),
    Fee is max(OW, OS).

% checked-bag fee for Main-Plus on the China <-> U.S. route
% (first 2 checked bags free, all others $200 each)
checked_bag_fee(Index, 0)   :- Index =< 2.
checked_bag_fee(Index, 200) :- Index  > 2.


/* ----------------------------  Case facts  ---------------------------- */

% bag(Number, Length, Width, Height, Weight).
% Bag #1 is used as the free carry-on; it is therefore excluded.
bag(2, 36, 20,  9, 94).
bag(3, 34, 20,  9, 59).
bag(4, 43, 25, 15, 53).
bag(5, 51, 32, 25, 62).
bag(6, 46, 27, 22, 53).
bag(7, 38, 12, 13, 53).
bag(8, 37, 17, 11, 94).
bag(9, 51, 28, 25, 64).
bag(10,44, 27, 21, 95).
bag(11,35, 19, 12, 53).

flight_ticket(1101).


/* ------------------------  Charge computation  ------------------------ */

% total for one checked bag (index within checked-bag sequence)
bag_total_fee(Index, BagNo, Fee) :-
    bag(BagNo, L, W, H, Weight),
    SumDim is L+W+H,
    extra_fee(Weight, SumDim, Extra),     % overweight / oversize
    checked_bag_fee(Index, CheckedFee),   % basic checked-bag fee
    Fee is Extra + CheckedFee.

% helper to create the ordered list of checked bags
checked_bag_list([2,3,4,5,6,7,8,9,10,11]).

% sum all bag fees
all_bags_fee(Total) :-
    checked_bag_list(List),
    all_bags_fee(List, 1, 0, Total).

all_bags_fee([], _, Acc, Acc).
all_bags_fee([BagNo|Rest], Index, Acc, Total) :-
    bag_total_fee(Index, BagNo, Fee),
    Acc1 is Acc + Fee,
    Index1 is Index + 1,
    all_bags_fee(Rest, Index1, Acc1, Total).

% grand total (ticket + all luggage charges)
total_cost(Total) :-
    flight_ticket(Ticket),
    all_bags_fee(BagFees),
    Total is Ticket + BagFees.


/* -----------------------------  Query  ----------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.