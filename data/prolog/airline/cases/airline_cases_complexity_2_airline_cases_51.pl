:- use_module(library(lists)).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Facts for Patricia's itinerary
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ticket_price(230).                        % The fare itself

% bag(Index, Length, Width, Height, Weight).
% (Only the 10 checked pieces - her smallest backpack is free carry-on)
bag(1,40,21,20,52).
bag(2,36,16,13,69).
bag(3,46,28,26,52).
bag(4,33,18,12,52).
bag(5,36,13,14,67).
bag(6,43,25,18,51).
bag(7,38,17,11,59).
bag(8,48,29,27,52).
bag(9,38,13,14,56).
bag(10,54,31,27,87).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Base checked-bag fees (Main Cabin, within U.S.)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
base_fee(1, 40).
base_fee(2, 45).
base_fee(3, 150).
base_fee(N, 200) :-                       % 4th bag and higher
    N >= 4.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Oversize surcharges  (all regions)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
oversize_fee(Linear, 0)   :- Linear =< 62.
oversize_fee(Linear, 30)  :- Linear  > 62, Linear =< 65.
oversize_fee(Linear, 200) :- Linear  > 65.                 % up to 115 in.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Overweight surcharges (within U.S.)
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
overweight_fee(Weight, 0)   :- Weight =< 50.
overweight_fee(Weight, 30)  :- Weight > 50, Weight =< 53.
overweight_fee(Weight, 100) :- Weight > 53, Weight =< 70.
overweight_fee(Weight, 200) :- Weight > 70, Weight =< 100.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Helper: larger of two fees
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
max_fee(A,B,A) :- A >= B, !.
max_fee(_,B,B).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Cost of each individual checked bag
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
bag_total_cost(N, Cost) :-
    bag(N,L,W,H,Weight),
    base_fee(N, Base),
    Linear is L + W + H,
    oversize_fee(Linear, OverSize),
    overweight_fee(Weight, OverWt),
    max_fee(OverSize, OverWt, Surcharge),
    Cost is Base + Surcharge.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Aggregate costs
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
total_bag_cost(Total) :-
    findall(C, (bag(N,_,_,_,_), bag_total_cost(N,C)), List),
    sumlist(List, Total).

total_cost(Total) :-
    total_bag_cost(BagFees),
    ticket_price(Ticket),
    Total is BagFees + Ticket.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%  Query & output
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.