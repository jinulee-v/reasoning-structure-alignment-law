/* ----------  Statutory rules needed for this case  ---------- */

:- use_module(library(lists)).      % for permutation/2 and min_list/2

/*  Base checked-bag fee for a Basic-Economy customer
    flying to / from Australia or New Zealand            */
base_fee(1, 75).          % 1st bag
base_fee(2, 100).         % 2nd bag
base_fee(N, 200) :-       % 3rd bag and all subsequent bags
    N >= 3.

/* Oversize fee (Australia / New Zealand - U.S. market)            */
oversize_fee(Size, 0   ) :- Size =< 62.
oversize_fee(Size, 30  ) :- Size  > 62, Size =< 65.
oversize_fee(Size, 200 ) :- Size  > 65, Size =< 115.

/* Over-weight fee (all markets)                                   */
overweight_fee(W, 0  ) :- W =< 50.
overweight_fee(W, 30 ) :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.

/* Surcharge for a particular bag = max(oversize, overweight)      */
bag_surcharge(Id, Fee) :-
    bag(Id, L, W, H, Weight),
    Size is L + W + H,
    oversize_fee(Size, OverSizeFee),
    overweight_fee(Weight, OverWeightFee),
    Fee is max(OverSizeFee, OverWeightFee).

/* ----------  Facts for Michael's trip  ---------- */

flight_ticket(747).

/*  Bag facts: bag(Id, Length, Width, Height, Weight)              */
bag(2, 43, 29, 23, 52).   % luggage box
bag(3, 37, 15, 11, 52).   % luggage box
bag(4, 47, 27, 26, 56).   % luggage box
bag(5, 33, 18, 13, 67).   % backpack (checked)

checked_bags([2,3,4,5]).  % 4 checked bags (carry-on bag #1 is free)

/* ----------  Cost computation  ---------- */

/* Cost for one particular ordering of the checked bags            */
checked_fees_perm(Perm, Total) :-
    checked_fees_perm(Perm, 1, 0, Total).

checked_fees_perm([], _, Total, Total).
checked_fees_perm([Id|Rest], Ord, Acc0, Total) :-
    base_fee(Ord, Base),
    bag_surcharge(Id, Surcharge),
    Acc1 is Acc0 + Base + Surcharge,
    Ord1 is Ord + 1,
    checked_fees_perm(Rest, Ord1, Acc1, Total).

/* Minimum possible total checked-bag fees over all permutations   */
min_total_checked_fee(Min) :-
    checked_bags(Bags),
    findall(Fee,
            ( permutation(Bags, Perm),
              checked_fees_perm(Perm, Fee)
            ),
            Fees),
    min_list(Fees, Min).

/* Final overall cost                                              */
total_cost(Total) :-
    flight_ticket(Flight),
    min_total_checked_fee(BagFees),
    Total is Flight + BagFees.

/* ----------  Query & output  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.