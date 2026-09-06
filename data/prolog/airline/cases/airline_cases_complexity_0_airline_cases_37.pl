/* -------------  Statutory rules that apply to this case ------------- */

flight_ticket_cost(312).

% Passenger data
class(premium_economy).
region(to_from_japan).          % 'Japan <--> U.S.' bracket

/* ------------  Items Elizabeth is travelling with  ----------------- */
/* item(Id, Length, Width, Height, WeightInLbs) */

item(1, 19, 14,  7,  6).   % cabin bag - will be treated as carry-on
item(2, 38, 12, 14, 52).
item(3, 36, 18, 10, 86).
item(4, 49, 30, 21, 90).
item(5, 38, 18,  9, 55).

/* --------------------  Helper predicates  --------------------------- */

dims_sum(L, W, H, S) :- S is L+W+H.

/* Carry-on test (22 x 14 x 9 in. or smaller) */
carry_on(L, W, H) :- L =< 22, W =< 14, H =< 9.

/* A checked item is any piece that is NOT a carry-on */
checked_item_id(Id) :-
    item(Id, L, W, H, _),
    \+ carry_on(L, W, H).

checked_items(Ids) :-
    findall(Id, checked_item_id(Id), Ids).   % [2,3,4,5] in this case

/* -----------------  Base fee for checked bags  ---------------------- */

base_bag_fee(N, premium_economy, to_from_japan, 0)   :- N =< 2.   % 1st & 2nd free
base_bag_fee(3, premium_economy, to_from_japan, 200).
base_bag_fee(N, premium_economy, to_from_japan, 200) :- N >= 4.   % 4th +  $200

/* ------------------  Over-WEIGHT surcharges  ------------------------ */

overweight_fee(W, _,                0)  :- W =< 50.
overweight_fee(W, _,               30)  :- W  > 50, W =< 53.
overweight_fee(W, to_from_japan,  100)  :- W  > 53, W =< 70.
overweight_fee(W, to_from_japan,  450)  :- W  > 70, W =< 100.

/* ------------------  Over-SIZE surcharges  -------------------------- */

oversize_fee(S, _,                0)  :- S =< 62.
oversize_fee(S, to_from_japan,   30)  :- S  > 62, S =< 65.
oversize_fee(S, to_from_japan,  200)  :- S  > 65, S =< 115.

/* -------- Highest of over-weight vs over-size (only one applies) ---- */

bag_extra_fee(W, S, Region, Extra) :-
    overweight_fee(W, Region, OW),
    oversize_fee( S, Region, OS),
    ( OW >= OS -> Extra = OW ; Extra = OS ).

/* -------------------------  Bag cost  ------------------------------- */

bag_cost(Index, Cost) :-
    checked_items(Ids),
    nth1(Index, Ids, Id),                    % keeps bag order 1,2,3,4
    item(Id, L, W, H, Weight),
    dims_sum(L, W, H, SizeSum),
    class(Class),
    region(Region),
    base_bag_fee(Index, Class, Region, Base),
    bag_extra_fee(Weight, SizeSum, Region, Extra),
    Cost is Base + Extra.

/* ------------  Aggregate costs for all checked bags  ---------------- */

total_bags_cost(Total) :-
    findall(C, bag_cost(_, C), Cs),
    sumlist(Cs, Total).

/* -----------------------  Grand total  ------------------------------ */

total_cost(Total) :-
    flight_ticket_cost(Ticket),
    total_bags_cost(Bags),
    Total is Ticket + Bags.

/* -------------------------  Query  ---------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.