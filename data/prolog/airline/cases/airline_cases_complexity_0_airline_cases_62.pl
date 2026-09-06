/* ---------------  Statutory rules that apply to this case --------------- */

/* region of Mary's trip */
region(within_us).          /* Portland - Phoenix */

/* passenger data */
passenger(mary).
class(mary,premium_economy).
ticket_price(mary,118).

/* Mary's items  (BagId, Length, Width, Height, Weight) */
bag(1,20,11, 6,  5).   /* carry-on (free)            */
bag(2,48,36,24, 53).   /* checked #1                 */
bag(3,33,21,10, 51).   /* checked #2                 */
bag(4,35,16,12, 61).   /* checked #3                 */
bag(5,35,15,14, 69).   /* checked #4                 */

/* ----------------------------------------------------------------------- */
/* --------------------   Auxiliary arithmetic helpers   ----------------- */
size_sum(Bag,Sum) :- bag(Bag,L,W,H,_), Sum is L+W+H.
weight(Bag,Wt)   :- bag(Bag,_,_,_,Wt).

max_fee(F1,F2,F1) :- F1>=F2, !.
max_fee(_,F2,F2).

/* ---------------- Oversize fee (domestic U.S. trips) ------------------- */
oversize_fee(Bag,Fee) :-
    size_sum(Bag,Sum),
    (   Sum =< 62  -> Fee=0
    ;   Sum =< 65  -> Fee=30
    ;   Sum =<115  -> Fee=200
    ;   Fee = 999999   /* not accepted - value never chosen in this case */
    ).

/* ---------------- Overweight fee (lbs) --------------------------------- */
overweight_fee(Bag,Fee) :-
    weight(Bag,W),
    (   W =< 50  -> Fee=0
    ;   W =< 53  -> Fee=30
    ;   W =< 70  -> Fee=100
    ;   Fee = 999999  /* >70 not needed here                              */
    ).

/* ------------- base checked-bag fee for Premium Economy ---------------- */
base_checked_fee(Order,Fee) :-
    (   Order =< 2 -> Fee = 0          /* 1st & 2nd checked bags free     */
    ;   Order = 3  -> Fee = 150        /* 3rd checked bag                 */
    ;   Order >= 4 -> Fee = 200        /* 4th+ checked bag                */
    ).

/* ----------------- overall fee for one checked bag --------------------- */
checked_bag_fee(Order,Bag,TotalFee) :-
    base_checked_fee(Order,Base),
    oversize_fee(Bag,OFee),
    overweight_fee(Bag,WFee),
    max_fee(OFee,WFee,Extra),
    TotalFee is Base + Extra.

/* ----------------- list of Mary's checked bags in order ---------------- */
checked_bag_order(1,2).
checked_bag_order(2,3).
checked_bag_order(3,4).
checked_bag_order(4,5).

/* ----------------- total of all checked-bag fees ----------------------- */
all_checked_fees(Sum) :-
    findall(F,
            (checked_bag_order(Order,Bag),
             checked_bag_fee(Order,Bag,F)),
            L),
    sum_list(L,Sum).

sum_list([],0).
sum_list([H|T],Sum) :- sum_list(T,S1), Sum is H+S1.

/* ----------------------------- grand total ----------------------------- */
total_cost(Total) :-
    passenger(mary),
    ticket_price(mary,Ticket),
    all_checked_fees(Checked),
    Total is Ticket + Checked.

/* -----------------------------  Query  --------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.