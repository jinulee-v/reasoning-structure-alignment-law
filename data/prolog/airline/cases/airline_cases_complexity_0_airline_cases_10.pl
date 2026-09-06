/* -------------  Statutory rules (relevant extract) ------------- */

:- use_module(library(lists)).

/* Base checked-bag fees for a Main Cabin customer travelling
   within the U.S. (Charlotte <-> Washington, D.C.)               */
base_fee(1,  40).   /* 1st checked bag */
base_fee(2,  45).   /* 2nd checked bag */
base_fee(3, 150).   /* 3rd checked bag */
base_fee(4, 200).   /* 4th checked bag and every bag thereafter */

/* Oversize fees (within U.S.) - linear dimension in inches */
oversize_fee(Size, 0  ) :- Size =< 62.
oversize_fee(Size, 30 ) :- Size  > 62, Size =< 65.
oversize_fee(Size, 200) :- Size  > 65, Size =< 115.
/* (>115 in not accepted - not needed for this case)            */

/* Over-weight fees (within U.S.) - weight in pounds */
overweight_fee(W, 0  ) :- W =< 50.
overweight_fee(W, 30 ) :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.
/* (>100 lb not accepted - not needed for this case)            */

/* For any checked bag the "extra" charge is
   the HIGHER of the over-size and over-weight fees.           */
bag_extra(Size, W, Extra) :-
    oversize_fee(Size, OS),
    overweight_fee(W,  OW),
    Extra is max(OS, OW).

/* -------------  Case-specific facts ------------- */

/* One carry-on (22*14*6, 5 lb) is free and therefore omitted.
   The 4 remaining items are checked.  We number them 1-4.      */
bag(1, 99, 95).   /* Backpack 48*27*24 in, 95 lb  */
bag(2, 71, 63).   /* Luggage box 35*20*16 in, 63 lb */
bag(3, 65, 51).   /* Luggage box 35*21*9  in, 51 lb */
bag(4, 94, 52).   /* Backpack 46*29*19 in, 52 lb  */

ticket_price(196).

/* -------------  Fee calculations ------------- */

bag_fee(Index, TotalFee) :-
    bag(Index, Size, W),
    base_fee(Index, Base),
    bag_extra(Size, W, Extra),
    TotalFee is Base + Extra.

total_bag_fees(Sum) :-
    findall(Fee, bag_fee(_, Fee), Fees),
    sum_list(Fees, Sum).

total_cost(Total) :-
    ticket_price(Tix),
    total_bag_fees(Bags),
    Total is Tix + Bags.

/* -------------  Query ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.