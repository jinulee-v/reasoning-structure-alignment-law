/* =========  Statutory rules (only those needed for this case)  ========= */

/* --------  Route group and passenger cabin ---------------------------- */
route(aus_usa).          /* journey is Australia  <->  U.S.             */
cabin(first).            /* Joseph travels First Class                  */

/* --------  Free-bag allowances ---------------------------------------- */
/*
   1st bag is free on trips "to / from Australia" (all cabins except Basic).
   In First Class the 2nd and 3rd bags are also free.
*/
free_checked_bags(3).    /* total number of complimentary checked bags  */

/* --------  Size and weight limits for complimentary bags -------------- */
complimentary_weight_limit(first, 70).   /* lbs */
complimentary_size_limit(62).            /* in   */

/* --------  Over-size fees (Australia group) --------------------------- */
/* Size is the sum L+W+H in inches                                        */
oversize_fee(aus_usa, Size, 0   ) :- Size =< 62.
oversize_fee(aus_usa, Size, 30  ) :- Size  > 62, Size =< 65.
oversize_fee(aus_usa, Size, 200 ) :- Size  > 65, Size =< 115.

/* --------  Over-weight fees (Australia group) ------------------------- */
/* Paid = yes  -> the bag is NOT complimentary (weight limit 50 lb)
   Paid = no   -> the bag IS complimentary   (weight limit 70 lb)
*/
overweight_fee(_Group, no,  Weight, 0  ) :- Weight =< 70.
overweight_fee(_Group, yes, Weight, 0  ) :- Weight =< 50.
overweight_fee(_Group, yes, Weight, 30 ) :- Weight  > 50, Weight =< 53.
overweight_fee(aus_usa, yes, Weight,100) :- Weight  > 53, Weight =< 70.

/* --------  Base checked-bag fee (Australia group, First Class) -------- */
checked_bag_fee(aus_usa, first, Index, 0  ) :- Index =< 3.  /* 1st-3rd free */
checked_bag_fee(aus_usa, first, 4,     200).                /* 4th bag      */

/* =========  Case facts (Joseph)  ====================================== */

/* flight ticket price */
ticket_cost(787).

/* Each checked bag: bag(Id,L,W,H,Weight).  (carry-on is omitted) */
bag(b2,45,30,26,52).
bag(b3,35,16,13,69).
bag(b4,33,21,10,51).
bag(b5,34,15,14,53).

/* =========  Auxiliary computations  =================================== */

size(L,W,H,Sum) :- Sum is L+W+H.

/* extra_cost(Paid, BagId, Extra) : Extra is max(oversize, overweight) */
extra_cost(Paid, BagId, Extra) :-
    bag(BagId,L,W,H,Weight),
    size(L,W,H,Size),
    route(Route),
    oversize_fee(Route,Size,OSFee),
    overweight_fee(Route, Paid, Weight, OWFee),
    Extra is max(OSFee,OWFee).

/* cost_for_choice(PaidBag, TotalBagCost) ------------------------------- */
cost_for_choice(PaidBag, TotalCost) :-
    findall(B, bag(B,_,_,_,_), BagList),
    route(Route), cabin(first),

    /* split into paid bag and the others (free) */
    select(PaidBag, BagList, FreeBags),

    /* paid bag costs: base checked fee + extra */
    checked_bag_fee(Route, first, 4, BaseFee),  /* 4th bag fee = 200   */
    extra_cost(yes, PaidBag, ExtraPaid),
    PaidCost is BaseFee + ExtraPaid,

    /* free bags: only extra fees apply (weight limit 70) */
    findall(ExtraF,
            (member(BF, FreeBags), extra_cost(no, BF, ExtraF)),
            FreeExtras),
    sum_list(FreeExtras, FreeCost),

    TotalCost is PaidCost + FreeCost.

/* overall minimum bag cost ------------------------------------------------*/
minimum_bag_cost(MinCost) :-
    findall(Cost, (bag(B,_,_,_,_), cost_for_choice(B,Cost)), Costs),
    min_list(Costs, MinCost).

/* =========  Grand total  ============================================== */
total_cost(Total) :-
    ticket_cost(Ticket),
    minimum_bag_cost(BagFees),
    Total is Ticket + BagFees.

/* =========  Query and output  ========================================= */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.