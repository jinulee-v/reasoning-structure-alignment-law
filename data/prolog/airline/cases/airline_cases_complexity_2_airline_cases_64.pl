/* ----------  Facts about the passenger and her journey ---------- */
flight_region(within_us).                 /* Miami - Las Vegas          */
passenger_class(main_plus).               /* Main Plus (= Main Cabin^) */
flight_ticket_cost(269).                  /* USD                       */

 /* every bag: bag(Id, Length, Width, Height, Weight).  */
bag(1, 21, 11,  8,  8).   /* carry-on (free) */
bag(2, 33, 18, 12, 67).
bag(3, 37, 17, 11, 62).
bag(4, 33, 20, 12, 54).
bag(5, 44, 22, 20, 71).
bag(6, 34, 21, 10, 57).
bag(7, 35, 14, 14, 70).
bag(8, 36, 21, 16, 59).
bag(9, 34, 20,  9, 94).
bag(10,42, 22, 18, 58).
bag(11,50, 28, 22, 86).

/* -----------------------  Carry-on test  ------------------------- */
carry_on_max(22,14,9).

carry_on(Id) :-
    bag(Id,L,W,H,_),
    carry_on_max(ML,MW,MH),
    L =< ML, W =< MW, H =< MH.

/* ------------------  Overweight / Oversize fees  ----------------- */
overweight_fee(Weight,0)  :- Weight =< 50.
overweight_fee(Weight,30) :- Weight > 50, Weight =< 53.
overweight_fee(Weight,100):- Weight > 53, Weight =< 70.
overweight_fee(Weight,200):- Weight > 70, Weight =< 100.

oversize_fee(Dim,0)    :- Dim =< 62.
oversize_fee(Dim,30)   :- Dim > 62, Dim =< 65.
oversize_fee(Dim,200)  :- Dim > 65, Dim =< 115.

/* choose higher of the two fees */
surcharge(Weight,Dim,S) :-
    overweight_fee(Weight,OW),
    oversize_fee(Dim,OS),
    (OW >= OS -> S = OW ; S = OS).

/* ---------------------  Base checked-bag fees  -------------------- */
/* For Main Plus on a domestic itinerary: 1st bag free, 2nd $45,
   3rd $150, 4th+ $200                                       */

base_fee(Pos,0)   :- Pos =:= 1.           /* free extra bag (Main Plus) */
base_fee(Pos,45)  :- Pos =:= 2.
base_fee(Pos,150) :- Pos =:= 3.
base_fee(Pos,200) :- Pos >= 4.

/* ----------------  Gather checked bags and compute  --------------- */
checked_bag_ids(Ids) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), Ids).

dim_sum(Id,Sum) :-
    bag(Id,L,W,H,_),
    Sum is L+W+H.

bag_total_fee(Pos,Id,Total) :-
    bag(Id,_,_,_,Wt),
    dim_sum(Id,Dim),
    surcharge(Wt,Dim,Extra),
    base_fee(Pos,Base),
    Total is Base + Extra.

/* total fee for all checked bags */
total_checked_bag_fee(Total) :-
    checked_bag_ids(Ids),
    findall(Fee,
            (nth1(Pos,Ids,Id), bag_total_fee(Pos,Id,Fee)),
            Fees),
    sum_list(Fees,Total).

/* overall trip cost (ticket + all bag fees) */
total_cost(Total) :-
    flight_ticket_cost(Tix),
    total_checked_bag_fee(Bags),
    Total is Tix + Bags.

/* -----------------------  Produce answer  ------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.