/************************************************************************
*  Statutory rules and facts that are RELEVANT to Emily's situation     *
************************************************************************/

%%%%%%%%%%%%%
%  FLIGHT   %
%%%%%%%%%%%%%

% The only flight we care about for this case
origin(charlotte).
destination(havana).

% Region category needed by the bag-fee tables
% (Charlotte is in the U.S.; Havana is in Cuba.)
flight_category(us_to_cuba).           

%%%%%%%%%%%%%
% PASSENGER %
%%%%%%%%%%%%%

ticket_price(184).                      % price of the ticket in U.S. dollars
passenger_class(basic_economy).         % Emily's booking class

%%%%%%%%%%%%%%%%
%   THE BAGS   %
%%%%%%%%%%%%%%%%
% bag(ID, Length, Width, Height, Weight).
bag(1, 21, 13,  6,  7).                 % fits as carry-on
bag(2, 37, 15, 12, 53).                 % checked bag #1
bag(3, 34, 16, 13, 61).                 % checked bag #2

/************************************************************************
*  Helper predicates                                                    *
************************************************************************/

bag_size(L, W, H, S) :- S is L+W+H.     % total outside dimensions

% Carry-on test (American Airlines limit 22*14*9 inches)
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% -------------------- BASE CHECKED-BAG FEES ---------------------------
% first_checked_fee(Position, FlightCategory, Class, Fee).

first_checked_fee(1, us_to_cuba, basic_economy, 35).
first_checked_fee(2, us_to_cuba, basic_economy,150).

% If ever needed, more rules could be added here for extra bags.

% -------------------- OVERWEIGHT FEES ---------------------------------
% overweight_fee(Weight, FlightCategory, Class, Fee).
% -- up to 53 lbs (strictly >50, =<53) - flat $30, any region / class
overweight_fee(W, _, _, 30) :- W>50, W=<53.

% -- 53-70 lbs for flights to / from Cuba
overweight_fee(W, us_to_cuba, basic_economy, 200) :- W>53, W=<70.

% (Heavier categories are irrelevant to this case.)

% No fee if within 50 lbs
overweight_fee(W, _, _, 0) :- W =< 50.

% -------------------- OVERSIZE FEES -----------------------------------
% oversize_fee(Size, FlightCategory, Fee).
% 62-65 in to / from the Caribbean (Cuba is Caribbean) - $30
oversize_fee(S, us_to_cuba, 30) :- S>62, S=<65.

% No fee if =<62 in
oversize_fee(S, _, 0) :- S =< 62.

% -------------------- EXTRA FEE PER BAG -------------------------------
% Per American's rule: "The HIGHER fee between oversize and overweight
% applies, in addition to the checked-bag fee."
extra_fee(ID, Fee) :-
    passenger_class(Class),
    flight_category(FC),
    bag(ID, L, W, H, Wt),
    bag_size(L,W,H,Size),
    overweight_fee(Wt, FC, Class, OW),
    oversize_fee(Size, FC, OS),
    Fee is max(OW,OS).

% -------------------- POSITION OF EACH CHECKED BAG --------------------
% collect bags that are NOT carry-ons and keep their original order
checked_bags(List) :-
    findall(ID, (bag(ID,_,_,_,_), \+ carry_on(ID)), List).

% position_in_queue(BagID, Position).
position_in_queue(ID, Pos) :-
    checked_bags(L),
    nth1(Pos, L, ID).

% -------------------- TOTAL FOR ONE CHECKED BAG -----------------------
bag_total_cost(ID, Cost) :-
    position_in_queue(ID, Pos),
    passenger_class(Class),
    flight_category(FC),
    first_checked_fee(Pos, FC, Class, BaseFee),
    extra_fee(ID, Extra),
    Cost is BaseFee + Extra.

% -------------------- TOTAL BAGGAGE COST ------------------------------
total_baggage_cost(Total) :-
    findall(C, (checked_bags(L), member(ID,L), bag_total_cost(ID,C)), Cs),
    sum_list(Cs, Total).

/************************************************************************
*  FINAL TOTAL COST (ticket + bags)                                     *
************************************************************************/

total_cost(GrandTotal) :-
    ticket_price(Tix),
    total_baggage_cost(Bags),
    GrandTotal is Tix + Bags.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.