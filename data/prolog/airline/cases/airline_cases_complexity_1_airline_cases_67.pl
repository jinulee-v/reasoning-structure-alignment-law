/* -------------  Facts describing Joseph's trip  ------------------ */

/* ticket price */
flight_cost(77).

/* checked bags: bag(Id,Length,Width,Height,Weight)                */
bag(2,34,18,11,70).
bag(3,48,35,24,63).
bag(4,33,20,11,81).
bag(5,44,20,19,68).
bag(6,41,30,17,97).
bag(7,54,32,27,60).
bag(8,46,31,20,52).

/* list of all checked-bag Ids                                      */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------------------------------------------------------------- */
/* -----------------  Statutory rules / predicates  ---------------- */
/* ----------------------------------------------------------------- */

/* sum of the three dimensions of a bag                              */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - within / between U.S. and Canada                   */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62  -> Fee = 0
       ;   Sum =< 65  -> Fee = 30
       ;   Sum =< 115 -> Fee = 200 ).

/* overweight fee. 'Thresh' is the free allowance in lbs.            */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 200 ).

/* penalty for 1 bag = higher of oversize vs overweight              */
penalty(BagId,comp,Pen) :-                     /* complimentary bag  */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),           % 70-lb allowance
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-                  /* fee-paying bag     */
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),           % 50-lb allowance
       Pen is max(OS,OW).

/* checked-bag base fee for First Class on domestic / Canada route   */
bag_fee(1,0).      % 1st checked bag free
bag_fee(2,0).      % 2nd checked bag free
bag_fee(3,150).
bag_fee(N,200) :- N>=4.

/* ----------------------------------------------------------------- */
/* ----------------------  Helper predicates  ---------------------- */
/* ----------------------------------------------------------------- */

/* choose 2 different elements (F1 < F2) from a list                 */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* put the 2 complimentary bags first, keep the rest in given order  */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* compute cost for one particular selection of complimentary bags   */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* walk through the ordered list accumulating fees and penalties     */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* minimal total cost over all ways of picking 2 complimentary bags  */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------------------------------------------------------------- */
/* ------------------------  Final answer  ------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.