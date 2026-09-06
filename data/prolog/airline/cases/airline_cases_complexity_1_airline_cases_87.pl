/* ---------------  Statutory rules that apply to this case --------------- */

% the trip is between Mexico and the U.S.
route(between_mexico_us).

% passenger's cabin
cabin(business).

% ---------------- Checked-bag "base" fee for this route / cabin -----------

% Index = chronological order in which the bags are checked
base_bag_fee(Idx, Fee) :-
    cabin(business),
    route(between_mexico_us),
    (   Idx =< 2            -> Fee = 0            % 1st / 2nd bag
    ;   Idx =:= 3           -> Fee = 200          % 3rd bag
    ;   Idx >= 4            -> Fee = 200          % 4th,5th ...
    ).

% --------------- Complimentary weight allowance for Business --------------

weight_limit(Idx, 70) :- Idx =< 2.     % 1st and 2nd bag
weight_limit(Idx, 50) :- Idx  > 2.     % all later bags (charged bags)

% ---------------------- OverWEIGHT fee on this route ----------------------

overweight_fee(Weight, Fee) :-
    (   Weight =< 50           -> Fee = 0
    ;   Weight =< 53           -> Fee = 30
    ;   Weight =< 70           -> Fee = 100
    ;   Weight =< 100          -> Fee = 200     % 70 - 100 lb
    ).

% ----------------------- OverSIZE fee on this route -----------------------

oversize_fee(DimSum, Fee) :-
    (   DimSum =< 62           -> Fee = 0
    ;   DimSum =< 65           -> Fee = 30
    ;   DimSum =< 115          -> Fee = 200     % 65 - 115 in
    ).

% --------------- For each bag pick the HIGHER of the two fees -------------

extra_fee(Idx, DimSum, Weight, Fee) :-
    oversize_fee(DimSum, OS),
    weight_limit(Idx, Lim),
    overweight_fee(Weight, OW0),
    % if within complimentary limit there is no over-weight
    (Weight =< Lim -> OW = 0 ; OW = OW0),
    (OS >= OW -> Fee = OS ; Fee = OW).

/* -------------------------- Traveller's bags ----------------------------- 
   bag(Id, Length, Width, Height, Weight).          (inches, pounds)        */

bag(1, 35,16,12,53).   % big backpack
bag(2, 36,13,14,67).   % luggage box
bag(3, 36,19,15,53).   % luggage box
bag(4, 44,24,15,68).   % luggage box
bag(5, 42,27,16,77).   % luggage box

% carry-on backpack (18*13*9, 8 lb) is free and is therefore omitted

/* --------------------  Cost of every individual bag --------------------- */

% checked_bag_cost(Id, TotalForThatBag)
checked_bag_cost(Id, Cost) :-
    bag(Id, L,W,H,Weight),
    DimSum is L+W+H,
    bag_index(Id, Idx),
    base_bag_fee(Idx, Base),
    extra_fee(Idx, DimSum, Weight, Extra),
    Cost is Base + Extra.

% map Id -> chronological index (same order as facts)
bag_index(Id, Id).

/* ---------------------- Total cost for all checked bags ------------------ */

total_bags_cost(Total) :-
    findall(C, checked_bag_cost(_,C), Cs),
    sumlist(Cs, Total).

/* ----------------------------- Grand total ------------------------------ */

ticket_price(133).

total_cost(Total) :-
    total_bags_cost(Bags),
    ticket_price(Tix),
    Total is Bags + Tix.

/* ---------------------------  Query & output ---------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.