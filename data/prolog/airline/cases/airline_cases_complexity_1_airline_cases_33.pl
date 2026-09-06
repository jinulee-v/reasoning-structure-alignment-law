/************************************************************************
*  Statutory rules needed for the present case (simplified to the       *
*  Europe <-> U.S. market, Main-Plus cabin, and the weight / size bands   *
*  that actually occur in Robert's bags).                               *
************************************************************************/

% ----------------------------  ROUTE  ---------------------------------
route(europe_us).           % Roma  -> Atlanta  (Trans-Atlantic)

% ----------------------  FREE-BAG ALLOWANCE  --------------------------
% Main Plus = Main-Cabin + 1 extra free checked bag   (max 2 free bags)
free_checked_bags(main_plus, 2).

% -------------------------  BAG FEES  ---------------------------------
% Checked-bag fee by ordinal number on the Europe <-> U.S. market
checked_bag_fee(Idx, 0)  :- Idx =< 2.         % 1st & 2nd are free
checked_bag_fee(3,   200).
checked_bag_fee(Idx, 200) :- Idx >= 4.        % 4th and higher

% ------------------  OVER-WEIGHT / OVER-SIZE FEES  --------------------
% oversize_fee(Route, SizeSumInInches, Fee).
oversize_fee(europe_us, S, 0)   :- S =< 62.
oversize_fee(europe_us, S, 30)  :- S > 62, S =< 65.
oversize_fee(europe_us, S, 150) :- S > 65, S =< 115.

% overweight_fee(Route, WeightLbs, Fee).
overweight_fee(_, W, 0)    :- W =< 50.
overweight_fee(_, W, 30)   :- W > 50, W =< 53.
overweight_fee(_, W, 100)  :- W > 53, W =< 70.
overweight_fee(_, W, 200)  :- W > 70, W =< 100.

% For every bag, the "special-handling" charge is the HIGHER of the
% oversize and overweight fee bands that apply.
special_fee(Route, Size, Wt, Fee) :-
    oversize_fee(Route, Size, OSizeFee),
    overweight_fee(Route, Wt, OWtFee),
    Fee is max(OSizeFee, OWtFee).

% -----------------------------  CASE  ---------------------------------
% Bag facts: checked_bag(Ordinal, SizeSumInInches, WeightLbs).
checked_bag(1, 65, 70).
checked_bag(2, 64, 52).
checked_bag(3, 64, 56).
checked_bag(4, 63, 52).
checked_bag(5,100, 58).
checked_bag(6, 69, 53).
checked_bag(7, 64, 52).

% -----------------------  TOTAL COST RULES  ---------------------------
flight_ticket(577).

bag_cost(BagIdx, Cost) :-
    route(Route),
    checked_bag(BagIdx, Size, Wt),
    checked_bag_fee(BagIdx, BaseFee),
    special_fee(Route, Size, Wt, Special),
    Cost is BaseFee + Special.

total_bag_fees(Total) :-
    findall(C, (checked_bag(Idx,_,_), bag_cost(Idx,C)), Cs),
    sum_list(Cs, Total).

total_cost(Total) :-
    flight_ticket(Price),
    total_bag_fees(BagFees),
    Total is Price + BagFees.

% ---------------------------  QUERY  ----------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.