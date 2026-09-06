/* =====================  Statutory rules ===================== */

/* carry-on limits */
carry_on_max(22,14,9).

/* checked-bag base fees for Main Cabin - between Canada and U.S. */
checked_fee(1, 35).      /* 1st checked bag               */
checked_fee(2, 45).      /* 2nd checked bag               */
checked_fee(3,150).      /* 3rd checked bag               */
checked_fee(N,200) :- N>=4.   /* 4th bag and beyond        */

/* over-size fees (within / between U.S. & Canada) */
oversize_fee(Dim,30)  :- Dim>62, Dim=<65.
oversize_fee(Dim,200) :- Dim>65, Dim=<115.
oversize_fee(Dim,0)   :- Dim=<62.

/* over-weight fees (charged bags - 50-lb base limit) */
overweight_fee(W,30)  :- W>50 , W=<53.
overweight_fee(W,100) :- W>53 , W=<70.
overweight_fee(W,200) :- W>70 , W=<100.
overweight_fee(W,0)   :- W=<50.

/* the single extra fee for a bag is the higher of the two */
extra_fee(Dim,W,Fee) :-
    oversize_fee(Dim,OS),
    overweight_fee(W,OW),
    (OS>=OW -> Fee=OS ; Fee=OW).


/* =====================  Trip facts (Emily) ===================== */

flight_ticket(291).
cabin(main_cabin).
route(canada_us).   /* Ottawa - Dallas */

/* bag(Id,Length,Width,Height,Weight) */
bag(1,19,14, 9,  6).      /* backpack - will be the carry-on */
bag(2,46,27,21, 52).
bag(3,41,26,16, 52).
bag(4,38,17, 9, 55).
bag(5,41,23,14, 52).


/* =====================  Helper predicates ===================== */

/* sum of the three dimensions */
dim_sum(Id,Sum) :- bag(Id,L,W,H,_), Sum is L+W+H.

/* does the bag fit the carry-on template? */
carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L=<MaxL, W=<MaxW, H=<MaxH.

/* find the N-th checked bag (after removing the one carry-on) */
checked_bag_number(Id,N) :-
    findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), Bs),
    nth1(N,Bs,Id).

/* total fee for one checked bag: base + extra (oversize / overweight) */
bag_total_fee(Id,Total) :-
    checked_bag_number(Id,N),
    checked_fee(N,Base),
    dim_sum(Id,Dim),
    bag(Id,_,_,_,W),
    extra_fee(Dim,W,Extra),
    Total is Base + Extra.

/* sum of all checked-bag fees */
total_checked_bag_fees(Sum) :-
    findall(F, bag_total_fee(_,F), Fs),
    sum_list(Fs,Sum).

/* grand total (ticket + all luggage charges) */
compute_total(Total) :-
    flight_ticket(Tix),
    total_checked_bag_fees(Bags),
    Total is Tix + Bags.


/* =====================  Query & output ===================== */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.