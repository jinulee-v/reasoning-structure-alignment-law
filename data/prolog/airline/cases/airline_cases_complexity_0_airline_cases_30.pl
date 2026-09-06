/********************************************************************
*  Statutory rules - (subset needed for this case only)
********************************************************************/

% Passenger / flight data
passenger_class(basic_economy).
route(europe_us).                 % Washington D.C.  <->  Stockholm
ticket_cost(638).

/********************************************************************
*  Checked bags carried by the passenger
*  bag(PositionAmongChecked, LinearDimensionInches, WeightLbs)
********************************************************************/
bag(1, 65 , 52).    % backpack 35 x 16 x 14  -> 65"   52 lbs
bag(2,106 , 65).    % backpack 48 x 32 x 26  ->106"   65 lbs
bag(3, 65 , 55).    % backpack 36 x 16 x 13  -> 65"   55 lbs
bag(4,107 , 54).    % luggage   52 x 31 x 24 ->107"   54 lbs

/********************************************************************
*  Base checked-bag fees for Basic-Economy on Europe<->US routes
********************************************************************/
base_checked_fee(1, 75).
base_checked_fee(2,100).
base_checked_fee(3,200).
base_checked_fee(N,200) :- N >= 4.

/********************************************************************
*  Oversize fees (Europe<->US)
********************************************************************/
oversize_fee(Dim,0)   :- Dim =< 62, !.
oversize_fee(Dim,30)  :- Dim > 62, Dim =< 65, !.      % small oversize
oversize_fee(Dim,150) :- Dim > 65, Dim =< 115, !.     % large oversize
% (>115" not accepted - not needed for this case)

/********************************************************************
*  Over-weight fees (Europe<->US)
********************************************************************/
overweight_fee(W,0)   :- W =< 50, !.
overweight_fee(W,30)  :- W > 50, W =< 53, !.
overweight_fee(W,100) :- W > 53, W =< 70, !.
% (>70 lbs not accepted - not needed for this case)

/********************************************************************
*  Extra fee per bag = higher of oversize vs. overweight fee
********************************************************************/
extra_fee(Dim,Weight,Extra) :-
    oversize_fee(Dim,OS),
    overweight_fee(Weight,OW),
    (OS >= OW -> Extra = OS ; Extra = OW).

/********************************************************************
*  Total cost per checked bag  (base fee + extra fee)
********************************************************************/
bag_cost(Pos,Dim,Weight,Cost) :-
    base_checked_fee(Pos,Base),
    extra_fee(Dim,Weight,Extra),
    Cost is Base + Extra.

/********************************************************************
*  Utilities
********************************************************************/
sum_list([],0).
sum_list([H|T],Sum) :- sum_list(T,S0), Sum is H+S0.

/********************************************************************
*  Aggregate bag fees
********************************************************************/
total_bag_fees(Total) :-
    findall(C, (bag(Pos,D,W), bag_cost(Pos,D,W,C)), Cs),
    sum_list(Cs,Total).

/********************************************************************
*  Grand total (ticket + all bag fees)
********************************************************************/
total_cost(Total) :-
    ticket_cost(Tk),
    total_bag_fees(Bags),
    Total is Tk + Bags.

/********************************************************************
*  Query - prints the answer required by the problem
********************************************************************/
:- total_cost(T), format('Total cost: ~w~n', [T]).
:- halt.