/* ---------- Statutory rules (subset needed for this case) ---------- */

/* oversize fees - domestic (U.S.-U.S.) */
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size  > 62, Size =< 65.
oversize_fee(Size,200) :- Size  > 65, Size =< 115.

/* overweight fees - domestic (U.S.-U.S.) */
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W  > 50, W =< 53.
overweight_fee(W,100)  :- W  > 53, W =< 70.
overweight_fee(W,200)  :- W  > 70, W =< 100.

/* checked-bag base fees for Basic Economy - domestic */
checked_bag_fee(1,40).
checked_bag_fee(2,45).
checked_bag_fee(3,150).
checked_bag_fee(N,200) :- N >= 4.

/* choose the higher of the two special-need fees */
special_need_fee(Size,Weight,Fee) :-
    oversize_fee(Size,OFee),
    overweight_fee(Weight,WFee),
    ( OFee >= WFee -> Fee = OFee ; Fee = WFee ).

/* charge for an individual checked bag */
bag_charge(N,Charge) :-
    bag(N,L,W,H,Weight),
    Size is L+W+H,
    special_need_fee(Size,Weight,SFee),
    checked_bag_fee(N,BaseFee),
    Charge is SFee + BaseFee.

/* total of all checked bags */
total_bags_cost(Total) :-
    findall(C,bag_charge(_,C),Cs),
    sum_list(Cs,Total).

/* flight ticket */
flight_ticket_fee(171).

/* overall cost */
total_cost(Total) :-
    total_bags_cost(Bags),
    flight_ticket_fee(Ticket),
    Total is Bags + Ticket.

/* ---------- Facts for Michael's case ---------- */

/* Order of checked bags (personal item already accounted for) */
bag(1,37,15,13,62).   /* 1st checked bag */
bag(2,44,28,23,64).   /* 2nd */
bag(3,37,17,11,68).   /* 3rd */
bag(4,50,38,27,95).   /* 4th */
bag(5,48,29,26,87).   /* 5th */
bag(6,49,32,22,54).   /* 6th */
bag(7,38,12,14,56).   /* 7th */
bag(8,35,19,14,87).   /* 8th */
bag(9,35,16,13,51).   /* 9th */
bag(10,53,29,27,90).  /* 10th */

/* ---------- Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.