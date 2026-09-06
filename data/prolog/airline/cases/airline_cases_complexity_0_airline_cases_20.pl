/* ---------------  Statutory rules we need for this case --------------- */

/* price of the ticket */
ticket_price(824).

/* --------------------------  ROUTE in the case ------------------------ */
route(to_from_china).        /* Salt Lake City (U.S.)  ->  Guangzhou (China) */

/* ----------------------  Checked-bag order fees ----------------------- */
/* Premium Economy - to / from China
      1st & 2nd bag free, 3rd bag $200, 4th+ bag $200                    */

base_checked_fee(BagNo,0)   :- BagNo =< 2.          /* 1st & 2nd        */
base_checked_fee(BagNo,200) :- BagNo  >= 3.         /* 3rd, 4th ...       */

/* -------------------  Overweight fee (to / from China) ---------------- */
overweight_fee(W,450) :- W  > 70,  W =< 100.
overweight_fee(W,100) :- W  > 53,  W =< 70.
overweight_fee(W, 30) :- W  > 50,  W =< 53.
overweight_fee(W,  0) :- W =< 50.

/* --------------------  Oversize fee (to / from China) ----------------- */
oversize_fee(D,200) :- D  > 65,  D =< 115.
oversize_fee(D, 30) :- D  > 62,  D =< 65.
oversize_fee(D,  0) :- D =< 62.

/* ---------------  The extra charge for any single bag ----------------- */
max_num(X,Y,X) :- X>=Y.
max_num(X,Y,Y) :- Y> X.

extra_charge(Weight,Dim,Fee) :-
        overweight_fee(Weight,OW),
        oversize_fee(Dim,OS),
        max_num(OW,OS,Fee).

/* ---------------------------------------------------------------------- */
/* -------------------  Facts for Patricia's baggage  ------------------- */
/* checkedbag(SequentialNumber, Length, Width, Height, Weight).          */

checkedbag(1,35,20,10,74).   /* "luggage box"   */
checkedbag(2,46,34,21,89).   /* backpack        */
checkedbag(3,44,25,22,64).   /* backpack        */
checkedbag(4,54,30,27,70).   /* luggage box     */

/* ------------------------  Helper predicates  ------------------------- */
dim_sum(L,W,H,S) :- S is L+W+H.

bag_fee(BagNo,TotalFee) :-
    checkedbag(BagNo,L,W,H,Weight),
    dim_sum(L,W,H,Dim),
    base_checked_fee(BagNo,Base),
    extra_charge(Weight,Dim,Extra),
    TotalFee is Base + Extra.

/* ----------------------  Aggregate total cost  ------------------------ */
total_bags_cost(Sum) :-
    findall(F,bag_fee(_,F),Fees),
    sum_list(Fees,Sum).

total_cost(Total) :-
    ticket_price(Ticket),
    total_bags_cost(Bags),
    Total is Ticket + Bags.

/* -----------------------  Produce the answer  ------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.