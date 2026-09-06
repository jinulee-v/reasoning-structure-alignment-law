/* ----------  Facts describing the flight and the bags ---------- */

flight_cost(461).                         % Ticket price in USD

%  bag(ID, Length, Width, Height, Weight).
bag(bag1, 21, 13,  7,  8).                % Carry-on (free)
bag(bag2, 50, 38, 27, 74).                % Checked #1
bag(bag3, 37, 16, 10, 51).                % Checked #2
bag(bag4, 43, 25, 18, 65).                % Checked #3
bag(bag5, 34, 17, 13, 75).                % Checked #4

/* ----------  Helper predicates ---------- */

% size(+BagID, -Size)   - total outside dimensions in inches
size(BagID, Size) :-
    bag(BagID, L, W, H, _),
    Size is L + W + H.

% carry_on(+BagID)      - true when bag fits the carry-on sizer
carry_on(BagID) :-
    bag(BagID, L, W, H, _),
    L =< 22, W =< 14, H =< 9.

% The four checked bags in the order we'll charge them
checked_bag(1, bag2).
checked_bag(2, bag3).
checked_bag(3, bag4).
checked_bag(4, bag5).

/* ----------  Base checked-bag fees for First Class (Peru->USA) ---------- */

% First Class: bags 1-3 free, 4th and later $200
base_fee(Index, 0   ) :- Index =< 3, !.
base_fee(_,     200).

/* ----------  Oversize / Over-weight fees (South America -> U.S.) ---------- */

% oversize_fee(+Size, -Fee)
oversize_fee(Size, 0  ) :- Size =< 62, !.
oversize_fee(Size, 30 ) :- Size =< 65, !.
oversize_fee(Size, 150) :- Size =< 115, !.
oversize_fee(_,    0  ).          % Larger than 115 in. would be "not accepted"

% overweight_fee(+Weight, -Fee)
overweight_fee(W, 0  ) :- W =< 50, !.
overweight_fee(W, 30 ) :- W =< 53, !.
overweight_fee(W, 100) :- W =< 70, !.
overweight_fee(W, 200) :- W =< 100, !.
overweight_fee(_, _)  :- fail.     % >100 lb not accepted (not needed here)

/* ----------  Fee for each checked bag ---------- */

% bag_fee(+Index, +BagID, -FeeForThatBag)
% "Higher of oversize / overweight" + base checked-bag fee.
bag_fee(Index, BagID, TotalFee) :-
    bag(BagID, _, _, _, W),
    size(BagID, S),
    oversize_fee(S, OSFee),
    overweight_fee(W, OWFee),
    ( OSFee >= OWFee -> Extra is OSFee ; Extra is OWFee ),
    base_fee(Index, Base),
    TotalFee is Base + Extra.

/* ----------  Total of all bag fees ---------- */

total_bag_fees(Total) :-
    findall(F, (checked_bag(I, B), bag_fee(I, B, F)), Fees),
    sum_list(Fees, Total).

/* ----------  Grand total (ticket + bags) ---------- */

total_cost(Total) :-
    flight_cost(Ticket),
    total_bag_fees(Bags),
    Total is Ticket + Bags.

/* ----------  Query to display the answer ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.