/* ----------  Rules derived from the statutes  ---------- */

/*  Base checked-bag fee for a Main Cabin passenger on a trip
    between the U.S. and Europe (Austin - Brussels)
       1st bag : $0
       2nd bag : $100
       3rd bag : $200
       4th+    : $200                                       */

base_bag_fee(Index, Fee) :-
    (   Index =:= 1 -> Fee = 0
    ;   Index =:= 2 -> Fee = 100
    ;   Index  >= 3 -> Fee = 200).

/*  Over-weight surcharge (all cabins, Europe-U.S. flights)
       >50-53 lbs  : $30
       >53-70 lbs  : $100                                   */

overweight_fee(Weight, Fee) :-
    (   Weight > 50, Weight =< 53 -> Fee = 30
    ;   Weight > 53, Weight =< 70 -> Fee = 100
    ;   otherwise                 -> Fee = 0).

/*  Over-size surcharge for Europe-U.S.
       >62-65 in  : $30
       >65-115 in : $150                                   */

oversize_fee(Size, Fee) :-
    (   Size > 62, Size =< 65  -> Fee = 30
    ;   Size > 65, Size =< 115 -> Fee = 150
    ;   otherwise              -> Fee = 0).

/*  The higher of the two surcharges applies                  */

surcharge(Weight, Size, Fee) :-
    overweight_fee(Weight, WFee),
    oversize_fee(Size, SFee),
    Fee is max(WFee, SFee).

/*  Total fee for one checked bag                             */

bag_total_fee(Index, Weight, Size, Fee) :-
    base_bag_fee(Index, Base),
    surcharge(Weight, Size, Surch),
    Fee is Base + Surch.

/*  ---------  Facts describing Daniel's trip  --------- */

ticket_cost(197).

/*  checked_bag(Index, Weight_lbs, Size_in)                   */
checked_bag(1, 51,  68).
checked_bag(2, 57, 107).
checked_bag(3, 57,  63).
checked_bag(4, 65,  84).
checked_bag(5, 52,  64).
checked_bag(6, 52,  65).
checked_bag(7, 53, 105).
checked_bag(8, 67,  64).
checked_bag(9, 54,  91).
checked_bag(10,51,  64).

/*  ---------  Aggregate computations  --------- */

total_checked_bag_fees(Sum) :-
    findall(F,
            (checked_bag(I,W,S), bag_total_fee(I,W,S,F)),
            List),
    sum_list(List, Sum).

total_cost(Total) :-
    ticket_cost(T),
    total_checked_bag_fees(BagFees),
    Total is T + BagFees.

/*  ---------  Query to print the answer  --------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.