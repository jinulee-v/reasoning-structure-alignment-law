/* -------------  Statutory rules we need for this case ------------- */

/*  Flight type  */
region(domestic).            /* Dallas - Salt Lake City */

/*  Passenger class and free-bag allowance                       */
free_bags(main_plus,1).      /* Main Plus gets 1 free checked bag       */

/*  Base checked-bag fees (within / between U.S., Puerto Rico, USVI, Canada)  */
base_checked_fee(1, 40).     /* would cost $40, but may be waived        */
base_checked_fee(2, 45).
base_checked_fee(3,150).
base_checked_fee(N,200) :-   /* 4th bag and every bag afterwards */
    N >= 4.

/* ---------------- Over-weight fees (domestic) -------------------- */
overweight_fee(Weight, Fee) :-
    Weight =< 50 , Fee = 0.
overweight_fee(Weight, 30) :-
    Weight  > 50 , Weight =< 53.
overweight_fee(Weight, 100) :-
    Weight  > 53 , Weight =< 70.
overweight_fee(Weight, 200) :-
    Weight  > 70 , Weight =< 100.

/* ---------------- Over-size fees (domestic) ---------------------- */
oversize_fee(Size, Fee) :-
    Size =< 62 , Fee = 0.
oversize_fee(Size, 30) :-
    Size  > 62 , Size =< 65.
oversize_fee(Size, 200) :-
    Size  > 65 , Size =< 115.

/*  For a given bag, the higher of the 2 special-need fees applies  */
special_fee(Weight, Size, Fee) :-
    overweight_fee(Weight, F1),
    oversize_fee(Size,    F2),
    Fee is max(F1,F2).


/* -------------  Facts describing Jessica's situation ------------- */

passenger(jessica).
class(jessica, main_plus).
ticket_cost(jessica,150).

/*  bag(Number, Weight(lbs), Length, Width, Height)  */
bag(1, 61, 36,18,11).
bag(2, 60, 34,20, 9).
bag(3, 78, 33,19,12).
bag(4, 51, 39,16,13).

/* -------------  Derived calculations ----------------------------- */

/*  Size of a bag = L+W+H  */
bag_size(N, Size) :-
    bag(N,_,L,W,H),
    Size is L+W+H.

/*  Special-need fee for bag N  */
bag_special_fee(N, Fee) :-
    bag(N,Weight,_,_,_),
    bag_size(N,Size),
    special_fee(Weight,Size,Fee).

/*  Base checked-bag fee for bag N after free-bag privilege */
bag_checked_fee(N, Fee) :-
    class(jessica,Class),
    free_bags(Class,Free),
    ( N =< Free                        % falls into free allowance
      -> Fee = 0
      ;  base_checked_fee(N,Fee) ).

/*  Total fee for a single bag = checked fee + special-need fee      */
bag_total_fee(N, Total) :-
    bag_checked_fee(N,Chk),
    bag_special_fee(N,Sp),
    Total is Chk + Sp.

/*  Sum of all bag fees  */
bags_fees(Sum) :-
    findall(F, (bag(N,_,_,_,_), bag_total_fee(N,F)), List),
    sum_list(List,Sum).

/* -----------------  Grand total for the trip --------------------- */
total_cost(Total) :-
    bags_fees(Bags),
    ticket_cost(jessica,Ticket),
    Total is Ticket + Bags.

/* ---------------------  Query / Output  -------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.