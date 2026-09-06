/* ---------- Facts (the case) ---------- */

% passenger and itinerary
class(premium_economy).
route(within_us).          % Minneapolis - Chicago (domestic)

% flight ticket price
flight_ticket(79).

% the 8 pieces Daniel wants to take
%  bag(#, Length, Width, Height, Weight).
bag(1,22,11, 8,  6).   % backpack - will be the carry-on
bag(2,38,17,10,100).
bag(3,49,31,22, 53).
bag(4,38,15,10, 51).
bag(5,37,22,17, 70).
bag(6,38,17, 9, 51).
bag(7,42,26,21, 84).
bag(8,40,18,16, 58).

/* ---------- Statutory thresholds ---------- */

% carry-on size limits
carry_on_limit(22,14,9).

% size fee rules  (within U.S.)
oversize_fee(Size,Fee) :-
    Size =< 62, Fee = 0.
oversize_fee(Size,30) :-
    Size  > 62, Size =< 65.
oversize_fee(Size,200) :-
    Size  > 65, Size =< 115.
oversize_fee(Size,not_accepted) :-
    Size  > 115.

% weight fee rules (within U.S.)
overweight_fee(W,0)  :- W =< 50.
overweight_fee(W,30) :- W  > 50, W =< 53.
overweight_fee(W,100):- W  > 53, W =< 70.
overweight_fee(W,200):- W  > 70, W =< 100.
overweight_fee(W,not_accepted):- W  > 100.

% checked-bag base fee rules (within U.S., Premium Economy)
base_checked_fee(Index,0)   :- class(premium_economy), Index =< 2.  % 1st-2nd free
base_checked_fee(3,150)     :- class(premium_economy).
base_checked_fee(Index,200) :- class(premium_economy), Index >= 4.

% helper - max of two numbers
max_two(A,B,A) :- A>=B.
max_two(A,B,B) :- B>A.

/* ---------- Derivations ---------- */

% is a piece a carry-on?
is_carry_on(BagID) :-
    bag(BagID,L,W,H,_),
    carry_on_limit(CL,CW,CH),
    L =< CL, W =< CW, H =< CH.

% enumerate checked pieces in the original order
checked_bag_index(Index,BagID) :-
    findall(ID,(bag(ID,_,_,_,_), \+ is_carry_on(ID)),IDs),
    nth1(Index,IDs,BagID).

% fee for one checked bag
bag_fee(Index,BagID,TotalFee) :-
    bag(BagID,L,W,H,Weight),
    Size is L+W+H,
    oversize_fee(Size,OverSizeFee),
    overweight_fee(Weight,OverWeightFee),
    % check acceptance
    OverSizeFee \= not_accepted,
    OverWeightFee \= not_accepted,
    max_two(OverSizeFee,OverWeightFee,ExtraFee),
    base_checked_fee(Index,BaseFee),
    TotalFee is BaseFee + ExtraFee.

% sum of all checked-bag fees
total_checked_fees(Sum) :-
    findall(Fee,
            (checked_bag_index(I,BID), bag_fee(I,BID,Fee)),
            Fees),
    sum_list(Fees,Sum).

% grand total (bags + ticket)
total_cost(Total) :-
    flight_ticket(T),
    total_checked_fees(BagSum),
    Total is T + BagSum.

/* ---------- Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.