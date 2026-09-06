/* ---------------  RULES (statutes) --------------- */

% ---------------- Carry-on rules ----------------
carry_on_size_ok(L, W, H) :-
    L =< 22, W =< 14, H =< 9.

% ---------------- Base checked-bag fees (Premium Economy - within U.S.) ----------------
base_fee_premium_us(1, 0).
base_fee_premium_us(2, 0).
base_fee_premium_us(3, 150).
base_fee_premium_us(N, 200) :- N >= 4.

% ---------------- Overweight fees (within U.S.) ----------------
overweight_fee(Weight, 0)   :- Weight =< 50.
overweight_fee(Weight, 30)  :- Weight  > 50, Weight =< 53.
overweight_fee(Weight, 100) :- Weight  > 53, Weight =< 70.
overweight_fee(Weight, 200) :- Weight  > 70, Weight =< 100.

% ---------------- Oversize fees (within U.S.) ----------------
oversize_fee(L, W, H, 0)   :- S is L+W+H, S =< 62.
oversize_fee(L, W, H, 30)  :- S is L+W+H, S  > 62, S =< 65.
oversize_fee(L, W, H, 200) :- S is L+W+H, S  > 65, S =< 115.

% ---------------- Fee for a single checked bag ----------------
bag_fee(Index, L, W, H, Weight, Fee) :-
    base_fee_premium_us(Index, Base),
    oversize_fee(L, W, H, OSize),
    overweight_fee(Weight, OWeight),
    Extra is max(OSize, OWeight),
    Fee is Base + Extra.

% ---------------- Sum a list ----------------
sum_list([], 0).
sum_list([H|T], Sum) :-
    sum_list(T, Rest), Sum is H + Rest.

/* ---------------  FACTS (case description) --------------- */

% bag(Id, Length, Width, Height, Weight).
bag( 1, 21, 14,  6,  10).   % Backpack (chosen as carry-on)
bag( 2, 34, 21,  9,  52).
bag( 3, 50, 30, 22,  71).
bag( 4, 34, 19, 10,  52).
bag( 5, 37, 18,  9,  94).
bag( 6, 36, 16, 11,  81).
bag( 7, 40, 13, 16,  51).
bag( 8, 38, 27, 14,  52).
bag( 9, 44, 18, 20,  75).
bag(10, 45, 20, 20,  58).
bag(11, 35, 20,  9,  78).

% Flight ticket price
ticket_price(228).

/* ---------------  Determine which bags are checked --------------- */

% Bag 1 fits carry-on size, therefore it is NOT checked.
checked_bag_id(Id) :-
    bag(Id, L, W, H, _),
    \+ (carry_on_size_ok(L, W, H), Id = 1),  % only bag 1 qualifies and is used as carry-on
    Id \= 1.                                 % every other bag is checked

/* ---------------  Compute total checked-bag cost --------------- */

checked_bag_fees(Fees) :-
    findall(F,
            (               % enumerate checked bags in the order 2,3,4,...
                findall(Id, checked_bag_id(Id), Ids),
                nth1(Index, Ids, Id),
                bag(Id, L, W, H, Weight),
                bag_fee(Index, L, W, H, Weight, F)
            ),
            Fees).

total_bag_cost(Total) :-
    checked_bag_fees(Fees),
    sum_list(Fees, Total).

/* ---------------  Total trip cost --------------- */

total_cost(Total) :-
    ticket_price(T),
    total_bag_cost(BagCost),
    Total is T + BagCost.

/* ---------------  Query & print ---------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.