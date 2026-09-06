% -------------  RULES (statutes needed for this case only)  -------------

% main_plus gets 2 free checked bags (1st Main-Cabin allowance + 1 extra)
free_checked_bags(main_plus, 2).

% Bag fee for a Europe -> U.S. flight in Main Cabin / Main Plus
bag_fee(Number, Fee) :-
    Number =< 2,                % the 2 complimentary bags
    Fee = 0.
bag_fee(Number, 200) :-         % 3rd bag and every bag after that
    Number  > 2.

% Size (L+W+H) in inches of every bag
size(Bag, S) :-
    bag(Bag,L,W,H,_),
    S is L+W+H.

% Oversize fee (Europe rules)
oversize_fee(Bag, Fee) :-
    size(Bag,S),
    (   S =< 62 -> Fee = 0
    ;   S =< 65 -> Fee = 30
    ;   S =< 115 -> Fee = 150).

% Over-weight fee (Europe rules)
overweight_fee(Bag, Fee) :-
    bag(Bag,_,_,_,W),
    (   W =< 50 -> Fee = 0
    ;   W =< 53 -> Fee = 30
    ;   W =< 70 -> Fee = 100).

% The special-needs fee for each bag is the higher of the two
special_fee(Bag, Fee) :-
    oversize_fee(Bag, OSize),
    overweight_fee(Bag, OWeight),
    Fee is max(OSize,OWeight).

% ----------------  FACTS (the concrete case)  ---------------------------

% bag(Id, Length, Width, Height, Weight)
bag( 1, 21,14, 8,  9).   % Carry-on, not checked
bag( 2, 34,19,10, 55).
bag( 3, 33,21,10, 59).
bag( 4, 53,31,24, 64).
bag( 5, 35,17,12, 60).
bag( 6, 48,34,28, 67).
bag( 7, 34,20,10, 66).
bag( 8, 37,12,14, 69).
bag( 9, 41,20,17, 63).
bag(10, 39,15,14, 51).
bag(11, 45,30,20, 56).

% List of the checked bags in the order we'll present them at the counter
checked_bag_list([2,3,4,5,6,7,8,9,10,11]).

% --------------------  TOTAL COST CALCULATION  --------------------------

% Bag fees for all checked pieces
total_bag_fee(Total) :-
    checked_bag_list(List),
    total_bag_fee(List,1,0,Total).

total_bag_fee([],_,T,T).
total_bag_fee([Bag|Rest],N,Acc,Total) :-
    bag_fee(N,Fee),
    N1 is N+1,
    Acc1 is Acc+Fee,
    total_bag_fee(Rest,N1,Acc1,Total).

% Total of all overweight / oversize ("special-needs") fees
total_special_fee(Total) :-
    checked_bag_list(List),
    total_special_fee(List,0,Total).

total_special_fee([],T,T).
total_special_fee([Bag|Rest],Acc,Total) :-
    special_fee(Bag,Fee),
    Acc1 is Acc+Fee,
    total_special_fee(Rest,Acc1,Total).

% Flight ticket price
ticket_price(223).

% Grand total
total_cost(Total) :-
    ticket_price(Tix),
    total_bag_fee(BagFees),
    total_special_fee(Special),
    Total is Tix + BagFees + Special.

% -----------------  QUERY TO PRINT THE RESULT  --------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.