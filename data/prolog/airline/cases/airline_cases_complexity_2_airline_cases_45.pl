/**************************************************************************
  Statutory rules (only the portions that matter for this scenario)
**************************************************************************/

% flight region for PHL-NYC
region(domestic).

% passenger class
class(basic_economy).

/* ---------- BASE (checked-bag-number) FEES - Basic Economy, Domestic ---*/
% bag_number, base_fee
base_fee(1,40).
base_fee(2,45).
base_fee(3,150).
base_fee(N,200) :- N >= 4.     % 4th bag and every bag after it

/* -----------------------  OVERWEIGHT FEES  ----------------------------*/
% weight in pounds -> overweight fee (domestic, Basic Economy - values are
% the same for all classes on domestic flights, so class not re-stated).

overweight_fee(W,0)  :- W =< 50.                    % not overweight
overweight_fee(W,30) :- W  > 50, W =< 53.           % 50-53 lb
overweight_fee(W,100):- W  > 53, W =< 70.           % 53-70 lb
overweight_fee(W,200):- W  > 70, W =< 100.          % 70-100 lb
% (>100 lb not accepted - not relevant in this case)

/* ------------------------  OVERSIZE FEES ------------------------------*/
% sum of dimensions (in) -> oversize fee (domestic)

oversize_fee(Sum,0)  :- Sum =< 62.                  % not oversize
oversize_fee(Sum,30) :- Sum  > 62, Sum =< 65.       % 62-65 in
oversize_fee(Sum,200):- Sum  > 65, Sum =< 115.      % 65-115 in
% (>115 in not accepted - not relevant here)

/* For any given bag, choose HIGHER of oversize vs overweight fee */
bag_extra_fee(Weight,Sum,Extra) :-
    overweight_fee(Weight,OW),
    oversize_fee(Sum,OS),
    (OW >= OS -> Extra = OW ; Extra = OS).

/**************************************************************************
  Facts describing James's items
  bag(ID, Length, Width, Height, Weight).
**************************************************************************/

bag(b1,21,13, 8,  8 ).   % free carry-on (fits 22*14*9)
bag(b2,33,20,10, 54).
bag(b3,38,13,14, 66).
bag(b4,36,17,12, 52).
bag(b5,33,19,11, 53).
bag(b6,38,16, 9, 94).
bag(b7,36,19, 9, 65).
bag(b8,49,27,24, 53).
bag(b9,46,33,24, 64).
bag(b10,33,20,11,52).
bag(b11,37,19, 9, 78).

/* ---------------- Which bags are checked? -----------------------------
   1 personal item maximum + 1 carry-on maximum are free.
   b1 is the only item that fits the carry-on sizer; no item meets
   the personal-item size, so the rest are checked.                  */

checked_order([b2,b3,b4,b5,b6,b7,b8,b9,b10,b11]).

/**************************************************************************
  Computations
**************************************************************************/

% single bag total fee ----------------------------------------------------
checked_bag_fee(Index,BagID,TotalFee) :-
    bag(BagID,L,W,H,Weight),
    Sum is L+W+H,
    bag_extra_fee(Weight,Sum,Extra),
    base_fee(Index,Base),
    TotalFee is Base + Extra.

% list processing to accumulate fees -------------------------------------
list_fees([],_,0).
list_fees([BagID|Rest],Index,Total) :-
    checked_bag_fee(Index,BagID,F1),
    NextIndex is Index + 1,
    list_fees(Rest,NextIndex,RestTotal),
    Total is F1 + RestTotal.

% overall checked-bag fees
total_checked_fees(Total) :-
    checked_order(Bags),
    list_fees(Bags,1,Total).

% flight ticket
ticket_price(185).

% grand total
total_cost(Grand) :-
    total_checked_fees(BagFees),
    ticket_price(Tix),
    Grand is BagFees + Tix.

/**************************************************************************
  Query - print the result
**************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.