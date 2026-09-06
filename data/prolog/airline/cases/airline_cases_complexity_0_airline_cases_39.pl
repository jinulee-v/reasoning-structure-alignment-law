/* ----------  RULES (statute model - only what we need for this case) --------- */

/* flight characteristics */
flight(within_us).           /* Daniel flies Washington-DC -> Las-Vegas        */
class(basic_economy).        /* Daniel's booking class                         */

/* price of the ticket itself */
ticket_cost(110).

/* carry-on limits (in inches) */
carry_on_limit(22,14,9).

/* checked-bag base fees for Basic Economy on a flight within the U.S.          */
base_checked_fee(1,40).
base_checked_fee(2,45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N>3.

/* domestic overweight fees (per bag) */
overweight_fee(W,30)  :- W>50 , W=<53.
overweight_fee(W,100) :- W>53 , W=<70.
overweight_fee(W,200) :- W>70 , W=<100.
overweight_fee(W,0)   :- W=<50.

/* domestic oversize fees (per bag, using sum of dimensions) */
oversize_fee(D,30)  :- D>62 , D=<65.
oversize_fee(D,200) :- D>65 , D=<115.
oversize_fee(D,0)   :- D=<62.

/* higher of the two extra fees that apply to a bag                              */
extra_fee(BagId,Fee) :-
    bag(BagId,_,L,Wid,H,Weight),
    Sum is L+Wid+H,
    overweight_fee(Weight,OF),
    oversize_fee(Sum,SF),
    Fee is max(OF,SF).

/* total fee for one checked bag = base fee (by order) + extra fee               */
bag_total_fee(BagId,Total) :-
    checked_bag_ids(IDs),
    nth1(N,IDs,BagId),            /* position => 1st, 2nd, 3rd, ...               */
    base_checked_fee(N,Base),
    extra_fee(BagId,Extra),
    Total is Base+Extra.

/* list of IDs of bags that are NOT free carry-ons                               */
checked_bag_ids(IDs) :-
    findall(Id,checked_bag(Id),IDs).

/* A bag is free carry-on if it fits the carry-on dimensional limits             */
carry_on(BagId) :-
    bag(BagId,_,L,W,H,_),
    carry_on_limit(LC,WC,HC),
    L=<LC, W=<WC, H=<HC.

/* everything else is a checked bag                                              */
checked_bag(BagId) :- bag(BagId,_,_,_,_,_), \+ carry_on(BagId).

/* sum of all checked-bag fees                                                   */
total_bag_fees(Sum) :-
    findall(F, (checked_bag(Id), bag_total_fee(Id,F)), Fees),
    sum_list(Fees,Sum).

/* Grand total = ticket + all bag charges                                        */
total_cost(Total) :-
    ticket_cost(T),
    total_bag_fees(Bags),
    Total is T + Bags.

/* ----------  FACTS (Daniel's actual pieces of luggage)  ---------------------- */
/* bag(Id,Type,Length,Width,Height,Weight).  Units: inches, pounds               */
bag(1,backpack,22,11,8,  5).
bag(2,luggage_box,41,19,12,65).
bag(3,backpack,43,25,20,52).
bag(4,backpack,35,18,11,70).
bag(5,backpack,35,15,14,51).

/* ----------  QUERY ----------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.