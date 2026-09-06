/*  ---------  RULES (taken from the statutes) -------------------  */

/* route of the itinerary */
route(europe_us).           /* Rome (Europe)  -> Washington D.C. (U.S.) */

/* passenger's cabin */
cabin(main_plus).           /* Main Plus is a Main Cabin fare with 1 extra free bag */

/* -----------------  FREE-BAG ALLOWANCE  ------------------------- */

/* 2 checked bags free for Main Plus on Europe <--> U.S. routes */
free_checked_bags(2).

/* -----------------  BAG-FEE TABLES  ----------------------------- */

/* basic checked-bag fee once the free allowance is exceeded       */
/* (Europe / Israel / Qatar <--> U.S. etc.)                        */
bag_fee(Order, 0)  :- free_checked_bags(Free), Order =< Free.     /* within free allowance */
bag_fee(3, 200).                                                /* 3rd bag                */
bag_fee(Order, 200) :- Order >= 4.                              /* 4th and each additional*/

/* -------------  OVERSIZE FEES (Europe <--> U.S.)  --------------- */

oversize_fee(Dim, 0)   :- Dim =< 62.                             /* standard size */
oversize_fee(Dim, 30)  :- Dim > 62, Dim =< 65.                   /* 62-65 in      */
oversize_fee(Dim, 150) :- Dim > 65, Dim =< 115.                  /* 65-115 in     */

/* -------------  OVERWEIGHT FEES (Europe <--> U.S.)  ------------- */

overweight_fee(W, 0)    :- W =< 50.                              /* up to 50 lb   */
overweight_fee(W, 30)   :- W > 50, W =< 53.                      /* 50-53 lb      */
overweight_fee(W, 100)  :- W > 53, W =< 70.                      /* 53-70 lb      */

/* -------------  EXTRA FEE PER BAG  ------------------------------ */

extra_fee(Dim, W, Fee) :-             /* higher of oversize / overweight */
    oversize_fee(Dim, O),
    overweight_fee(W, OW),
    (O >= OW -> Fee = O ; Fee = OW).

/* -------------  BAG FACTS  -------------------------------------- */

/* carry-on (free)                                                   */
bag(b1,  20, 13,  9,  5).   /* qualifies as the one carry-on, not checked */

/* checked bags (order in which they are checked)                    */
bag(b2,  41, 17, 17, 63).   /* checked bag #1 */
bag(b3,  37, 14, 14, 53).   /* checked bag #2 */
bag(b4,  35, 16, 14, 70).   /* checked bag #3 */
bag(b5,  35, 21,  9, 52).   /* checked bag #4 */

/* helper: only bags that exceed carry-on limits are 'checked' */
checked_order([b2,b3,b4,b5]).   /* already in the order they will be processed */

/* -------------  COST OF EACH CHECKED BAG  ------------------------ */

checked_bag_cost(N, Fee) :-
    checked_order(List),
    nth1(N, List, B),
    bag(B,L,Wid,H,Weight),
    Dim is L + Wid + H,
    bag_fee(N, BaseFee),
    extra_fee(Dim, Weight, Extra),
    Fee is BaseFee + Extra.

/* -------------  TOTAL BAG FEES  --------------------------------- */

total_bag_fees(Total) :-
    checked_order(List),
    length(List, Num),
    findall(F, (between(1,Num,N), checked_bag_cost(N,F)), Fs),
    sum_list(Fs, Total).

/* ----------------  FLIGHT TICKET  -------------------------------- */

flight_ticket_cost(253).

/* ----------------  TOTAL COST  ----------------------------------- */

total_cost(Total) :-
    flight_ticket_cost(Tix),
    total_bag_fees(Bags),
    Total is Tix + Bags.

/* ----------------  QUERY  ---------------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.