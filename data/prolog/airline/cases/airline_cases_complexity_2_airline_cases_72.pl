/************************************************************************
 *  Statutory rules that apply to Joseph's trip (Chicago -> Miami, U.S.) *
 ************************************************************************/

% ---------------------------
% 1.  Base checked-bag fees
% ---------------------------
% Main Plus on a wholly-domestic itinerary (U.S. / P.R. / USVI / Canada)
%  - 1st bag is free
%  - 2nd bag  $45
%  - 3rd bag  $150
%  - 4th+ bag $200

bag_base_fee(1, 0).           % first checked bag
bag_base_fee(2, 45).          % second
bag_base_fee(3, 150).         % third
bag_base_fee(N, 200) :- N >= 4.  % fourth or higher


% -----------------------------------
% 2.  Oversize-fee table (domestic)
% -----------------------------------
oversize_fee(SumInch, 0)   :- SumInch =< 62.
oversize_fee(SumInch, 30)  :- SumInch > 62, SumInch =< 65.
oversize_fee(SumInch, 200) :- SumInch > 65, SumInch =< 115.


% ------------------------------------
% 3.  Over-weight-fee table (domestic)
% ------------------------------------
overweight_fee(Lbs, 0)   :- Lbs =< 50.
overweight_fee(Lbs, 30)  :- Lbs > 50, Lbs =< 53.
overweight_fee(Lbs, 100) :- Lbs > 53, Lbs =< 70.
overweight_fee(Lbs, 200) :- Lbs > 70, Lbs =< 100.


% ------------------------------------------------------
% 4.  For each bag, choose the HIGHER of the two extras
% ------------------------------------------------------
surcharge(L, W, H, Lbs, Fee) :-
    Sum is L + W + H,
    oversize_fee(Sum,  OSFee),
    overweight_fee(Lbs, OWFee),
    (OSFee >= OWFee -> Fee = OSFee ; Fee = OWFee).


/*********************************************************************
 *  Facts that describe Joseph's baggage (personal item excluded)    *
 *********************************************************************/

% bag(Index, Length, Width, Height, WeightLbs).

bag(1, 51, 32, 27, 70).
bag(2, 36, 21, 14, 51).
bag(3, 47, 27, 19, 54).
bag(4, 37, 16, 10, 63).
bag(5, 41, 24, 16, 58).
bag(6, 36, 18, 10, 76).
bag(7, 37, 14, 13, 86).
bag(8, 36, 21, 10, 52).
bag(9, 38, 20, 16, 53).
bag(10,41, 25, 14, 74).


/*******************************************************************
 *  Aggregate cost of every individual checked bag                  *
 *******************************************************************/

bag_cost(Index, Cost) :-
    bag(Index, L, W, H, WT),
    bag_base_fee(Index, Base),
    surcharge(L, W, H, WT, Extra),
    Cost is Base + Extra.

all_bags_cost(Total) :-
    findall(C, bag_cost(_, C), Cs),
    sum_list(Cs, Total).


/******************************
 *  Flight ticket cost
 ******************************/
flight_ticket(156).


/******************************
 *  Grand-total for Joseph
 ******************************/
total_cost(Grand) :-
    all_bags_cost(Bags),
    flight_ticket(Tix),
    Grand is Bags + Tix.


/******************************
 *  Produce the answer
 ******************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.