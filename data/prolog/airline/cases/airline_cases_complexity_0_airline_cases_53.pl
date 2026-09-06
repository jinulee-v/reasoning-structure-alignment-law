/* ----------  Statutory rules that apply to this case  ---------- */

/* Region and cabin class for Joseph */
region(aus_nz).               /* 'To / from Australia and New Zealand'    */
cabin_class(basic_economy).

/* ----------  Base checked-bag fees for Basic Economy to / from NZ  ---------- */
base_checked_fee(BagNo, 75)  :- cabin_class(basic_economy), BagNo =:= 1.
base_checked_fee(BagNo, 100) :- cabin_class(basic_economy), BagNo =:= 2.
base_checked_fee(BagNo, 200) :- cabin_class(basic_economy), BagNo >= 3.

/* ----------  Over-WEIGHT fees to / from NZ  ---------- */
overweight_fee(Weight, 0)     :- Weight =< 50.                /* not overweight                */
overweight_fee(Weight, 30)    :- Weight  > 50, Weight =< 53.  /* 50-53 lbs                     */
overweight_fee(Weight, 100)   :- Weight  > 53, Weight =< 70.  /* 53-70 lbs                     */

/* ----------  Over-SIZE fees to / from NZ  ---------- */
oversize_fee(Size, 0)     :- Size =< 62.                      /* not oversize                  */
oversize_fee(Size, 30)    :- Size  > 62, Size =< 65.          /* 62-65 in                      */
oversize_fee(Size, 200)   :- Size  > 65, Size =< 115.         /* 65-115 in                     */

/* ----------  Surcharge (pick the higher of the two if both apply)  ---------- */
bag_surcharge(Size, Weight, Surcharge) :-
    oversize_fee(Size, O), overweight_fee(Weight, W),
    (O >= W -> Surcharge = O ; Surcharge = W).

/* ----------  Facts representing Joseph's checked bags  ---------- */
/*    bag(CheckedBagNo, SizeSumInInches, WeightInLbs).               */

bag(1, 65, 60).   /* Backpack 36*19*10  */
bag(2, 63, 69).   /* Luggage box 37*15*11 */
bag(3, 70, 51).   /* Backpack 39*15*16  */
bag(4, 64, 59).   /* Backpack 37*14*13  */

/* ----------  Compute the cost for one checked bag  ---------- */
one_bag_cost(BagNo, Cost) :-
    bag(BagNo, Size, Weight),
    base_checked_fee(BagNo, BaseFee),
    bag_surcharge(Size, Weight, Surcharge),
    Cost is BaseFee + Surcharge.

/* ----------  Sum all checked-bag costs  ---------- */
total_bag_fees(Total) :-
    findall(C, (bag(N,_,_), one_bag_cost(N, C)), List),
    sum_list(List, Total).

/* ----------  Flight ticket price  ---------- */
flight_ticket(884).

/* ----------  Grand total (ticket + bags)  ---------- */
total_cost(Total) :-
    flight_ticket(Ticket),
    total_bag_fees(BagFees),
    Total is Ticket + BagFees.

/* ----------  Produce the answer  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.