%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Statutory rules that apply to Thomas' itinerary
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

% route category that applies to every checked bag in this case
route(panama_us).

%%%%%%%%%%%%%%%%%%%%
% Oversize fees
%%%%%%%%%%%%%%%%%%%%
% fee(SizeSum, Fee) - SizeSum is L+W+H in inches
oversize_fee(Sum, 0)   :- Sum =< 62.
oversize_fee(Sum, 30)  :- Sum  > 62, Sum =< 65.              % 62 - 65 in
oversize_fee(Sum, 150) :- Sum  > 65, Sum =< 115.             % 65 - 115 in

%%%%%%%%%%%%%%%%%%%%
% Over-weight fees
%%%%%%%%%%%%%%%%%%%%
% fee(WeightLbs, Fee)
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.

%%%%%%%%%%%%%%%%%%%%
% Checked-bag base fees for Main Plus
%%%%%%%%%%%%%%%%%%%%
% For the route Panama <-> U.S.:
%   - Main Cabin 1st bag = $0
%   - Main Plus gets 1 extra free bag (max 2 free)
%   - 3rd bag  = $200, 4th+ = $200 each
base_checked_fee(Index, 0)   :- Index =< 2.      % 1st & 2nd free
base_checked_fee(Index, 200) :- Index >= 3.      % 3rd, 4th ... $200

%%%%%%%%%%%%%%%%%%%%
% Helper predicates
%%%%%%%%%%%%%%%%%%%%
dimension_sum(L, W, H, Sum) :- Sum is L+W+H.

max_val(X, Y, X) :- X >= Y, !.
max_val(X, Y, Y) :- Y > X.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Facts that describe Thomas' checked items
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% bag(Number, L, W, H, Weight)
bag(1, 39, 21, 19, 53).
bag(2, 35, 20, 14, 65).
bag(3, 33, 18, 13, 55).
bag(4, 45, 21, 19, 95).
bag(5, 48, 27, 23, 51).
bag(6, 51, 29, 26, 51).
bag(7, 47, 29, 24, 53).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Per-bag total fee  = base checked fee  +  highest of
%                        (oversize fee, overweight fee)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
bag_total_fee(Index, TotalFee) :-
    bag(Index, L, W, H, Weight),
    dimension_sum(L, W, H, Sum),
    oversize_fee(Sum, Oversize),
    overweight_fee(Weight, Overweight),
    max_val(Oversize, Overweight, ExtraFee),
    base_checked_fee(Index, Base),
    TotalFee is Base + ExtraFee.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Aggregate baggage cost
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
baggage_cost(Total) :-
    findall(F, bag_total_fee(_, F), Fees),
    sum_list(Fees, Total).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Flight ticket cost
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
flight_ticket_cost(178).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Grand total
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
total_cost(Total) :-
    baggage_cost(BagCost),
    flight_ticket_cost(Ticket),
    Total is BagCost + Ticket.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%   Query - prints the answer the user asked for
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.