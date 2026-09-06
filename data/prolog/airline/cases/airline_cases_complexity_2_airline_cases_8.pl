/* -------------  STATUTORY RULES (relevant subset) ------------- */

% Complimentary checked-bag allowance for Premium Economy
complimentary_bag_number(2).     % 1st & 2nd bags free

% Checked-bag base fee (Qatar <-> U.S.)                                   
checked_bag_base_fee(Index, 0) :- complimentary_bag_number(N), Index =< N.
checked_bag_base_fee(Index, 200) :- complimentary_bag_number(N), Index > N.

% Oversize fee (Qatar <-> U.S.)
oversize_fee(Size, 0)  :- Size =< 62.                 % within allowance
oversize_fee(Size, 30) :- Size  > 62, Size =< 65.     % 62-65 in
oversize_fee(Size, 150):- Size  > 65.                 % 65-115 in

% Overweight fee (Qatar <-> U.S.)      (50 lb allowance for Premium Economy)
overweight_fee(W, 0)   :- W =< 50.                    % within allowance
overweight_fee(W, 30)  :- W  > 50, W =< 53.           % 50-53 lb
overweight_fee(W, 100) :- W  > 53, W =< 70.           % 53-70 lb

% When both oversize and overweight apply, charge the higher one
size_weight_surcharge(Size, Wt, Fee) :-
        oversize_fee(Size, OS),
        overweight_fee(Wt,  OW),
        (OS >= OW -> Fee = OS ; Fee = OW).

/* ------------------  CASE FACTS  ------------------ */

ticket_price(1034).

% Thomas uses the smallest backpack as his carry-on; the remaining 10 items
% are checked.  bag(Id, SizeSumInches, WeightLbs).

bag(1,  79, 54).      % luggage box 42x21x16
bag(2,  99, 70).      % backpack 50x28x21
bag(3, 113, 61).      % luggage box 49x34x30
bag(4,  63, 64).      % backpack 35x14x14
bag(5,  64, 62).      % backpack 33x21x10
bag(6,  65, 55).      % luggage box 36x16x13
bag(7,  72, 70).      % luggage box 40x15x17
bag(8,  71, 68).      % backpack 37x21x13
bag(9,  64, 59).      % backpack 36x14x14
bag(10, 69, 62).      % backpack 39x19x11

/* -----------------  FEE CALCULATIONS ----------------- */

% Total fee for each checked bag = base checked-bag fee + surcharge
bag_total_fee(Id, Total) :-
        bag(Id, Size, Wt),
        checked_bag_base_fee(Id, Base),
        size_weight_surcharge(Size, Wt, Surcharge),
        Total is Base + Surcharge.

% Sum the fees of all checked bags
bags_fee(Sum) :-
        findall(F, bag_total_fee(_,F), L),
        sum_list(L, Sum).

% Overall cost = ticket + all bag fees
total_cost(Total) :-
        ticket_price(T),
        bags_fee(Bags),
        Total is T + Bags.

/* -----------------  QUERY ----------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.