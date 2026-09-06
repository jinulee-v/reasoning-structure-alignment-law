/* ----------  Statutory rules needed for this case ---------- */

/* ticket price */
flight_ticket(emily,495).

/* Main Plus gives Main-Cabin fares with 1 extra free checked bag         */
/* For Main Cabin on Europe<->USA routes:                                   */
/*    1st bag  $0                                                         */
/*    2nd bag $100                                                        */
/*    3rd bag $200                                                        */
/*    4th+   $200                                                        */

base_fee_nomember(1,0).          /* Europe<->USA, Main Cabin */
base_fee_nomember(2,100).
base_fee_nomember(3,200).
base_fee_nomember(N,200) :- N>=4.

/* free-bag allowance for Main Plus on this itinerary */
free_checked_bag_count(2).

/* --------------- size / weight surcharges ------------------ */

/* oversize - Europe<->USA */
oversize_fee(Size,30)  :- Size>62, Size=<65.
oversize_fee(Size,150) :- Size>65, Size=<115.
oversize_fee(Size,0)   :- Size=<62.

/* overweight - any route (only ranges we need) */
overweight_fee(W,30)  :- W>50 , W=<53.
overweight_fee(W,100) :- W>53 , W=<70.
overweight_fee(W,0)   :- W=<50.

/* --------------- Emily's bags ------------------------------ */

/* carry-on (free, ignored for checked-bag maths) */
carry_on(1,18,14,9,8).

/* checked bags: id, L, W, H, Weight */
bag(2,35,16,12,54).
bag(3,39,17,10,60).
bag(4,38,15,10,61).
bag(5,38,14,11,51).

/* --------------- helpers ----------------------------------- */
dimension_size(L,W,H,S) :- S is L+W+H.

/* compute total surcharge (higher of overweight / oversize) */
surcharge(L,W,H,Weight,Surcharge) :-
    dimension_size(L,W,H,Size),
    oversize_fee(Size,OverSizeFee),
    overweight_fee(Weight,OverWtFee),
    Surcharge is max(OverSizeFee,OverWtFee).

/* sum of all checked-bag costs */
bag_costs_sum(Sum) :-
    findall(Id, bag(Id,_,_,_,_), Unsorted),
    sort(Unsorted, IDs),                 /* ensure deterministic order  */
    free_checked_bag_count(Free),        /* free-bag allowance          */
    bag_costs(IDs,1,Free,0,Sum).

bag_costs([],_,_,Sum,Sum).
bag_costs([Id|Rest],Order,Free,Acc,Sum) :-
    bag(Id,L,W,H,Weight),
    surcharge(L,W,H,Weight,Surcharge),
    base_fee_nomember(Order,Base0),
    ( Order =< Free -> BaseFee = 0 ; BaseFee = Base0 ),
    BagCost is BaseFee + Surcharge,
    Acc1   is Acc + BagCost,
    Order1 is Order + 1,
    bag_costs(Rest,Order1,Free,Acc1,Sum).

/* --------------- final total -------------------------------- */
ticket_fee(Fee) :- flight_ticket(emily,Fee).

total_cost(Total) :-
    ticket_fee(Ticket),
    bag_costs_sum(Bags),
    Total is Ticket + Bags.

/* --------------- query & print ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.