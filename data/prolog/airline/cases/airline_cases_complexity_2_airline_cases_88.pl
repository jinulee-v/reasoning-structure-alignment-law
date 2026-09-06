/* -------------  Statutory rules (abridged to the portions that apply) ------------- */

/* flight type and passenger class for this case */
flight(within_us).
passenger_class(main_cabin).

/* base checked-bag fees for a Main Cabin passenger on a wholly-U.S. itinerary */
checked_fee(Order, 40) :- Order =:= 1.
checked_fee(Order, 45) :- Order =:= 2.
checked_fee(Order, 150) :- Order =:= 3.
checked_fee(Order, 200) :- Order >= 4.

/* oversize fees (within U.S.) - bag size is L+W+H */
oversize_fee(Size, 0  ) :- Size =< 62.
oversize_fee(Size, 30 ) :- Size > 62 , Size =< 65.
oversize_fee(Size, 200) :- Size > 65 , Size =< 115.
/* sizes above 115 in. are not accepted - not needed for this case */

/* overweight fees (within U.S.) - bag weight in lbs */
overweight_fee(W, 0  ) :- W =< 50.
overweight_fee(W, 30 ) :- W > 50 , W =< 53.
overweight_fee(W, 100) :- W > 53 , W =< 70.
overweight_fee(W, 200) :- W > 70 , W =< 100.
/* weights above 100 lbs not accepted - not needed for this case */

/* choose the higher of oversize or overweight (if both apply) */
higher_fee(F1, F2, F1) :- F1 >= F2.
higher_fee(F1, F2, F2) :- F2 >  F1.

/* ----------------------------  Case facts  ---------------------------- */

ticket_cost(132).

/* bag(ID, Length, Width, Height, Weight) */
bag(1, 22, 11,  7,  5).
bag(2, 37, 18, 10, 53).
bag(3, 38, 13, 13, 88).
bag(4, 41, 25, 17, 53).
bag(5, 51, 35, 26, 97).
bag(6, 33, 19, 11, 57).
bag(7, 37, 17, 11, 74).
bag(8, 33, 18, 12, 52).
bag(9, 33, 20, 12,100).
bag(10,33, 18, 12, 53).
bag(11,53, 30, 27, 52).

/* a bag fits the carry-on sizer if it does not exceed 22*14*9 inches */
fits_carry_on(L,W,H) :- L =< 22, W =< 14, H =< 9.

/* exactly 1 carry-on permitted - pick the first bag that fits */
carry_on(ID) :-
    bag(ID,L,W,H,_),
    fits_carry_on(L,W,H),
    \+ (bag(Prev,_,_,_,_), Prev < ID, fits_carry_on(_,_,_,_), Prev \= ID).

/* every other bag is checked */
checked_bag_ids(List) :-
    findall(ID,
            (bag(ID,_,_,_,_), \+ carry_on(ID)),
            List0),
    sort(List0, List).                 /* ascending order */

/* determine the order number of a checked bag */
checked_order(ID, Order) :-
    checked_bag_ids(List),
    nth1(Order, List, ID).

/* -------------  Fee computation for each checked bag ------------- */
bag_total_fee(ID, TotalFee) :-
    checked_order(ID, Order),
    checked_fee(Order, BaseFee),
    bag(ID,L,W,H,Weight),
    Size is L+W+H,
    oversize_fee(Size, OverSizeFee),
    overweight_fee(Weight, OverWeightFee),
    higher_fee(OverSizeFee, OverWeightFee, AddFee),
    TotalFee is BaseFee + AddFee.

/* sum fees for all checked bags */
total_checked_bag_fees(Total) :-
    findall(Fee, bag_total_fee(_,Fee), Fees),
    sum_list(Fees, Total).

/* --------------------  Grand total -------------------- */
total_cost(Total) :-
    ticket_cost(Ticket),
    total_checked_bag_fees(BagFees),
    Total is Ticket + BagFees.

/* --------------------  Query / Output -------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.