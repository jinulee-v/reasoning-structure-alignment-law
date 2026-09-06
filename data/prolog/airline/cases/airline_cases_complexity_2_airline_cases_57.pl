/* ----------  STATUTORY RULES NEEDED FOR THIS CASE  ---------- */

/* Base checked-bag fee for a Main Cabin customer travelling
   within / between the U.S., Puerto Rico and the U.S. Virgin Islands */
bag_base_fee(1,40).
bag_base_fee(2,45).
bag_base_fee(3,150).
bag_base_fee(N,200) :- N>3.

/* Over-WEIGHT fees (any cabin, same region)     */
overweight_fee(W,0)   :- W =< 50.                 /* 50 lb or less            */
overweight_fee(W,30)  :- W  > 50 , W =< 53.       /* 50+ - 53 lb              */
overweight_fee(W,100) :- W  > 53 , W =< 70.       /* 53+ - 70 lb              */
overweight_fee(W,200) :- W  > 70 , W =< 100.      /* 70+ -100 lb (max allowed)*/

/* Over-SIZE fees (same region)                  */
oversize_fee(S,0)    :- S =< 62.                  /* 62 in or less            */
oversize_fee(S,30)   :- S  > 62 , S =< 65.        /* 62+ - 65 in              */
oversize_fee(S,200)  :- S  > 65 , S =< 115.       /* 65+ -115 in (max allowed)*/

/* For bags that are BOTH over-weight and over-size,
   the HIGHER of the two applies (plus base checked-bag fee) */
excess_fee(W,S,Fee) :-
        overweight_fee(W,OW),
        oversize_fee(S,OS),
        ( OW >= OS -> Fee = OW ; Fee = OS ).

/* ----------  FACTS FOR SARAH'S TRIP  ---------- */

/* bag(Index, Length, Width, Height, Weight).     */
/* Only the *checked* pieces are listed (10 of them). */
bag(1,51,32,31,81).
bag(2,37,12,14,53).
bag(3,33,21, 9,85).
bag(4,37,26,13,85).
bag(5,33,19,13,66).
bag(6,38,15,10,53).
bag(7,43,29,19,63).
bag(8,49,32,27,52).
bag(9,45,24,23,52).
bag(10,33,21,9,52).

/* Sarah's ticket price */
flight_ticket_price(158).

/* ----------  BAG COST CALCULATIONS  ---------- */

bag_total_fee(Index,TotalFee) :-
        bag(Index,L,W,H,Weight),
        SumDim is L+W+H,
        excess_fee(Weight,SumDim,Excess),
        bag_base_fee(Index,Base),
        TotalFee is Base + Excess.

/* Sum the fees for all checked bags */
total_checked_bag_fee(Sum) :-
        findall(Fee,bag_total_fee(_,Fee),List),
        sum_list(List,Sum).

/* Grand total = ticket + all bag costs */
total_cost(Total) :-
        total_checked_bag_fee(BagFees),
        flight_ticket_price(Ticket),
        Total is Ticket + BagFees.

/* ----------  QUERY  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.