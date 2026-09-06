/* -------------  Statutory rules needed for this case --------------- */

/* The itinerary is U.S. <-> China, Main Cabin (not Basic Economy)     */

/* ---------------  helpers  ------------------- */
dims_sum(dimensions(L,W,H),Sum)  :- Sum is L+W+H.

/* oversize fee for U.S. <-> China, Japan, India ... (all treated alike) */
oversize_fee(Sum,Fee) :-
        Sum =< 62,             Fee = 0  ;
        Sum =< 65,             Fee = 30 ;
        Sum =< 115,            Fee = 200 ;
        Sum  > 115,            fail.          /* not accepted - doesn't occur */

/* overweight fee for U.S. <-> China, Japan, India ... (Main Cabin) */
overweight_fee(W,Fee) :-
        W =< 50,                     Fee = 0 ;
        W  > 50,  W =< 53,           Fee = 30 ;
        W  > 53,  W =< 70,           Fee = 100 ;
        W  > 70,  W =< 100,          Fee = 450 ;
        W  > 100,                    fail.     /* not accepted - doesn't occur */

/* choose the larger of over-weight / over-size (statute wording) */
additional_fee(W,Sum,Fee) :-
        oversize_fee(Sum,OS),
        overweight_fee(W,OW),
        Fee is max(OS,OW).

/* base checked-bag fee for U.S. <-> China, Main Cabin */
base_checked_fee(Ordinal,Fee) :-
        Ordinal =:= 1  -> Fee = 0   ;      /* 1st bag (destinations list - free) */
        Ordinal =:= 2  -> Fee = 100 ;      /* 2nd bag                              */
        Ordinal =:= 3  -> Fee = 200 ;      /* 3rd bag                              */
        Ordinal  >= 4  -> Fee = 200.       /* 4th+                                 */

/* -----------------  case facts  ------------------- */

/* ticket price                                                 */
ticket_price(1308).

/* one carry-on (free) - we omit it from checked-bag processing */

/* checked bags: id -> dimensions -> weight (lbs) */
bag(2, dimensions(34,19,11), 54).
bag(3, dimensions(50,31,22), 66).
bag(4, dimensions(35,18,10), 93).
bag(5, dimensions(51,29,26), 70).
bag(6, dimensions(43,31,21), 51).
bag(7, dimensions(42,23,18), 91).
bag(8, dimensions(44,25,21), 83).

/* the order they'll be checked in (after the carry-on)          */
checked_bag_order([2,3,4,5,6,7,8]).

/* ----------------  cost calculation  ------------------ */

/* cost for one checked bag given its ordinal position in the queue */
bag_total_cost(Ordinal,Id,Total) :-
        bag(Id,Dims,W),
        dims_sum(Dims,Sum),
        base_checked_fee(Ordinal,Base),
        additional_fee(W,Sum,Add),
        Total is Base + Add.

/* sum all checked-bag costs                                    */
bags_cost(Sum) :-
        checked_bag_order(List),
        bags_cost(List,1,Sum).

bags_cost([],_,0).
bags_cost([Id|Rest],Ordinal,Sum) :-
        bag_total_cost(Ordinal,Id,CostThis),
        NextOrd is Ordinal+1,
        bags_cost(Rest,NextOrd,SumRest),
        Sum is CostThis + SumRest.

/* total travel cost                                             */
total_cost(Total) :-
        ticket_price(Ticket),
        bags_cost(Bags),
        % (no extra "special needs" costs in this case)
        Total is Ticket + Bags.

/* ----------------  query & output  ------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.