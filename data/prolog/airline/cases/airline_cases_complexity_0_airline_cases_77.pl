/************************************************************************
  Statutory rules (excerpt - only what is needed for this case)
************************************************************************/

% ----------------------------------------------------------------------
% oversize_fee(+SizeSum, -Fee)
% ----------------------------------------------------------------------
% Standard bag limit is 62 in.  Route involved is "to / from Australia or
% New Zealand", so oversize scale is:
%  - 62 in or less : $0
%  - >62 - 65 in   : $30
%  - >65 - 115 in  : $200
% ----------------------------------------------------------------------
oversize_fee(Size, 0   ) :- Size =< 62.
oversize_fee(Size, 30  ) :- Size  > 62, Size =< 65.
oversize_fee(Size, 200 ) :- Size  > 65, Size =< 115.

% ----------------------------------------------------------------------
% overweight_fee(+WeightLbs, -Fee)
% ----------------------------------------------------------------------
% For the same route the scale is:
%  - 50 lbs or less          : $0
%  - >50 - 53 lbs            : $30
%  - >53 - 70 lbs            : $100
% ----------------------------------------------------------------------
overweight_fee(W, 0   ) :- W =< 50.
overweight_fee(W, 30  ) :- W  > 50, W =< 53.
overweight_fee(W, 100 ) :- W  > 53, W =< 70.

% ----------------------------------------------------------------------
% surcharge(+SizeSum,+WeightLbs,-Fee)
% ----------------------------------------------------------------------
% If a bag is both oversize AND overweight, collect only the HIGHER of
% the two surcharges.
% ----------------------------------------------------------------------
surcharge(Size,Weight,Fee) :-
        oversize_fee(Size,OF),
        overweight_fee(Weight,WF),
        ( OF >= WF -> Fee = OF ; Fee = WF ).

% ----------------------------------------------------------------------
% base_checked_fee(+BagNumber,-Fee)
% ----------------------------------------------------------------------
% Main Plus customers flying to / from New Zealand:
%   - 1st & 2nd bag: free
%   - 3rd bag     : $200
%   - 4th bag +   : $200
% ----------------------------------------------------------------------
base_checked_fee(N,0   ) :- N =< 2.         % 2 complimentary bags
base_checked_fee(3,200).
base_checked_fee(N,200) :- N >= 4.

/************************************************************************
  Facts for Michael's journey
************************************************************************/

ticket_price(815).              % Flight ticket itself ($)
free_checked_allowance(2).       % Main Plus extra allowance

% checked_bag(Index,Weight(lbs),SizeSum(in))
checked_bag(1,63,115).           % Backpack 52*37*26  in, 63 lbs
checked_bag(2,51,103).           % Backpack 46*33*24  in, 51 lbs
checked_bag(3,58,67 ).           % Backpack 39*14*14  in, 58 lbs
checked_bag(4,52,65 ).           % Backpack 38*15*12  in, 52 lbs
% (The small 19*12*9 carry-on is free and therefore not listed)

/************************************************************************
  Cost calculation
************************************************************************/

% single_bag_cost(+Index,-Cost)
single_bag_cost(Index,Cost) :-
        checked_bag(Index,Weight,Size),
        base_checked_fee(Index,Base),
        surcharge(Size,Weight,Sur),
        Cost is Base + Sur.

% total_bag_cost(-Sum)
total_bag_cost(Sum) :-
        findall(C, single_bag_cost(_,C), List),
        sum_list(List, Sum).

% total_cost(-Total)
total_cost(Total) :-
        ticket_price(Ticket),
        total_bag_cost(Bags),
        Total is Ticket + Bags.

/************************************************************************
  Query - compute and print answer
************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.