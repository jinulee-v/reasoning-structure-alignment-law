/*********************************************************************
 Statutory rules (only the parts that apply to this case)
*********************************************************************/

% ---------- OVERSIZE FEES (U.S. <-> South America, except Guyana/Suriname)
% Size = total outside dimensions (inches)
oversize_fee(Size, 0)      :- Size =< 62.
oversize_fee(Size, 30)     :- Size  > 62, Size =< 65.          % 62-65 in
oversize_fee(Size, 150)    :- Size  > 65,  Size =< 115.        % 65-115 in

% ---------- OVERWEIGHT FEES (U.S. <-> South America, Premium Economy)
% Weight in pounds
overweight_fee(W, 0)     :- W =< 50.
overweight_fee(W, 30)    :- W  > 50, W =< 53.                  % 50-53 lbs
overweight_fee(W, 100)   :- W > 53,  W =< 70.                  % 53-70 lbs
overweight_fee(W, 200)   :- W > 70,  W =< 100.                 % 70-100 lbs

% ---------- EXTRA FEE PER BAG (take the higher of oversize / overweight)
bag_extra_fee(Size, W, Fee) :-
    oversize_fee(Size, FO),
    overweight_fee(W,  FW),
    Fee is max(FO, FW).

% ---------- BASE CHECKED-BAG FEES (Premium Economy, U.S. <-> S. America)
% 1st & 2nd free, 3rd/4th/5th = $200 each
base_bag_fee(Idx, 0)   :- Idx =< 2.        % first & second
base_bag_fee(Idx, 200) :- Idx  > 2.        % third and beyond


/*********************************************************************
 Facts that describe Daniel's trip
*********************************************************************/

ticket_price(735).

% checked_bag(Index, TotalSize, Weight)
checked_bag(1, 72, 53).     % backpack 37*23*12
checked_bag(2, 85, 53).     % luggage box 44*23*18
checked_bag(3, 64, 70).     % luggage box 34*19*11
checked_bag(4,112, 53).     % luggage box 51*33*28
checked_bag(5, 65, 66).     % luggage box 36*16*13

/*********************************************************************
 Computations
*********************************************************************/

% fee for one checked bag = base fee + (higher of oversize / overweight)
one_bag_fee(Idx, Fee) :-
    checked_bag(Idx, Size, W),
    base_bag_fee(Idx, Base),
    bag_extra_fee(Size, W, Extra),
    Fee is Base + Extra.

% total of all checked-bag fees
total_checked_bag_fees(Total) :-
    findall(F, (checked_bag(I,_,_), one_bag_fee(I, F)), L),
    sum_list(L, Total).

% grand total = ticket + checked-bag fees
total_cost(Total) :-
    ticket_price(P),
    total_checked_bag_fees(Bags),
    Total is P + Bags.

/*********************************************************************
 Query - prints the answer and halts
*********************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.