/* ---------- Rules from the statutes that matter for this case ---------- */

/* Oversize fee (within / between U.S., Puerto Rico, U.S.V.I., Canada) */
oversize_fee(Size, Fee) :-
    (   Size =< 62 -> Fee = 0         % not oversize
    ;   Size =< 65 -> Fee = 30        % 62-65 in.
    ;   Size =< 115 -> Fee = 200      % 65-115 in.
    ).

/* Over-weight fee (within / between U.S., Puerto Rico, U.S.V.I., Canada)  */
overweight_fee(Index, Weight, Fee) :-
    % 1st & 2nd checked bags - 70-lb allowance for Business class
    Index =< 2,
    (   Weight =< 70  -> Fee = 0
    ;   Weight =< 100 -> Fee = 200              % 70-100 lb
    ).
overweight_fee(Index, Weight, Fee) :-
    % 3rd bag onward - 50-lb allowance
    Index > 2,
    (   Weight =< 50  -> Fee = 0
    ;   Weight =< 70  -> Fee = 100             % 50-70 lb
    ;   Weight =< 100 -> Fee = 200             % 70-100 lb
    ).

/* Checked-bag fee for Business class, travel wholly within the U.S. */
bag_number_fee(Index, Fee) :-
    (   Index =< 2 -> Fee = 0           % 1st & 2nd bags free
    ;   Index  = 3 -> Fee = 150         % 3rd bag
    ;   Index  > 3 -> Fee = 200         % 4th bag +
    ).

/* Helper: larger of two numbers */
max_fee(A, B, A) :- A >= B, !.
max_fee(_, B, B).

/* -------------------- Facts for this particular case -------------------- */

/* We choose an order that minimises cost
   (bags 8 and 11 become the 1st and 2nd checked bags)                */
bag(1,  65, 55).   % original item 8  - 37x18x10 (=65"), 55 lb
bag(2,  63, 64).   % original item 11 - 33x17x13 (=63"), 64 lb
bag(3, 104, 55).   % original item 2
bag(4,  88, 66).   % original item 3
bag(5,  69, 66).   % original item 4
bag(6,  65, 95).   % original item 5
bag(7,  64, 95).   % original item 6
bag(8,  80, 53).   % original item 7
bag(9,  90, 56).   % original item 9
bag(10, 90, 88).   % original item 10

/* ----------------------- Cost of every single bag ----------------------- */
bag_total(Index, Total) :-
    bag(Index, Size, Weight),
    oversize_fee(Size, OFee),
    overweight_fee(Index, Weight, WFee),
    max_fee(OFee, WFee, ExtraFee),          % only the higher of the two
    bag_number_fee(Index, NumFee),
    Total is ExtraFee + NumFee.

/* ---------------------------- Grand total ------------------------------- */
sum_list([], 0).
sum_list([H|T], S) :-
    sum_list(T, S0),
    S is H + S0.

total_cost(Total) :-
    findall(C, bag_total(_, C), Cs),
    sum_list(Cs, BagsCost),
    Ticket = 80,                           % flight ticket price
    Total is BagsCost + Ticket.

/* ------------------------------ Query ----------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.