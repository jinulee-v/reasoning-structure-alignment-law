/* ----------  Facts about the flight / passenger  ---------- */
flight_route(chengdu, atlanta).          % From China to U.S.
travel_class(main_cabin).                % Main Cabin customer
flight_ticket(563).                      % USD

/* ----------  Checked-bag facts (carry-on is not listed here) ---------- */
/* bag(Id, Length, Width, Height, Weight). */
bag(2, 33, 22, 10, 60).
bag(3, 46, 21, 20, 63).
bag(4, 33, 18, 13, 51).
bag(5, 36, 13, 14, 78).
bag(6, 43, 21, 19, 55).
bag(7, 42, 23, 21, 51).
bag(8, 45, 34, 22, 60).
bag(9, 38, 15, 11, 51).
bag(10, 49, 29, 23, 66).
bag(11, 45, 25, 17, 51).

/* ----------  Rules for oversize / overweight fees (China <--> U.S.) ---------- */
oversize_fee(Dim, 0)   :- Dim =< 62.
oversize_fee(Dim, 30)  :- Dim > 62,  Dim =< 65.
oversize_fee(Dim, 200) :- Dim > 65,  Dim =< 115.
oversize_fee(Dim, nf)  :- Dim > 115.          % nf = not-accepted (won't occur here)

overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W > 50,  W =< 53.
overweight_fee(W, 100) :- W > 53,  W =< 70.
overweight_fee(W, 450) :- W > 70,  W =< 100.
overweight_fee(W, nf)  :- W > 100.            % not-accepted (won't occur here)

/* Choose the higher of the 2 fees (if both apply) */
surcharge(Id, Fee) :-
    bag(Id,L,W,H,Weight),
    Dim is L+W+H,
    oversize_fee(Dim, OF),
    overweight_fee(Weight, WF),
    max_fee(OF, WF, Fee).

max_fee(nf, _, nf).
max_fee(_, nf, nf).
max_fee(F1, F2, F1) :- number(F1), number(F2), F1 >= F2.
max_fee(F1, F2, F2) :- number(F1), number(F2), F2 >  F1.

/* ----------  Base checked-bag fees for Main Cabin (China <--> U.S.) ---------- */
/* 1st bag free (complimentary for flights to / from China, non-Basic) */
base_fee(1, 0).
base_fee(2, 100).
base_fee(N, 200) :- N >= 3.

/* ----------  Total for all checked bags  ---------- */
bag_total(Total) :-
    findall(Id, bag(Id,_,_,_,_), Ids),
    checked_bags_cost(Ids, 1, 0, Total).

checked_bags_cost([], _, Acc, Acc).
checked_bags_cost([Id|Rest], Index, Acc0, Total) :-
    base_fee(Index, BF),
    surcharge(Id, SF),
    Acc1 is Acc0 + BF + SF,
    NextIndex is Index + 1,
    checked_bags_cost(Rest, NextIndex, Acc1, Total).

/* ----------  Grand total (ticket + bags) ---------- */
total_cost(Total) :-
    flight_ticket(Ticket),
    bag_total(Bags),
    Total is Ticket + Bags.

/* ----------  Query & output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.