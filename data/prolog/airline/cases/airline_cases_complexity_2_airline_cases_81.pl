:- format("~w~n", ["Label: 2764"]).
/* =====================================================================
   American Airlines baggage-fee calculator
   Case: Joseph - Business Class  (New Orleans  ->  Los Angeles)
   ===================================================================== */

/* ------------  ticket ------------------------------------------------ */
flight_cost(234).

/* ------------  bags -------------------------------------------------- */
/* bag(Id, Length, Width, Height, Weight) */

bag(1,20,11, 7,11).               /* fits as carry-on - excluded below */

bag(2,33,22,10,53).
bag(3,33,19,12,62).
bag(4,37,15,13,52).
bag(5,33,20,11,70).
bag(6,36,19, 9,53).
bag(7,35,17,13,71).
bag(8,52,32,26,90).
bag(9,34,17,14,52).
bag(10,35,17,12,87).
bag(11,41,22,18,65).

/* list of CHECKED bags (carry-on #1 left out) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ------------  statutory helpers ------------------------------------ */

/* sum of outside dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - within / between U.S. & Canada */
oversize_fee(S,Fee) :-
      (  S =< 62  -> Fee = 0
      ;  S =< 65  -> Fee = 30
      ;  S =< 115 -> Fee = 200 ).

/* overweight fees - threshold depends on whether bag is complimentary   */
/* overweight_fee(Weight,Allowed,Fee) */
overweight_fee(W,Allowed,Fee) :-
      (  W =< Allowed -> Fee = 0
      ;  W =< 53      -> Fee = 30
      ;  W =< 70      -> Fee = 100
      ;  W =< 100     -> Fee = 200 ).

/* penalty = higher of oversize vs. overweight fee */
penalty(BagId,complimentary,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,S),
      oversize_fee(S,OS),
      overweight_fee(Weight,70,OW),          /* 70-lb limit for free bags */
      Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
      bag(BagId,L,W,H,Weight),
      dims_sum(L,W,H,S),
      oversize_fee(S,OS),
      overweight_fee(Weight,50,OW),          /* 50-lb limit for paid bags */
      Pen is max(OS,OW).

/* base checked-bag fee for Business Class - domestic */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* ------------  combinatorics for picking 2 free bags ----------------- */

/* choose 2 distinct elements (F1 occurs before F2 in the list) */
choose_two(List,F1,F2) :-
      append(_,[F1|Tail],List),
      member(F2,Tail).

/* place chosen freebies first, keep relative order for the rest */
ordered_list(F1,F2,Ordered) :-
      checked_bag_ids(All),
      select(F1,All,Rest1),
      select(F2,Rest1,Rest),
      Ordered = [F1,F2|Rest].

/* cost for one particular choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
      ordered_list(F1,F2,Ordered),
      cost_bags(Ordered,1,CostBags,Penalties),
      flight_cost(Flight),
      Total is Flight + CostBags + Penalties.

/* walk through ordered list, accumulating base fees & penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
      (Idx =< 2 -> Class = complimentary ; Class = charged),
      bag_fee(Idx,Base),
      penalty(Bag,Class,Pen),
      NextIdx is Idx + 1,
      cost_bags(Bs,NextIdx,RestCost,RestPen),
      CostSum is Base + RestCost,
      PenSum  is Pen  + RestPen.

/* compute minimal total over all ways of selecting 2 complimentary bags */
total_cost(MinTotal) :-
      checked_bag_ids(L),
      findall(T, (choose_two(L,F1,F2), cost_for_choice(F1,F2,T)), Ts),
      min_list(Ts,MinTotal).

/* ------------  query & output --------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.