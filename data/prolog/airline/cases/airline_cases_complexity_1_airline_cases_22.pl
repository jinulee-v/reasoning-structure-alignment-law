/* ---------- Statutory rules (domestic U.S. trip, Main Cabin) ---------- */

% Oversize fees (in inches - sum of L+W+H)
oversize_fee(Size, 0)    :- Size =< 62.
oversize_fee(Size, 30)   :- Size  > 62, Size =< 65.
oversize_fee(Size, 200)  :- Size  > 65, Size =< 115.          % upper limit for acceptance

% Over-weight fees (in pounds)
overweight_fee(W, 0)     :- W =< 50.
overweight_fee(W, 30)    :- W  > 50,  W =< 53.
overweight_fee(W, 100)   :- W  > 53,  W =< 70.
overweight_fee(W, 200)   :- W  > 70,  W =< 100.               % >100 lbs not accepted

% The higher of the 2 surcharges applies (in addition to the checked-bag base fee)
surcharge(Size, Wt, Fee) :-
    oversize_fee(Size, O),
    overweight_fee(Wt,  W),
    (O >= W -> Fee = O ; Fee = W).

/* ---------- Checked-bag base fees (domestic Main Cabin) ---------- */
base_fee(1, 40).
base_fee(2, 45).
base_fee(3, 150).
base_fee(N, 200) :- N >= 4.

/* ---------- Robert's checked items (carry-on already free) ---------- */
/* bag(Index, Length, Width, Height, Weight) */
bag(1, 43, 22, 18, 67).
bag(2, 42, 20, 17, 99).
bag(3, 33, 20, 10, 52).
bag(4, 51, 28, 27, 57).
bag(5, 37, 15, 11, 85).
bag(6, 37, 17, 16, 53).
bag(7, 44, 21, 17, 53).

/* ---------- Cost calculation for a single bag ---------- */
bag_cost(Id, Cost) :-
    bag(Id, L, W, H, Weight),
    Size is L + W + H,
    surcharge(Size, Weight, Sur),
    base_fee(Id, Base),
    Cost is Base + Sur.

/* ---------- Utility: sum of a list ---------- */
sumlist([], 0).
sumlist([H|T], Sum) :-
    sumlist(T, Rest),
    Sum is H + Rest.

/* ---------- Aggregate costs ---------- */
checked_bags_cost(Total) :-
    findall(C, bag_cost(_, C), Costs),
    sumlist(Costs, Total).

flight_ticket(94).

total_cost(Total) :-
    checked_bags_cost(BagFees),
    flight_ticket(Ticket),
    Total is Ticket + BagFees.

/* ---------- Query & output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.