/* ===========================================================
   American Airlines - luggage cost calculator
   Case: Jennifer (First Class, New York  ->  Washington D.C.)
   =========================================================== */

/* ----------  Ticket price  -------------------------------- */

flight_cost(258).

/* ----------  Checked bags: bag(Id,Length,Width,Height,Weight)  */

bag(1,19,12,6,8).     /* Carry-on backpack */
bag(2,36,15,12,60).
bag(3,34,19,10,54).
bag(4,38,18,9,75).
bag(5,38,13,12,100).
bag(6,47,24,20,51).
bag(7,37,14,12,59).
bag(8,39,24,15,88).
bag(9,38,13,13,54).
bag(10,36,17,11,78).
bag(11,48,34,25,80).

/*  List of all checked-bag Ids (bag 1 is carry-on, so not checked) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ----------  Statutory rules for this domestic itinerary  --- */

/* sum of a bag's dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - within / between U.S. and Canada */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fees - within / between U.S. and Canada
   Thresh = weight allowed before charges apply
            (70 lb for complimentary, 50 lb otherwise)         */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* penalty for 1 bag = higher of -oversize vs -overweight       */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,70,OW),          % complimentary bag
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Wt,50,OW),          % charged bag
       Pen is max(OS,OW).

/* Checked-bag fees for First Class on this domestic route      */
bag_fee(1,0).            /* 1st checked bag free  */
bag_fee(2,0).            /* 2nd checked bag free  */
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------  Helper predicates  ----------------------------- */

/* choose 2 distinct elements (F1<F2) from a list               */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* place the 2 freebies first, keep remaining order             */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of complimentary bags           */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,Fees,Penalties),
       flight_cost(Flight),
       Total is Flight + Fees + Penalties.

/* walk through ordered list, tallying bag fees & penalties     */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,FeeRest,PenRest),
       FeeSum is Fee + FeeRest,
       PenSum  is Pen + PenRest.

/* compute minimal total cost over all possible free-bag pairs  */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------  Query and print result ------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.