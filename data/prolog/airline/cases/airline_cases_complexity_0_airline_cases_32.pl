/* -------------  Statutory rules that are relevant to this case ------------- */

/* Complimentary (base) bag fees for a First-Class customer travelling
   between the U.S. and Mexico                                     */
base_bag_fee(BagNumber, 0) :- BagNumber =< 3.     /* 1st - 3rd bag free  */
base_bag_fee(BagNumber, 200) :- BagNumber  > 3.   /* 4th bag +  $200    */

/* ---------------- Oversize surcharge (length+width+height) ----------------- */
oversize_surcharge(Dim, 0   ) :- Dim =< 62.                       /* standard */
oversize_surcharge(Dim, 30  ) :- Dim  > 62, Dim =< 65.            /* 62-65"  */
oversize_surcharge(Dim, 200 ) :- Dim  > 65, Dim =< 115.           /* 65-115" */

/* ---------------- Over-weight surcharge (pounds) --------------------------- */
overweight_surcharge(W, 0   ) :- W =< 50.                         /* =<50 lbs */
overweight_surcharge(W, 30  ) :- W  > 50, W =< 53.                /* 50-53   */
overweight_surcharge(W, 100 ) :- W  > 53, W =< 70.                /* 53-70   */
overweight_surcharge(W, 200 ) :- W  > 70, W =< 100.               /* 70-100  */

/*  When both an over-size and an over-weight surcharge apply,
    only the HIGHER one is collected (per AA policy).              */
highest_surcharge(W,Dim,S) :-
        oversize_surcharge(Dim, SO),
        overweight_surcharge(W  , SW),
        S is max(SO,SW).

/* --------------------------  Case facts  ----------------------------------- */

/* Passenger, itinerary and ticket */
ticket_price(104).
class(first).                       /* first class */
route(us, mexico).                  /* U.S.  ->  Mexico */

/* Carry-on (free, so it is NOT listed among checked bags) */

/* Checked bags: bag(ID,Length,Width,Height,WeightLbs) */
bag(1, 50,27,24, 74).   /* 1st checked bag  */
bag(2, 48,27,25, 70).   /* 2nd checked bag  */
bag(3, 50,31,23, 57).   /* 3rd checked bag  */
bag(4, 54,32,28, 84).   /* 4th checked bag  */

/* --------------------  Fee calculation for one bag  ------------------------ */
bag_total_fee(BagNumber, Fee) :-
        bag(BagNumber,L,W,H,Weight),
        Dim is L+W+H,
        base_bag_fee(BagNumber     , Base),
        highest_surcharge(Weight,Dim,Surcharge),
        Fee is Base + Surcharge.

/* --------------------  Aggregate all checked bag fees  --------------------- */
all_bag_fees(Total) :-
        findall(F, bag_total_fee(_,F), Fees),
        sum_list(Fees, Total).

/* ---------------------------  Grand total  --------------------------------- */
total_cost(Total) :-
        ticket_price(Ticket),
        all_bag_fees(BagFees),
        Total is Ticket + BagFees.

/* ---------------------------  Query & output  ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.