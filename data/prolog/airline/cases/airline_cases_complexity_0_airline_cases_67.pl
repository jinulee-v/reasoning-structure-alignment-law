:- format("~w~n", ["Label: 1256"]).
/* =========================================================
   Susan - Business Class
   Denver (DEN)  ->  Minneapolis (MSP)   -  Domestic route
   ========================================================= */

/* -------- Ticket ---------------------------------------- */
flight_cost(276).

/* -------- Checked bags  (carry-on item not listed) ------ */
/* bag(Id,Length,Width,Height,Weight) */
bag(2,42,28,18,63).
bag(3,46,19,22,52).
bag(4,35,22,11,67).
bag(5,35,17,13,62).

/* list of all checked-bag Ids                              */
checked_bag_ids([2,3,4,5]).

/* -------- Statutory charges ----------------------------- */

/* Sum of outside dimensions                                */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fee - within / between U.S. & Canada            */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* Over-weight fee                                          */
/* Complimentary bags: limit 70 lb, Charged bags: 50 lb     */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* Penalty = higher of oversize vs overweight               */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),
       Pen is max(OS,OW).

/* Base checked-bag fee - Business Class, domestic          */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* -------- Helper predicates ----------------------------- */

/* choose 2 different elements (F1 < F2) from a list        */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* build ordered list with the 2 complimentary bags first   */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for one particular choice of complimentary bags     */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BagsCost,PenSum),
       flight_cost(Flight),
       Total is Flight + BagsCost + PenSum.

/* walk through list accumulating base fees and penalties   */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,RestCost,RestPen),
       CostSum is Fee + RestCost,
       PenSum  is Pen + RestPen.

/* minimise over all ways of selecting 2 complimentary bags */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* -------- Query / output -------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.