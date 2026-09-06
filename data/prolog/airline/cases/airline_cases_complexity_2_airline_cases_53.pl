/* -------------  Statutory rules (only the parts that matter here) ------------- */

/* base fee for the N-th checked bag (Main Cabin, travel inside U.S./PR/US-VI)   */
base_checked_fee(1,40).
base_checked_fee(2,45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N>3.

/* oversize fees (inside U.S./PR/US-VI) - 0 means not oversize                   */
oversize_fee(Dim,0)   :- Dim =< 62.
oversize_fee(Dim,30)  :- Dim  > 62, Dim =< 65.
oversize_fee(Dim,200) :- Dim  > 65, Dim =< 115.

/* overweight fees (inside U.S./PR/US-VI) - 0 means not overweight               */
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W > 50, W =< 53.
overweight_fee(W,100) :- W > 53, W =< 70.
overweight_fee(W,200) :- W > 70, W =< 100.

/* for a bag that is both oversize and overweight, charge ONLY the higher one    */
extra_fee(Weight,Dim,Fee) :-
    oversize_fee(Dim,OF), overweight_fee(Weight,WF),
    Fee is max(OF,WF).

/* -------------  Case facts ------------- */

/* bag(ID,Length,Width,Height,Weight).  ID = 1..11 as stated in the case         */
bag(1,18,11, 9,  8).   /* goes as carry-on, so not checked                        */
bag(2,42,25,20, 64).
bag(3,39,19,10, 72).
bag(4,48,25,23, 51).
bag(5,38,14,11, 89).
bag(6,44,24,23, 59).
bag(7,39,25,15, 55).
bag(8,35,17,12, 52).
bag(9,33,20,10, 74).
bag(10,33,22, 9, 57).
bag(11,42,23,22, 53).

/* flight ticket price                                                           */
ticket_cost(287).

/* -------------  Checked-bag computations ------------- */

/* IDs of checked bags - every bag except the carry-on (#1)                      */
checked_bag_id(Id) :- bag(Id,_,_,_,_), Id \= 1.

/* order of a checked bag: first checked = 1, second = 2, ...                      */
checked_bag_order(Id,Order) :-
    findall(I, checked_bag_id(I), Ids),
    msort(Ids,Sorted),                 % ensure ascending order
    nth1(Order,Sorted,Id).

/* cost for one checked bag (base + extra)                                       */
bag_cost(Id,Cost) :-
    checked_bag_order(Id,Order),
    base_checked_fee(Order,Base),
    bag(Id,L,W,H,Weight),
    Dim is L+W+H,
    extra_fee(Weight,Dim,Extra),
    Cost is Base + Extra.

/* total of all checked bags                                                     */
checked_bags_total(Total) :-
    findall(C, (checked_bag_id(Id), bag_cost(Id,C)), Cs),
    sum_list(Cs,Total).

/* final total: ticket + all bag charges                                         */
total_cost(Total) :-
    ticket_cost(T),
    checked_bags_total(Bags),
    Total is T + Bags.

/* -------------  Query to produce the answer ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.