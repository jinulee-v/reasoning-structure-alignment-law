/* ----------  Rules from the statutes that are relevant  ---------- */

/* carry-on limits */
carry_on_max(22,14,9).

/* domestic checked-bag fees for Main Cabin */
checked_fee(1, 40).   /* 1st checked bag          */
checked_fee(2, 45).   /* 2nd checked bag          */
checked_fee(3,150).   /* 3rd checked bag          */
checked_fee(N,200) :- N>=4.   /* 4th bag and beyond */

/* oversize fees - within U.S. / Canada / PR / USVI */
oversize_fee(Dim,30) :- Dim>62, Dim=<65.
oversize_fee(Dim,200) :- Dim>65, Dim=<115.
oversize_fee(Dim,0) :- Dim=<62.             /* not oversize */

/* overweight fees - within U.S. / Canada / PR / USVI */
overweight_fee(W,30)  :- W>50 , W=<53.
overweight_fee(W,100) :- W>53 , W=<70.
overweight_fee(W,200) :- W>70 , W=<100.
overweight_fee(W,0)   :- W=<50.

/* extra fee for a bag that is both oversize and/or overweight      */
/* "the higher fee ... applies, in addition to the checked-bag fee."  */
extra_fee(Dim,W,Fee) :-
    oversize_fee(Dim,OS),
    overweight_fee(W,OW),
    (OS>=OW -> Fee=OS ; Fee=OW).

/* ----------  Facts describing Sarah's flight and bags  ---------- */

flight_ticket(180).
cabin(main_cabin).
route(domestic).           /* Orlando-Philadelphia inside U.S. */

/* bag(Id,Length,Width,Height,Weight) */
bag(1,22,13, 6, 10).    /* backpack - will be carry-on        */
bag(2,44,22,20, 69).
bag(3,34,18,12, 51).
bag(4,38,22,16, 84).
bag(5,38,14,11, 90).

/* ----------  Helper predicates  ---------- */

/* sum of the three dimensions */
dim_sum(Id,Sum) :- bag(Id,L,W,H,_), Sum is L+W+H.

/* does the bag fit the carry-on limits?  */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L=<MaxL, W=<MaxW, H=<MaxH.

/* checked bag ordering (exclude the single carry-on) */
checked_bag_number(Id,N) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), Bs),
    nth1(N,Bs,Id).

/* fee for one checked bag (includes base checked fee plus extra) */
bag_total_fee(Id,Total) :-
    checked_bag_number(Id,N),
    checked_fee(N,Base),
    dim_sum(Id,Dim),
    bag(Id,_,_,_,W),
    extra_fee(Dim,W,Extra),
    Total is Base + Extra.

/* sum of all checked-bag fees */
total_checked_bag_fees(Sum) :-
    findall(F, (bag_total_fee(_,F)), Fs),
    sum_list(Fs,Sum).

/* ----------  Grand total (ticket + all luggage charges) ---------- */
total_cost(Total) :-
    flight_ticket(Tix),
    total_checked_bag_fees(Bags),
    Total is Tix + Bags.

/* ----------  Query and output ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.