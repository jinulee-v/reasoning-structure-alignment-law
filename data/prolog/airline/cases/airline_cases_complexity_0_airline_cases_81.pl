/* ---------- FACTS ABOUT JOHN'S ITINERARY ---------- */
flight_region(within_us).        /* Dallas - Los Angeles            */
cabin_class(basic_economy).

flight_ticket_cost(30).

/* Bags: bag(Id, Length, Width, Height, Weight).        */
bag(b1,22,14,8, 11).
bag(b2,45,25,16,78).
bag(b3,38,15,10,64).
bag(b4,39,18,10,51).
bag(b5,42,31,18,54).

/* ---------- RULES ---------- */

/* Carry-on test (AA rule: 22 x 14 x 9 in. max) */
carry_on(BagId) :-
    bag(BagId,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* John may take exactly 1 carry-on for free.            */
checked_bags(List) :-
    findall(B, (bag(B,_,_,_,_), \+ carry_on(B)), All),
    List = All.

/* Index of a bag in the checked-bag list (for 1st/2nd/3rd/4th fee) */
bag_index(Bag,Idx) :-
    checked_bags(List),
    nth1(Idx,List,Bag).

/* ---------- BASE CHECKED-BAG FEES (Basic Economy, within U.S.) */
base_checked_fee(1,40).
base_checked_fee(2,45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N>=4.

/* ---------- OVERSIZE FEES (within U.S.) ------------------------ */
/* Size = L+W+H                                                    */
oversize_fee(Size,0)                :- Size =< 62.
oversize_fee(Size,30)               :- Size > 62, Size =< 65.
oversize_fee(Size,200)              :- Size > 65.

/* ---------- OVERWEIGHT FEES (within U.S.) ---------------------- */
overweight_fee(W,0)                 :- W =< 50.
overweight_fee(W,30)                :- W > 50,  W =< 53.
overweight_fee(W,100)               :- W > 53,  W =< 70.
overweight_fee(W,200)               :- W > 70,  W =< 100.

/* ---------- TOTAL FEE FOR ONE CHECKED BAG ---------------------- */
bag_checked_fee(Bag,TotalFee) :-
    bag(Bag,L,W,H,Weight),
    bag_index(Bag,Idx),
    base_checked_fee(Idx,Base),
    Size is L+W+H,
    oversize_fee(Size,OverSizeFee),
    overweight_fee(Weight,OverWeightFee),
    MaxExtra is max(OverSizeFee,OverWeightFee),
    TotalFee is Base + MaxExtra.

/* ---------- TOTAL ITINERARY COST ------------------------------- */
total_cost(Total) :-
    flight_ticket_cost(TicketCost),
    findall(Fee, bag_checked_fee(_,Fee), FeeList),
    sum_list(FeeList,BaggageCost),
    Total is TicketCost + BaggageCost.

/* ---------- QUERY ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.