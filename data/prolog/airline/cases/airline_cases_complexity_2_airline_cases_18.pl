/* ----------  Statutory rules (extracts relevant to this case) ---------- */

/* 1.  Base checked-bag fee (Premium Economy, within the U.S.) */
base_checked_fee(Index, Fee) :-
    ( Index =< 2 -> Fee = 0          % 1st - 2nd bag free
    ; Index =:= 3 -> Fee = 150       % 3rd bag
    ; Index  >= 4 -> Fee = 200       % 4th bag +
    ).

/* 2.  Oversize fee (within U.S.) */
oversize_fee(DimSum, Fee) :-
    ( DimSum =< 62  -> Fee = 0
    ; DimSum =< 65  -> Fee = 30
    ; DimSum =< 115 -> Fee = 200
    ;                    Fee = 0    % >115 in not accepted - none in this case
    ).

/* 3.  Over-weight fee (within U.S.) */
overweight_fee(W, Fee) :-
    ( W =< 50  -> Fee = 0
    ; W =< 53  -> Fee = 30
    ; W =< 70  -> Fee = 100
    ; W =< 100 -> Fee = 200
    ;               Fee = 0        % >100 lbs not accepted - none in this case
    ).

/* 4.  Highest of overweight / oversize applies */
surcharge(DimSum, W, Fee) :-
    oversize_fee(DimSum, F1),
    overweight_fee(W,    F2),
    Fee is max(F1,F2).

/* 5.  Total fee per bag = base fee + surcharge */
bag_total_fee(Index, DimSum, W, Total) :-
    base_checked_fee(Index, Base),
    surcharge(DimSum, W, Surch),
    Total is Base + Surch.

/* ----------  Facts for William's trip ---------- */

ticket_price(146).

/* bag(Index, DimensionSumInches, WeightLbs)  - checked bags only        */
bag(1,108,52).
bag(2,109,52).
bag(3, 98,63).
bag(4,111,52).
bag(5, 63,67).
bag(6,114,74).
bag(7, 64,58).
bag(8, 65,51).
bag(9, 81,52).
bag(10,64,82).

/* ----------  Auxiliary ---------- */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S1), S is H+S1.

/* ----------  Aggregate baggage fees ---------- */
total_baggage_fee(Sum) :-
    findall(F, (bag(I,D,W), bag_total_fee(I,D,W,F)), L),
    sum_list(L, Sum).

/* ----------  Grand total (ticket + bags) ---------- */
total_cost(Total) :-
    ticket_price(P),
    total_baggage_fee(Bags),
    Total is P + Bags.

/* ----------  Query & output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.