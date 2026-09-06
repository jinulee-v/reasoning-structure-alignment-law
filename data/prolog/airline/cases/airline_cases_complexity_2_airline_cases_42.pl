/* --------------  Statutory rules (domestic U.S., Main Cabin) -------------- */

/* base fee of the N-th checked bag */
bag_base_fee(1,40).
bag_base_fee(2,45).
bag_base_fee(3,150).
bag_base_fee(N,200) :-                      % 4th bag and higher
    N >= 4.

/* over-weight fee (within U.S.) */
overweight_fee(Weight,30)  :- Weight  > 50, Weight =< 53.
overweight_fee(Weight,100) :- Weight  > 53, Weight =< 70.
overweight_fee(Weight,200) :- Weight  > 70, Weight =< 100.
overweight_fee(Weight,0)   :- Weight =< 50.           % not overweight

/* over-size fee (within U.S.) - we use the sum of all 3 dimensions */
oversize_fee(Sum,30)  :- Sum  > 62, Sum =< 65.
oversize_fee(Sum,200) :- Sum  > 65, Sum =< 115.
oversize_fee(Sum,0)   :- Sum =< 62.                   % not oversize

/* one extra fee (the higher of overweight vs. oversize) applies              */
additional_fee(Id,Fee) :-
    item(Id,L,W,H,Weight),
    Sum is L + W + H,
    oversize_fee(Sum,OverSizeFee),
    overweight_fee(Weight,OverWeightFee),
    Fee is max(OverSizeFee,OverWeightFee).

/* carry-on qualification (free) */
carryon_item(Id) :-
    item(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* ---------------------  Case facts (the 11 items)  ------------------------ */

item(1,19,11,7,11).
item(2,37,14,12,51).
item(3,33,22,9,72).
item(4,41,24,14,53).
item(5,33,20,12,54).
item(6,36,20,9,100).
item(7,33,20,10,89).
item(8,36,21,13,56).
item(9,34,15,14,84).
item(10,36,16,12,90).
item(11,33,19,12,53).

/* pick item #1 as the free carry-on (it is the only one that fits)           */
checked_order(2,1).
checked_order(3,2).
checked_order(4,3).
checked_order(5,4).
checked_order(6,5).
checked_order(7,6).
checked_order(8,7).
checked_order(9,8).
checked_order(10,9).
checked_order(11,10).

/* complete fee for each checked piece */
bag_total_fee(Id,Total) :-
    checked_order(Id,Nth),
    bag_base_fee(Nth,Base),
    additional_fee(Id,Add),
    Total is Base + Add.

/* sum of all checked-bag fees */
bag_fees_total(Sum) :-
    findall(F,bag_total_fee(_,F),List),
    sum_list(List,Sum).

/* flight ticket price */
flight_ticket(65).

/* -----------------------------  Query  ------------------------------------ */

total_cost(Total) :-
    bag_fees_total(Bags),
    flight_ticket(Ticket),
    Total is Bags + Ticket.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.