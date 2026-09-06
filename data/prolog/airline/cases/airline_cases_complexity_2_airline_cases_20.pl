/* ---------------  Facts describing the passenger and the trip --------------- */

% flight and passenger facts
ticket_cost(473).
cabin_class(first).                                % James is a First Class customer
route(india_to_usa).                               % Mumbai (India)  --->  Philadelphia (USA)

% the 1st item (index 1) is a carry-on, so only items 2-11 are checked
% bag(Index, Length, Width, Height, Weight).
bag( 2, 43, 29, 19, 51).
bag( 3, 35, 16, 13, 71).
bag( 4, 36, 13, 14, 54).
bag( 5, 38, 13, 13, 53).
bag( 6, 33, 17, 13, 68).
bag( 7, 38, 14, 11, 98).
bag( 8, 36, 16, 13, 63).
bag( 9, 37, 16, 12, 51).
bag(10, 37, 13, 14, 97).
bag(11, 36, 16, 11, 51).

checked_indices([2,3,4,5,6,7,8,9,10,11]).

/* --------------------------  Helper predicates  ----------------------------- */

% linear size of a bag
size(Index, S) :- bag(Index, L, W, H, _), S is L+W+H.

% ---------------- Oversize fee (to / from India) ----------------
% 0-62 in  -> 0   ;  >62-65 in -> $30 ;   >65-115 in -> $200
oversize_fee(Index, Fee) :-
    size(Index, S),
    (   S =< 62                    -> Fee = 0
    ;   S =< 65                    -> Fee = 30
    ;   S =< 115                   -> Fee = 200 ).

% ---------------- Over-weight fee (to / from India) ---------------
% table valid for all cabins, including First
weight_band_fee(W, 0   ) :- W =< 50.
weight_band_fee(W, 30  ) :- W > 50,  W =< 53.
weight_band_fee(W, 100 ) :- W > 53,  W =< 70.
weight_band_fee(W, 450 ) :- W > 70,  W =< 100.

% fee actually payable, taking into account 70-lb allowance
% for the 3 complimentary bags
overweight_fee(Index, complimentary, Fee) :-
    bag(Index, _, _, _, W),
    (   W =< 70
    ->  Fee = 0
    ;   weight_band_fee(W, Fee)
    ).
overweight_fee(Index, charged, Fee) :-
    bag(Index, _, _, _, W),
    weight_band_fee(W, Fee).

% ---------------- Base (checked-bag) fee ----------------
% First Class, India<->USA :
%   bags 1-3 : $0
%   bag 4+   : $200  each
base_fee(BagNo, 0) :- BagNo =< 3.                 % complimentary
base_fee(BagNo, 200) :- BagNo  > 3.               % fourth bag +

/* -------- Fee for one bag, given whether it's complimentary ---------- */
single_bag_fee(Index, BagSeqNo, complimentary, Fee) :-
    oversize_fee(Index, OS),
    overweight_fee(Index, complimentary, OW),
    Max is max(OS, OW),
    base_fee(BagSeqNo, BF),
    Fee is BF + Max.

single_bag_fee(Index, BagSeqNo, charged, Fee) :-
    oversize_fee(Index, OS),
    overweight_fee(Index, charged, OW),
    Max is max(OS, OW),
    base_fee(BagSeqNo, BF),        % BF = 200 here
    Fee is BF + Max.

/* ----------  Choosing which 3 bags are complimentary  ---------------- */

% choose K elements out of a list (simple combinatorial helper)
combination(0, _, []).
combination(K, [H|T], [H|Rest]) :-
        K > 0, K1 is K-1, combination(K1, T, Rest).
combination(K, [_|T], Rest) :-
        K > 0, combination(K, T, Rest).

% cost for a given set of 3 complimentary bag indices
bags_cost(FreeIndices, Total) :-
    checked_indices(All),
    findall(Fee,
        (nth1(Pos, All, Index),
         (member(Index, FreeIndices) -> Status = complimentary ; Status = charged),
         single_bag_fee(Index, Pos, Status, Fee)),
        Fees),
    sumlist(Fees, Total).

% minimal possible cost for all checked luggage
minimal_bags_cost(Min) :-
    checked_indices(All),
    findall(Cost,
       (combination(3, All, Free), bags_cost(Free, Cost)),
       Costs),
    min_list(Costs, Min).

/* ---------------  Grand total (ticket + all luggage) ---------------- */
total_cost(Total) :-
    ticket_cost(Ticket),
    minimal_bags_cost(Bags),
    Total is Ticket + Bags.

/* -----------------------------  Query  -------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.