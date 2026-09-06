/*  ---------- Statutory rules ----------  */

/* size (length+width+height) of a bag */
bag_size(L,W,H,Size) :- Size is L+W+H.

/* oversize fee (within / between U.S., P.R., USVI, Canada)            */
/* 0-62 in  -> 0                                                        */
/* 62+-65  -> 30                                                        */
/* 65+-115 -> 200                                                       */
oversize_fee(Size,0  ) :- Size =< 62.
oversize_fee(Size,30 ) :- Size  > 62, Size =< 65.
oversize_fee(Size,200) :- Size  > 65, Size =< 115.

/* overweight fee (within / between U.S., P.R., USVI, Canada)          */
/* 0-50 lb -> 0                                                         */
/* 50+-53  -> 30                                                        */
/* 53+-70  -> 100                                                       */
/* 70+-100 -> 200                                                       */
overweight_fee(W,0  ) :- W =< 50.
overweight_fee(W,30 ) :- W  > 50, W =< 53.
overweight_fee(W,100) :- W  > 53, W =< 70.
overweight_fee(W,200) :- W  > 70, W =< 100.

/* for any bag, only the higher of the two (oversize / overweight)     */
extra_fee(L,W,H,Weight,Fee) :-
    bag_size(L,W,H,Size),
    oversize_fee(Size,OverSizeFee),
    overweight_fee(Weight,OverWgtFee),
    Fee is max(OverSizeFee,OverWgtFee).

/* checked-bag base fee numbers (domestic, Main Cabin basis)            */
base_checked_fee(1,40).
base_checked_fee(2,45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N>=4.

/* Main Plus => first checked bag fee is waived                          */
checked_fee(main_plus,1,0).
checked_fee(main_plus,N,Fee) :-
    N>1,
    base_checked_fee(N,Fee).

/*  ---------- Facts about the trip ----------  */

class(main_plus).
ticket_cost(241).

/* carry-on (bag #1) - free, not entered as a checked bag              */

/* bag(Id, Length, Width, Height, Weight) - the 10 checked pieces      */
bag(2,39,17,12,52).
bag(3,34,15,14,91).
bag(4,46,25,18,53).
bag(5,41,17,15,84).
bag(6,51,35,25,59).
bag(7,48,29,20,95).
bag(8,40,24,13,52).
bag(9,47,31,21,60).
bag(10,34,17,13,60).
bag(11,34,19,10,53).

/* order in which the bags are checked                                  */
checked_order([2,3,4,5,6,7,8,9,10,11]).

/*  ---------- Cost calculation ----------  */

bag_total_cost(Order,Id,Cost) :-
    bag(Id,L,W,H,Weight),
    extra_fee(L,W,H,Weight,Extra),
    class(Class),
    checked_fee(Class,Order,Base),
    Cost is Base + Extra.

bags_cost(List,Order,Sum) :-
    bags_cost(List,Order,0,Sum).
bags_cost([],_,Acc,Acc).
bags_cost([Id|Rest],Order,Acc,Sum) :-
    bag_total_cost(Order,Id,Cost),
    NextOrder is Order+1,
    NewAcc is Acc + Cost,
    bags_cost(Rest,NextOrder,NewAcc,Sum).

total_cost(Total) :-
    checked_order(Bags),
    bags_cost(Bags,1,CheckedBagsFees),
    ticket_cost(Ticket),
    Total is Ticket + CheckedBagsFees.

/*  ---------- Query ----------  */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.