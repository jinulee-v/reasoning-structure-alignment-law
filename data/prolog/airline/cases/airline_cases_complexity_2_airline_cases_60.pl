/* ===================================================================== */
/*  David - Business Class - Salt Lake City (SLC)  ->  Atlanta (ATL)      */
/* ===================================================================== */

/* ---------------  Flight information  -------------------------------- */

flight_cost(194).               /* ticket price - U.S. dollars          */

route(domestic).                /* SLC-ATL is wholly within the U.S.    */
cabin(business).                /* confirmed Business class ticket       */


/* ---------------  Bags to be CHECKED --------------------------------- */
/* (carry-on bag 1 *  personal item are free and therefore omitted)      */
/* bag(Id, Length, Width, Height, Weight)                                */

bag(2, 33,20,10, 51).
bag(3, 43,19,19, 66).
bag(4, 49,26,27, 68).
bag(5, 46,22,20, 53).
bag(6, 47,26,26, 58).
bag(7, 35,19,11, 53).
bag(8, 51,31,26,100).
bag(9, 34,20, 9, 81).
bag(10,38,16,11, 66).
bag(11,41,18,14, 59).

/* convenient list of all checked bag Ids (10 bags total)               */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).


/* ===================================================================== */
/*  Statutory rules that apply to this itinerary                         */
/* ===================================================================== */

/* ----------  Oversize fees - within / between U.S. & Canada ---------- */
/* Sum of dimensions = L + W + H                                         */

oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* ----------  Over-weight fees - domestic (lbs) ----------------------- */
/* 'Thresh' is 70 lbs for complimentary bags, 50 lbs for charged bags    */

overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* ----------  Penalty for a single bag -------------------------------- */
/* Higher of its oversize-fee vs overweight-fee applies                  */

dims_sum(L,W,H,S) :- S is L+W+H.

penalty(BagId,complimentary,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,70,OW),           % complimentary -> 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,50,OW),           % charged bag -> 50-lb limit
       Pen is max(OS,OW).

/* ----------  Checked-bag base fees for Business class, domestic ------ */

bag_fee(1,0).                               % 1st checked bag - free
bag_fee(2,0).                               % 2nd checked bag - free
bag_fee(3,150).                             % 3rd bag
bag_fee(N,200) :- N>=4.                     % 4th bag & beyond


/* ===================================================================== */
/*  Helper predicates to enumerate which 2 bags will be complimentary    */
/* ===================================================================== */

/* choose 2 distinct elements (F1 comes before F2) out of a list         */
choose_two(List,F1,F2) :-
       append(_, [F1|Tail], List),
       member(F2, Tail).

/* Place the two complimentary bags in positions #1 and #2               */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* Accumulate base fees + penalties across the ordered list              */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Kind = complimentary ; Kind = charged),
       bag_fee(Idx,Base),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,FeeRest,PenRest),
       FeeSum is Base + FeeRest,
       PenSum  is Pen  + PenRest.

/* Total cost for a specific choice of the 2 complimentary bags          */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BaseFees,Penalties),
       flight_cost(Ticket),
       Total is Ticket + BaseFees + Penalties.

/* --------------------------------------------------------------------- */
/*  Search all ways of selecting 2 complimentary bags, take the minimum  */
/* --------------------------------------------------------------------- */
total_cost(MinTotal) :-
       checked_bag_ids(Ids),
       findall(T,
               ( choose_two(Ids,F1,F2),
                 cost_for_choice(F1,F2,T) ),
               Totals),
       min_list(Totals,MinTotal).

/* ===================================================================== */
/*  Query & output (required format)                                     */
/* ===================================================================== */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.