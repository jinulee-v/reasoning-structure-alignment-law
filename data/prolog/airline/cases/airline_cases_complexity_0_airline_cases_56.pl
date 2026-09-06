/* ===== Statutory rules we need for this case ===== */

/* flight details */
flight_class(business).
route(los_angeles,chengdu).           /* U.S.  --->  China  */
flight_ticket(800).

/* passenger's items: bag(Index,Length,Width,Height,Weight) */
bag(1,22,14,9, 7).
bag(2,42,18,18,63).
bag(3,38,18,9,55).
bag(4,46,36,22,96).
bag(5,49,30,22,54).

/* -------------------------------------------------- */
/* Carry-on test (American allows 1 carry-on =<22*14*9) */

carryon(BagId) :-
    bag(BagId,L,W,H,_),
    L =< 22, W =< 14, H =< 9.         /* meets size box */

/* ---------------- Checked-bag ordering ------------ */

checked_bag_list(List) :-
    findall(Id,(bag(Id,_,_,_,_), \+ carryon(Id)),Unsorted),
    sort(Unsorted,List).              /* keep ascending index */

bag_number(BagId,N) :-                /* N = 1st,2nd... checked bag */
    checked_bag_list(List),
    nth1(N,List,BagId).

/* -------------- Base fee for checked bag ---------- */
/* Business class, U.S.-China                         */
/* 1st & 2nd free, 3rd = $200, 4th+ = $200            */

base_bag_fee(N,0)  :- N =< 2.
base_bag_fee(N,200):- N >= 3.

/* -------------- Oversize fee (U.S.<->China) --------- */

dimension_sum(BagId,S) :-
    bag(BagId,L,W,H,_), S is L+W+H.

oversize_fee(BagId,30)  :-            /* 62-65 in  */
    dimension_sum(BagId,S),
    S > 62, S =< 65.
oversize_fee(BagId,200) :-            /* 65-115 in */
    dimension_sum(BagId,S),
    S > 65, S =< 115.
oversize_fee(BagId,0)   :-            /* =<62 in    */
    dimension_sum(BagId,S),
    S =< 62.

/* -------------- Over-weight fee (U.S.<->China) ------ */
/* Business complimentary weight limit = 70 lb        */
/* Only charge if 70-100 lb                           */

overweight_fee(BagId,450) :-
    bag(BagId,_,_,_,W),
    W > 70, W =< 100.
overweight_fee(BagId,0) :-
    bag(BagId,_,_,_,W),
    W =< 70.

/* -------------- Per-bag total cost ---------------- */

bag_cost(BagId,0) :- carryon(BagId).  /* carry-on is free */

bag_cost(BagId,Cost) :-
    \+ carryon(BagId),
    bag_number(BagId,N),
    base_bag_fee(N,Base),
    oversize_fee(BagId,OSFee),
    overweight_fee(BagId,OWFee),
    MaxExtra is max(OSFee,OWFee),     /* higher of the two applies */
    Cost is Base + MaxExtra.

/* -------------- Total cost ------------------------ */

total_bag_cost(Total) :-
    findall(C, (bag(Id,_,_,_,_), bag_cost(Id,C)), Costs),
    sumlist(Costs,Total).

total_cost(Total) :-
    flight_ticket(Ticket),
    total_bag_cost(BagFees),
    Total is Ticket + BagFees.

/* ================================================== */
/*                Produce the answer                  */
/* ================================================== */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.