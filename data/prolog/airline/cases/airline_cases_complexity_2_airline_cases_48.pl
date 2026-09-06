% ---------------  Statutory rules that apply to this case ---------------

:- use_module(library(lists)).

% Base checked-bag fee for a Basic-Economy passenger on a flight
% between Canada and the U.S.
base_fee(Index, Fee) :-
    ( Index =:= 1 -> Fee = 35           % 1st checked bag
    ; Index =:= 2 -> Fee = 45           % 2nd checked bag
    ; Index =:= 3 -> Fee = 150          % 3rd checked bag
    ; Index  >= 4 -> Fee = 200          % 4th bag and beyond
    ).

% Over-weight fee (within / between U.S. & Canada)
overweight_fee(Weight, Fee) :-
    ( Weight > 70 , Weight =< 100 -> Fee = 200  % >70 - 100 lbs
    ; Weight > 53 , Weight =< 70  -> Fee = 100  % >53 - 70  lbs
    ; Weight > 50 , Weight =< 53  -> Fee = 30   % >50 - 53  lbs
    ;                                           % =<50 lbs
      Fee = 0
    ).

% Over-size fee (within / between U.S. & Canada)
oversize_fee(Size, Fee) :-
    ( Size > 65 , Size =< 115 -> Fee = 200      % >65 - 115 in
    ; Size > 62 , Size =< 65  -> Fee = 30       % >62 - 65  in
    ;                                           % =<62 in
      Fee = 0
    ).

% Extra fee = the higher of the applicable over-size or over-weight fee
extra_fee(Size, Weight, Fee) :-
    oversize_fee(Size, O),
    overweight_fee(Weight, W),
    ( O >= W -> Fee = O ; Fee = W).

% -------- Facts for Elizabeth's checked bags (carry-on is free) ---------
% bag(Index, SizeInInches, WeightInLbs).

bag(1, 63, 74).
bag(2, 65, 54).
bag(3, 64, 65).
bag(4, 63, 81).
bag(5, 64, 85).
bag(6, 63, 53).
bag(7, 65, 73).
bag(8, 80, 80).
bag(9, 64, 53).
bag(10,65, 68).

% ------------------------  Fee computations  ---------------------------

bag_cost(Index, Cost) :-
    bag(Index, Size, Weight),
    base_fee(Index, Base),
    extra_fee(Size, Weight, Extra),
    Cost is Base + Extra.

total_bag_cost(Total) :-
    findall(C, bag_cost(_, C), Costs),
    sum_list(Costs, Total).

% Elizabeth's ticket price
flight_ticket(224).

total_cost(Total) :-
    total_bag_cost(BagTotal),
    flight_ticket(Ticket),
    Total is BagTotal + Ticket.

% --------------------  Query: print total cost  ------------------------

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.