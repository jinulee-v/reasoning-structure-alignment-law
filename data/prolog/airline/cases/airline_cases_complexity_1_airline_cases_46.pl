%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Statutory rules needed for Linda's situation
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% ---------------------
%  BASE-FEE FOR A CHECKED BAG
% ---------------------
%  Route: United-States  <--->  Europe   (Boston-Athens)
%  Cabin: Premium-Economy
%  1st & 2nd bags are free, every bag from the 3rd onward costs $200
%  ( "Third Bag" table   +   "Fourth bag +" table )

base_checked_fee(BagNumber, 0)   :- BagNumber =< 2.          % 1st, 2nd bag
base_checked_fee(3, 200).                              % 3rd bag
base_checked_fee(N, 200)         :- N >= 4.            % 4th, 5th ...


% ---------------------
%  OVERSIZE FEE  (Europe <-> U.S.)
% ---------------------
oversize_fee(Size, 0)                                        :- Size =< 62.
oversize_fee(Size, 30)                                       :- Size  > 62, Size =< 65.
oversize_fee(Size, 150)                                      :- Size  > 65, Size =< 115.

% ---------------------
%  OVERWEIGHT FEE
% ---------------------
overweight_fee(W, 0)                                         :- W =< 50.
overweight_fee(W, 30)                                        :- W  > 50, W =< 53.
overweight_fee(W, 100)                                       :- W  > 53, W =< 70.
%  (>70 lbs not present in Linda's case)

% ---------------------
%  ACTUAL EXTRA FEE PER BAG
%  (only the HIGHER of over-size vs over-weight applies)
% ---------------------
extra_fee(Size, Weight, Fee) :-
        oversize_fee(Size, SFee),
        overweight_fee(Weight, WFee),
        ( SFee >= WFee -> Fee = SFee ; Fee = WFee ).


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Facts describing Linda's items   (only checked bags listed)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% checked_bag(SequentialNumber, SizeInInches, WeightInLbs).

checked_bag(1, 64, 52).
checked_bag(2,108, 52).
checked_bag(3, 64, 68).
checked_bag(4, 74, 62).
checked_bag(5, 71, 51).
checked_bag(6, 87, 51).
checked_bag(7,102, 59).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Cost of each checked bag
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
checked_bag_cost(BagNumber, TotalFee) :-
        checked_bag(BagNumber, Size, Weight),
        base_checked_fee(BagNumber, Base),
        extra_fee(Size, Weight, Extra),
        TotalFee is Base + Extra.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Sum up all bag fees
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
total_bags_fee(Sum) :-
        findall(F, checked_bag_cost(_,F), L),
        sum_list(L, Sum).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Flight ticket
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
flight_ticket_cost(655).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Grand total
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
total_cost(Total) :-
        flight_ticket_cost(T),
        total_bags_fee(B),
        Total is T + B.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Query & output
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.