/* --------------  Statutory rules that are relevant to this case -------------- */

/* Region of the itinerary */
region(jennifer, within_us).

/* Jennifer's cabin */
cabin(jennifer, basic_economy).

/* Base checked-bag fee for Basic Economy, within U.S.
   1st, 2nd, 3rd, 4th bag respectively                         */
base_checked_fee(basic_economy, within_us, 1, 40).
base_checked_fee(basic_economy, within_us, 2, 45).
base_checked_fee(basic_economy, within_us, 3, 150).
base_checked_fee(basic_economy, within_us, 4, 200).

/* -------------------- size / weight surcharges -------------------- */

/* Over-size fee (sum of edges = Dim) for trips within U.S.          */
oversize_fee(within_us, Dim, 30)  :- Dim > 62 , Dim =< 65.
oversize_fee(within_us, Dim, 200) :- Dim > 65 , Dim =< 115.
oversize_fee(within_us, Dim, 0)   :- Dim =< 62.

/* Over-weight fee for trips within U.S. (lbs)                       */
overweight_fee(within_us, W, 0)   :- W =< 50.                 /* no surcharge  */
overweight_fee(within_us, W, 30)  :- W > 50 , W =< 53.
overweight_fee(within_us, W, 100) :- W > 53 , W =< 70.
overweight_fee(within_us, W, 200) :- W > 70 , W =< 100.

/* When both surcharges apply, only the higher one is charged        */
bag_surcharge(Reg, Dim, W, F) :-
    oversize_fee(Reg, Dim, FO),
    overweight_fee(Reg, W,  FW),
    (FO >= FW -> F = FO ; F = FW).

/* --------------------------- the case ----------------------------- */

/* Bags: bag(ID, Len, Wid, Hgt, Weight)                              */
bag(1, 21, 12,  8, 11).          /* backpack - intended carry-on     */
bag(2, 36, 14, 14, 72).
bag(3, 35, 21,  9, 82).
bag(4, 40, 19, 12, 51).
bag(5, 35, 17, 11, 51).

/* Carry-on test (max 22*14*9 in)                                    */
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* -------------------- cost calculation ---------------------------- */

/* Checked bag in the order they are presented, skipping carry-on    */
checked_index(ID,Idx) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)),BagList),
    nth1(Idx,BagList,ID).

/* Fee of a particular checked bag                                   */
checked_bag_cost(ID,Cost) :-
    cabin(jennifer,Cabin),
    region(jennifer,Reg),
    checked_index(ID,Idx),
    base_checked_fee(Cabin,Reg,Idx,Base),
    bag(ID,L,W,H,Weight),
    Dim is L+W+H,
    bag_surcharge(Reg,Dim,Weight,Surch),
    Cost is Base + Surch.

/* Sum all checked-bag fees                                          */
total_checked_fees(Sum) :-
    findall(C, (bag(ID,_,_,_,_), \+ carry_on(ID), checked_bag_cost(ID,C)), Cs),
    sum_list(Cs,Sum).

/* Flight ticket price                                               */
ticket_price(245).

/* ------------------------- grand total ---------------------------- */
total_cost(Total) :-
    ticket_price(T),
    total_checked_fees(BagFees),
    Total is T + BagFees.

/* ----------------------------- query ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.